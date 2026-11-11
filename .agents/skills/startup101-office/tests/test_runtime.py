# /// script
# requires-python = ">=3.11"
# dependencies = ["markdown-it-py==3.0.0", "jinja2==3.1.6", "portalocker==3.2.0", "opencc-python-reimplemented==0.1.7"]
# ///
"""Executable behavioral checks; uv run tests/test_runtime.py."""
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

SPEC=importlib.util.spec_from_file_location('runtime',Path(__file__).resolve().parents[1]/'scripts/legacy_runtime.py')
r=importlib.util.module_from_spec(SPEC);SPEC.loader.exec_module(r)

def add_note_draft(p,qid,value):
    turn_id = r.uid()
    r.note(p,turn_id,value,p.load().doc['project']['revision'])
    r.draft(p,qid,turn_id=turn_id)

class RuntimeTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        base=Path(self.temp.name);self.assets=base/'assets';self.assets.mkdir()
        questions=[{'id':k,'question':'What do you know?','category':'Evidence','cautionOnly':False} for k in ['q1','q2']]
        catalog={'questions':questions,'categories':[{'name':'Evidence'}],'questionCount':2,'cautionCount':0}
        req={'schema_version':1,'version':'1','questions':[{'question_id':q['id'],'allowed_answer_kinds':['fact','hypothesis'],'required_parts':[{'id':'scope','text':'State scope','required':True,'applies_to':['fact','hypothesis']}]} for q in questions]}
        for name,data in [('catalog',catalog),('requirements',req),('rubric',{'schema_version':1,'version':'1'})]:r.putjson(self.assets/(name+'.json'),data)
        self.patch=patch.object(r,'ASSETS',self.assets);self.patch.start();self.addCleanup(self.patch.stop)
        self.root=base/'中文 startup';r.init_project(self.root,'Test startup');self.p=r.Project(self.root)
    def packet(self,q='q1',value='I observed two shops yesterday.',deps=None):
        add_note_draft(self.p,q,value);return r.evaluation_input(self.p,q,'fact',dependencies=deps)
    def result(self,packet):
        return {'evaluation_id':r.uid(),'question_id':packet['question_id'],'input_sha256':packet['input_sha256'],'candidate_sha256':packet['candidate_sha256'],'rubric_version':'1','question_requirements_version':'1','verdict':'pass','scores':dict.fromkeys(r.DIMENSIONS,2),'score_reasons':dict.fromkeys(r.DIMENSIONS,'specific user report within stated scope'),'claims':[{'text':packet['candidate_text'],'evidence_status':'reported','source_refs':[packet['note_turns'][-1]['turn_id']]}],'blocking_issues':[],'next_question':None,'what_changes_verdict':'Contrary observations','evaluated_at':r.now(),'dependencies':packet['dependencies'],'evaluator':'test evaluator fixture','requirements_met':['scope']}
    def accepted(self,q='q1',value='I observed two shops yesterday.',deps=None):
        packet=self.packet(q,value,deps);result=self.result(packet);r.accept(self.p,result,packet['document_revision']);return result
    def test_pending_projection_requires_current_markdown_and_matching_evaluation(self):
        packet=self.packet();evaluation=self.result(packet)
        r.record_evaluation(self.p,evaluation)
        self.assertEqual(r.pending_view(self.p)['q1']['evaluation'],evaluation)
        add_note_draft(self.p,'q1','A new observation replaces the prior input.')
        self.assertIsNone(r.pending_view(self.p)['q1']['evaluation'])
        self.assertEqual(r.pending_view(self.p)['q1']['text'],'A new observation replaces the prior input.')
        r.evaluation_input(self.p,'q1','fact',candidate='Rewritten text not saved in Markdown.',confirmed=True)
        self.assertEqual(r.pending_view(self.p)['q1']['role'],'rewrite_needs_save')
        self.assertEqual(r.pending_view(self.p)['q1']['text'],'A new observation replaces the prior input.')

    def test_key_points_preserve_answers_and_reject_stale_input(self):
        self.accepted()
        p=self.p.load();before=p.doc['answers'];metadata=p.doc['project'];notes=p.doc['notes'];states=p.statuses()
        original=p.docpath.read_bytes()
        payload=r.key_points_input(p)
        for entry in payload['entries']:
            entry.pop('text');entry['points']=['Observed two shops']
        r.set_key_points(p,payload)
        self.assertEqual(p.doc['answers'],before);self.assertEqual(p.doc['project'],metadata)
        self.assertEqual(p.doc['notes'],notes);self.assertEqual(p.statuses(),states)
        self.assertTrue(p.docpath.read_bytes().startswith(original.rstrip(b'\n')))
        self.assertEqual(r.key_points_view(p)['q1']['formal']['points'],['Observed two shops'])
        with self.assertRaises(r.Invalid):r.set_key_points(p,payload)
        changed=r.text(p.docpath).replace('startup101-text\nI observed two shops yesterday.','startup101-text\nI observed three shops yesterday.')
        # Change formal text only; an edited source hides stale key points.
        r.atomic(p.docpath,changed);p.load()
        self.assertEqual(r.key_points_view(p),{})

    def test_empty_key_points_are_explicit_and_preserve_answer(self):
        self.accepted(value='We have not identified this yet.')
        p=self.p.load();before=p.doc['answers'];states=p.statuses();revision=p.doc['project']['revision']
        payload=r.key_points_input(p)
        for entry in payload['entries']:
            entry.pop('text');entry['points']=[]
        r.set_key_points(p,payload)
        self.assertEqual(r.key_points_view(p)['q1']['formal']['points'],[])
        self.assertEqual(p.doc['answers'],before);self.assertEqual(p.statuses(),states)
        self.assertEqual(p.doc['project']['revision'],revision)

    def test_key_points_pending_and_invalid_payload(self):
        self.packet();payload=r.key_points_input(self.p)
        for entry in payload['entries']:
            entry.pop('text');entry['points']=['Two shops observed']
        r.set_key_points(self.p,payload)
        self.assertIn('pending',r.key_points_view(self.p)['q1'])
        add_note_draft(self.p,'q1','A different input.')
        self.assertEqual(r.key_points_view(self.p),{})
        current=r.key_points_input(self.p)
        for entry in current['entries']:
            entry.pop('text');entry['points']=['Duplicate','Duplicate']
        before=self.p.docpath.read_bytes()
        with self.assertRaises(r.Invalid):r.set_key_points(self.p,current)
        self.assertEqual(before,self.p.docpath.read_bytes())

    def test_note_preserves_lines_and_reserved_markers(self):
        raw = "  中文\r\n\r舊行\n\u2028分隔\v符號\n```startup101-answer\n{}\n```\n~~~~~\n"
        self.assertEqual(r.note(self.p, 'm01', raw, 0)['revision'], 1)
        self.assertEqual(self.p.load().doc['notes']['m01'], raw)
        self.assertIn(raw.encode(), self.p.docpath.read_bytes())
        self.assertEqual(self.p.statuses(), {})
        before = self.p.docpath.read_bytes()
        self.assertEqual(r.note(self.p, 'm01', raw, 0)['status'], 'already_noted')
        self.assertEqual(self.p.docpath.read_bytes(), before)
        with self.assertRaisesRegex(r.Invalid, 'different content'):
            r.note(self.p, 'm01', raw + '!', 1)
        with self.assertRaisesRegex(r.Invalid, 'revision conflict'):
            r.note(self.p, 'm02', raw, 0)
        self.assertEqual(self.p.docpath.read_bytes(), before)
        self.assertEqual(r.note(self.p, 'm02', raw, 1)['revision'], 2)
        self.assertEqual(len(self.p.load().doc['notes']), 2)

    def test_early_note_without_question_and_resolution_from_markdown(self):
        raw = 'PM asks RD.\nSales waits.\n'
        self.p.load()
        appendix = '\n## 舊訪談人工補錄\n\n不得覆寫。\n'
        r.atomic(self.p.docpath, self.p.doc['source'] + appendix)
        r.note(self.p, 'original', raw, 0)
        self.assertIn(appendix, self.p.load().doc['source'])
        self.assertFalse(self.p.session()['drafts'])
        with self.assertRaisesRegex(r.Invalid, 'save the edited note'):
            r.draft(self.p, 'q1', 'invented', turn_id='absent')
        with self.assertRaisesRegex(r.Invalid, 'match the edited note'):
            r.draft(self.p, 'q1', 'changed excerpt', turn_id='original')
        for qid, excerpt in [('q1', 'PM asks RD.'), ('q2', 'Sales waits.')]:
            r.draft(self.p, qid, excerpt, turn_id='original')
            r.draft(self.p, qid, excerpt, turn_id='original')
            saved = self.p.session()['drafts'][qid]['turns']
            self.assertEqual(len(saved), 1)
            self.assertNotIn('text', saved[0])
            packet = r.evaluation_input(self.p, qid, 'fact')
            self.assertEqual(packet['note_turns'][0]['text'], raw)
            self.assertEqual(packet['note_turns'][0]['excerpt'], excerpt)
            self.assertEqual(packet['candidate_text'], excerpt)
        r.accept(self.p, self.result(r.evaluation_input(self.p, 'q1', 'fact')), 1)
        self.assertEqual(self.p.load().statuses(), {'q1':'accepted'})
        self.assertEqual(self.p.doc['answers']['q1']['metadata']['source_turns'], ['original'])
        self.assertIn(appendix, self.p.doc['source'])
        # Reconstruct the other question's draft interrupted between event and session writes.
        r.putjson(self.p.path('.startup101/session.json'), {'drafts':{}})
        r.recover(self.p)
        self.assertEqual(self.p.session()['drafts']['q2']['turns'][0]['turn_id'], 'original')
        self.assertEqual(self.p.doc['notes']['original'], raw)

    def test_accepted_answer_tracks_its_markdown_note(self):
        raw = 'first founder observation'
        r.note(self.p, 'm01', raw, 0)
        r.draft(self.p, 'q1', turn_id='m01')
        packet = r.evaluation_input(self.p, 'q1', 'fact')
        r.accept(self.p, self.result(packet), 1)
        self.assertEqual(self.p.load().statuses(), {'q1':'accepted'})
        block = r.fence(f'startup101-note m01 {r.sha(raw)}', raw)
        source = self.p.doc['source']
        for replacement in ['', r.fence(f'startup101-note m01 {r.sha("altered")}', 'altered')]:
            r.atomic(self.p.docpath, source.replace(block, replacement))
            self.assertEqual(self.p.load().statuses(), {'q1':'unverifiable'})

    def test_note_failure_leaves_no_success_and_same_id_can_resume(self):
        original = self.p.load().docpath.read_bytes()
        with patch.object(r,'atomic',side_effect=OSError('disk full')):
            with self.assertRaises(OSError):
                r.note(self.p, 'm01', 'first', 0)
        self.assertEqual(self.p.docpath.read_bytes(), original)
        self.p.path('.startup101/pending.json').write_text('{}')
        with self.assertRaisesRegex(r.Invalid, 'recover pending'):
            r.note(self.p, 'm01', 'first', 0)
        self.p.path('.startup101/pending.json').unlink()
        r.note(self.p, 'm01', 'first', 0)
        self.p.docpath.write_bytes(self.p.docpath.read_bytes().replace(b'\nfirst\n', b'\nother\n'))
        with self.assertRaisesRegex(r.Invalid, 'transcript checksum'):
            self.p.load()

    def test_authoritative_next_question(self):
        self.accepted()
        before = self.p.load().doc['answers']
        self.assertEqual(r.set_next(self.p, 'q2', 2)['revision'], 3)
        self.assertEqual(self.p.load().summary()['next_question_id'], 'q2')
        self.assertEqual(before, self.p.doc['answers'])
        self.assertEqual(self.p.statuses()['q1'], 'accepted')
        self.assertEqual(r.set_next(self.p, 'q2', 3)['revision'], 3)
        with self.assertRaisesRegex(r.Invalid, 'revision conflict'):
            r.set_next(self.p, 'q2', 1)
        with self.assertRaisesRegex(r.Invalid, 'already accepted'):
            r.set_next(self.p, 'q1', 3)
        with self.assertRaisesRegex(r.Invalid, 'unknown question'):
            r.set_next(self.p, 'missing', 3)
        self.accepted('q2')
        self.assertIsNone(self.p.load().summary()['next_question_id'])
        self.assertNotIn('next_question_id', self.p.doc['project'])

    def test_accept_idempotent_and_roundtrip_arbitrary_text(self):
        value='中文\n```json\n{"x": "</script>"}\n```\n~~~\n# heading\n`literal`\n'
        result=self.accepted(value=value);self.assertEqual(r.Project(self.root).load().doc['answers']['q1']['text'],value)
        self.assertEqual(r.accept(self.p,result,self.p.load().doc['project']['revision'])['status'],'already_committed')
    def test_low_score_and_stale_packet_rejected(self):
        packet=self.packet();result=self.result(packet);result['scores']['clarity']=1
        with self.assertRaises(r.Invalid):r.accept(self.p,result,self.p.load().doc['project']['revision'])
        result=self.result(packet);path=self.root/'startup101.md';path.write_text(path.read_text()+'\nExternal edit\n')
        with self.assertRaises(r.Invalid):r.accept(self.p,result,self.p.load().doc['project']['revision'])
        self.assertFalse(r.Project(self.root).load().doc['answers'])
    def test_required_parts_and_wrong_hash_rejected(self):
        packet=self.packet();result=self.result(packet);result['requirements_met']=[]
        with self.assertRaises(r.Invalid):r.accept(self.p,result,self.p.load().doc['project']['revision'])
        result=self.result(packet);result['candidate_sha256']='bad'
        with self.assertRaises(r.Invalid):r.accept(self.p,result,self.p.load().doc['project']['revision'])
    def test_rewrite_requires_confirmation(self):
        self.packet()
        with self.assertRaises(r.Invalid):r.evaluation_input(self.p,'q1','fact','Everyone will pay')
        packet=r.evaluation_input(self.p,'q1','fact','I retract the broad claim.',True)
        self.assertTrue(packet['confirmed_rewrite'])
    def test_manual_edit_invalidates_and_dependency_propagates(self):
        self.accepted();self.accepted('q2','Decision based on two shops',['q1'])
        path=self.root/'startup101.md';path.write_text(path.read_text().replace('startup101-text\nI observed two shops yesterday.','startup101-text\nI observed three shops yesterday.'))
        statuses=r.Project(self.root).load().statuses();self.assertEqual(statuses['q1'],'unreviewed');self.assertEqual(statuses['q2'],'needs_review')
    def test_receipt_missing_downgrades_not_parse_error(self):
        result=self.accepted();(self.root/'.startup101/receipts'/f"{result['evaluation_id']}.json").unlink()
        self.assertEqual(r.Project(self.root).load().statuses()['q1'],'unverifiable')
    def test_recover_after_commit_before_receipt(self):
        packet=self.packet();result=self.result(packet)
        with patch.object(r,'finish',side_effect=OSError('disk full')):
            with self.assertRaisesRegex(r.Invalid,'answer committed'):r.accept(self.p,result,self.p.load().doc['project']['revision'])
        self.assertEqual(r.recover(self.p)['status'],'committed_recovered');self.assertEqual(self.p.load().statuses()['q1'],'accepted')
    def test_recover_before_commit_keeps_draft(self):
        packet=self.packet();result=self.result(packet);real=r.atomic
        def fail_doc(path,value):
            if path.name=='startup101.md':raise OSError('write denied')
            return real(path,value)
        with patch.object(r,'atomic',side_effect=fail_doc):
            with self.assertRaises(OSError):r.accept(self.p,result,self.p.load().doc['project']['revision'])
        self.assertEqual(r.recover(self.p)['status'],'not_committed_draft_preserved');self.assertIn('q1',self.p.session()['drafts'])
    def test_duplicate_keys_and_orphan_blocks_rejected(self):
        with self.assertRaises(r.Invalid):r.loads('{"x":1,"x":2}')
        with self.assertRaises(r.Invalid):r.loads('{"x":NaN}')
        source=(self.root/'startup101.md').read_text()
        with self.assertRaises(r.Invalid):r.parse(source+r.fence('startup101-text','orphan'))
        with self.assertRaises(r.Invalid):r.parse(source+'\n```startup101-answer\n{}\n')
    def test_lock_and_symlink_boundary(self):
        with r.lock(self.root):
            with self.assertRaises(r.Invalid):
                with r.lock(self.root):pass
        outside=Path(self.temp.name)/'outside';outside.mkdir();link=self.root/'escape';link.symlink_to(outside,target_is_directory=True)
        with self.assertRaises(r.Invalid):r.safe(self.root,'escape/file')
    def test_pins_detect_changes(self):
        (self.root/'.startup101/catalog.json').write_text('{}')
        with self.assertRaisesRegex(r.Invalid,'catalog checksum'):self.p.load()
    def test_note_view_excludes_all_legacy_raw_and_keeps_question_links(self):
        legacy = '这是旧的逐字记录'
        self.p.load()
        appendix = '\n## 創辦人訪談原話\n\n### 舊案例\n\n' + legacy + '\n'
        old = r.fence(f'startup101-turn old-turn {r.sha(legacy)}',legacy)
        r.atomic(self.p.docpath,self.p.doc['source']+old+appendix)
        self.assertEqual(r.note_view(self.p.load()), [])
        with self.assertRaisesRegex(r.Invalid, 'edited note'):
            r.draft(self.p,'q1',turn_id='old-turn')
        r.note(self.p,'n-1','顧問觀察到跨部門交接時遺失資訊。',0,['q2'])
        r.note(self.p,'n-2','No question yet.',1)
        r.draft(self.p,'q1',turn_id='n-1')
        rows=r.note_view(self.p.load())
        self.assertEqual([row['source'] for row in rows],['note','note'])
        self.assertEqual(rows[0]['questionIds'],['q2','q1'])
        self.assertEqual(rows[1]['questionIds'],[])
        self.assertEqual(self.p.statuses(),{})
        packet=r.evaluation_input(self.p,'q1','fact')
        self.assertNotIn(legacy,r.dumps(packet))
        self.assertNotIn('raw_turns',packet)
        r.accept(self.p,self.result(packet),2)
        self.assertEqual(r.note_view(self.p.load())[0],rows[0])

    def test_simplified_chinese_is_rejected_before_any_new_data_write(self):
        self.p.load();prior=self.p.docpath.read_bytes()
        with self.assertRaisesRegex(r.Invalid, 'Traditional Chinese'):
            r.note(self.p,'m', '顾问发现多个团队发生重复开发。',0)
        for unsupported in ('これは日本語です', '한국어만', 'Только кириллица'):
            with self.assertRaisesRegex(r.Invalid, 'Traditional Chinese'):
                r.note(self.p,'m',unsupported,0)
        self.assertEqual(self.p.docpath.read_bytes(),prior)
        r.note(self.p,'m','台灣的 PM 與 RD 使用英文 CRM。',0)
        with self.assertRaisesRegex(r.Invalid, 'Traditional Chinese'):
            r.draft(self.p,'q1',turn_id='m',sources=[{'id':'external','text':'这是来源','checked':False}])
        r.draft(self.p,'q1',turn_id='m')
        with self.assertRaisesRegex(r.Invalid, 'Traditional Chinese'):
            r.evaluation_input(self.p,'q1','fact',candidate='顾问确认',confirmed=True)
        packet=r.evaluation_input(self.p,'q1','fact')
        result=self.result(packet);result['what_changes_verdict']='这是意见'
        with self.assertRaisesRegex(r.Invalid,'Traditional Chinese'):
            r.record_evaluation(self.p,result)

    def test_render_injection_offline_and_failure_preserves_last(self):
        self.accepted(value='</script><script>alert(1)</script> & 中文')
        bundle=Path(self.temp.name)/'template';bundle.mkdir()
        template='<html><!-- STARTUP101_READONLY --><script type="application/json" id="model">{{ model_json }}</script><p>{{ model.answers.q1.text }}</p></html>'
        (bundle/'canvas.html.jinja').write_text(template)
        r.putjson(bundle/'manifest.json',{'template_api_version':1,'version':'test','entry':'canvas.html.jinja','document_schema_versions':[1],'assets':[{'path':'canvas.html.jinja','sha256':r.sha(template),'required':True}]})
        r.render(self.p,bundle);output=(self.root/'startup101.html').read_text()
        self.assertNotIn('<script>alert(1)</script>',output);self.assertIn('\\u003c/script',output)
        (bundle/'canvas.html.jinja').write_text('broken')
        with self.assertRaises(r.Invalid):r.render(self.p,bundle)
        self.assertEqual((self.root/'startup101.html').read_text(),output)
    def test_missing_template_preserves_md(self):
        self.accepted();source=(self.root/'startup101.md').read_text()
        with self.assertRaisesRegex(r.Invalid,'template-unavailable'):r.render(self.p,self.root/'missing')
        self.assertEqual((self.root/'startup101.md').read_text(),source)
    def test_recovery_does_not_resurrect_superseded_accepted_turns(self):
        self.accepted();self.accepted(value='A revised current report.')
        r.recover(self.p);self.assertEqual(self.p.session()['drafts'],{})
    def test_metadata_and_text_must_be_adjacent(self):
        self.accepted();source=(self.root/'startup101.md').read_text()
        modified=source.replace('```startup101-text','```python\nprint(1)\n```\n```startup101-text')
        with self.assertRaisesRegex(r.Invalid,'line .*immediately'):r.parse(modified)
    def test_invalid_metadata_has_line_diagnostic(self):
        self.accepted();source=(self.root/'startup101.md').read_text()
        for old,new in [('"evaluation_id":"','"evaluation_id":"../'),('"revision":1','"revision":true'),('"answer_sha256":"','"answer_sha256":"x')]:
            with self.assertRaisesRegex(r.Invalid,'line '):r.parse(source.replace(old,new,1))
    def test_bad_sources_do_not_persist_turn(self):
        r.note(self.p,'m','A report',0)
        with self.assertRaises(r.Invalid):r.draft(self.p,'q1',turn_id='m',sources=[{'id':'x','text':'quote','checked':True,'url':'javascript:alert(1)'}])
        self.assertFalse((self.root/'.startup101/events.jsonl').exists());self.assertEqual(self.p.session()['drafts'],{})
    def test_init_partial_write_recover(self):
        new=Path(self.temp.name)/'partial';real=r.atomic
        def fail_config(path,value):
            if path.name=='config.json':raise OSError('disk full')
            return real(path,value)
        with patch.object(r,'atomic',side_effect=fail_config):
            with self.assertRaises(OSError):r.init_project(new,'Partial')
        self.assertTrue((new/'startup101.md').exists());self.assertFalse((new/'.startup101/config.json').exists())
        result=r.recover(r.Project(new));self.assertEqual(result['status'],'initialization_recovered')
        self.assertEqual(r.Project(new).load().doc['project']['title'],'Partial')
    def test_nonpass_evaluation_and_session_action_persist(self):
        packet=self.packet();result=self.result(packet);result.update(verdict='revise',next_question='Which shop?',blocking_issues=['scope'])
        result['scores']['specificity']=1
        r.record_evaluation(self.p,result);r.session_action(self.p,'q1','defer','Need source interview')
        self.assertEqual(self.p.session()['drafts']['q1']['last_evaluation']['verdict'],'revise')
        self.assertEqual(self.p.session()['drafts']['q1']['state'],'defer');self.assertFalse(self.p.load().doc['answers'])
    def test_unchecked_source_cannot_claim_checked(self):
        packet=self.packet();result=self.result(packet);result['claims'][0]['evidence_status']='source_checked'
        with self.assertRaisesRegex(r.Invalid,'checked source excerpt'):r.accept(self.p,result,self.p.load().doc['project']['revision'])
    def test_undefined_template_keeps_previous_output(self):
        self.accepted();bundle=Path(self.temp.name)/'undefined';bundle.mkdir();template='STARTUP101_READONLY {{ absent }}'
        (bundle/'canvas.html.jinja').write_text(template)
        r.putjson(bundle/'manifest.json',{'template_api_version':1,'version':'test','entry':'canvas.html.jinja','document_schema_versions':[1],'assets':[]})
        (self.root/'startup101.html').write_text('last good')
        with self.assertRaises(r.TemplateError):r.render(self.p,bundle)
        self.assertEqual((self.root/'startup101.html').read_text(),'last good')
    def test_fact_cannot_pass_with_only_hypothesis_claims(self):
        packet=self.packet(value='I assume two shops might need this.');result=self.result(packet)
        result['claims']=[{'text':packet['candidate_text'],'evidence_status':'hypothesis','source_refs':[]}]
        with self.assertRaisesRegex(r.Invalid,'fact pass requires'):r.accept(self.p,result,self.p.load().doc['project']['revision'])
        hypothesis=r.evaluation_input(self.p,'q1','hypothesis');result=self.result(hypothesis)
        result['claims']=[{'text':hypothesis['candidate_text'],'evidence_status':'hypothesis','source_refs':[]}]
        self.assertEqual(r.accept(self.p,result,self.p.load().doc['project']['revision'])['status'],'committed')
    def test_needs_context_uses_null_scores_not_fake_low_score(self):
        packet=self.packet();result=self.result(packet)
        result.update(verdict='needs_context',scores=None,score_reasons=None,claims=[],blocking_issues=['Missing source access'],next_question='Can you supply the source?',requirements_met=[])
        self.assertEqual(r.record_evaluation(self.p,result)['verdict'],'needs_context')
        result['evaluation_id']=r.uid();result['scores']=dict.fromkeys(r.DIMENSIONS,0)
        with self.assertRaisesRegex(r.Invalid,'must use null scores'):r.record_evaluation(self.p,result)
    def test_project_moves_with_pins_and_receipts(self):
        self.accepted();new=Path(self.temp.name)/'moved';self.root.rename(new)
        self.assertEqual(r.Project(new).load().statuses()['q1'],'accepted')

if __name__=='__main__':unittest.main()
