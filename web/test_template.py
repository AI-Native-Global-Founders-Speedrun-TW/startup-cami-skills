# /// script
# requires-python = ">=3.10"
# dependencies = ["Jinja2==3.1.6"]
# ///
"""唯讀樣板的非瀏覽器驗證。uv run web/test_template.py --bundle <bundle-directory>"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess
import tempfile
from jinja2 import Environment, FileSystemLoader, StrictUndefined, select_autoescape
from markupsafe import Markup


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--bundle', type=Path, required=True)
    args = parser.parse_args()
    web = Path(__file__).resolve().parent
    catalog = json.loads((web.parent/'.agents/skills/startup-cami-office/assets/catalog.json').read_text())
    manifest = json.loads((args.bundle/'manifest.json').read_text())
    for asset in manifest['assets']:
        assert hashlib.sha256((args.bundle/asset['path']).read_bytes()).hexdigest() == asset['sha256']
    model = {'project':{'name':'範例 <script>alert(1)</script>'},
        'categories':[c for c in catalog['categories'] if not c['cautionOnly']],
        'questions':[q for q in catalog['questions'] if not q['cautionOnly']],
        'cautions':[q for q in catalog['questions'] if q['cautionOnly']],
        'answers':{}, 'readonly':True,'source':{'revision':0,'sha256':'fixture'},'template_version':manifest['version']}
    q=model['questions'][0]
    model['answers'][q['id']]={'text':'</script><script>alert(99)</script>\n範例','status':'needs_review','scores':{'clarity':2},'claims':[],'revision':1}
    encoded=json.dumps(model,ensure_ascii=False).replace('&','\\u0026').replace('<','\\u003c').replace('>','\\u003e').replace('\u2028','\\u2028').replace('\u2029','\\u2029')
    env=Environment(loader=FileSystemLoader(args.bundle),undefined=StrictUndefined,autoescape=select_autoescape(default=True))
    html=env.get_template(manifest['entry']).render(model=model,model_json=Markup(encoded))
    assert '<script>alert(99)</script>' not in html
    assert not re.search(r'<script[^>]+src=|<link[^>]+href=',html)
    assert 'STARTUP_CAMI_READONLY' in html
    for forbidden in ['localStorage','id="answer-text"','data-action="import-json"','data-action="new-venture"','data-action="use-structure"','data-action="download-json"']:
        assert forbidden not in html, forbidden
    assert 'Previous evaluation — no longer current or not verifiable' in html
    scripts=re.findall(r'<script>(.*?)</script>',html,re.S)
    with tempfile.TemporaryDirectory() as tmp:
        for i,script in enumerate(scripts):
            path=Path(tmp)/f'script-{i}.js'; path.write_text(script)
            subprocess.run(['node','--check',str(path)],check=True,capture_output=True)
        # 執行資料轉換本身，無 DOM、無瀏覽器；檢查 runtime 的 28 categories + 11 cautions 能建立完整視圖。
        app=(web/'app.js').read_text()
        mode_helper=re.search(r'^  const isCore = .*$',app,re.M).group(0)
        adapter=app[app.index('        const oldCats ='):app.index('      init(validateData(data));')]
        adapter=adapter.rsplit('      }',1)[0]
        base=scripts[1]
        script='const window={};\n'+mode_helper+'\n'+base+'\nconst data=window.STUDIO_DATA;\nconst model='+encoded+';\n'+adapter+'\nif(data.questions.length!==362 || data.categories.filter(c=>!c.caution).length!==28 || data.categories.filter(c=>c.caution).length!==1)throw Error("Adapter count mismatch");\n'
        path=Path(tmp)/'adapter.js';path.write_text(script)
        subprocess.run(['node',str(path)],check=True,capture_output=True)
    # Execute the exact production progress function, with no browser or DOM.
    app=(web/'app.js').read_text()
    helper=app[app.index('  function progressData('):app.index('  function renderProgress(')]
    checks="""
const assert=require('node:assert/strict');
const qs=Array.from({length:351},(_,i)=>({id:String(i)}));
qs.push({id:'caution',caution:true},{id:'defer',cautionOnly:true});
let p=progressData(qs,{});
assert.equal(p.total,351);assert.equal(p.missing,351);assert.equal(p.percent,0);
const answers=Object.fromEntries(qs.slice(0,350).map(q=>[q.id,{recordStatus:'accepted',text:'Recorded answer'}]));
p=progressData(qs,answers);assert.equal(p.accepted,350);assert.equal(p.percent,99);
answers['350']={recordStatus:'accepted',text:'Recorded answer'};
p=progressData(qs,answers);assert.equal(p.percent,100);assert.equal(p.pending.length,0);
answers['0']={recordStatus:'needs_review',text:'Recorded answer'};answers['1']={recordStatus:'unreviewed',text:'Recorded answer'};answers['2']={recordStatus:'unverifiable',text:'Recorded answer'};delete answers['3'];
p=progressData(qs,answers);assert.equal(p.accepted,347);assert.equal(p.review,2);assert.equal(p.unverifiable,1);assert.equal(p.missing,1);assert.equal(p.pending.length,4);
assert.equal(progressData([],{}).percent,0);
"""
    completed_helper=re.search(r'^  const completed = .*$',app,re.M).group(0)
    subprocess.run(['node','-e','const window={};\n'+mode_helper+'\n'+completed_helper+'\n'+helper+checks],check=True,capture_output=True)
    assert 'id="progress-summary"' in html
    print('PASS: manifest checksums; Jinja; injection escaping; inline assets; read-only controls; stale-score label; four JS syntax checks; 362-question adapter')


if __name__=='__main__':main()
