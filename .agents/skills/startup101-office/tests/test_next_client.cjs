// Execute the actual React state updater without a browser.
const fs=require('node:fs'),path=require('node:path'),vm=require('node:vm'),assert=require('node:assert/strict');
const source=fs.readFileSync(path.join(__dirname,'../assets/next-app/app/page.js'),'utf8');
const updater=source.match(/setCanvas\((old=>.*?)\);setError/)[1];
function run(old,data){return vm.runInNewContext(`(${updater})(old)`,{old,data});}
const old={hash:'en-hash',locale:'en',source:{sha256:'same'},templateVersion:'v',html:'old iframe'};
const zh={hash:'zh-hash',locale:'zh-TW',source:{sha256:'same'},templateVersion:'v',html:'new iframe'};
assert.equal(run(old,zh).html,'old iframe');assert.equal(run(old,zh).hash,'zh-hash');
assert.equal(run(old,{...zh,source:{sha256:'changed'}}).html,'new iframe');
assert.equal(run(old,{...zh,templateVersion:'new'}).html,'new iframe');
assert.equal(run(old,{...zh,hash:'en-hash'}),old);
assert.equal(run(null,zh),zh);
assert(source.includes('setError(e.message);setCanvas(null)'));
console.log('PASS: locale-only change preserves iframe, source/template changes replace it, errors clear stale iframe');
