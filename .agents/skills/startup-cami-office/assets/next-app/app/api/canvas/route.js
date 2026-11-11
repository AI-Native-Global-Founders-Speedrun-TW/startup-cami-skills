import {readFile,stat,readdir} from 'node:fs/promises';
import {resolve,sep} from 'node:path';
import {execFile} from 'node:child_process';
import {promisify} from 'node:util';
import {createHash} from 'node:crypto';
export const runtime='nodejs';export const dynamic='force-dynamic';const exec=promisify(execFile);const pending=new Map();const snapshots=new Map();
// Legacy names from before the rename: view folders configured by startup101.local.json and
// projects that still keep startup101.yaml. The Python runtime picks the same file.
const CONFIG='startup-cami.local.json',LEGACY_CONFIG='startup101.local.json',DOCUMENTS=['startup-cami.yaml','startup101.yaml'];
async function configFile(base){
 for(const name of [CONFIG,LEGACY_CONFIG]){const path=resolve(base,name);try{return {path,raw:await readFile(path,'utf8')};}catch(e){if(e.code!=='ENOENT')throw e;}}
 throw Error('Missing '+CONFIG+'; run setup.py for this view.');
}
async function fileState(path){try{const s=await stat(path,{bigint:true});return [path,s.dev,s.ino,s.size,s.mtimeNs,s.ctimeNs].join(':');}catch(e){if(e.code==='ENOENT')return path+':missing';throw e;}}
// Successful immutable snapshots only. ctime and inode also catch atomic replacements.
async function identity(locale){
 const base=process.cwd(),{path:configPath,raw}=await configFile(base),config=JSON.parse(raw);
 const paths=[...DOCUMENTS.map(name=>resolve(base,config.project,name)),configPath];
 for(const directory of ['runtime/scripts','runtime/templates','runtime/assets/studio-template']){
  const folder=resolve(base,directory);
  for(const name of (await readdir(folder)).filter(name=>/\.(py|json|jinja)$/.test(name)).sort())paths.push(resolve(folder,name));
 }
 const parts=await Promise.all(paths.map(fileState));
 return createHash('sha256').update(JSON.stringify([raw,locale||config.locale||'en',parts])).digest('hex');
}
async function snapshot(locale){
 const key=locale||'default',before=await identity(locale),cached=snapshots.get(key);
 if(cached?.identity===before)return cached.value;
 const value=await render(locale);
 if(await identity(locale)!==before)throw Error('Project changed while rendering; retrying the latest YAML.');
 snapshots.set(key,{identity:before,value});return value;
}
async function render(locale){const base=process.cwd();const config=JSON.parse((await configFile(base)).raw);const project=resolve(base,config.project);
 const {stdout}=await exec(config.uv||'uv',['run',resolve(base,'runtime/scripts/startup_cami.py'),'--project',project,'render','--template-bundle',resolve(base,'runtime/assets/studio-template'),'--locale',locale || config.locale || 'en','--include-html'],{timeout:60000,maxBuffer:16*1024*1024,windowsHide:true});
 const result=JSON.parse(stdout);const output=resolve(result.output);if(!output.startsWith(project+sep))throw Error('Renderer output outside configured project.');
 let html=result.html;if(typeof html!=='string')throw Error('Renderer did not return HTML.');html=html.replace('window.STARTUP_CAMI_LOCALE=','window.STARTUP_CAMI_LIVE=true;window.STARTUP_CAMI_LOCALE=');return {locale:result.locale,templateVersion:result.template_version,html,hash:createHash('sha256').update(html).digest('hex'),source:result.source};}
export async function GET(request){const url=new URL(request.url),host=request.headers.get('host')||'',origin=request.headers.get('origin');
 if(!/^(localhost|127\.0\.0\.1)(:\d+)?$/.test(host)||(origin&&origin!==url.origin))return Response.json({error:'Local same-origin access only.'},{status:403});
 const locale=url.searchParams.get('locale');if(locale && !['en','zh-TW'].includes(locale))return Response.json({error:'Unsupported locale.'},{status:400});
 try{const key=locale||'default';if(!pending.has(key))pending.set(key,snapshot(locale).finally(()=>pending.delete(key)));return Response.json(await pending.get(key),{headers:{'Cache-Control':'no-store'}});}catch(e){return Response.json({error:e.stderr?.trim()||e.message},{status:503,headers:{'Cache-Control':'no-store'}});}}
