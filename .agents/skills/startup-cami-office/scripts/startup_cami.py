# /// script
# requires-python = ">=3.11"
# dependencies = ["ruamel.yaml==0.18.16", "jsonschema==4.25.1", "markdown-it-py==3.0.0", "jinja2==3.1.6", "portalocker==3.2.0", "opencc-python-reimplemented==0.1.7"]
# ///
"""Cami Startup Canvas: single-YAML database CLI; JSON on stdout, errors on stderr."""
import argparse
from copy import deepcopy
import json
from pathlib import Path
import sys
from ruamel.yaml.scalarstring import LiteralScalarString
from jinja2 import Environment, FileSystemLoader, StrictUndefined, select_autoescape
from markupsafe import Markup
import startup_cami_yaml as storage
# The scoring validator is unchanged. Markdown parsing is used only by explicit migration.
import legacy_runtime as scoring

Invalid=scoring.Invalid
check=scoring.check
sha=scoring.sha
digest=scoring.digest
now=scoring.now
uid=scoring.uid
dumps=scoring.dumps
ASSETS=Path(__file__).resolve().parents[1]/'assets'
TEMPLATES=Path(__file__).resolve().parents[1]/'templates'
KINDS=scoring.KINDS

class Project:
    def __init__(self,root):
        # Current startup-cami.yaml, or a legacy startup101.yaml read and written in place.
        self.root=Path(root).resolve();self.docpath=storage.document_path(self.root)
        self.config={'document':self.docpath.name,'output':'startup-cami.html'}
    def path(self,relative):return scoring.safe(self.root,relative)
    def load(self,optional=False,readonly=False):
        self.db,self.source_hash=storage.load(self.docpath,roundtrip=not readonly)
        self.__dict__.pop('_statuses',None)
        self.questions=self.db['questions'];self.records=self.db['records'];self.rubric=self.db['rules']['rubric']
        return self
    def question(self,qid):
        check(not self.db.get('core_canvas'),'Active core Canvas: use explicit sync_core.py to update reviewed core answers; original questions are preserved as history')
        check(qid in self.questions,'unknown question or caution');return self.questions[qid]
    def save(self,expected=None,revision=None):
        check(not self.db.get('core_canvas'),'Active core Canvas cannot be changed by legacy question commands; use sync_core.py')
        if expected is not None:check(expected==self.source_hash,'source hash conflict; inspect again')
        if revision is not None:check(revision==self.db['project']['revision'],'document revision conflict')
        self.db['project']['revision']+=1
        self.source_hash=storage.save(self.docpath,self.db,self.source_hash)
        self.__dict__.pop('_statuses',None)
        return {'revision':self.db['project']['revision'],'source_sha256':self.source_hash}
    def statuses(self):
        if hasattr(self,'_statuses'):return self._statuses
        result={};legacy={}
        if self.db.get('legacy_archive',{}).get('files'):
            from migrate_yaml import legacy_statuses, legacy_project
            self._legacy_project=legacy_project(self.db)
            legacy=legacy_statuses(self.db,project=self._legacy_project)
        for qid,q in self.questions.items():
            snap=q['accepted_version']
            if not snap:continue
            if snap['receipt_id'].startswith('legacy:'):
                result[qid]=legacy.get(qid,'unverifiable');continue
            try:
                receipt=self.records['receipts'][snap['receipt_id']]
                check(receipt['question_id']==qid and receipt['answer_hash']==snap['answer_hash'] and receipt['revision']==snap['revision'],'receipt mismatch')
                check(bool(receipt['evaluation_ids']),'receipt needs evaluation')
                check(receipt['evaluation_hashes']=={eid:digest(self.records['evaluations'][eid]) for eid in receipt['evaluation_ids']},'receipt evaluation changed')
                packet=self.records['packets'][receipt['packet_id']]
                check(packet['question_id']==qid and packet['answer']==snap['answer'],'accepted text differs')
                check(receipt['dependencies']==packet['dependencies'],'receipt dependencies mismatch')
                packet_valid(self,packet,current=False)
                for eid in receipt['evaluation_ids']:
                    ev=self.records['evaluations'][eid];scoring.validate_result(ev,evaluator_packet(self,packet));check(ev['verdict']=='pass','not pass')
                if packet['review_policy']=='independent':
                    resolution=self.records['reviews'][receipt['resolution_id']]
                    check(receipt['resolution_hash']==digest(resolution),'receipt resolution changed')
                    validate_review(self,resolution,packet,require_agreed=True)
                result[qid]='accepted'
            except (KeyError,Invalid,ValueError,TypeError):result[qid]='unverifiable'
        # Dependency graph reaches a fixed point, including cycles and transitive invalidation.
        for _ in range(len(result)+1):
            changed=False
            for qid,state in list(result.items()):
                if state!='accepted':continue
                snap=self.questions[qid]['accepted_version']
                if snap['receipt_id'].startswith('legacy:'):continue
                receipt=self.records['receipts'][snap['receipt_id']]
                for dep in receipt['dependencies']:
                    other=self.questions[dep['question_id']]['accepted_version']
                    if result.get(dep['question_id'])!='accepted' or not other or other['revision']!=dep['revision'] or other['answer_hash']!=dep['answer_sha256']:
                        result[qid]='needs_review';changed=True;break
            if not changed:break
        self._statuses=result;return result
    def summary(self):
        if self.db.get('core_canvas'):
            core=self.db['core_canvas'];statuses={qid:q['status'] for qid,q in core['questions'].items()}
            next_question=next((qid for category in core['categories'] for qid in category['questions'] if statuses[qid]=='empty'),None)
            return {'project':self.db['project'],'source_sha256':self.source_hash,'core_mode':True,
                    'core_revision':core['revision'],'question_count':len(core['questions']),
                    'category_count':len(core['categories']),'saved_count':sum(status=='saved' for status in statuses.values()),'accepted_count':0,
                    'archived_source_question_count':len(self.questions),'statuses':statuses,'current_statuses':statuses,
                    'next_question_id':next_question,'caution_count':0,
                    'source_markdown_sha256':core['source_markdown_sha256'],
                    'document':self.docpath.name,'legacy_document_name':storage.is_legacy(self.docpath),
                    'pending_transaction':storage.journal_path(self.docpath).exists()}
        statuses=self.statuses()
        current={qid:('empty' if not q['answer'] else 'accepted' if statuses.get(qid)=='accepted' and q['accepted_version']['answer']==q['answer'] else 'unreviewed') for qid,q in self.questions.items()}
        return {'project':self.db['project'],'source_sha256':self.source_hash,'next_question_id':self.db['session']['next_question'],
                'statuses':statuses,'current_statuses':current,'question_count':len(self.questions),'caution_count':len(self.db['canvas']['cautions']),
                'notes':{k:sha(v['text']) for k,v in self.db['notes'].items()},'pending_transaction':storage.journal_path(self.docpath).exists(),
                'document':self.docpath.name,'legacy_document_name':storage.is_legacy(self.docpath),
                'drafts':{k:{'state':v['action'],'reason':v['reason']} for k,v in self.db['session']['actions'].items()},
                'sidecars':sidecar_summary(self)}

