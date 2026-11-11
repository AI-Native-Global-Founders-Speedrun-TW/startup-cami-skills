# /// script
# requires-python = ">=3.11"
# dependencies = ["ruamel.yaml==0.18.16"]
# ///
"""Installer protection and restart tests; no browser or network dependency."""
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
SKILL=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('installer',SKILL/'scripts/setup.py');module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
class SetupTests(unittest.TestCase):
 def test_yaml_answer_language_ignores_catalog(self):
  with tempfile.TemporaryDirectory() as temp:
   project=Path(temp)
   data={'schema_version':2,'questions':{'one':{'answer':'我們的產品讓業務產品工程一起討論客戶需求。'*30,'question':{'en':'English catalog words '*1000}}}}
   with (project/'startup101.yaml').open('w') as f:module.YAML().dump(data,f)
   self.assertEqual(module.detect_locale(project)['locale'],'zh-TW')
 def test_core_language_uses_saved_project_preference_not_archived_answers(self):
  with tempfile.TemporaryDirectory() as temp:
   project=Path(temp)
   data={'schema_version':2,'project':{'language':'en'},
         'questions':{'old':{'answer':'封存的中文答案不應影響目前核心內容的語言。'*100}},
         'core_canvas':{'questions':{'core':{'answer':{'en':'New English answer.','zh-TW':'新的中文答案。'}}}}}
   with (project/'startup101.yaml').open('w') as f:module.YAML().dump(data,f)
   result=module.detect_locale(project)
   self.assertEqual(result['locale'],'en');self.assertEqual(result['reason'],'active-core-project-language')
   self.assertEqual(result['sampled_bytes'],0)
   data['project']['language']='zh-TW'
   with (project/'startup101.yaml').open('w') as f:module.YAML().dump(data,f)
   self.assertEqual(module.detect_locale(project)['locale'],'zh-TW')
   data['project']['language']='unsupported'
   with (project/'startup101.yaml').open('w') as f:module.YAML().dump(data,f)
   with self.assertRaisesRegex(ValueError,'project.language'):module.detect_locale(project)
 def test_legacy_only_project_rejected_without_writes(self):
  with tempfile.TemporaryDirectory() as temp:
   project=Path(temp);(project/'startup101.md').write_text('legacy')
   with self.assertRaisesRegex(ValueError,'migrate'):module.setup(project,project/'view',3010,False)
   self.assertFalse((project/'view').exists())
 def test_upgrade_copy_failure_rolls_back(self):
  with tempfile.TemporaryDirectory() as temp:
   project=Path(temp)/'project';(project/'.startup101').mkdir(parents=True)
   (project/'startup101.yaml').write_text('schema_version: 2\nquestions: {}\n');target=Path(temp)/'app'
   module.setup(project,target,3010,False)
   page=target/'app/page.js';page.write_text('// local original')
   before={str(p.relative_to(target)):p.read_bytes() for p in target.rglob('*') if p.is_file()}
   original=module.shutil.copy2;failed=False
   def fail_once(src,dst,*args,**kwargs):
    nonlocal failed
    if not failed and Path(dst).resolve()==(target/'runtime/scripts/startup101.py').resolve():
     failed=True;raise OSError('simulated disk failure')
    return original(src,dst,*args,**kwargs)
   with patch.object(module.shutil,'copy2',side_effect=fail_once):
    with self.assertRaises(OSError):module.setup(project,target,None,False,upgrade=True)
   after={str(p.relative_to(target)):p.read_bytes() for p in target.rglob('*') if p.is_file()}
   self.assertTrue(failed);self.assertEqual(before,after)
 def test_install_resume_and_protect(self):
  with tempfile.TemporaryDirectory() as temp:
   root=Path(temp);project=root/'project 資料';(project/'.startup101').mkdir(parents=True);(project/'startup101.yaml').write_text('schema_version: 2\nquestions: {}\n');target=root/'Next app'
   first=module.setup(project,target,3010,False);self.assertEqual(first['status'],'files_ready');self.assertTrue((target/'runtime/scripts/startup101.py').is_file());self.assertTrue((target/'package-lock.json').is_file())
   self.assertEqual((target/json.loads((target/'startup101.local.json').read_text())['project']).resolve(),project.resolve())
   page=target/'app/page.js';page.write_text('// local change');module.setup(project,target,3010,False);self.assertEqual(page.read_text(),'// local change')
   module.setup(project,target,3010,False,'zh-TW');self.assertEqual(json.loads((target/'startup101.local.json').read_text())['locale'],'zh-TW')
   module.setup(project,target,3010,False);self.assertEqual(json.loads((target/'startup101.local.json').read_text())['locale'],'zh-TW')
   before_yaml=(project/'startup101.yaml').read_bytes()
   (project/'.startup101/catalog.json').write_text('pinned catalog')
   upgraded=module.setup(project,target,None,False,upgrade=True)
   self.assertEqual(page.read_text(),(SKILL/'assets/next-app/app/page.js').read_text())
   self.assertEqual((Path(upgraded['backup_dir'])/'app/page.js').read_text(),'// local change')
   self.assertEqual((project/'startup101.yaml').read_bytes(),before_yaml)
   self.assertTrue((target/'runtime/templates/startup101.schema.json').is_file())
   self.assertTrue((target/'runtime/templates/startup101.yaml').is_file())
   self.assertEqual((project/'.startup101/catalog.json').read_text(),'pinned catalog')
   self.assertEqual(json.loads((target/'startup101.local.json').read_text())['port'],3010)
   self.assertEqual(json.loads((target/'startup101.local.json').read_text())['install_status'],'files_ready')
   self.assertEqual(upgraded['locale'],'zh-TW');self.assertFalse(upgraded['upgrade_available'])
   with self.assertRaises(ValueError):module.setup(project,target,3011,False)
   occupied=root/'occupied';occupied.mkdir();(occupied/'keep.txt').write_text('keep')
   with self.assertRaises(ValueError):module.setup(project,occupied,3010,False)
   self.assertEqual((occupied/'keep.txt').read_text(),'keep')
   with self.assertRaises(ValueError):module.setup(root/'missing',root/'other',3010,False)
if __name__=='__main__':unittest.main()
