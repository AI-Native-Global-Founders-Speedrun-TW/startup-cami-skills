"""Native YAML workflow and storage regression tests (no private fixture data)."""
import sys
from pathlib import Path
from copy import deepcopy
import json
import pytest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import startup_cami as r
import startup_cami_yaml as s

@pytest.fixture
def project(tmp_path):
    r.init_project(tmp_path,'Synthetic project');p=r.Project(tmp_path).load()
    card_id=next(iter(p.db['canvas']['cards']));card=p.db['canvas']['cards'][card_id]
    ids={m['question_id'] for m in card['questions']};category=card['primary_category']
    p.db['questions']={k:v for k,v in p.db['questions'].items() if k in ids}
    p.db['canvas']['cards']={card_id:card};p.db['canvas']['categories']={category:p.db['canvas']['categories'][category]}
    p.db['canvas']['category_order']=[category];p.db['canvas']['cautions']={}
    p.save();return p.load()

def evaluation(p,packet,eid='test-eval',evaluator='reviewer A'):
    return {'evaluation_id':eid,'question_id':packet['question_id'],'input_sha256':packet['input_sha256'],
        'candidate_sha256':packet['candidate_sha256'],'rubric_version':packet['rubric_version'],
        'question_requirements_version':packet['question_requirements_version'],'verdict':'pass',
        'scores':{k:2 for k in r.scoring.DIMENSIONS},'score_reasons':{k:'Clear synthetic decision.' for k in r.scoring.DIMENSIONS},
        'claims':[{'text':packet['candidate_text'],'evidence_status':'not_applicable','source_refs':[]}],
        'blocking_issues':[],'next_question':None,'what_changes_verdict':'New evidence changes the decision.',
        'evaluated_at':r.now(),'dependencies':packet['dependencies'],'evaluator':evaluator,
        'requirements_met':[v['id'] for v in packet['requirements']['required_parts']]}

def prepared(p,policy='single'):
    qid=next(iter(p.questions));body='We choose to help small teams coordinate decisions across roles.'
    r.note(p,'note-test',body,p.db['project']['revision'],[qid]);p.load()
    r.draft(p,qid,turn_id='note-test');p.load()
    packet=r.evaluation_input(p,qid,'decision',review_policy=policy);p.load()
    return qid,packet

def test_init_complete(tmp_path):
    r.init_project(tmp_path,'Synthetic project');p=r.Project(tmp_path).load();assert len(p.questions)==351;assert len(p.db['canvas']['cards'])==132
    assert p.summary()['statuses']=={}
    assert not (p.root/'startup101.md').exists()

def test_accept_edit_clear_keep_accepted(project):
    p=project;qid,packet=prepared(p);ev=evaluation(p,packet)
    r.accept(p,ev,p.db['project']['revision']);p.load();assert p.statuses()[qid]=='accepted'
    p.questions[qid]['answer']='We now have a different decision.';p.save();p.load()
    assert p.summary()['current_statuses'][qid]=='unreviewed';assert p.statuses()[qid]=='accepted'
    assert r.projection(p)['pendingAnswers'][qid]['text']=='We now have a different decision.'
    p.questions[qid]['answer']='';p.save();p.load()
    assert p.statuses()[qid]=='accepted';assert p.summary()['current_statuses'][qid]=='empty'

def test_stale_candidate_and_source(project):
    p=project;qid,packet=prepared(p);ev=evaluation(p,packet)
    p.questions[qid]['answer']='Changed answer';p.save();p.load()
    with pytest.raises(r.Invalid,match='answer changed'):r.accept(p,ev,p.db['project']['revision'])

def test_independent_gate(project):
    p=project;qid,packet=prepared(p,'independent');one=evaluation(p,packet)
    with pytest.raises(r.Invalid,match='independent review required'):r.accept(p,one,p.db['project']['revision'])
    r.record_evaluation(p,one);p.load();two=evaluation(p,packet,'test-eval-two','reviewer B');r.record_evaluation(p,two);p.load()
    review={'review_id':'test-review','question_id':qid,'input_sha256':packet['input_sha256'],'evaluation_ids':[one['evaluation_id'],two['evaluation_id']],
        'resolution':'agreed','resolution_reasons':['Both independently agree.'],'reviewed_at':r.now()}
    r.record_review(p,review);p.load();r.accept(p,one,p.db['project']['revision']);p.load();assert p.statuses()[qid]=='accepted'

def test_keypoints_empty_and_cas(project):
    p=project;qid,packet=prepared(p);payload=r.key_points_input(p)
    payload['entries']=[{k:v for k,v in payload['entries'][0].items() if k!='text'}|{'points':[]}]
    r.set_key_points(p,payload);p.load();assert r.projection(p)['keyPoints'][qid]['pending']['points']==[]
    old=p.source_hash;p.docpath.write_text(p.docpath.read_text()+'\n# human edit\n')
    with pytest.raises(s.Invalid,match='source changed'):s.save(p.docpath,p.db,old)
    assert '# human edit' in p.docpath.read_text()