def sidecar_summary(p):
    result={}
    legacy_summary={}
    if p.records.get('legacy'):
        from migrate_yaml import legacy_sidecar_summary
        legacy_summary=legacy_sidecar_summary(p.db,project=getattr(p,'_legacy_project',None))
    for kind in ('reviews','decisions'):
        rows=[]
        for rid,payload in p.records[kind].items():
            rows.append({'payload':payload,'recorded_at':payload.get('reviewed_at',payload.get('assessed_at','')),'native':True})
        for rid,record in p.records.get('legacy',{}).get(kind,{}).items():
            rows.append({'payload':record['payload'],'recorded_at':record.get('recorded_at',''),'native':False})
        latest={}
        for row in sorted(rows,key=lambda row:row['recorded_at']):
            payload=row['payload'];qid=payload['question_id'];fresh=False
            try:
                packet=current_packet(p,qid)
                fresh=packet['input_hash']==payload['input_sha256']
                if kind=='decisions':
                    evaluation=p.records['evaluations'][payload['evaluation_id']]
                    scoring.validate_result(evaluation,evaluator_packet(p,packet))
            except (KeyError,Invalid,ValueError,TypeError):pass
            latest[qid]={'payload':payload,'recorded_at':row['recorded_at'],**({'current_packet':fresh} if kind=='reviews' else {'stale':not fresh})}
            if not row['native'] and qid in legacy_summary.get(kind,{}).get('latest_by_question',{}):
                latest[qid]=legacy_summary[kind]['latest_by_question'][qid]
        result[kind]={'count':len(rows),'latest_by_question':latest}
    return result

def init_project(root,title,locale='en'):
    p=Project(root);check(not p.docpath.exists(),p.docpath.name+' already exists')
    # startup101.md is the legacy Markdown-era document; it is migrated, never overwritten.
    check(not p.path('startup101.md').exists(),'legacy Markdown found: run migrate-yaml explicitly')
    db,_=storage.load(TEMPLATES/'startup-cami.yaml');db['project'].update(id=uid(),name=title,language=locale)
    storage.save(p.docpath,db,None);return Project(root).load().summary()

def snapshot(q,revision,kind='draft',receipt=None):
    return {'answer':str(q['answer']),'answer_hash':sha(q['answer']),'revision':max(1,revision),'key_points':deepcopy(q['key_points']),
            'note_refs':list(q['note_refs']),'receipt_id':receipt,'saved_at':now(),'kind':kind}

