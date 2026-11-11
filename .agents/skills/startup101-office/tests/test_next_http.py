# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Real HTTP integration, no browser. --node-modules points to an installed Next app's node_modules."""
import argparse
from html.parser import HTMLParser
import hashlib
import json
from pathlib import Path
import socket
import subprocess
import tempfile
import time
import urllib.request
import urllib.error
SKILL=Path(__file__).resolve().parents[1]

def main():
 parser=argparse.ArgumentParser();parser.add_argument('--node-modules',type=Path,required=True);args=parser.parse_args()
 with tempfile.TemporaryDirectory() as tmp:
  root=Path(tmp).resolve();project=root/'project';app=root/'app'
  subprocess.run(['uv','run',str(SKILL/'scripts/startup101.py'),'--project',str(project),'init','--title','Fixture'],check=True,capture_output=True)
  with socket.socket() as s:s.bind(('127.0.0.1',0));port=s.getsockname()[1]
  subprocess.run(['uv','run',str(SKILL/'scripts/setup.py'),'--project',str(project),'--app-dir',str(app),'--port',str(port),'--no-install'],check=True,capture_output=True)
  (app/'node_modules').symlink_to(args.node_modules.resolve(),target_is_directory=True)
  log=open(root/'server.log','w')
  proc=subprocess.Popen(['node',str(app/'node_modules/next/dist/bin/next'),'dev','--hostname','127.0.0.1','--port',str(port),'--webpack'],cwd=app,stdout=log,stderr=log)
  url=f'http://127.0.0.1:{port}/api/canvas'
  def get(headers={}):
   try:
    with urllib.request.urlopen(urllib.request.Request(url,headers=headers),timeout=70) as response:return response.status,json.load(response)
   except urllib.error.HTTPError as e:return e.code,json.load(e)
  try:
   for _ in range(60):
    try:status,first=get();break
    except urllib.error.URLError:time.sleep(.5)
   else:raise AssertionError('Server not ready')
   assert status==200,first
   assert first['locale']=='en'
   with urllib.request.urlopen(url+'?locale=zh-TW',timeout=70) as r:zh=json.load(r)
   assert zh['locale']=='zh-TW' and zh['hash']!=first['hash']
   try:urllib.request.urlopen(url+'?locale=xx',timeout=10);raise AssertionError('Invalid locale accepted')
   except urllib.error.HTTPError as e:assert e.code==400
   source=project/'startup101.yaml';initial=source.read_text();sha=hashlib.sha256(source.read_bytes()).hexdigest();assert first['source']['sha256']==sha
   _,again=get();assert again['hash']==first['hash'];assert source.read_text()==initial
   source.write_text(initial.replace('Fixture','Changed fixture'));status,changed=get();assert status==200;assert changed['hash']!=first['hash'];assert changed['source']['sha256']==hashlib.sha256(source.read_bytes()).hexdigest()
   source.write_text('broken yaml');status,error=get();assert status==503;assert 'error' in error
   source.write_text(initial);status,recovered=get();assert status==200;assert recovered['hash']==first['hash']
   assert get({'Origin':'https://external.example'})[0]==403
   assert get({'Host':'external.example'})[0]==403
   try:urllib.request.urlopen(urllib.request.Request(url,data=b'{}',method='POST'),timeout=10);raise AssertionError('POST accepted')
   except urllib.error.HTTPError as e:assert e.code==405
   about_url=f'http://127.0.0.1:{port}/about'
   def about(query=''):
    with urllib.request.urlopen(about_url+query,timeout=70) as response:
     assert response.status==200
     return response.read().decode('utf-8')
   class VisibleText(HTMLParser):
    def __init__(self):super().__init__();self.skip=0;self.parts=[]
    def handle_starttag(self,tag,attrs):
     if tag in ('script','style'):self.skip+=1
    def handle_endtag(self,tag):
     if tag in ('script','style'):self.skip-=1
    def handle_data(self,data):
     if not self.skip:self.parts.append(data)
   def visible(page):
    parser=VisibleText();parser.feed(page);return ' '.join(parser.parts)
   en_about=about('?locale=en');zh_about=about('?locale=zh-TW')
   for page in (en_about,zh_about):
    assert 'Cami Lu' in page and 'aifounders.tw' in page
    assert 'https://www.startup101.biz/' in page
    assert 'www.linkedin.com/in/camillialu/' in page
    assert 'cami.works' not in page
   assert '教學知識貢獻自 Cami Lu' in visible(zh_about)
   assert 'Skill 由 aifounders.tw 社群投入製作' in visible(zh_about)
   assert 'Course material contributed from Cami' in visible(en_about)
   assert 'Back to canvas' in visible(en_about) and '回到畫布' in visible(zh_about)
   assert 'href="/"' in en_about and 'href="/"' in zh_about
   assert en_about!=zh_about
   config_path=app/'startup101.local.json';config=json.loads(config_path.read_text());config['locale']='zh-TW';config_path.write_text(json.dumps(config))
   assert '教學知識貢獻自 Cami Lu' in visible(about())
   assert source.read_text()==initial
   print('PASS: live YAML, read-only HTTP boundaries, bilingual About credits and configured default locale')
  finally:
   proc.terminate()
   try:proc.wait(timeout=15)
   except subprocess.TimeoutExpired:proc.kill();proc.wait()
   log.close()
if __name__=='__main__':main()