def test_strict_syntax(project):
    raw=project.docpath.read_text()
    for bad in [raw+'\n---\nx: y\n',raw.replace('schema_version: 2','schema_version: 2\nschema_version: 2'),raw.replace('schema_version: 2','schema_version: &x 2'),raw+'\nunknown: true\n']:
        with pytest.raises(s.Invalid):s.parse(bad)

def test_recovery_and_comment_preservation(project):
    p=project;raw=p.docpath.read_bytes();p.docpath.write_bytes(raw+b'\n# keep my comment\n');p.load();p.save();assert '# keep my comment' in p.docpath.read_text()
    current=p.docpath.read_bytes();after=current+b'\n# next\n';journal=p.path('.startup-cami/yaml-pending.json')
    s.atomic(journal,json.dumps({'before':s.sha(current),'after':s.sha(after),'content':after.decode()}).encode())
    assert s.recover(p.docpath)['status']=='recovered';assert p.docpath.read_bytes()==after
    s.atomic(journal,json.dumps({'before':s.sha(current),'after':s.sha(after),'content':after.decode()}).encode())
    p.docpath.write_bytes(after+b'\n# external\n')
    with pytest.raises(s.Invalid,match='conflict'):s.recover(p.docpath)
    assert journal.exists()

def test_confirmed_rewrite_and_exact_excerpt(project):
    p=project;qid=next(iter(p.questions));body='Context. We choose small teams. Other context.'
    r.note(p,'excerpt-note',body,p.db['project']['revision'],[qid]);p.load();r.draft(p,qid,'We choose small teams.',turn_id='excerpt-note');p.load()
    packet=r.evaluation_input(p,qid,'decision');assert packet['candidate_text']=='We choose small teams.'
    p.load();packet=r.evaluation_input(p,qid,'decision','We choose distributed product teams.',True)
    p.load();assert p.questions[qid]['answer']=='We choose distributed product teams.'
    assert p.questions[qid]['history'][-1]['answer']=='We choose small teams.'

def test_tampered_receipt_and_same_identity(project):
    p=project;qid,packet=prepared(p,'independent');one=evaluation(p,packet,evaluator='Reviewer  A');two=evaluation(p,packet,'two','reviewer a')
    r.record_evaluation(p,one);p.load();r.record_evaluation(p,two);p.load()
    review={'review_id':'bad-review','question_id':qid,'input_sha256':packet['input_sha256'],'evaluation_ids':[one['evaluation_id'],two['evaluation_id']],
        'resolution':'agreed','resolution_reasons':['same person'],'reviewed_at':r.now()}
    with pytest.raises(r.Invalid,match='identities'):r.record_review(p,review)
    p.questions[qid]['note_refs']=[]
    with pytest.raises(r.Invalid,match='evidence links'):r.record_evaluation(p,one)

def test_decision_actions_next_and_fact_gate(project):
    p=project;qid,packet=prepared(p);ev=evaluation(p,packet);r.record_evaluation(p,ev);p.load()
    decision={'assessment_id':'decision-test','question_id':qid,'input_sha256':packet['input_sha256'],'evaluation_id':ev['evaluation_id'],
        'decision':'Run a pilot','status':'unknown','evidence_refs':['note-test'],'missing_information':['Pilot outcome'],
        'what_changes_verdict':'Observed pilot results','assessor':'Founder','assessed_at':r.now()}
    r.record_decision(p,decision);p.load();assert p.summary()['sidecars']['decisions']['latest_by_question'][qid]['stale'] is False
    r.session_action(p,qid,'defer','Need more context');p.load();assert p.summary()['drafts'][qid]['state']=='defer'
    r.set_next(p,qid,p.db['project']['revision']);p.load();assert p.summary()['next_question_id']==qid
    bad=deepcopy(packet);bad['answer_kind']='fact'
    with pytest.raises(r.Invalid,match='fact pass'):r.scoring.validate_result(ev,bad)
    baddecision=deepcopy(decision);baddecision['decision']=''
    with pytest.raises(r.Invalid):r.record_decision(p,baddecision)

def test_source_scope_and_relevant_mutation(project):
    p=project;qid=next(iter(p.questions));body='We choose a pilot with small teams.'
    r.note(p,'scope-note',body,p.db['project']['revision'],[qid]);p.load()
    source={'id':'source-one','text':'A checked source excerpt.','checked':True}
    r.draft(p,qid,sources=[source],turn_id='scope-note');p.load();packet=r.evaluation_input(p,qid,'decision');p.load();ev=evaluation(p,packet)
    p.db['sources']['unrelated']={'id':'unrelated','text':'Other context','checked':False};p.save();p.load()
    r.record_evaluation(p,ev);p.load()
    p.db['sources']['source-one']['text']='Changed source excerpt';p.save();p.load()
    with pytest.raises(r.Invalid,match='sources changed'):r.accept(p,ev,p.db['project']['revision'])

