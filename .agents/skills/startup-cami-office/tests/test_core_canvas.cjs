// 執行真正的 Canvas helpers，驗證核心問答的保存狀態與中英文切換。
const fs=require('node:fs'),vm=require('node:vm'),path=require('node:path'),assert=require('node:assert/strict');
const file=path.join(__dirname,'../assets/studio-template/canvas.html.jinja');
let source=[...fs.readFileSync(file,'utf8').matchAll(/<script(?:\s[^>]*)?>([\s\S]*?)<\/script>/g)].map(m=>m[1]).find(s=>s.includes('function progressData('));
source=source.replace("  document.addEventListener('DOMContentLoaded'",`  window.testCore={cardFitScale,schedulePreview,showPreview,readingRestorePlan,questionDomain,layoutIdentity,coreCardWidth,progressData,applyContentLocale,keyPointRecord,coreFollowupsHtml,exportRows,cn,hydrate(qs){Q=Object.fromEntries(qs.map(q=>[q.id,{...q,_original:structuredClone(q)}]));mainQs=Object.values(Q);restoreVenture();applyContentLocale();},question:id=>Q[id],answer:answerOf};\n  document.addEventListener('DOMContentLoaded'`);
let locale='zh-TW';
const qs=Array.from({length:20},(_,i)=>({id:'core-'+i,question:'English '+i,prompt:{en:'English '+i,'zh-TW':'中文 '+i},category:'Theme',alternateQuestions:[{en:'Other wording','zh-TW':'換句話問'}],followups:[{en:'Check <script>','zh-TW':'追問 <script>'}]}));
const model={coreMode:true,project:{title:'AllWill'},answers:Object.fromEntries(qs.map(q=>[q.id,{text:'中文回答',textI18n:{en:'Full answer','zh-TW':'中文回答'},status:'saved'}])),keyPoints:{'core-0':{formal:{points:['中文頭條'],pointsI18n:{en:['English headline'],'zh-TW':['中文頭條']}}}},coreContent:{categories:{Theme:{en:'Theme','zh-TW':'主題'}}}};
const window={STARTUP_CAMI_MODEL:model,matchMedia:()=>({matches:false}),STUDIO_I18N:{get locale(){return locale;},catalog:()=>({questions:{}}),t:k=>k}};
const scheduled=[];
vm.runInNewContext(source,{setTimeout:fn=>{scheduled.push(fn);return scheduled.length;},clearTimeout(){},window,location:{search:''},URLSearchParams,document:{addEventListener(){}},structuredClone,console});
const api=window.testCore;api.hydrate(qs);
// 混合滑鼠／觸控裝置也不能在手機或完整答案上方顯示 hover preview。
window.__studio.state.mode='mobile';api.schedulePreview('core-0');api.showPreview('core-0');assert.equal(scheduled.length,0);
window.__studio.state.mode='desktop';window.__studio.state.panelOpen=true;
api.schedulePreview('core-0');api.showPreview('core-0');assert.equal(scheduled.length,0);
window.__studio.state.panelOpen=false;api.schedulePreview('core-0');assert.equal(scheduled.length,1);
window.__studio.state.panelOpen=true;scheduled.pop()();assert.equal(window.__studio.state.previewId,undefined);
window.__studio.state.panelOpen=false;