def note(p,turn_id,body,expected,questions=()):
    scoring.valid_id(turn_id,'turn_id');scoring.valid_string(body,'note');scoring.check_language(body)
    for qid in questions:p.question(qid)
    old=p.db['notes'].get(turn_id)
    if old:
        check(old['text']==body and old['question_ids']==list(dict.fromkeys(questions)),'note ID already used');return {'status':'already_noted'}
    p.db['notes'][turn_id]={'text':LiteralScalarString(body),'question_ids':list(dict.fromkeys(questions)),'created_at':now(),'content_hash':sha(body)}
    return {'status':'noted','turn_id':turn_id,**p.save(revision=expected)}

def draft(p,qid,excerpt=None,sources=None,turn_id=None):
    q=p.question(qid);check(turn_id in p.db['notes'],'save note first');body=p.db['notes'][turn_id]['text']
    excerpt=body if excerpt is None else excerpt;check(excerpt and excerpt in body,'draft excerpt must match note')
    scoring.check_language(excerpt)
    if q['answer'] and q['answer']!=excerpt:q['history'].append(snapshot(q,p.db['project']['revision']))
    q['answer']=LiteralScalarString(excerpt)
    if turn_id not in q['note_refs']:q['note_refs'].append(turn_id)
    if qid not in p.db['notes'][turn_id]['question_ids']:p.db['notes'][turn_id]['question_ids'].append(qid)
    for source in sources or []:
        scoring.exact(source,('id','text','checked'),('url',))
        check(isinstance(source['id'],str) and isinstance(source['text'],str) and type(source['checked']) is bool,'invalid source')
        scoring.check_language(source['text'])
        if 'url' in source:check(isinstance(source['url'],str) and source['url'].startswith(('https://','http://')),'source URL must use http/https')
        old=p.db['sources'].get(source['id'])
        check(old is None or old==source,'source identifier already used with different content');p.db['sources'][source['id']]=source
    if sources is not None:q['source_refs']=[source['id'] for source in sources]
    q['review']=None
    return {'status':'drafted',**p.save()}

def semantic_hash(packet):return digest({k:v for k,v in packet.items() if k!='input_hash'})

def packet_valid(p,packet,current=True):
    check(packet['input_hash']==semantic_hash(packet),'packet hash mismatch')
    check(packet['answer_hash']==sha(packet['answer']),'candidate hash mismatch')
    check(packet['project_id']==p.db['project']['id'],'packet project mismatch')
    check(packet['rules_hash']==digest(p.db['rules']),'rules changed')
    q=p.question(packet['question_id'])
    check(packet['requirements_hash']==digest({'requirements':q['requirements'],'prompt':q['prompt'],'definition':q['definition']}),'question requirements changed')
    check(packet['sources_hash']==digest({sid:p.db['sources'][sid] for sid in packet['source_refs']}),'sources changed')
    if current:
        check(q['answer']==packet['answer'],'answer changed; evaluate again')
        check(q['note_refs']==[n['note_id'] for n in packet['note_spans']] and q['source_refs']==packet['source_refs'],'answer evidence links changed')
        for dep in packet['dependencies']:
            snap=p.questions[dep['question_id']]['accepted_version']
            check(p.statuses().get(dep['question_id'])=='accepted' and snap and snap['revision']==dep['revision'] and snap['answer_hash']==dep['answer_sha256'],'dependency changed')
    for span in packet['note_spans']:
        body=p.db['notes'][span['note_id']]['text']
        check(sha(body)==span['content_hash'] and span['excerpt'] in body and sha(span['excerpt'])==span['excerpt_hash'],'note changed')
    return packet

def evaluator_packet(p,packet):
    q=p.question(packet['question_id'])
    return {'question_id':packet['question_id'],'question':{'question':q['prompt']['en'],**q['definition']},'requirements':q['requirements'],
        'question_requirements_version':p.db['rules']['requirements_version'],'answer_kind':packet['kind'],
        'note_turns':[{'turn_id':s['note_id'],'excerpt':s['excerpt'],'text':p.db['notes'][s['note_id']]['text']} for s in packet['note_spans']],
        'candidate_text':packet['answer'],'candidate_sha256':packet['answer_hash'],'rubric':p.rubric,'rubric_version':p.rubric['version'],
        'dependencies':packet['dependencies'],'sources':[p.db['sources'][sid] for sid in packet['source_refs']],
        'input_sha256':packet['input_hash'],'review_policy':packet['review_policy'],'project_id':packet['project_id'],
        'related_answers':[{'dependency':d,'text':p.questions[d['question_id']]['accepted_version']['answer']} for d in packet['dependencies']]}