def test_direct_answer_can_enter_note_evaluation_flow(project):
    p=project;qid=next(iter(p.questions));body='We choose to help small teams coordinate product decisions.'
    p.questions[qid]['answer']=body;p.save();p.load()
    r.note(p,'direct-answer-note',body,p.db['project']['revision'],[qid]);p.load()
    r.draft(p,qid,turn_id='direct-answer-note');p.load()
    assert p.questions[qid]['answer']==body and p.questions[qid]['history']==[]
    packet=r.evaluation_input(p,qid,'decision')
    assert packet['candidate_text']==body and packet['note_turns'][0]['turn_id']=='direct-answer-note'

def test_frozen_history_preserves_comments_ids_and_whitespace(project):
    p=project;qid=next(iter(p.questions))
    p.db['notes']['legacy']={'text':'A note named legacy.','question_ids':[qid],'created_at':r.now(),'content_hash':r.sha('A note named legacy.')}
    p.db['sources']['legacy']={'id':'legacy','text':'x'*140+'\t線上會議\nsecond line\tend','checked':False}
    # Build fresh serialization once, so the next load can preserve these blocks.
    p.db['records']['legacy']={'format':'startup101-records-v1','packets':{},'evaluations':{},'reviews':{},'decisions':{},'receipts':{},'session':{},'events':[]}
    plain=json.loads(json.dumps(p.db,ensure_ascii=False));raw=s.encode(plain).decode()
    raw=raw.replace('  legacy:\n    format:', '  legacy:\n# keep this unindented comment\n    format:')
    db=s.parse(raw);assert db['notes']['legacy']['text']=='A note named legacy.'
    assert db['sources']['legacy']['text']==plain['sources']['legacy']['text']
    db['questions'][qid]['answer']='A current answer.'
    emitted=s.encode(db);restored=s.parse(emitted,roundtrip=False)
    assert restored==db and b'# keep this unindented comment' in emitted
    for _,body,_ in db._startup_cami_frozen:assert body.encode() in emitted
    db['records']['legacy']['events'].append({'type':'changed'})
    with pytest.raises(s.Invalid,match='immutable legacy'):s.encode(db)


def test_native_long_headlines_do_not_change_answers_or_scoring(project):
    p=project;qid,packet=prepared(p);ev=evaluation(p,packet)
    r.accept(p,ev,p.db['project']['revision']);p.load()
    before=deepcopy(p.db);before_status=p.statuses()[qid]
    payload=r.key_points_input(p)
    points=[
        '每個角色繼續使用自己的人工智慧工具，系統找出互相衝突的前提，再邀請需要的人一起比較方案與做決定。',
        'People keep working with their own AI. The workspace finds conflicting assumptions, asks the right people, and helps them compare possible plans before deciding what to do together.'
    ]
    payload['entries']=[{k:v for k,v in payload['entries'][0].items() if k!='text'}|{'points':points}]
    r.set_key_points(p,payload);p.load()
    assert p.questions[qid]['key_points']['items']==points
    assert p.questions[qid]['accepted_version']['key_points']['items']==points
    assert p.questions[qid]['answer']==before['questions'][qid]['answer']
    for key in ('records','rules','notes'):
        assert p.db[key]==before[key]
    assert p.questions[qid]['history']==before['questions'][qid]['history']
    for key,value in before['questions'][qid]['accepted_version'].items():
        if key!='key_points':assert p.questions[qid]['accepted_version'][key]==value
    assert p.statuses()[qid]==before_status=='accepted'
    # The historical validator stays strict for historical provenance, while
    # native current headline writes use the new shared storage contract.
    with pytest.raises(r.Invalid,match='Chinese key point exceeds'):
        r.scoring.validate_key_points(payload['entries'])


@pytest.mark.parametrize('bad',[
    ['duplicate','duplicate'],[' leading'],['trailing '],['two\nlines'],
    ['two\rlines'],['two\u2028lines'],[''],['x'*1001],['point '+str(i) for i in range(13)],
    [None],'not an array'
])
def test_headline_shape_rejects_invalid_values(bad):
    with pytest.raises(s.Invalid):s.validate_headlines(bad)


def test_headline_shape_supports_long_bilingual_and_empty():
    assert s.validate_headlines([])==[]
    points=['中'*1000,'Keep your own AI. Make decisions together without another meeting.']
    assert s.validate_headlines(points)==points


def test_shared_headline_schema_accepts_same_shape_in_both_modes():
    from jsonschema import Draft202012Validator
    schema=json.loads(s.SCHEMA.read_text())
    defs=schema['$defs'];items={'$ref':'#/$defs/headline_items','$defs':defs}
    validator=Draft202012Validator(items)
    assert not list(validator.iter_errors([]))
    assert not list(validator.iter_errors(['中'*1000]))
    for bad in [['x'*1001],['x','x'],['x'+str(i) for i in range(13)]]:
        assert list(validator.iter_errors(bad))
    assert defs['key_points']['properties']['items']['$ref']=='#/$defs/headline_items'
    assert all(value['$ref']=='#/$defs/headline_items' for value in defs['core_question']['properties']['headlines']['properties'].values())
