# /// script
# requires-python = ">=3.11"
# dependencies = ["markdown-it-py==3.0.0", "jinja2==3.1.6", "portalocker==3.2.0", "opencc-python-reimplemented==0.1.7"]
# ///
"""Full shipped-catalog/template integration. Evaluator result is a synthetic test fixture."""
import importlib.util
from pathlib import Path
import re
import tempfile
import unittest

SPEC=importlib.util.spec_from_file_location('runtime',Path(__file__).resolve().parents[1]/'scripts/startup101.py')
r=importlib.util.module_from_spec(SPEC);SPEC.loader.exec_module(r)
BUNDLE=Path(__file__).resolve().parents[1]/'assets/studio-template'
QID='585020cf36a01faf'

class FullBundleIntegration(unittest.TestCase):
    def test_full_catalog_accept_manual_edit_move_render(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)/'測試 startup';r.init_project(root,'Synthetic integration fixture')
            p=r.Project(root)
            value='Hypothesis, not observed: small sellers manually synchronize three channels after each order, delaying fulfillment. Fixture literal: </script><script>alert(1)</script> & 中文.'
            r.note(p,'fixture',value,0);r.draft(p,QID,turn_id='fixture');packet=r.evaluation_input(p,QID,'hypothesis')
            result={'evaluation_id':'integration-fixture','question_id':QID,'input_sha256':packet['input_sha256'],'candidate_sha256':packet['candidate_sha256'],'rubric_version':packet['rubric_version'],'question_requirements_version':packet['question_requirements_version'],'verdict':'pass','scores':dict.fromkeys(r.DIMENSIONS,2),'score_reasons':dict.fromkeys(r.DIMENSIONS,'Synthetic plumbing fixture; not a real business evaluation.'),'claims':[{'text':value,'evidence_status':'hypothesis','source_refs':[]}],'blocking_issues':[],'next_question':None,'what_changes_verdict':'Synthetic fixture only','evaluated_at':r.now(),'dependencies':[],'evaluator':'Synthetic integration test fixture, not a model assessment','requirements_met':[part['id'] for part in packet['requirements']['required_parts']]}
            accepted=r.accept(p,result,1);self.assertEqual(accepted['revision'],2)
            receipt=r.render(p,BUNDLE);self.assertEqual(receipt['source']['revision'],2)
            html=(root/'startup101.html').read_text()
            embedded=re.search(r'window.STARTUP101_MODEL = (.*?);</script>',html,re.S).group(1)
            model=r.loads(embedded)
            self.assertEqual(len(model['questions']),351);self.assertEqual(len(model['cautions']),11);self.assertEqual(len(model['categories']),28)
            self.assertTrue(model['readonly']);self.assertEqual(model['answers'][QID]['status'],'accepted');self.assertEqual(model['answers'][QID]['text'],value)
            self.assertNotIn('</script><script>alert(1)</script>',html);self.assertIn('\\u003c/script',embedded)
            self.assertEqual(model['source']['sha256'],r.sha((root/'startup101.md').read_text()))
            md=root/'startup101.md';md.write_text(md.read_text().replace('startup101-text\n'+value, 'startup101-text\n'+value.replace('delaying fulfillment','delaying order fulfillment')))
            r.render(p,BUNDLE);edited=(root/'startup101.html').read_text();edited_model=r.loads(re.search(r'window.STARTUP101_MODEL = (.*?);</script>',edited,re.S).group(1))
            self.assertEqual(edited_model['answers'][QID]['status'],'unreviewed')
            moved=Path(folder)/'moved 專案';root.rename(moved)
            moved_result=r.render(r.Project(moved),BUNDLE)
            self.assertEqual(moved_result['source']['revision'],2);self.assertTrue((moved/'startup101.html').exists())
            self.assertEqual(r.Project(moved).load().statuses()[QID],'unreviewed')

if __name__=='__main__':unittest.main()