def evaluation_input(p,qid,kind,candidate=None,confirmed=False,dependencies=(),review_policy='single'):
    q=p.question(qid);check(kind in q['requirements']['allowed_answer_kinds'],'answer kind not allowed')
    check(q['answer'],'answer is empty')
    candidate=q['answer'] if candidate is None else candidate
    if candidate!=q['answer']:
        check(confirmed,'rewritten candidate requires --confirmed')
        q['history'].append(snapshot(q,p.db['project']['revision']))
        q['answer']=LiteralScalarString(candidate)
    notes=[{'note_id':nid,'content_hash':sha(p.db['notes'][nid]['text']),'excerpt':str(p.db['notes'][nid]['text']),'excerpt_hash':sha(p.db['notes'][nid]['text'])} for nid in q['note_refs']]
    check(notes,'save and link an interview note first')
    check(confirmed or any(candidate in n['excerpt'] for n in notes),'rewritten answer requires --confirmed')
    for n in notes:
        if candidate in n['excerpt']:n['excerpt']=str(candidate);n['excerpt_hash']=sha(candidate)
    lock=p.db['session']['review_policy_locks'].get(qid)
    turn_ids=list(q['note_refs'])
    check(not lock or lock['turn_ids']!=turn_ids or lock['policy']!='independent' or review_policy=='independent','independent review cannot be downgraded')
    deps=[]
    for depid in dependencies:
        check(depid!=qid and p.statuses().get(depid)=='accepted','dependency must be another accepted answer')
        a=p.question(depid)['accepted_version'];deps.append({'question_id':depid,'revision':a['revision'],'answer_sha256':a['answer_hash']})
    source_ids=[p.db['sources'][sid]['id'] for sid in q['source_refs']]
    check(len(source_ids)==len(set(source_ids)),'one packet cannot include conflicting versions of the same source identifier')
    packet={'question_id':qid,'project_id':p.db['project']['id'],'answer':str(candidate),'answer_hash':sha(candidate),'input_hash':'',
        'kind':kind,'review_policy':review_policy,'rules_hash':digest(p.db['rules']),
        'requirements_hash':digest({'requirements':q['requirements'],'prompt':q['prompt'],'definition':q['definition']}),
        'note_spans':notes,'source_refs':list(q['source_refs']),'sources_hash':digest({sid:p.db['sources'][sid] for sid in q['source_refs']}),'dependencies':deps,'created_at':now(),'confirmed_rewrite':confirmed}
    packet['input_hash']=semantic_hash(packet);pid=packet['input_hash'];p.records['packets'][pid]=packet
    q['review']={'packet_id':pid,'evaluation_ids':[],'resolution_id':None,'acceptance_receipt_id':None}
    p.db['session']['review_policy_locks'][qid]={'policy':review_policy,'turn_ids':turn_ids}
    p.save();return evaluator_packet(p,packet)

def current_packet(p,qid):
    q=p.question(qid);check(q['review'] is not None,'generate evaluation input first')
    return packet_valid(p,p.records['packets'][q['review']['packet_id']])

def record_evaluation(p,result,save=True):
    scoring.check_language(result)
    packet=current_packet(p,result['question_id']);scoring.validate_result(result,evaluator_packet(p,packet))
    eid=result['evaluation_id'];old=p.records['evaluations'].get(eid);check(old is None or old==result,'evaluation identifier already used')
    p.records['evaluations'][eid]=result;ids=p.questions[result['question_id']]['review']['evaluation_ids']
    if eid not in ids:ids.append(eid)
    return {'status':'evaluation_recorded',**(p.save() if save else {})}

def validate_review(p,review,packet,require_agreed=False):
    scoring.exact(review,scoring.REVIEW_KEYS,('evaluation_hashes',))
    scoring.valid_id(review['review_id'],'review_id');scoring.valid_string(review['reviewed_at'],'reviewed_at')
    check(review['question_id']==packet['question_id'] and review['input_sha256']==packet['input_hash'],'review packet mismatch')
    check(review['resolution'] in ('agreed','unresolved','unavailable'),'invalid resolution')
    check(isinstance(review['resolution_reasons'],list) and review['resolution_reasons'] and all(isinstance(s,str) and s.strip() for s in review['resolution_reasons']),'review reasons required')
    ids=review['evaluation_ids'];check(len(ids)<=2 and len(ids)==len(set(ids)),'review requires distinct evaluation identifiers')
    results=[]
    for eid in ids:
        ev=p.records['evaluations'][eid];scoring.validate_result(ev,evaluator_packet(p,packet));results.append(ev)
    if 'evaluation_hashes' in review:check(review['evaluation_hashes']=={eid:digest(p.records['evaluations'][eid]) for eid in ids},'review evaluation history changed')
    identities=[' '.join(r['evaluator'].split()).casefold() for r in results]
    check(len(identities)==len(set(identities)),'independent evaluator identities must differ')
    if require_agreed:check(review['resolution']=='agreed','independent review not agreed')
    if review['resolution']=='agreed':check(len(results)==2 and all(r['verdict']=='pass' for r in results),'two passing independent evaluations required')
    return review

def record_review(p,review):
    packet=current_packet(p,review['question_id']);check(packet['review_policy']=='independent','review requires independent policy')
    validate_review(p,review,packet)
    review={**review,'evaluation_hashes':{eid:digest(p.records['evaluations'][eid]) for eid in review['evaluation_ids']}}
    rid=review['review_id'];old=p.records['reviews'].get(rid)
    check(old is None or old==review,'review identifier already used');p.records['reviews'][rid]=review
    p.questions[review['question_id']]['review']['resolution_id']=rid
    return {'status':'review_recorded',**p.save()}