let p=api.progressData(qs,Object.fromEntries(qs.map(q=>[q.id,api.answer(q.id)])));
assert.equal(p.total,20);assert.equal(p.accepted,20);assert.equal(p.pending.length,0);assert.equal(api.answer('core-0').status,'saved');assert.equal(api.exportRows(true).length,20);
assert.equal(api.question('core-0').question,'中文 0');assert.equal(api.keyPointRecord('core-0').points[0],'中文頭條');assert.equal(api.cn('Theme'),'主題');
assert(api.coreFollowupsHtml('core-0').includes('追問 &lt;script&gt;'));assert(!api.coreFollowupsHtml('core-0').includes('<script>'));
locale='en';api.applyContentLocale();
assert.equal(api.question('core-0').question,'English 0');assert.equal(api.answer('core-0').text,'Full answer');assert.equal(api.keyPointRecord('core-0').points[0],'English headline');assert.equal(api.cn('Theme'),'Theme');
model.answers['core-0'].text='';model.answers['core-0'].textI18n={en:'','zh-TW':''};api.hydrate(qs);
p=api.progressData(qs,Object.fromEntries(qs.map(q=>[q.id,api.answer(q.id)])));assert.equal(p.accepted,19);assert.equal(p.pending[0].id,'core-0');
// 舊351題鏡頭不能套用到20題；同題庫的回答更新與語言切換必須保留鏡頭。
const oldCam={x:19000,y:12000,s:.72};
let restore=api.readingRestorePlan({selectedId:'legacy-removed',cam:oldCam});
assert.equal(restore.valid,false);assert.equal(restore.selectedId,'core-0');assert.equal(restore.cam,null);
restore=api.readingRestorePlan({selectedId:'core-1',questionDomain:'legacy-question-domain',cam:oldCam});
assert.equal(restore.valid,false);assert.equal(restore.cam,null);
restore=api.readingRestorePlan({selectedId:'core-1',questionDomain:api.questionDomain(),layoutKey:api.layoutIdentity(),cam:oldCam});
assert.equal(restore.valid,true);assert.equal(restore.selectedId,'core-1');assert.equal(restore.cam,oldCam);
locale='zh-TW';api.applyContentLocale();assert.equal(api.readingRestorePlan({selectedId:'core-1',questionDomain:api.questionDomain(),layoutKey:api.layoutIdentity(),cam:oldCam}).cam,oldCam);
assert.equal(api.readingRestorePlan({selectedId:'core-1',cam:{x:NaN,y:0,s:1}}).cam,null);
restore=api.readingRestorePlan({selectedId:'core-1',questionDomain:api.questionDomain(),layoutKey:'core:560:1',cam:oldCam});
assert.equal(restore.valid,true);assert.equal(restore.selectedId,'core-1');assert.equal(restore.cam,null);
assert.equal(api.readingRestorePlan({selectedId:'core-1',cam:oldCam}).cam,null);
assert.equal(api.coreCardWidth(390),560);assert.equal(api.coreCardWidth(1440),1040);
api.question('core-1').wx=200;api.question('core-1').wy=300;
restore=api.readingRestorePlan({selectedId:'core-1',questionDomain:api.questionDomain(),layoutKey:api.layoutIdentity(),cam:oldCam,selectedAnchor:{x:100,y:200}});
assert.equal(restore.cam.x,oldCam.x+100);assert.equal(restore.cam.y,oldCam.y+100);

model.coreMode=false;p=api.progressData(qs,{'core-0':{recordStatus:'saved',text:'saved'},'core-1':{recordStatus:'accepted',text:'accepted'}});assert.equal(p.accepted,1);
console.log('PASS:20-core fill progress, no inherited acceptance, bilingual question/answer/headline/theme, safe followups, missing-answer, camera domain migration, same-domain reading preservation, hybrid/mobile preview suppression, and legacy semantics');
// 執行真正 refreshTile：0、4、5、12張與HTML字元都不能被裁掉。
const tileSource=source.slice(source.indexOf('  function refreshTile('),source.indexOf('  function refreshAllTiles('));
for(const count of [0,1,4,5,12]){
 const points=Array.from({length:count},(_,i)=>`headline ${i} <safe>`);
 const nodes=new Map();const el=()=>({innerHTML:'',textContent:'',dataset:{},classList:{toggle(){}},setAttribute(){},removeAttribute(){},querySelector:selector=>node(selector)});
 function node(selector){if(!nodes.has(selector))nodes.set(selector,el());return nodes.get(selector);}
 const card={id:'q',members:[{id:'q'}],other:[]};const root=el();
 const ctx={CARD_BY_Q:{q:card},S:{selectedId:'q'},Q:{q:{question:'Question'}},cardProgress:()=>({accepted:1,total:1,pending:[],otherPending:[]}),numberedQuestion:q=>q.question,progressLabel:()=> '已填',keyPointRecord:()=>({role:'formal',points}),I18N:{locale:'zh-TW'},esc:s=>s.replaceAll('<','&lt;').replaceAll('>','&gt;'),icon:()=>'',isCore:()=>true,window:{STARTUP_CAMI_MODEL:{}},tr:x=>x};
 vm.runInNewContext(tileSource+';this.draw=refreshTile;',ctx);ctx.draw('q',root);
 const html=node('.card-answer').innerHTML;
 assert.equal((html.match(/class="keypoint"/g)||[]).length,count);
 for(let i=0;i<count;i++)assert(html.includes(`headline ${i} &lt;safe&gt;`));
 assert(!node('.card-notes').innerHTML.includes(' · +'));
}
console.log('PASS: all 0/1/4/5/12 headline tiles render, escaped text, no hidden-headline count');

// 核心長卡依寬度維持可讀倍率，不為塞滿高度縮小字體。
model.coreMode=true;
assert.equal(api.cardFitScale({w:560,h:900},{w:390,h:600}),api.cardFitScale({w:560,h:5000},{w:390,h:600}));
assert(api.cardFitScale({w:560,h:5000},{w:390,h:600})>.6);
console.log('PASS: long core cards keep readable width-based scale');
