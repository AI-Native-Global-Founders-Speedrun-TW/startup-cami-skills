# /// script
# requires-python = ">=3.11"
# dependencies = ["ruamel.yaml==0.18.16"]
# ///
"""Install a local Next view at an explicitly chosen empty directory.
uv run scripts/setup.py --project PATH --app-dir PATH [--port 3000] [--no-install]
"""
import argparse
import hashlib
import tempfile
import json
import os
import re
from pathlib import Path
import shutil
import subprocess
import sys
from ruamel.yaml import YAML


LOCALES=('en','zh-TW')
SKIP_DIRS={'node_modules','vendor','dist','build','out','coverage','runtime','assets','__pycache__','view'}

def detect_locale(root,excluded=(),max_files=200,max_bytes=1000000):
    """Bounded local prose heuristic. Never transmits content or records filenames."""
    root=Path(root).resolve();excluded={Path(p).resolve() for p in excluded}
    if not root.is_dir():raise ValueError('Language source must be an existing directory.')
    chinese=english=sampled=read_bytes=0
    # The fixed bilingual catalog is not evidence of the founder's language.
    database=root/'startup101.yaml'
    if database.is_file():
        data=YAML(typ='safe').load(database.read_text(encoding='utf8'))
        if data.get('core_canvas'):
            # Both translations are present by design; archived answers are not
            # evidence of the active language. Reuse the saved project preference.
            selected=data.get('project',{}).get('language')
            if selected not in LOCALES:raise ValueError('Active core YAML needs project.language en or zh-TW.')
            return {'locale':selected,'source_root':str(root),'sampled_files':0,
                    'chinese_characters':0,'english_words':0,'sampled_bytes':0,
                    'reason':'active-core-project-language'}
        prose='\n'.join(q.get('answer','') for q in data.get('questions',{}).values())[:max_bytes]
        chinese=len(re.findall(r'[\u3400-\u4dbf\u4e00-\u9fff]',prose))
        english=len(re.findall(r"[A-Za-z]{2,}(?:'[A-Za-z]+)?",prose))
        read_bytes=len(prose.encode('utf8'));sampled=int(bool(prose.strip()))
    for current,dirs,files in os.walk(root,followlinks=False):
        here=Path(current)
        dirs[:]=sorted(d for d in dirs if not d.startswith('.') and d not in SKIP_DIRS
            and not (here/d).is_symlink() and (here/d).resolve() not in excluded
            and not (here/d/'.git').exists())
        for name in sorted(files):
            path=here/name
            if path.is_symlink() or path.resolve() in excluded or path.suffix.lower() not in {'.md','.mdx','.txt','.rst'}:continue
            if name in {'AGENTS.md','CLAUDE.md','MAP.md'}:continue
            if sampled>=max_files or read_bytes>=max_bytes:break
            try:
                with path.open('rb') as handle:raw=handle.read(min(32000,max_bytes-read_bytes))
                content=raw.decode('utf8',errors='ignore')
            except (OSError,UnicodeError):continue
            read_bytes+=len(raw)
            if '<!-- startup101-generated-readme -->' in content or '\x00' in content:continue
            if name=='startup101.md':
                # Count only actual answer text, never generated question headings/metadata.
                blocks=re.findall(r'^(`{3,}|~{3,})startup101-text\s*\n(.*?)^\1\s*$',content,re.M|re.S)
                content='\n'.join(body for _,body in blocks)
            else:
                content=re.sub(r'\A---\n.*?\n---\n','',content,flags=re.S)
                content=re.sub(r'```.*?```|~~~.*?~~~','',content,flags=re.S)
                content=re.sub(r'https?://\S+|`[^`]*`','',content)
            zh=len(re.findall(r'[\u3400-\u4dbf\u4e00-\u9fff]',content))
            en=len(re.findall(r"[A-Za-z]{2,}(?:'[A-Za-z]+)?",content))
            if zh+en<20:continue
            chinese+=zh;english+=en;sampled+=1
        if sampled>=max_files or read_bytes>=max_bytes:break
    # Approximate Chinese word units using two characters per unit.
    zh_units=chinese/2;total=zh_units+english
    ambiguous=total<30 or abs(zh_units-english)/max(total,1)<0.15
    locale='en' if ambiguous or english>=zh_units else 'zh-TW'
    return {'locale':locale,'source_root':str(root),'sampled_files':sampled,'chinese_characters':chinese,'english_words':english,'sampled_bytes':read_bytes,'reason':'ambiguous-default-en' if ambiguous else 'dominant-local-prose'}

