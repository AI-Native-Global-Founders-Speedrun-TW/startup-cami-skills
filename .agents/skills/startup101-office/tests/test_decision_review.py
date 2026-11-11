# /// script
# requires-python = ">=3.11"
# dependencies = ["markdown-it-py==3.0.0", "jinja2==3.1.6", "portalocker==3.2.0", "opencc-python-reimplemented==0.1.7"]
# ///
"""Review/decision sidecar behavior; run with uv run tests/test_decision_review.py."""
import copy
import unittest
import test_runtime as fixtures
r=fixtures.r

class ReviewDecisionTests(unittest.TestCase):
    setUp=fixtures.RuntimeTests.setUp
    packet=fixtures.RuntimeTests.packet
    result=fixtures.RuntimeTests.result
    def independent(self):
        self.packet();return r.evaluation_input(self.p,'q1','fact',review_policy='independent')
    def pair(self,packet):
        first=self.result(packet);second=self.result(packet);second['evaluator']='independent peer fixture'
        r.record_evaluation(self.p,first);r.record_evaluation(self.p,second);return first,second
    def review(self,packet,results,resolution='agreed'):
        return {'review_id':r.uid(),'question_id':'q1','input_sha256':packet['input_sha256'],'evaluation_ids':[item['evaluation_id'] for item in results],'resolution':resolution,'resolution_reasons':['Both reviewers independently justify the scoped answer; no disagreements remain.'],'reviewed_at':r.now()}
    def assessment(self,packet,result):
        return {'assessment_id':r.uid(),'question_id':'q1','input_sha256':packet['input_sha256'],'evaluation_id':result['evaluation_id'],'decision':'Run a small validation experiment, not a production launch.','status':'not_ready','evidence_refs':[packet['note_turns'][-1]['turn_id']],'missing_information':['No observed willingness to pay.'],'what_changes_verdict':'Observed paid commitments from the target audience.','assessor':'context reviewer fixture','assessed_at':r.now()}
    def test_independent_requires_recorded_pair_and_resolution(self):
        packet=self.independent();first=self.result(packet)
        with self.assertRaisesRegex(r.Invalid,'recorded review'):r.accept(self.p,first,self.p.load().doc['project']['revision'])
        review=self.review(packet,[first,self.result(packet)])
        with self.assertRaisesRegex(r.Invalid,'actually be recorded'):r.record_review(self.p,review)
        first,second=self.pair(packet);review=self.review(packet,[first,second]);r.record_review(self.p,review)
        self.assertEqual(r.accept(self.p,first,self.p.load().doc['project']['revision'])['status'],'committed')
        receipt=r.readjson(self.p.path('.startup101/receipts/'+first['evaluation_id']+'.json'))
        self.assertEqual(receipt['independent_review']['payload'],review)
    def test_same_identity_and_nonpassing_peer_rejected(self):
        packet=self.independent();first,second=self.pair(packet)
        second=self.result(packet);second['evaluator']='  TEST evaluator FIXTURE  ';r.record_evaluation(self.p,second)
        with self.assertRaisesRegex(r.Invalid,'different evaluator'):r.record_review(self.p,self.review(packet,[first,second]))
        second=self.result(packet);second['evaluator']='Peer';second['verdict']='revise';second['scores']['clarity']=1;second['blocking_issues']=['Missing scope'];second['next_question']='Which shops?';r.record_evaluation(self.p,second)
        with self.assertRaisesRegex(r.Invalid,'two recorded passes'):r.record_review(self.p,self.review(packet,[first,second]))
        with self.assertRaisesRegex(r.Invalid,'distinct'):r.record_review(self.p,self.review(packet,[first,first]))
    def test_latest_unresolved_and_unavailable_block_acceptance(self):
        packet=self.independent();first,second=self.pair(packet);r.record_review(self.p,self.review(packet,[first,second]))
        for status in ('unresolved','unavailable'):
            review=self.review(packet,[] if status=='unavailable' else [first,second],status);r.record_review(self.p,review)
            with self.assertRaisesRegex(r.Invalid,'unresolved or unavailable'):r.accept(self.p,first,self.p.load().doc['project']['revision'])
        self.assertFalse(self.p.load().doc['answers'])
    def test_review_immutable_and_policy_pinned_before_verdict(self):
        packet=self.independent();first,second=self.pair(packet)
        with self.assertRaisesRegex(r.Invalid,'policy cannot change'):r.evaluation_input(self.p,'q1','fact',review_policy='single')
        r.evaluation_input(self.p,'q1','fact','A confirmed rewritten answer.',True,review_policy='independent')
        with self.assertRaisesRegex(r.Invalid,'policy cannot change'):r.evaluation_input(self.p,'q1','fact',review_policy='single')
        session=self.p.session();session['drafts']['q1']['packet']=packet;r.putjson(self.p.path('.startup101/session.json'),session)
        review=self.review(packet,[first,second]);r.record_review(self.p,review)
        changed=copy.deepcopy(review);changed['resolution_reasons']=['Changed']
        with self.assertRaisesRegex(r.Invalid,'reused'):r.record_review(self.p,changed)
    def test_history_tamper_rejected_and_foreign_packet_rejected(self):
        packet=self.independent();first,second=self.pair(packet);r.record_review(self.p,self.review(packet,[first,second]))
        history=self.p.path('.startup101/evaluations/'+second['evaluation_id']+'.json');data=r.readjson(history);data['evaluation']['score_reasons']['clarity']='Changed';r.putjson(history,data)
        with self.assertRaisesRegex(r.Invalid,'history changed'):r.accept(self.p,first,self.p.load().doc['project']['revision'])
        fixtures.add_note_draft(self.p,'q1','A new user turn.');new=r.evaluation_input(self.p,'q1','fact',review_policy='independent')
        with self.assertRaisesRegex(r.Invalid,'same input packet'):r.record_review(self.p,self.review(new,[first,second]))
    def test_decision_does_not_modify_answers_scores_and_becomes_stale(self):
        packet=self.packet();result=self.result(packet);r.record_evaluation(self.p,result);r.accept(self.p,result,self.p.load().doc['project']['revision'])
        before=self.p.load().docpath.read_bytes();history=self.p.path('.startup101/evaluations/'+result['evaluation_id']+'.json').read_bytes()
        assessment=self.assessment(packet,result);out=r.record_decision(self.p,assessment)
        self.assertFalse(out['stale']);self.assertEqual(self.p.docpath.read_bytes(),before);self.assertEqual(self.p.path('.startup101/evaluations/'+result['evaluation_id']+'.json').read_bytes(),history)
        self.assertEqual(self.p.load().statuses()['q1'],'accepted')
        current=self.p.summary()['sidecars']['decisions']['latest_by_question']['q1'];self.assertFalse(current['stale'])
        self.p.docpath.write_text(self.p.docpath.read_text()+'\nMore context.\n');self.assertTrue(self.p.load().summary()['sidecars']['decisions']['latest_by_question']['q1']['stale'])
        changed=copy.deepcopy(assessment);changed['status']='ready'
        with self.assertRaisesRegex(r.Invalid,'reused'):r.record_decision(self.p,changed)
    def test_decision_invalid_evidence_and_unrecorded_evaluation_rejected(self):
        packet=self.packet();result=self.result(packet);assessment=self.assessment(packet,result)
        with self.assertRaisesRegex(r.Invalid,'actually be recorded'):r.record_decision(self.p,assessment)
        r.record_evaluation(self.p,result);assessment['evidence_refs']=['imagined-source']
        with self.assertRaisesRegex(r.Invalid,'absent packet source'):r.record_decision(self.p,assessment)
    def test_receipt_loss_invalidates_decision_without_markdown_change(self):
        packet=self.packet();result=self.result(packet);r.record_evaluation(self.p,result);r.accept(self.p,result,self.p.load().doc['project']['revision'])
        r.record_decision(self.p,self.assessment(packet,result));before=self.p.load().docpath.read_bytes()
        self.p.path('.startup101/receipts/'+result['evaluation_id']+'.json').unlink()
        summary=self.p.load().summary()
        self.assertEqual(summary['statuses']['q1'],'unverifiable')
        self.assertTrue(summary['sidecars']['decisions']['latest_by_question']['q1']['stale'])
        self.assertEqual(before,self.p.docpath.read_bytes())
    def test_dependency_receipt_loss_invalidates_unaccepted_decision(self):
        dependency_packet=self.packet('q2');dependency_result=self.result(dependency_packet);r.accept(self.p,dependency_result,self.p.load().doc['project']['revision'])
        packet=self.packet(deps=['q2']);result=self.result(packet);r.record_evaluation(self.p,result)
        r.record_decision(self.p,self.assessment(packet,result));before=self.p.load().docpath.read_bytes()
        self.assertFalse(self.p.summary()['sidecars']['decisions']['latest_by_question']['q1']['stale'])
        self.p.path('.startup101/receipts/'+dependency_result['evaluation_id']+'.json').unlink()
        self.assertTrue(self.p.load().summary()['sidecars']['decisions']['latest_by_question']['q1']['stale'])
        self.assertEqual(before,self.p.docpath.read_bytes())
    def test_altered_own_or_dependency_receipt_evaluation_is_stale(self):
        dep_packet=self.packet('q2');dep_result=self.result(dep_packet);r.accept(self.p,dep_result,self.p.load().doc['project']['revision'])
        packet=self.packet(deps=['q2']);result=self.result(packet);r.record_evaluation(self.p,result);r.accept(self.p,result,self.p.load().doc['project']['revision'])
        r.record_decision(self.p,self.assessment(packet,result))
        for evaluation in (result,dep_result):
            path=self.p.path('.startup101/receipts/'+evaluation['evaluation_id']+'.json');original=path.read_bytes();receipt=r.readjson(path)
            receipt['evaluation']['score_reasons']['clarity']='Receipt changed';r.putjson(path,receipt)
            self.assertEqual(self.p.load().statuses()['q1'],'accepted')
            self.assertTrue(self.p.summary()['sidecars']['decisions']['latest_by_question']['q1']['stale'])
            path.write_bytes(original)
        self.assertFalse(self.p.load().summary()['sidecars']['decisions']['latest_by_question']['q1']['stale'])

    def test_evaluation_history_and_pinned_rules_invalidate_decision(self):
        packet=self.packet();result=self.result(packet);r.record_evaluation(self.p,result)
        r.record_decision(self.p,self.assessment(packet,result));path=self.p.path('.startup101/evaluations/'+result['evaluation_id']+'.json');original=path.read_bytes()
        stored=r.readjson(path);stored['evaluation']['score_reasons']['clarity']='A different reason';r.putjson(path,stored)
        self.assertTrue(self.p.load().summary()['sidecars']['decisions']['latest_by_question']['q1']['stale'])
        path.unlink();self.assertTrue(self.p.load().summary()['sidecars']['decisions']['latest_by_question']['q1']['stale'])
        path.write_bytes(original);self.p.path('.startup101/rubric.json').unlink()
        self.assertTrue(self.p.load(optional=True).summary()['sidecars']['decisions']['latest_by_question']['q1']['stale'])

    def test_single_escalates_to_independent_with_only_fresh_results(self):
        packet=self.packet();old=self.result(packet);r.record_evaluation(self.p,old)
        upgraded=r.evaluation_input(self.p,'q1','fact',review_policy='independent')
        self.assertNotEqual(upgraded['input_sha256'],packet['input_sha256'])
        with self.assertRaisesRegex(r.Invalid,'policy cannot change'):r.evaluation_input(self.p,'q1','fact',review_policy='single')
        fresh=self.result(upgraded);fresh['evaluator']='fresh peer';r.record_evaluation(self.p,fresh)
        with self.assertRaisesRegex(r.Invalid,'same input packet'):r.record_review(self.p,self.review(upgraded,[old,fresh]))
        first,second=self.pair(upgraded);r.record_review(self.p,self.review(upgraded,[first,second]));self.assertEqual(r.accept(self.p,first,self.p.load().doc['project']['revision'])['status'],'committed')
    def test_new_user_turn_marks_assessment_stale_before_new_packet(self):
        packet=self.packet();result=self.result(packet);r.record_evaluation(self.p,result)
        r.record_decision(self.p,self.assessment(packet,result))
        self.assertFalse(self.p.load().summary()['sidecars']['decisions']['latest_by_question']['q1']['stale'])
        fixtures.add_note_draft(self.p,'q1','New evidence changes my answer.')
        self.assertTrue(self.p.load().summary()['sidecars']['decisions']['latest_by_question']['q1']['stale'])
    def test_old_evaluation_cannot_be_laundered_as_current_decision_context(self):
        packet=self.packet();result=self.result(packet);r.record_evaluation(self.p,result)
        self.p.load().docpath.write_text(self.p.docpath.read_text()+'\nChanged source.\n')
        out=r.record_decision(self.p,self.assessment(packet,result));self.assertTrue(out['stale'])
        self.assertEqual(out['assessment']['context']['document_sha256'],packet['document_sha256'])
        self.assertTrue(self.p.load().summary()['sidecars']['decisions']['latest_by_question']['q1']['stale'])
    def test_legacy_packet_keeps_single_policy(self):
        packet=self.packet();packet.pop('review_policy');packet['input_sha256']=r.digest({k:v for k,v in packet.items() if k!='input_sha256'})
        session=self.p.session();session['drafts']['q1']['packet']=packet;r.putjson(self.p.path('.startup101/session.json'),session)
        self.assertEqual(r.accept(self.p,self.result(packet),self.p.load().doc['project']['revision'])['status'],'committed')

if __name__=='__main__':unittest.main()
