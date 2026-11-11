# /// script
# requires-python = ">=3.11"
# dependencies = ["ruamel.yaml==0.18.16", "jsonschema==4.25.1", "markdown-it-py==3.0.0", "jinja2==3.1.6", "portalocker==3.2.0", "opencc-python-reimplemented==0.1.7"]
# ///
"""Migration invariants and failure safety. uv run tests/test_migration.py."""
import base64
import copy
import gzip
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import migrate_yaml as m
r=m.old

class MigrationTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)/'startup';r.init_project(self.root,'Migration fixture')
        self.p=r.Project(self.root).load();self.qid=next(q for q in self.p.questions if not self.p.questions[q]['cautionOnly'])
        r.note(self.p,'note-one','We help small teams make shared decisions.',0)
        r.draft(self.p,self.qid,turn_id='note-one')
        packet=r.evaluation_input(self.p,self.qid,'decision')
        result={'evaluation_id':'evaluation-one','question_id':self.qid,'input_sha256':packet['input_sha256'],'candidate_sha256':packet['candidate_sha256'],'rubric_version':packet['rubric_version'],'question_requirements_version':packet['question_requirements_version'],'verdict':'pass','scores':dict.fromkeys(r.DIMENSIONS,2),'score_reasons':dict.fromkeys(r.DIMENSIONS,'Explicit scope and intended change.'),'claims':[{'text':packet['candidate_text'],'evidence_status':'not_applicable','source_refs':[]}],'blocking_issues':[],'next_question':None,'what_changes_verdict':'A different customer segment.','evaluated_at':r.now(),'dependencies':[],'evaluator':'migration fixture evaluator','requirements_met':[part['id'] for part in self.p.requirement(self.qid)['required_parts']]}
        r.accept(self.p,result,packet['document_revision'])
        points=r.key_points_input(self.p)
        for entry in points['entries']: entry.pop('text');entry['points']=['Shared decisions']
        r.set_key_points(self.p,points)

    def test_exact_answer_scores_notes_archive_and_no_writes(self):
        before={str(p.relative_to(self.root)):p.read_bytes() for p in self.root.rglob('*') if p.is_file()}
        db,report=m.migrate_project(self.root)
        self.assertEqual(before,{str(p.relative_to(self.root)):p.read_bytes() for p in self.root.rglob('*') if p.is_file()})
        p=m.legacy_project(db)
        self.assertEqual(self.p.load().doc,p.doc)
        self.assertEqual(m.legacy_statuses(db),{self.qid:'accepted'})
        self.assertEqual(db['questions'][self.qid]['answer'],'We help small teams make shared decisions.')
        self.assertEqual(db['questions'][self.qid]['key_points']['items'],['Shared decisions'])
        self.assertEqual(report['notes'],1)
        for name,raw in m.archive_files(db).items(): self.assertEqual(raw,before[name])

    def test_bad_archive_hash_rejected(self):
        db,_=m.migrate_project(self.root);db['legacy_archive']['files']['startup101.md']['sha256']='0'*64
        with self.assertRaisesRegex(r.Invalid,'checksum'):m.legacy_statuses(db)

    def test_tampered_receipt_does_not_forge_pass_even_with_new_file_hash(self):
        db,_=m.migrate_project(self.root)
        item=db['legacy_archive']['files']['.startup101/receipts/evaluation-one.json']
        files=m.archive_files(db);data=json.loads(files['.startup101/receipts/evaluation-one.json']);data['answer_text']='Forged answer'
        files['.startup101/receipts/evaluation-one.json']=json.dumps(data).encode()
        bundle=b''
        for name,raw in sorted(files.items()):
            db['legacy_archive']['files'][name]={'offset':len(bundle),'length':len(raw),'sha256':r.sha(raw)};bundle+=raw
        db['legacy_archive']['content']=base64.b64encode(gzip.compress(bundle,mtime=0)).decode()
        db['records']['legacy']['receipts']['evaluation-one']={k:v for k,v in data.items() if k!='packet'}
        db['records']['legacy']['receipts']['evaluation-one']['packet_ref']=r.digest(data['packet'])
        self.assertEqual(m.legacy_statuses(db)[self.qid],'unverifiable')

    def test_serialization_preserves_tabs_quotes_and_long_multiline(self):
        import startup101_yaml as storage
        raw='prefix\t'+'long text '*40+'\t線上會議\n"quoted"\n  indented\tvalue\n'
        r.note(self.p,'whitespace-note',raw,self.p.load().doc['project']['revision'])
        db,_=m.migrate_project(self.root)
        parsed=storage.parse(storage.encode(db),roundtrip=False)
        self.assertEqual(parsed,db)
        self.assertEqual(parsed['notes']['whitespace-note']['text'],raw)
        m.legacy_project(parsed)

    def test_apply_checks_serialization_before_any_cutover(self):
        import startup101_yaml as storage
        db,_=m.migrate_project(self.root)
        altered=copy.deepcopy(db);altered['project']['name']='Altered by emitter'
        encoded=storage.encode(altered)
        with patch.object(storage,'encode',return_value=encoded):
            with self.assertRaisesRegex(r.Invalid,'serialization changed'):m.apply(self.root,db)
        self.assertTrue((self.root/'startup101.md').exists())
        self.assertFalse((self.root/'startup101.yaml').exists())

    def test_archive_bundle_ranges_must_be_exact(self):
        db,_=m.migrate_project(self.root)
        db['legacy_archive']['files']['startup101.md']['offset']+=1
        with self.assertRaises(r.Invalid):m.archive_files(db)

    def test_shared_packet_content_cannot_change_original_hashes(self):
        db,_=m.migrate_project(self.root)
        key=next(iter(db['records']['legacy']['shared_content']))
        db['records']['legacy']['shared_content'][key]={'tampered':True}
        with self.assertRaisesRegex(r.Invalid,'structured legacy'):m.legacy_project(db)

    def test_structured_legacy_record_tamper_is_rejected(self):
        db,_=m.migrate_project(self.root)
        db['records']['legacy']['receipts']['evaluation-one']['evaluation']['scores']['clarity']=0
        with self.assertRaisesRegex(r.Invalid,'structured legacy'):m.legacy_statuses(db)

    def test_note_edit_invalidates_legacy_acceptance(self):
        db,_=m.migrate_project(self.root);db['notes']['note-one']['text']='Changed evidence'
        self.assertEqual(m.legacy_statuses(db)[self.qid],'unverifiable')

    def test_session_action_survives(self):
        r.session_action(self.p,self.qid,'defer','Need another interview.')
        db,_=m.migrate_project(self.root)
        self.assertEqual(db['session']['actions'][self.qid]['action'],'defer')
        self.assertEqual(db['session']['actions'][self.qid]['reason'],'Need another interview.')
        self.assertTrue(db['session']['actions'][self.qid]['updated_at'])

    def test_pending_transaction_blocks_import(self):
        r.putjson(self.root/'.startup101/pending.json',{})
        with self.assertRaisesRegex(r.Invalid,'recover'):m.migrate_project(self.root)

    def test_partial_cutover_can_rollback_matching_surviving_files(self):
        db,_=m.migrate_project(self.root)
        original_unlink=Path.unlink
        def interrupt(path,*args,**kwargs):
            if path.name=='session.json': raise OSError('simulated interrupted cutover')
            return original_unlink(path,*args,**kwargs)
        with patch.object(Path,'unlink',interrupt):
            with self.assertRaisesRegex(OSError,'interrupted'):m.apply(self.root,db)
        backup=next((self.root/'.startup101/recovery').iterdir())
        m.rollback(self.root,backup)
        self.assertEqual(r.Project(self.root).load().statuses(),{self.qid:'accepted'})

    def test_failed_publication_never_exposes_partial_yaml(self):
        db,_=m.migrate_project(self.root)
        with patch.object(m.os,'link',side_effect=OSError('simulated publication failure')):
            with self.assertRaises(OSError):m.apply(self.root,db)
        self.assertFalse((self.root/'startup101.yaml').exists())
        self.assertTrue((self.root/'startup101.md').exists())
        backup=next((self.root/'.startup101/recovery').iterdir())
        m.rollback(self.root,backup)

    def test_cutover_rollback_and_edit_protection(self):
        db,_=m.migrate_project(self.root);backup=m.apply(self.root,db)
        self.assertFalse((self.root/'startup101.md').exists())
        self.assertFalse((self.root/'.startup101/session.json').exists())
        original=(self.root/'startup101.yaml').read_bytes()
        with (self.root/'startup101.yaml').open('ab') as stream:stream.write(b'\n# edit\n')
        with self.assertRaisesRegex(r.Invalid,'changed'):m.rollback(self.root,backup)
        (self.root/'startup101.yaml').write_bytes(original)
        m.rollback(self.root,backup)
        self.assertEqual(r.Project(self.root).load().statuses(),{self.qid:'accepted'})

if __name__=='__main__':unittest.main()