def setup(project,target,port,install=True,locale="auto",language_source=None,upgrade=False):
    project=Path(project).expanduser().resolve();target=Path(target).expanduser().resolve()
    skill=Path(__file__).resolve().parents[1]
    if not (project/'startup101.yaml').is_file():raise ValueError('Initialize or migrate startup101.yaml with startup101.py before setup. Legacy Markdown is not an active source.')
    database=YAML(typ='safe').load((project/'startup101.yaml').read_text(encoding='utf8'))
    if not isinstance(database,dict) or database.get('schema_version')!=2:raise ValueError('Expected startup101.yaml schema_version 2.')
    if port is None:
        saved=target/'startup101.local.json'
        port=json.loads(saved.read_text()).get('port',3000) if saved.is_file() else 3000
    if not 1024<=port<=65535:raise ValueError('Port must be between 1024 and 65535.')
    for command in ('uv','node','npm'):
        if not shutil.which(command):raise ValueError('Install uv and Node.js >=20.9 with npm before setup, then rerun uv run.')
    version=subprocess.check_output(['node','--version'],text=True).strip().lstrip('v').split('.')
    if tuple(map(int,version[:2]))<(20,9):raise ValueError('Node.js >=20.9 is required.')
    if locale not in ('auto',*LOCALES):raise ValueError('Locale must be auto, en, or zh-TW.')
    marker=target/'startup101.local.json'
    old={}
    if target.exists() and any(target.iterdir()):
        if not marker.is_file():raise ValueError('Destination is not empty. Choose an empty directory; existing files are preserved.')
        old=json.loads(marker.read_text())
        if old.get('kind')!='startup101-local-view' or (target/old['project']).resolve()!=project:raise ValueError('Destination belongs to a different project; existing files are preserved.')
        if old['port']!=port:raise ValueError('Existing setup uses a different port. Reuse its configured port.')
    else:
        target.mkdir(parents=True,exist_ok=True)
        shutil.copytree(skill/'assets/next-app',target,dirs_exist_ok=True,ignore=shutil.ignore_patterns('node_modules','.next'))
        runtime=target/'runtime';(runtime/'scripts').mkdir(parents=True)
        for source in (skill/'scripts').glob('*.py'):
            if source.name!='setup.py':shutil.copy2(source,runtime/'scripts'/source.name)
        shutil.copytree(skill/'templates',runtime/'templates')
        shutil.copytree(skill/'assets/studio-template',runtime/'assets/studio-template')
        old={'kind':'startup101-local-view','project':os.path.relpath(project,target),'port':port,'uv':shutil.which('uv')}
    # Upgrade only bundled files. Back up overwritten content first; never touch project data.
    bundle={}
    for source_root,prefix in ((skill/'assets/next-app',''),(skill/'assets/studio-template','runtime/assets/studio-template'),(skill/'templates','runtime/templates')):
        for source in source_root.rglob('*'):
            if source.is_file() and not any(part in {'node_modules','.next','__pycache__'} for part in source.relative_to(source_root).parts):
                bundle[str(Path(prefix)/source.relative_to(source_root))]=source
    for source in (skill/'scripts').glob('*.py'):
        if source.name!='setup.py':bundle['runtime/scripts/'+source.name]=source
    digest=hashlib.sha256()
    for relative,source in sorted(bundle.items()):
        digest.update(relative.encode());digest.update(source.read_bytes())
    version=digest.hexdigest()
    backup=None
    if upgrade:
        # Reject symlink escapes before writing any file.
        for relative in bundle:
            destination=target/relative
            if not destination.resolve().is_relative_to(target):
                raise ValueError('Upgrade destination escapes the app directory; existing files are preserved.')
        backup=Path(tempfile.mkdtemp(prefix='startup101-upgrade-'))
        changed=[]
        try:
            for relative,source in bundle.items():
                destination=target/relative
                if destination.exists():
                    saved=backup/relative;saved.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(destination,saved)
                changed.append(relative)
                destination.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(source,destination)
        except OSError:
            for relative in reversed(changed):
                destination=target/relative;saved=backup/relative
                if saved.exists():shutil.copy2(saved,destination)
                elif destination.exists():destination.unlink()
            raise
        old['bundle_version']=version
    elif not old.get('bundle_version') and not marker.exists():
        old['bundle_version']=version
    if locale=='auto' and old.get('locale') in LOCALES:
        detection=old.get('language_detection',{'reason':'saved-preference'});selected=old['locale']
    else:
        detection=detect_locale(language_source or project,excluded=(target,)) if locale=='auto' else {'reason':'explicit-override'}
        selected=detection.get('locale',locale)
    old.update(locale=selected,language_detection=detection,install_status='files_ready')
    marker.write_text(json.dumps(old,ensure_ascii=False,indent=2)+'\n')
    if install:subprocess.run(['npm','ci','--no-audit','--no-fund'],cwd=target,check=True,stdout=sys.stderr)
    if install:
        old['install_status']='ready';marker.write_text(json.dumps(old,ensure_ascii=False,indent=2)+'\n')
    (project/'.startup101').mkdir(exist_ok=True)
    (project/'.startup101/view.json').write_text(json.dumps({'app_dir':os.path.relpath(target,project),'port':port,'locale':selected,'language_detection':detection},indent=2)+'\n')
    return {'bundle_version':old.get('bundle_version'),'available_bundle_version':version,'upgrade_available':old.get('bundle_version')!=version,'backup_dir':str(backup) if backup else None,'status':'ready' if install else 'files_ready','app_dir':str(target),'project':str(project),'url':f'http://127.0.0.1:{port}','start':['npm','run','dev','--','--port',str(port)],'start_cwd':str(target),'locale':selected,'language_detection':detection}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--project',required=True);parser.add_argument('--app-dir',required=True)
    parser.add_argument('--port',type=int,default=None);parser.add_argument('--no-install',action='store_true')
    parser.add_argument('--locale',choices=('auto',*LOCALES),default='auto');parser.add_argument('--language-source',type=Path)
    parser.add_argument('--upgrade',action='store_true',help='Update bundled app/runtime files, preserving project data and backing up overwritten files.')
    args=parser.parse_args()
    try:print(json.dumps(setup(args.project,args.app_dir,args.port,not args.no_install,args.locale,args.language_source,args.upgrade),ensure_ascii=False));return 0
    except (ValueError,OSError,subprocess.SubprocessError) as error:print(json.dumps({'error':str(error)},ensure_ascii=False),file=sys.stderr);return 2

if __name__=='__main__':sys.exit(main())