def record_decision(p,assessment):
    scoring.exact(assessment,scoring.DECISION_KEYS)
    scoring.check_language(assessment)
    scoring.valid_id(assessment['assessment_id'],'assessment_id')
    for field in ('decision','what_changes_verdict','assessor','assessed_at'):scoring.valid_string(assessment[field],field)
    scoring.string_list(assessment['missing_information'],'missing_information');scoring.string_list(assessment['evidence_refs'],'evidence_refs')
    qid=assessment['question_id'];packet=current_packet(p,qid)
    check(assessment['input_sha256']==packet['input_hash'],'decision packet mismatch')
    check(assessment['status'] in ('ready','not_ready','unknown'),'invalid decision status')
    ev=p.records['evaluations'][assessment['evaluation_id']];scoring.validate_result(ev,evaluator_packet(p,packet))
    refs={p.db['sources'][sid]['id'] for sid in packet['source_refs']}|{n['note_id'] for n in packet['note_spans']}
    check(set(assessment['evidence_refs'])<=refs,'unknown decision evidence')
    aid=assessment['assessment_id'];old=p.records['decisions'].get(aid);check(old is None or old==assessment,'assessment identifier already used')
    p.records['decisions'][aid]=assessment
    if aid not in p.questions[qid]['decision_refs']:p.questions[qid]['decision_refs'].append(aid)
    return {'status':'decision_recorded',**p.save()}

def accept(p,result,expected):
    q=p.question(result['question_id']);eid=result['evaluation_id']
    if eid in p.records['receipts']:
        check(p.records['evaluations'].get(eid)==result,'evaluation identifier conflict');return {'status':'already_committed'}
    check(p.db['project']['revision']==expected,'document revision conflict')
    packet=current_packet(p,result['question_id']);record_evaluation(p,result,save=False);check(result['verdict']=='pass','only pass may be accepted')
    for dep in packet['dependencies']:
        a=p.questions[dep['question_id']]['accepted_version'];check(p.statuses().get(dep['question_id'])=='accepted' and a['revision']==dep['revision'] and a['answer_hash']==dep['answer_sha256'],'dependency changed')
    review=q['review']
    ids=[eid];rid=None
    if packet['review_policy']=='independent':
        rid=review['resolution_id'];check(rid in p.records['reviews'],'independent review required')
        resolution=validate_review(p,p.records['reviews'][rid],packet,require_agreed=True)
        check(eid in resolution['evaluation_ids'],'accept result absent from independent review');ids=list(resolution['evaluation_ids'])
    old=q['accepted_version'];revision=1 if old is None else old['revision']+1
    if old:q['history'].append(deepcopy(old))
    p.records['receipts'][eid]={'question_id':result['question_id'],'answer_hash':packet['answer_hash'],'revision':revision,
        'packet_id':review['packet_id'],'evaluation_ids':ids,'evaluation_hashes':{value:digest(p.records['evaluations'][value]) for value in ids},
        'resolution_id':rid,'resolution_hash':digest(p.records['reviews'][rid]) if rid else None,'accepted_at':now(),'dependencies':packet['dependencies']}
    q['accepted_version']=snapshot(q,revision,'accepted',eid);review['acceptance_receipt_id']=eid
    if p.db['session']['next_question']==result['question_id']:p.db['session']['next_question']=None
    p.db['session']['actions'].pop(result['question_id'],None)
    return {'status':'accepted','question_id':result['question_id'],**p.save(revision=expected)}

def set_next(p,qid,expected):
    q=p.question(qid);check(p.statuses().get(qid)!='accepted' or q['answer']!=q['accepted_version']['answer'],'question already accepted');p.db['session']['next_question']=qid
    return {'status':'next_question_set',**p.save(revision=expected)}

def session_action(p,qid,action,reason):
    p.question(qid);check(reason.strip(),'reason required');p.db['session']['actions'][qid]={'action':action,'reason':reason,'updated_at':now()}
    return {'status':action,**p.save()}

def key_points_input(p):
    rows=[]
    for qid,q in p.questions.items():
        a=q['accepted_version']
        if a:rows.append({'question_id':qid,'role':'formal','source_sha256':sha(a['answer']),'text':a['answer']})
        if q['answer'] and (not a or q['answer']!=a['answer']):rows.append({'question_id':qid,'role':'pending','source_sha256':sha(q['answer']),'text':q['answer']})
    return {'source_sha256':p.source_hash,'entries':rows}

def validate_native_key_points(entries):
    """Check current headline writes without applying the historical short caps."""
    check(isinstance(entries,list),'key points must be an array')
    seen=set()
    for item in entries:
        scoring.exact(item,('question_id','role','source_sha256','points'))
        scoring.valid_id(item['question_id'],'key points question')
        scoring.valid_hash(item['source_sha256'],'key points source')
        check(item['role'] in ('formal','pending'),'invalid key points role')
        identity=(item['question_id'],item['role'])
        check(identity not in seen,'duplicate key points question/role');seen.add(identity)
        storage.validate_headlines(item['points'])
        for point in item['points']:scoring.check_language(point)

