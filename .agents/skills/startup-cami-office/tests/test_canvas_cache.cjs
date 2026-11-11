// Verify polling never reruns Python for unchanged data, while edits and failures invalidate.
const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
const route=fs.readFileSync(require('node:path').join(__dirname,'../assets/next-app/app/api/canvas/route.js'),'utf8').replace(/^import .*;$/gm,'').replace(/export /g,'');
let version=1,calls=0,fail=false,changeDuring=false;
const context={Response,URL,Map,Promise,JSON,Error,process:{cwd:()=>'/app'},resolve:require('node:path').resolve,sep:'/',createHash:require('node:crypto').createHash,
 readFile:async()=>JSON.stringify({project:'/project',locale:'en'}),readdir:async()=>['file.py'],
 stat:async()=>({dev:1,ino:1,size:100,mtimeNs:version,ctimeNs:version}),
 execFile(){},promisify:()=>async(_cmd,args)=>{const locale=args[args.indexOf('--locale')+1];calls++;await new Promise(r=>setTimeout(r,5));if(fail)throw Error('Invalid YAML');if(changeDuring)version++;return {stdout:JSON.stringify({output:'/project/canvas.html',html:'window.STARTUP_CAMI_LOCALE="en";'+version,locale,source:{sha256:String(version)},template_version:'v'})};}};
vm.createContext(context);vm.runInContext(route,context);
const request={url:'http://localhost:3010/api/canvas',headers:new Headers({host:'localhost:3010'})};
(async()=>{
 let responses=await Promise.all([context.GET(request),context.GET(request)]);assert.equal(calls,1);assert.equal(responses[0].status,200);
 await context.GET(request);assert.equal(calls,1);
 version++;await context.GET(request);assert.equal(calls,2);
 version++;fail=true;assert.equal((await context.GET(request)).status,503);assert.equal((await context.GET(request)).status,503);assert.equal(calls,4);
 fail=false;assert.equal((await context.GET(request)).status,200);assert.equal(calls,5);
 version++;changeDuring=true;assert.equal((await context.GET(request)).status,503);
 changeDuring=false;assert.equal((await context.GET(request)).status,200);assert.equal(calls,7);
 const zh={...request,url:request.url+'?locale=zh-TW'};const [enResult,zhResult]=await Promise.all([context.GET(request),context.GET(zh)]);assert.equal((await enResult.json()).locale,'en');assert.equal((await zhResult.json()).locale,'zh-TW');assert.equal(calls,8);
 // A view folder installed before the rename only has startup101.local.json, and its project
 // only has startup101.yaml: the route must fall back to both legacy names.
 const enoent=path=>Object.assign(Error('ENOENT: '+path),{code:'ENOENT'});let legacyArgs=null,legacyVersion=1;
 const legacy={...context,readFile:async path=>{if(path.endsWith('/startup-cami.local.json'))throw enoent(path);if(path.endsWith('/startup101.local.json'))return JSON.stringify({project:'/project',locale:'en'});throw enoent(path);},
  stat:async path=>{if(path.endsWith('/startup-cami.yaml'))throw enoent(path);return {dev:1,ino:1,size:100,mtimeNs:legacyVersion,ctimeNs:legacyVersion};},
  promisify:()=>async(_cmd,args)=>{legacyArgs=args;return {stdout:JSON.stringify({output:'/project/startup-cami.html',html:'window.STARTUP_CAMI_LOCALE="en";',locale:'en',source:{sha256:'legacy'},template_version:'v'})};}};
 vm.createContext(legacy);vm.runInContext(route,legacy);
 const legacyResponse=await legacy.GET(request);assert.equal(legacyResponse.status,200);assert.equal((await legacyResponse.json()).source.sha256,'legacy');
 assert(legacyArgs[1].endsWith('/runtime/scripts/startup_cami.py'));assert((await (await legacy.GET(request)).json()).html.includes('window.STARTUP_CAMI_LIVE=true;'));
 const missing={...legacy,readFile:async path=>{throw enoent(path);}};vm.createContext(missing);vm.runInContext(route,missing);
 const missingResponse=await missing.GET(request);assert.equal(missingResponse.status,503);assert.match((await missingResponse.json()).error,/startup-cami\.local\.json/);
 console.log('PASS snapshot cache, request coalescing, edits, invalid YAML recovery, concurrent source change rejection, legacy startup101 config and YAML fallback');
})().catch(e=>{console.error(e);process.exit(1)});
