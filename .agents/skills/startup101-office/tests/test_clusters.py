# /// script
# requires-python = ">=3.11"
# dependencies = ["markdown-it-py==3.0.0", "jinja2==3.1.6", "portalocker==3.2.0"]
# ///
"""Cluster compatibility and original-question coverage; no answer migration."""
import copy
import importlib.util
from pathlib import Path
import unittest
import tempfile
import shutil
S=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('runtime',S/'scripts/startup101.py');r=importlib.util.module_from_spec(spec);spec.loader.exec_module(r)
class ClusterTests(unittest.TestCase):
 def setUp(self):
  self.catalog=r.readjson(S/'assets/catalog.json');self.cluster=r.readjson(S/'assets/clusters.json');self.sha=r.sha((S/'assets/catalog.json').read_bytes())
 def validate(self):return r.validate_clusters(self.cluster,self.catalog,self.sha)
 def test_complete_mapping(self):
  self.validate();self.assertEqual(len(self.cluster['cards']),132);self.assertEqual(sum(any(q['side']=='on_the_other_hand' for q in c['questions']) for c in self.cluster['cards']),19)
  self.assertEqual(sum(len(c['questions']) for c in self.cluster['cards']),351);self.assertEqual(len(self.cluster['cautions']),11)
 def test_wrong_source_rejected(self):
  with self.assertRaisesRegex(r.Invalid,'source mismatch'):r.validate_clusters(self.cluster,self.catalog,'0'*64)
 def test_missing_or_duplicate_question_rejected(self):
  self.cluster['cards'][0]['questions'].pop()
  with self.assertRaises(r.Invalid):self.validate()
  self.setUp();self.cluster['cards'][1]['questions'].append(copy.deepcopy(self.cluster['cards'][0]['questions'][1]))
  with self.assertRaises(r.Invalid):self.validate()
 def test_changed_wording_or_side_rejected(self):
  self.cluster['cards'][0]['questions'][0]['question']='Invented new question?'
  with self.assertRaisesRegex(r.Invalid,'wording'):self.validate()
  self.setUp();self.cluster['cards'][0]['questions'][0]['side']='on_the_other_hand'
  with self.assertRaises(r.Invalid):self.validate()
 def test_caution_not_active_and_all_attached(self):
  self.cluster['cards'][0]['questions'][0]['question_id']=self.cluster['cautions'][0]['question_id']
  with self.assertRaises(r.Invalid):self.validate()
  self.setUp();self.cluster['cautions'][0]['attached_to_ids']=[]
  with self.assertRaisesRegex(r.Invalid,'attachment'):self.validate()
 def test_render_rejects_incompatible_bundle_without_changing_source(self):
  with tempfile.TemporaryDirectory() as folder:
   root=Path(folder)/'project';r.init_project(root,'Cluster test');bundle=Path(folder)/'bundle'
   shutil.copytree(S/'assets/studio-template',bundle)
   manifest=r.readjson(bundle/'manifest.json')
   if not manifest.get('presentation'):self.skipTest('Cluster bundle has not been built yet')
   cp=bundle/manifest['presentation']['path'];bad=r.readjson(cp);bad['source_sha256']='0'*64;r.putjson(cp,bad)
   for asset in manifest['assets']:
    if asset['path']==cp.name:asset['sha256']=r.sha(cp.read_bytes())
   r.putjson(bundle/'manifest.json',manifest)
   before=(root/'startup101.md').read_bytes();catalog=(root/'.startup101/catalog.json').read_bytes()
   with self.assertRaisesRegex(r.Invalid,'source mismatch'):r.render(r.Project(root),bundle)
   self.assertEqual((root/'startup101.md').read_bytes(),before);self.assertEqual((root/'.startup101/catalog.json').read_bytes(),catalog)
   self.assertFalse((root/'startup101.html').exists())
   (root/'startup101.html').write_text('previous valid snapshot');(root/'.startup101/render-receipt.json').write_text('previous receipt')
   with self.assertRaisesRegex(r.Invalid,'source mismatch'):r.render(r.Project(root),bundle)
   self.assertEqual((root/'startup101.html').read_text(),'previous valid snapshot');self.assertEqual((root/'.startup101/render-receipt.json').read_text(),'previous receipt')
if __name__=='__main__':unittest.main()