def set_key_points(p,payload):
    scoring.exact(payload,('source_sha256','entries'));check(payload['source_sha256']==p.source_hash,'source changed')
    validate_native_key_points(payload['entries'])
    for item in payload['entries']:
        q=p.question(item['question_id']);target=q['accepted_version'] if item['role']=='formal' else q
        check(target and sha(target['answer'])==item['source_sha256'],'key points answer changed')
        target['key_points']={'items':item['points'],'answer_hash':item['source_sha256']}
        if q['answer']==target['answer']:q['key_points']=deepcopy(target['key_points'])
    return {'status':'key_points_saved',**p.save()}

def core_projection(p,locale=None):
    """Project only the active YAML layer, without legacy evaluations or notes."""
    db=p.db;core=db['core_canvas'];locale=locale or db['project']['language']
    questions=[];categories=[];cards=[];answers={};keypoints={}
    for index,category in enumerate(core['categories']):
        name=category['id']
        categories.append({'name':name,'titleI18n':dict(category['title']),
                           'center':{'x':900+(index%3)*2000,'y':900+(index//3)*1900},
                           'landmark':'','cautionOnly':False,'questionCount':len(category['questions'])})
        for qid in category['questions']:
            q=core['questions'][qid];prompt=dict(q['prompt']);text=q['answer'][locale]
            questions.append({'id':qid,'question':prompt['en'],'rawQuestion':prompt['en'],'prompt':prompt,
                              'category':name,'editorialNote':'','sourceSection':'','sourceRange':'','audience':'',
                              'help':{'why':'','example':'','avoid':'','synthetic':False},'cautionOnly':False,
                              'alternateQuestions':deepcopy(q['alternate_questions']),'followups':deepcopy(q['followups']),
                              'alternateMarkdown':q['alternate_markdown'],'followupsMarkdown':q['followups_markdown']})
            if q['status']=='saved':
                answers[qid]={'text':text,'textI18n':dict(q['answer']),'status':'saved','scores':None,
                              'claims':[],'revision':core['revision']}
                keypoints[qid]={'formal':{'points':list(q['headlines'][locale]),'pointsI18n':deepcopy(q['headlines']),
                                          'source_sha256':sha(text)}}
            cards.append({'id':qid,'title':prompt['en'],'titleI18n':prompt,'primary_category':name,
                          'categories':[name],'lead_question_id':qid,'reason':'',
                          'questions':[{'question_id':qid,'question':prompt['en'],'side':'main',
                                        'presentation':'primary','original_category':name}]})
    return {'coreMode':True,'coreContent':{'categories':{c['id']:dict(c['title']) for c in core['categories']},
                                         'questions':{qid:dict(q['prompt']) for qid,q in core['questions'].items()}},
            'keyPoints':keypoints,'pendingAnswers':{},'interviewNotes':[],
            'next_question_id':next((q['id'] for q in questions if q['id'] not in answers),None),
            'clusters':{'schema_version':1,'source_sha256':core['content_sha256'],'cards':cards,'cautions':[],
                        'counts':{'postits':len(cards),'active_questions':len(questions),'cautions':0,'postits_with_other_hand':0}},
            'locale':locale,'project':{'project_id':db['project']['id'],'title':db['project']['name'],
                                      'revision':db['project']['revision'],'catalog_sha256':core['content_sha256']},
            'categories':categories,'questions':questions,'cautions':[],'answers':answers,'readonly':True,
            'source':{'revision':db['project']['revision'],'sha256':p.source_hash}}

def projection(p,locale=None):
    if p.db.get('core_canvas'):return core_projection(p,locale)
    db=p.db;locale=locale or db['project']['language'];statuses=p.statuses();questions=[];categories=[];keypoints={};answers={};pending={}
    membership={m['question_id']:m['original_category'] for c in db['canvas']['cards'].values() for m in c['questions']}
    for category in db['canvas']['category_order']:
        c=db['canvas']['categories'][category]
        categories.append({'name':category,'center':c['layout_hint']['center'],'landmark':c['layout_hint']['landmark'],'cautionOnly':False,'questionCount':sum(membership[qid]==category for qid in p.questions)})
    legacy=db['records'].get('legacy',{})
    legacy_pending={}
    if legacy:
        from migrate_yaml import legacy_pending_view
        legacy_pending=legacy_pending_view(db)
    for qid,q in p.questions.items():
        d=q['definition'];questions.append({'id':qid,'question':q['prompt']['en'],'rawQuestion':q['prompt']['en'],'category':membership[qid],
            'editorialNote':d['editorial_note'],'sourceSection':d['source_section'],'sourceRange':d['source_range'],'audience':d['audience'],
            'help':d['help']['en'],'cautionOnly':False})
        a=q['accepted_version']
        if a:
            if a['receipt_id'].startswith('legacy:'):
                meta=legacy.get('receipts',{}).get(a['receipt_id'].split(':',1)[1],{}).get('metadata',{})
            else:
                receipt=p.records['receipts'][a['receipt_id']];meta=p.records['evaluations'][receipt['evaluation_ids'][0]]
            answers[qid]={'text':a['answer'],'status':statuses.get(qid,'unverifiable'),'scores':meta.get('scores'), 'claims':meta.get('claims',[]),'revision':a['revision']}
            if a['key_points']['answer_hash']==sha(a['answer']):keypoints.setdefault(qid,{})['formal']={'points':a['key_points']['items'],'source_sha256':a['key_points']['answer_hash']}
        if q['answer'] and (not a or q['answer']!=a['answer']):
            ev=None
            try:
                packet=current_packet(p,qid)
                ids=q['review']['evaluation_ids']
                if ids:
                    ev=p.records['evaluations'][ids[-1]];scoring.validate_result(ev,evaluator_packet(p,packet))
            except (KeyError,Invalid,TypeError,ValueError):ev=None
            pending[qid]={'role':'pending','text':q['answer'],'evaluation':ev or legacy_pending.get(qid,{}).get('evaluation'),'noteIds':q['note_refs']}
            if q['key_points']['answer_hash']==sha(q['answer']):keypoints.setdefault(qid,{})['pending']={'points':q['key_points']['items'],'source_sha256':q['key_points']['answer_hash']}
    cautions=[v['definition'] for v in db['canvas']['cautions'].values()]
    cards=[{'id':cid,**c,'questions':[{**m,'question':p.questions[m['question_id']]['prompt']['en']} for m in c['questions']]} for cid,c in db['canvas']['cards'].items()]
    clusters={'schema_version':1,'source_sha256':db['rules']['pinned_assets']['catalog']['sha256'],'cards':cards,
        'cautions':[{k:v for k,v in c.items() if k not in ('definition','requirements')} for c in db['canvas']['cautions'].values()],
        'counts':{'postits':len(cards),'active_questions':len(questions),'cautions':len(cautions),'postits_with_other_hand':sum(any(m['side']=='on_the_other_hand' for m in c['questions']) for c in cards)}}
    return {'keyPoints':keypoints,'pendingAnswers':pending,'interviewNotes':[{'id':nid,'text':n['text'],'source':'note','questionIds':n['question_ids']} for nid,n in db['notes'].items()],
        'next_question_id':db['session']['next_question'],'clusters':clusters,'locale':locale,
        'project':{'project_id':db['project']['id'],'title':db['project']['name'],'revision':db['project']['revision'],'catalog_sha256':db['rules']['pinned_assets']['catalog']['sha256']},
        'categories':categories,'questions':questions,'cautions':cautions,'answers':answers,'readonly':True,
        'source':{'revision':db['project']['revision'],'sha256':p.source_hash}}

def render(p,bundle,locale=None,include_html=False):
    bundle=Path(bundle).resolve();manifest=scoring.readjson(bundle/'manifest.json')
    check(manifest['template_api_version']==1 and 2 in manifest['document_schema_versions'],'template API/schema incompatible')
    for asset in manifest.get('assets',[]):
        path=scoring.safe(bundle,asset['path']);check(not asset.get('required',True) or path.is_file() and sha(path.read_bytes())==asset['sha256'],'template asset mismatch: '+asset['path'])
    model=projection(p,locale);model['template_version']=manifest['version']
    serialized=dumps(model).replace('&','\\u0026').replace('<','\\u003c').replace('>','\\u003e').replace('\u2028','\\u2028').replace('\u2029','\\u2029')
    env=Environment(loader=FileSystemLoader(str(bundle)),undefined=StrictUndefined,autoescape=select_autoescape(default=True))
    html=env.get_template(manifest['entry']).render(model=model,model_json=Markup(serialized))
    # STARTUP101_READONLY is the marker of template bundles installed before the rename.
    check('STARTUP_CAMI_READONLY' in html or 'STARTUP101_READONLY' in html,'template readonly adapter missing')
    output=p.path('startup-cami.html')
    if not include_html:storage.atomic(output,html.encode())
    return {'status':'rendered','locale':model['locale'],'output':str(output),'source':model['source'],'template_version':manifest['version'],'warnings':[],**({'html':html} if include_html else {})}

def root_for(value):
    if value:return Path(value).resolve()
    cwd=Path.cwd()
    for path in (cwd,*cwd.parents):
        if (path/storage.DOCUMENT).exists() or (path/storage.LEGACY_DOCUMENT).exists():return path
    return cwd

def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--project');sub=parser.add_subparsers(dest='command',required=True)
    ini=sub.add_parser('init');ini.add_argument('--title',default='My startup');ini.add_argument('--locale',choices=('en','zh-TW'),default='en')
    for command in ('inspect','validate','recover','key-points-input'):sub.add_parser(command)
    mig=sub.add_parser('migrate-yaml');mig.add_argument('--apply',action='store_true')
    name=sub.add_parser('migrate-name',help='Rename a legacy startup101.yaml project to startup-cami.yaml (preview unless --apply).');name.add_argument('--apply',action='store_true')
    kp=sub.add_parser('set-key-points');kp.add_argument('--file',required=True)
    nxt=sub.add_parser('set-next');nxt.add_argument('--question',required=True);nxt.add_argument('--expected-revision',type=int,required=True)
    cap=sub.add_parser('note');cap.add_argument('--question',action='append',default=[]);cap.add_argument('--turn-id',required=True);cap.add_argument('--text-file',required=True);cap.add_argument('--expected-revision',type=int,required=True)
    dr=sub.add_parser('draft');dr.add_argument('--turn-id',required=True);dr.add_argument('--question',required=True);dr.add_argument('--text-file');dr.add_argument('--sources-file')
    inp=sub.add_parser('evaluate-input');inp.add_argument('--question',required=True);inp.add_argument('--kind',choices=KINDS,required=True);inp.add_argument('--candidate-file');inp.add_argument('--confirmed',action='store_true');inp.add_argument('--dependency',action='append',default=[]);inp.add_argument('--review-policy',choices=('single','independent'),default='single')
    ac=sub.add_parser('accept');ac.add_argument('--evaluation',required=True);ac.add_argument('--expected-revision',type=int,required=True)
    ev=sub.add_parser('record-evaluation');ev.add_argument('--evaluation',required=True)
    rv=sub.add_parser('record-review');rv.add_argument('--review',required=True)
    dc=sub.add_parser('record-decision');dc.add_argument('--assessment',required=True)
    act=sub.add_parser('session-action');act.add_argument('--question',required=True);act.add_argument('--action',choices=('defer','skip','resume'),required=True);act.add_argument('--reason',required=True)
    ren=sub.add_parser('render');ren.add_argument('--template-bundle',required=True);ren.add_argument('--locale',choices=('en','zh-TW'));ren.add_argument('--include-html',action='store_true')
    for command in (nxt,cap,dr,inp,ac,ev,rv,dc,act):command.add_argument('--expected-source-sha256',required=True)
    args=parser.parse_args();root=root_for(args.project)
    try:
        if args.command=='migrate-yaml':
            from migrate_yaml import migrate_project, apply
            db,result=migrate_project(root)
            if args.apply:result={**result,'backup':apply(root,db),'status':'migrated'}
            print(dumps(result));return 0
        if args.command=='migrate-name':
            print(dumps(storage.migrate_name(root,args.apply)));return 0
        with storage.lock(root):
            if args.command=='init':result=init_project(root,args.title,args.locale)
            elif args.command=='recover':result=storage.recover(storage.document_path(root))
            else:
                p=Project(root).load(readonly=args.command in ('inspect','validate','render','key-points-input'))
                if hasattr(args,'expected_source_sha256'):check(args.expected_source_sha256==p.source_hash,'source hash conflict; inspect again')
                check(not p.db.get('core_canvas') or args.command in ('inspect','validate','render'),'Active core Canvas: use sync_core.py for reviewed core content; legacy question and evaluation commands cannot modify archived source questions')
                if args.command in ('inspect','validate'):result=p.summary()
                elif args.command=='key-points-input':result=key_points_input(p)
                elif args.command=='set-key-points':result=set_key_points(p,scoring.readjson(Path(args.file)))
                elif args.command=='set-next':result=set_next(p,args.question,args.expected_revision)
                elif args.command=='note':result=note(p,args.turn_id,Path(args.text_file).read_text(),args.expected_revision,args.question)
                elif args.command=='draft':result=draft(p,args.question,Path(args.text_file).read_text() if args.text_file else None,scoring.readjson(Path(args.sources_file)) if args.sources_file else None,args.turn_id)
                elif args.command=='evaluate-input':result=evaluation_input(p,args.question,args.kind,Path(args.candidate_file).read_text() if args.candidate_file else None,args.confirmed,args.dependency,args.review_policy)
                elif args.command=='accept':result=accept(p,scoring.readjson(Path(args.evaluation)),args.expected_revision)
                elif args.command=='record-evaluation':result=record_evaluation(p,scoring.readjson(Path(args.evaluation)))
                elif args.command=='record-review':result=record_review(p,scoring.readjson(Path(args.review)))
                elif args.command=='record-decision':result=record_decision(p,scoring.readjson(Path(args.assessment)))
                elif args.command=='session-action':result=session_action(p,args.question,args.action,args.reason)
                else:result=render(p,args.template_bundle,args.locale,args.include_html)
        print(dumps(result));return 0
    except (Invalid,storage.Invalid,OSError,KeyError,TypeError,ValueError) as error:
        print(dumps({'error':str(error),'command':args.command}),file=sys.stderr);return 2

if __name__=='__main__':sys.exit(main())
