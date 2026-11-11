# /// script
# requires-python = ">=3.11"
# dependencies = ["markdown-it-py==3.0.0", "jinja2==3.1.6", "portalocker==3.2.0", "opencc-python-reimplemented==0.1.7"]
# ///
"""Legacy (pre-YAML) local document lifecycle. Does not assess business claims or call an LLM.

Legacy names: this module reads projects created before the rename to Cami Startup
Canvas. Their startup101.md document, .startup101/ state directory and
startup101-* fenced block identifiers are an on-disk format; never rename them.
"""
from __future__ import annotations
import argparse
import contextlib
import hashlib
from functools import lru_cache
import json
import os
from pathlib import Path
import re
import sys
import tempfile
from datetime import datetime, timezone
import uuid
import unicodedata
from markdown_it import MarkdownIt
from jinja2 import Environment, FileSystemLoader, StrictUndefined, select_autoescape, TemplateError
import portalocker

ASSETS = Path(__file__).resolve().parents[1] / 'assets'
DIMENSIONS = ('clarity', 'specificity', 'relevance', 'consistency')
KINDS = ('fact', 'hypothesis', 'decision', 'reflection')
EVIDENCE = ('not_applicable', 'hypothesis', 'reported', 'source_checked', 'contradicted')
class Invalid(ValueError): pass

def now(): return datetime.now(timezone.utc).isoformat()
def uid(): return uuid.uuid4().hex
def sha(value): return hashlib.sha256(value.encode('utf-8') if isinstance(value, str) else value).hexdigest()
def dumps(value): return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False)
def digest(value): return sha(dumps(value))
def text(path): return path.read_bytes().decode('utf-8')

def markdown_lines(source):
    # markdown-it counts CR, LF and CRLF as line breaks, not other Unicode whitespace.
    return re.findall(r'[^\r\n]*(?:\r\n|\r|\n)|[^\r\n]+$', source)
@lru_cache(maxsize=1)
def traditional_converter():
    from opencc import OpenCC
    return OpenCC('s2tw')


def check_language(value):
    """Reject simplified prose without silently rewriting names or quoted product terms."""
    if isinstance(value, dict):
        for item in value.values():
            check_language(item)
    elif isinstance(value, list):
        for item in value:
            check_language(item)
    elif isinstance(value, str):
        for character in value:
            if character.isascii() or not unicodedata.category(character).startswith('L'):
                continue
            name = unicodedata.name(character, '')
            check(name.startswith(('LATIN ', 'CJK ', 'BOPOMOFO ', 'IDEOGRAPHIC ')),
                  'Use Traditional Chinese or English for project prose.')
        if not re.search(r'[\u3400-\u9fff]', value):
            return
        converted = traditional_converter().convert(value)
        # These traditional variants are accepted in Taiwan; preserve the author's choice.
        variants = str.maketrans({'臺':'台', '裏':'裡', '着':'著'})
        check(converted.translate(variants) == value.translate(variants),
              'Use Traditional Chinese or English. Edit the note before saving.')


def display_prose(value):
    # Legacy approved answers remain on disk; only translate Chinese script for display.
    if not isinstance(value,str):
        return value
    try:
        check_language(value)
        return value
    except Invalid:
        converted = traditional_converter().convert(value)
        try:
            check_language(converted)
        except Invalid:
            return '[Historical text requires a Traditional Chinese or English edit.]'
        return converted


def packet_notes(packet):
    # Historical receipts are read-only and can still verify answers created before notes.
    return packet.get('note_turns', packet.get('raw_turns', []))


def pairs(items):
    result = {}
    for key, value in items:
        if key in result: raise Invalid(f'duplicate JSON key: {key}')
        result[key] = value
    return result

def loads(value):
    try: return json.loads(value, object_pairs_hook=pairs, parse_constant=lambda x: (_ for _ in ()).throw(Invalid(f'nonfinite JSON: {x}')))
    except json.JSONDecodeError as error: raise Invalid(f'JSON line {error.lineno}: {error.msg}') from error

def readjson(path): return loads(text(path))
def check(condition, message):
    if not condition: raise Invalid(message)

def exact(obj, required, optional=()):
    check(isinstance(obj, dict), 'expected JSON object')
    check(not (set(required)-obj.keys()), f'missing keys: {set(required)-obj.keys()}')
    check(not (obj.keys()-set(required)-set(optional)), f'unknown keys: {obj.keys()-set(required)-set(optional)}')

def safe(root, relative):
    candidate = (root / relative).resolve()
    check(candidate.is_relative_to(root.resolve()), f'path outside project: {relative}')
    return candidate

def atomic(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix='.startup101-', dir=path.parent)
    try:
        with os.fdopen(fd, 'w', encoding='utf-8', newline='\n') as stream:
            stream.write(value); stream.flush(); os.fsync(stream.fileno())
        os.replace(name, path)
    finally:
        if os.path.exists(name): os.unlink(name)

def putjson(path, value): atomic(path, dumps(value)+'\n')

def root_for(explicit):
    if explicit: return Path(explicit).expanduser().resolve()
    start = Path.cwd().resolve()
    for parent in (start, *start.parents):
        if (parent/'.startup101/config.json').exists(): return parent
    return start

@contextlib.contextmanager
def lock(root):
    directory = safe(root, '.startup101'); directory.mkdir(parents=True, exist_ok=True)
    path = safe(root, '.startup101/write.lock')
    try:
        with portalocker.Lock(str(path), mode='a+', timeout=0): yield
    except portalocker.exceptions.LockException as error:
        raise Invalid('project locked by another writer; retry after it exits') from error

PROJECT_KEYS = ('schema_version','project_id','title','catalog_sha256','requirements_sha256','rubric_sha256','revision')
ANSWER_KEYS = ('question_id','revision','status','answer_kind','evaluation_id','answer_sha256','rubric_version','question_requirements_version','scores','claims','source_turns','dependencies','input_sha256','evaluated_at')

def valid_string(value, label):
    check(isinstance(value,str) and bool(value.strip()),f'{label} must be nonempty string')

def valid_id(value,label):
    check(isinstance(value,str) and re.fullmatch(r'[A-Za-z0-9_-]{1,100}',value) is not None,f'{label} invalid identifier')

def valid_hash(value,label):
    check(isinstance(value,str) and re.fullmatch(r'[a-f0-9]{64}',value) is not None,f'{label} must be SHA256 hex')

def extensions(obj):
    if 'extensions' in obj:
        check(isinstance(obj['extensions'],dict) and all(':' in key for key in obj['extensions']),'extensions keys must be namespaced')

def _parse(source):
    """AST recognizes only reserved top-level fenced blocks; prose is preserved on edits."""
    tokens = MarkdownIt('commonmark').parse(source)
    project = None; answers = {}; ranges = {}; project_range = None; pending = None
    transcripts, notes, note_questions = {}, {}, {}
    key_points=[]; key_points_range=None
    lines = markdown_lines(source); first_fence = True
    for token in tokens:
        if token.type == 'fence' and token.level != 0 and token.info.startswith('startup101'):
            raise Invalid(f'line {token.map[0]+1}: reserved block must be top-level')
        if token.level != 0: continue
        if pending and token.type != 'fence':
            raise Invalid(f'line {token.map[0]+1 if token.map else "?"}: text must immediately follow answer metadata')
        if token.type != 'fence': continue
        info = token.info.strip()
        if first_fence:
            check(info == 'startup101-project', 'first top-level fence must be startup101-project'); first_fence=False
        if pending: check(info=='startup101-text',f'line {token.map[0]+1}: text must immediately follow answer metadata')
        if not info.startswith('startup101'): continue
        if info.startswith(('startup101-turn ', 'startup101-note ')):
            parts = info.split()
            is_note = parts[0] == 'startup101-note'
            check(len(parts) >= 3 and (is_note or len(parts) == 3), 'invalid interview record metadata')
            turn_id, checksum = parts[1:3]
            valid_id(turn_id,'interview record id')
            valid_hash(checksum,'interview record checksum')
            for qid in parts[3:]:
                valid_id(qid, 'linked question')
            check(len(set(parts[3:])) == len(parts[3:]), 'duplicate linked question')
            start, end = token.map
            check(end > start + 1 and lines[end-1].rstrip('\r\n') == token.markup,
                  'unclosed transcript fence')
            body = ''.join(lines[start+1:end-1])
            check(body.endswith('\n') and sha(body[:-1]) == checksum, 'transcript checksum mismatch')
            check(turn_id not in transcripts and turn_id not in notes, 'duplicate interview identifier')
            if is_note:
                check_language(body[:-1])
                notes[turn_id] = body[:-1]
                note_questions[turn_id] = parts[3:]
            else:
                transcripts[turn_id] = body[:-1]
            continue
        if info == 'startup101-key-points':
            check(key_points_range is None, 'duplicate key points block')
            key_points=loads(token.content); validate_key_points(key_points); key_points_range=token.map
            check(lines[token.map[1]-1].strip()==token.markup,'unclosed key points fence')
            continue
        check(info in ('startup101-project','startup101-answer','startup101-text'), f'unknown reserved block {info}')
        check(token.map[1] <= len(lines) and re.match(r'^ {0,3}'+re.escape(token.markup[0])+r'{'+str(len(token.markup))+r',}\s*$', lines[token.map[1]-1].rstrip('\n')) is not None, f'line {token.map[0]+1}: unclosed reserved fence')
        if info == 'startup101-project':
            check(project is None and pending is None, 'duplicate/misplaced project block')
            project=loads(token.content); exact(project,PROJECT_KEYS,('extensions','next_question_id','next_question_text')); project_range=token.map
            check(type(project['schema_version']) is int and project['schema_version']==1 and type(project['revision']) is int and project['revision']>=0, 'unsupported schema/revision')
            if 'next_question_id' in project: valid_id(project['next_question_id'],'next_question_id')
            if 'next_question_text' in project:
                check('next_question_id' in project, 'next_question_text requires next_question_id')
                valid_string(project['next_question_text'],'next_question_text')
            valid_id(project['project_id'],'project_id');valid_string(project['title'],'title');extensions(project)
            for field in ('catalog_sha256','requirements_sha256','rubric_sha256'):valid_hash(project[field],field)
        elif info == 'startup101-answer':
            check(project is not None and pending is None, 'orphan answer metadata')
            meta=loads(token.content); exact(meta,ANSWER_KEYS,('extensions',));extensions(meta)
            for field in ('question_id','evaluation_id'):valid_id(meta[field],field)
            for field in ('answer_sha256','input_sha256'):valid_hash(meta[field],field)
            for field in ('rubric_version','question_requirements_version','evaluated_at'):valid_string(meta[field],field)
            check(isinstance(meta['source_turns'],list) and all(isinstance(x,str) and x for x in meta['source_turns']),'invalid source_turns')
            pending=(meta,token.map)
        else:
            check(pending is not None, 'orphan answer text')
            meta,start=pending; qid=meta['question_id']; check(isinstance(qid,str) and qid not in answers,'duplicate/invalid question id')
            check(meta['status']=='accepted' and meta['answer_kind'] in KINDS,'invalid answer status/kind')
            check(type(meta['revision']) is int and meta['revision']>0,'invalid answer revision')
            check(isinstance(meta['dependencies'],list) and isinstance(meta['claims'],list) and isinstance(meta['source_turns'],list),'invalid answer collections')
            validate_scores(meta['scores'])
            for dep in meta['dependencies']: validate_dependency(dep)
            for claim in meta['claims']: validate_claim(claim)
            answers[qid]={'metadata':meta,'text':token.content[:-1] if token.content.endswith('\n') else token.content}
            ranges[qid]=(start[0],token.map[1]); pending=None
    check(project is not None and pending is None,'missing project block or answer text')
    return {'project':project,'answers':answers,'ranges':ranges,'project_range':project_range,'transcripts':transcripts,'notes':notes,'note_questions':note_questions,'key_points':key_points,'key_points_range':key_points_range,'source':source}

def parse(source):
    try:
        return _parse(source)
    except Invalid as error:
        if 'line ' in str(error): raise
        # The exact failing metadata is identified independently for actionable diagnostics.
        for token in MarkdownIt('commonmark').parse(source):
            if token.type=='fence' and token.info in ('startup101-project','startup101-answer'):
                try:
                    data=loads(token.content)
                    if token.info=='startup101-project':
                        exact(data,PROJECT_KEYS,('extensions','next_question_id','next_question_text'));valid_id(data['project_id'],'project_id');valid_string(data['title'],'title')
                        for field in ('catalog_sha256','requirements_sha256','rubric_sha256'):valid_hash(data[field],field)
                    else:
                        exact(data,ANSWER_KEYS,('extensions',))
                        for field in ('question_id','evaluation_id'):valid_id(data[field],field)
                        for field in ('answer_sha256','input_sha256'):valid_hash(data[field],field)
                        for field in ('rubric_version','question_requirements_version','evaluated_at'):valid_string(data[field],field)
                        validate_scores(data['scores'])
                        for dep in data['dependencies']:validate_dependency(dep)
                    extensions(data)
                except (Invalid,TypeError,KeyError) as detail:
                    raise Invalid(f'line {token.map[0]+1}: {detail}') from error
        raise Invalid('line 1 (document structure): '+str(error)) from error

def fence(kind, value):
    longest=max((len(x) for x in re.findall(r'`+',value)),default=0)
    mark='`'*max(3,longest+1)
    return f'{mark}{kind}\n{value}\n{mark}\n'

def validate_scores(scores):
    exact(scores,DIMENSIONS)
    check(all(type(v) is int and 0<=v<=2 for v in scores.values()),'scores must be integers 0..2')

def validate_dependency(dep):
    exact(dep,('question_id','revision','answer_sha256'))
    valid_id(dep['question_id'],'dependency question_id');valid_hash(dep['answer_sha256'],'dependency answer_sha256')
    check(type(dep['revision']) is int and dep['revision']>0,'dependency revision must be positive integer')

def validate_claim(claim):
    exact(claim,('text','evidence_status','source_refs'))
    check(isinstance(claim['text'],str) and claim['text'].strip() and claim['evidence_status'] in EVIDENCE and isinstance(claim['source_refs'],list) and all(isinstance(x,str) and x for x in claim['source_refs']),'invalid claim')

class Project:
    def __init__(self,root): self.root=root.resolve()
    def path(self,name): return safe(self.root,name)
    def load(self, optional=False):
        config=readjson(self.path('.startup101/config.json'))
        check(config['schema_version']==1,'unsupported config')
        self.docpath=self.path(config['document']); self.doc=parse(text(self.docpath)); self.config=config
        self.catalog=readjson(self.path('.startup101/catalog.json'))
        check(sha(self.path('.startup101/catalog.json').read_bytes())==self.doc['project']['catalog_sha256'],'catalog checksum mismatch')
        self.questions={q['id']:q for q in self.catalog['questions']}
        check(len(self.questions)==len(self.catalog['questions']),'duplicate catalog id')
        check(len(self.questions)==self.catalog['questionCount']+self.catalog['cautionCount'],'catalog count mismatch')
        check(sum(not q['cautionOnly'] for q in self.questions.values())==self.catalog['questionCount'],'catalog eligible count mismatch')
        check(set(self.doc['answers'])<=set(self.questions),'unknown question id')
        for linked in self.doc['note_questions'].values():
            for qid in linked:
                self.question(qid)
        project = self.doc['project']
        if 'next_question_id' in project:
            question = self.question(project['next_question_id'])
            check(project.get('next_question_text', question['question']) == question['question'],
                  'next_question_text does not match the pinned catalog')
        self.requirements=None; self.rubric=None
        for name in ('requirements','rubric'):
            path=self.path(f'.startup101/{name}.json')
            if path.exists() and sha(path.read_bytes())==self.doc['project'][name+'_sha256']:
                setattr(self,name,readjson(path))
            elif not optional: raise Invalid(f'missing or modified pinned {name}')
        return self
    def statuses(self):
        states={}; answers=self.doc['answers']
        for qid,answer in answers.items():
            meta=answer['metadata']; state='accepted'
            if sha(answer['text'])!=meta['answer_sha256']: state='unreviewed'
            else:
                for dep in meta['dependencies']:
                    other=answers.get(dep['question_id'])
                    if not other or other['metadata']['revision']!=dep['revision'] or sha(other['text'])!=dep['answer_sha256']: state='needs_review'
                if state=='accepted':
                    receipt=self.path('.startup101/receipts/'+meta['evaluation_id']+'.json')
                    if not self.rubric or not self.requirements or not receipt.exists(): state='unverifiable'
                    else:
                        r=readjson(receipt)
                        if r.get('metadata')!=meta or r.get('answer_text')!=answer['text']:
                            state='unverifiable'
                        else:
                            for turn in packet_notes(r.get('packet',{})):
                                if 'note_sha256' in turn:
                                    body = self.doc['notes'].get(turn['turn_id'])
                                    checksum = turn['note_sha256']
                                elif 'capture_sha256' in turn:
                                    body = self.doc['transcripts'].get(turn['turn_id'])
                                    checksum = turn['capture_sha256']
                                else:
                                    continue  # Legacy inline receipt
                                if body is None or sha(body) != checksum:
                                    state = 'unverifiable'
                                    break
            states[qid]=state
        changed=True
        while changed:
            changed=False
            for qid,answer in answers.items():
                if states[qid] in ('unreviewed','needs_review'): continue
                if any(states.get(dep['question_id'])!='accepted' for dep in answer['metadata']['dependencies']):
                    states[qid]='needs_review';changed=True
        return states
    def marked_next(self, statuses):
        qid = self.doc['project'].get('next_question_id')
        question = self.questions.get(qid)
        if question and not question['cautionOnly'] and statuses.get(qid) != 'accepted':
            return qid
        return None

    def summary(self):
        # Legacy session packets may contain full original messages. Do not print them.
        drafts = {qid: {key: record[key] for key in ('state', 'review_policy_lock') if key in record}
                  | {'turns': [{'turn_id': item['turn_id']} for item in record['turns']]}
                  for qid, record in self.session().get('drafts',{}).items()}
        statuses = self.statuses()
        return {'project':{**self.doc['project'], 'title':display_prose(self.doc['project']['title'])},'next_question_id':self.marked_next(statuses),'statuses':statuses,'notes':{key:sha(value) for key,value in self.doc['notes'].items()},'pending_transaction':self.path('.startup101/pending.json').exists(),'question_count':self.catalog['questionCount'],'caution_count':self.catalog['cautionCount'],'drafts':drafts,'sidecars':sidecar_summary(self)}
    def session(self):
        path=self.path('.startup101/session.json'); return readjson(path) if path.exists() else {'drafts':{}}
    def event(self,event):
        path=self.path('.startup101/events.jsonl'); existing=text(path) if path.exists() else ''
        if existing and not existing.endswith('\n'): raise Invalid('incomplete event tail; recover first')
        atomic(path,existing+dumps(event)+'\n')
    def question(self,qid):
        check(qid in self.questions and not self.questions[qid]['cautionOnly'],'unknown question or caution-only item')
        return self.questions[qid]
    def requirement(self,qid):
        check(self.requirements is not None,'missing requirements')
        found=[x for x in self.requirements['questions'] if x['question_id']==qid]
        check(len(found)==1 and found[0].get('required_parts'),'missing question requirements')
        return found[0]

def complete_init(p,plan):
    allowed={'.startup101/catalog.json','.startup101/requirements.json','.startup101/rubric.json','startup101.md','.startup101/config.json','.startup101/session.json'}
    check(set(plan['files'])==allowed,'invalid pending init file set')
    for name,value in plan['files'].items():
        target=p.path(name)
        if target.exists(): check(text(target)==value,f'partial init conflict: {name}; preserve and reconcile manually')
    for name,value in plan['files'].items():
        target=p.path(name)
        if not target.exists():atomic(target,value)
    p.path('.startup101/init-pending.json').unlink()
    return p.load().summary()

def init_project(root,title):
    check_language(title)
    root.mkdir(parents=True,exist_ok=True); p=Project(root)
    with lock(root):
        pending=p.path('.startup101/init-pending.json')
        if pending.exists():return complete_init(p,readjson(pending))
        check(not p.path('.startup101/config.json').exists() and not p.path('startup101.md').exists(),'project/document exists; inspect instead')
        pinned={};files={}
        for name in ('catalog','requirements','rubric'):
            source=ASSETS/(name+'.json');check(source.exists(),f'bundle missing {name}')
            value=source.read_bytes();loads(value.decode('utf-8'))
            files['.startup101/'+name+'.json']=value.decode('utf-8');pinned[name+'_sha256']=sha(value)
        meta={'schema_version':1,'project_id':uid(),'title':title,'revision':0,**pinned}
        files['startup101.md']='# '+title.replace('\n',' ')+'\n\n'+fence('startup101-project',dumps(meta))
        files['.startup101/config.json']=dumps({'schema_version':1,'document':'startup101.md','output':'startup101.html'})+'\n'
        files['.startup101/session.json']=dumps({'drafts':{}})+'\n'
        plan={'files':files};putjson(pending,plan)
        return complete_init(p,plan)

def note(p, turn_id, body, expected, questions=()):
    valid_id(turn_id, 'turn_id')
    valid_string(body, 'edited interview note')
    check_language(body)
    p.load()
    check(not p.path('.startup101/pending.json').exists(), 'recover pending transaction first')
    question_ids = list(dict.fromkeys(questions))
    for qid in question_ids:
        p.question(qid)
    project = dict(p.doc['project'])
    notes = p.doc['notes']
    result = {'turn_id': turn_id, 'sha256': sha(body), 'document': p.config['document']}
    if turn_id in notes:
        check(notes[turn_id] == body and p.doc['note_questions'][turn_id] == question_ids,
              'note identifier already used with different content or question links')
        return dict(result, status='already_noted', revision=project['revision'])
    check(turn_id not in p.doc['transcripts'], 'identifier belongs to historical transcript')
    check(project['revision'] == expected, 'document revision conflict')
    project['revision'] += 1
    lines = markdown_lines(p.doc['source'])
    start, end = p.doc['project_range']
    lines[start:end] = [fence('startup101-project', dumps(project))]
    heading = '\n## 創辦人訪談筆記\n' if not notes else ''
    info = ' '.join(['startup101-note', turn_id, sha(body), *question_ids])
    source = ''.join(lines) + heading + '\n' + fence(info, body)
    check(parse(source)['notes'].get(turn_id) == body, 'note failed pre-write comparison')
    atomic(p.docpath, source)
    check(p.load().doc['notes'].get(turn_id) == body, 'note failed readback')
    return dict(result, status='noted', revision=project['revision'])


def source_note(p, reference):
    check('note_sha256' in reference, 'Replace historical raw drafts with edited interview notes before evaluation.')
    full = p.doc['notes'].get(reference['turn_id'])
    check(full is not None and sha(full) == reference['note_sha256'], 'edited note changed or missing')
    start, end = reference['span']
    check(0 <= start < end <= len(full), 'invalid note span')
    return {**reference, 'text': full, 'excerpt': full[start:end]}


def draft(p,qid,excerpt=None,sources=None,turn_id=None):
    p.load(); p.question(qid)
    valid_id(turn_id, 'turn_id')
    body = p.doc['notes'].get(turn_id)
    check(body is not None, 'save the edited note in Markdown before drafting')
    excerpt = body if excerpt is None else excerpt
    valid_string(excerpt, 'note excerpt')
    start = body.find(excerpt)
    check(start >= 0, 'draft excerpt must match the edited note')
    reference = {'turn_id': turn_id, 'note_sha256': sha(body), 'span': [start, start+len(excerpt)]}
    check(not p.path('.startup101/pending.json').exists(),'recover pending transaction first')
    session=p.session()
    record=session['drafts'].setdefault(qid,{'turns':[]})
    if any('note_sha256' not in turn for turn in record['turns']):
        # Editing replaces the old active draft. Do not carry legacy text or sources into new packets.
        record.clear()
        record['turns'] = []
    if sources is not None:
        check(isinstance(sources,list),'sources must be an array')
        for source in sources:
            exact(source,('id','text','checked'),('url',))
            check(isinstance(source['id'],str) and isinstance(source['text'],str) and type(source['checked']) is bool,'invalid source')
            check_language(source['text'])
            if 'url' in source: check(isinstance(source['url'],str) and source['url'].startswith(('https://','http://')),'source URL must use http/https')
        record['sources']=sources
    existing = next((item for item in record['turns'] if item['turn_id'] == turn_id), None)
    if existing is not None:
        check(existing.get('span') == reference['span'], 'note already linked with different excerpt')
        if sources is not None:
            record.pop('packet',None)
            putjson(p.path('.startup101/session.json'),session)
        return source_note(p,existing)
    turn = {**reference, 'at':now(), 'question_id':qid}
    p.event({'type':'user_turn',**turn});record['turns'].append(turn)
    record.pop('packet',None);putjson(p.path('.startup101/session.json'),session)
    return turn


def evaluation_input(p,qid,kind,candidate=None,confirmed=False,dependencies=None,review_policy='single'):
    check(review_policy in ('single','independent'),'invalid review policy')
    p.load();q=p.question(qid); req=p.requirement(qid)
    check(kind in req['allowed_answer_kinds'],'answer kind not allowed for question')
    session=p.session(); record=session['drafts'].get(qid);check(record and record['turns'],'draft a user turn first')
    policy_lock=record.get('review_policy_lock')
    if policy_lock and policy_lock['turn_ids']==[turn['turn_id'] for turn in record['turns']]:
        check(review_policy==policy_lock['policy'] or (policy_lock['policy']=='single' and review_policy=='independent'),'review policy cannot change from independent to single for the same user turn')
        policy_lock['policy']=review_policy
    old_packet=record.get('packet')
    if old_packet and record.get('last_evaluation',{}).get('input_sha256')==old_packet['input_sha256']:
        check(review_policy==old_packet.get('review_policy','single') or (old_packet.get('review_policy','single')=='single' and review_policy=='independent'),'review policy cannot change from independent to single for the same user turn')
        record['review_policy_lock']={'turn_ids':[turn['turn_id'] for turn in record['turns']],'policy':review_policy}
    resolved_turns = [source_note(p, turn) for turn in record['turns']]
    raw = resolved_turns[-1].get('excerpt', resolved_turns[-1]['text'])
    check(candidate is None or candidate==raw or confirmed,'rewritten/combined candidate requires user confirmation')
    value=raw if candidate is None else candidate
    check(value.strip(),'empty candidate')
    check_language(value)
    deps=[];states=p.statuses()
    for depid in dependencies or []:
        check(depid!=qid and states.get(depid)=='accepted','dependency must be another current accepted answer')
        answer=p.doc['answers'][depid]
        check_language(answer['text'])
        deps.append({'question_id':depid,'revision':answer['metadata']['revision'],'answer_sha256':sha(answer['text'])})
    packet={'review_policy':review_policy,'question_id':qid,'question':q,'requirements':req,'question_requirements_version':p.requirements['version'],'answer_kind':kind,'note_turns':resolved_turns,'candidate_text':value,'candidate_sha256':sha(value),'rubric':p.rubric,'rubric_version':p.rubric['version'],'related_answers':[{'dependency':dep,'text':p.doc['answers'][dep['question_id']]['text']} for dep in deps],'dependencies':deps,'document_revision':p.doc['project']['revision'],'document_sha256':sha(p.doc['source']),'project_id':p.doc['project']['project_id'],'catalog_sha256':p.doc['project']['catalog_sha256'],'confirmed_rewrite':confirmed,'sources':record.get('sources',[])}
    packet['input_sha256']=digest(packet);record['packet']=packet;putjson(p.path('.startup101/session.json'),session)
    return packet

RESULT_KEYS=('evaluation_id','question_id','input_sha256','candidate_sha256','rubric_version','question_requirements_version','verdict','scores','score_reasons','claims','blocking_issues','next_question','what_changes_verdict','evaluated_at','dependencies','evaluator','requirements_met')
def validate_result(result,packet):
    exact(result,RESULT_KEYS)
    check(re.fullmatch(r'[A-Za-z0-9_-]{1,100}',result['evaluation_id']) is not None,'invalid evaluation id')
    for field in ('question_id','input_sha256','candidate_sha256','rubric_version','question_requirements_version','dependencies'):
        check(result[field]==packet[field],f'evaluation {field} mismatch')
    check(result['verdict'] in ('pass','revise','needs_context'),'invalid verdict')
    if result['verdict']=='needs_context':
        check(result['scores'] is None and result['score_reasons'] is None,'needs_context must use null scores and score_reasons; do not invent low scores')
    else:
        validate_scores(result['scores']);exact(result['score_reasons'],DIMENSIONS)
        check(all(isinstance(x,str) and x.strip() for x in result['score_reasons'].values()),'score reasons required')
    check(isinstance(result['claims'],list) and isinstance(result['blocking_issues'],list),'invalid evaluation collections')
    for c in result['claims']:
        validate_claim(c)
        refs={t['turn_id'] for t in packet_notes(packet)}|{x['id'] for x in packet['sources']}
        check(all(isinstance(x,str) and x in refs for x in c['source_refs']),'claim references absent source')
        if c['evidence_status'] in ('reported','source_checked'): check(bool(c['source_refs']),'evidence claim needs source reference')
        if c['evidence_status']=='source_checked':
            checked={x['id'] for x in packet['sources'] if x['checked'] and x['text'].strip()}
            check(bool(set(c['source_refs'])&checked),'source_checked needs actually checked source excerpt')
    for dep in result['dependencies']:validate_dependency(dep)
    check(result['next_question'] is None or isinstance(result['next_question'],str),'next_question must be null or one string')
    check(isinstance(result['evaluator'],str) and result['evaluator'].strip(),'evaluator description required')
    check(isinstance(result['evaluated_at'],str) and result['evaluated_at'].strip(),'evaluated_at required')
    required={x['id'] for x in packet['requirements']['required_parts'] if x['required'] and packet['answer_kind'] in x['applies_to']}
    check(isinstance(result['requirements_met'],list) and all(isinstance(x,str) for x in result['requirements_met']),'requirements_met must be string array')
    check(set(result['requirements_met'])<={x['id'] for x in packet['requirements']['required_parts']},'unknown requirement id')
    if result['verdict']=='pass':
        check(all(v==2 for v in result['scores'].values()) and not result['blocking_issues'] and result['next_question'] is None,'pass with nonpassing score/blocker/followup')
        check(required<=set(result['requirements_met']),'required parts unmet')
        check(bool(result['claims']),'pass requires classified claims')
        check(all(c['evidence_status']!='contradicted' for c in result['claims']),'contradicted claim cannot pass')
        if packet['answer_kind']=='fact':
            check(any(c['evidence_status'] in ('reported','source_checked') and c['source_refs'] for c in result['claims']),'fact pass requires a sourced reported/source_checked claim; hypotheses alone are insufficient')


def record_evaluation(p,result):
    check_language(result)
    p.load(); qid=result['question_id'];session=p.session();record=session['drafts'].get(qid,{})
    packet=record.get('packet');check(packet is not None,'missing evaluation packet')
    check(packet['input_sha256']==digest({k:v for k,v in packet.items() if k!='input_sha256'}),'evaluation packet altered')
    validate_result(result,packet)
    check('note_turns' in packet and 'raw_turns' not in packet,'Create a new evaluation from edited notes before recording.')
    history=p.path('.startup101/evaluations/'+result['evaluation_id']+'.json')
    if history.exists():check(readjson(history)['evaluation']==result,'evaluation id reused')
    else:putjson(history,{'evaluation':result,'packet':packet})
    record['review_policy_lock']={'turn_ids':[turn['turn_id'] for turn in packet_notes(packet)],'policy':packet.get('review_policy','single')}
    record['last_evaluation']=result;putjson(p.path('.startup101/session.json'),session)
    p.event({'type':'evaluation','evaluation_id':result['evaluation_id'],'question_id':qid,'verdict':result['verdict'],'at':now()})
    return {'status':'evaluation_recorded','verdict':result['verdict']}

REVIEW_KEYS=('review_id','question_id','input_sha256','evaluation_ids','resolution','resolution_reasons','reviewed_at')
DECISION_KEYS=('assessment_id','question_id','input_sha256','evaluation_id','decision','status','evidence_refs','missing_information','what_changes_verdict','assessor','assessed_at')

def string_list(value,label,nonempty=False):
    check(isinstance(value,list) and (bool(value) or not nonempty),label+' must be a string array')
    for item in value:valid_string(item,label)

def recorded_result(p,evaluation_id):
    valid_id(evaluation_id,'evaluation_id')
    path=p.path('.startup101/evaluations/'+evaluation_id+'.json')
    check(path.exists(),'evaluation must actually be recorded first')
    record=readjson(path);packet=record['packet']
    check(packet['input_sha256']==digest({k:v for k,v in packet.items() if k!='input_sha256'}),'recorded packet altered')
    validate_result(record['evaluation'],packet)
    check(record['evaluation']['evaluation_id']==evaluation_id,'recorded evaluation identity mismatch')
    return record

def append_sidecar(p,kind,identity,payload,extra):
    valid_id(identity,kind+' id');path=p.path('.startup101/'+kind+'/'+identity+'.json')
    if path.exists():
        old=readjson(path);check(old['payload']==payload,kind+' id reused with different payload');return old
    record={'payload':payload,'recorded_at':now(),**extra};putjson(path,record);return record

def sidecar_records(p,kind):
    directory=p.path('.startup101/'+kind)
    records=[readjson(path) for path in sorted(directory.glob('*.json'))] if directory.exists() else []
    return sorted(records,key=lambda item:item['recorded_at'])

def validate_review(p,review,packet):
    exact(review,REVIEW_KEYS)
    for key in ('review_id','question_id'):valid_id(review[key],key)
    valid_hash(review['input_sha256'],'input_sha256');valid_string(review['reviewed_at'],'reviewed_at')
    check(review['question_id']==packet['question_id'] and review['input_sha256']==packet['input_sha256'],'review packet mismatch')
    check(review['resolution'] in ('agreed','unresolved','unavailable'),'invalid review resolution')
    string_list(review['resolution_reasons'],'resolution_reasons',True)
    ids=review['evaluation_ids'];string_list(ids,'evaluation_ids')
    check(len(ids)<=2 and len(set(ids))==len(ids),'review requires at most two distinct evaluation ids')
    results=[]
    for eid in ids:
        stored=recorded_result(p,eid);check(stored['packet']==packet,'review evaluations must use the same input packet');results.append(stored['evaluation'])
    identities=[' '.join(result['evaluator'].split()).casefold() for result in results]
    check(len(set(identities))==len(identities),'review requires different evaluator identities')
    if review['resolution']=='agreed':
        check(len(results)==2 and all(result['verdict']=='pass' for result in results),'agreed review requires two recorded passes; never average scores')
    return results

def record_review(p,review):
    check_language(review)
    p.load();exact(review,REVIEW_KEYS);p.question(review['question_id'])
    packet=p.session()['drafts'].get(review['question_id'],{}).get('packet');check(packet is not None,'missing current review packet')
    check(packet['input_sha256']==digest({k:v for k,v in packet.items() if k!='input_sha256'}),'evaluation packet altered')
    check(packet.get('review_policy','single')=='independent','independent review policy must be selected before evaluation')
    check('note_turns' in packet and 'raw_turns' not in packet,'Create a new evaluation from edited notes before review.')
    results=validate_review(p,review,packet)
    stored=append_sidecar(p,'reviews',review['review_id'],review,{'packet':packet,'evaluation_hashes':{result['evaluation_id']:digest(result) for result in results}})
    return {'status':'review_recorded','review':stored,'independence_limit':'Distinct recorded evaluator identities are checked; actual host or agent independence cannot be authenticated by this runtime.'}

def acceptance_review(p,packet,result):
    if packet.get('review_policy','single')=='single':return None
    check(packet.get('review_policy')=='independent','unknown packet review policy')
    reviews=[item for item in sidecar_records(p,'reviews') if item['payload']['input_sha256']==packet['input_sha256']]
    check(bool(reviews),'independent policy requires recorded review before acceptance')
    latest=reviews[-1];review=latest['payload'];results=validate_review(p,review,packet)
    check(latest['packet']==packet,'review packet altered')
    check(latest['evaluation_hashes']=={value['evaluation_id']:digest(value) for value in results},'review evaluation history changed')
    check(review['resolution']=='agreed' and result['evaluation_id'] in review['evaluation_ids'],'unresolved or unavailable independent review cannot accept')
    check(any(value==result for value in results),'acceptance result differs from recorded review')
    return latest

def record_decision(p,assessment):
    check_language(assessment)
    p.load();exact(assessment,DECISION_KEYS)
    for key in ('assessment_id','question_id'):valid_id(assessment[key],key)
    for key in ('decision','what_changes_verdict','assessor','assessed_at'):valid_string(assessment[key],key)
    valid_hash(assessment['input_sha256'],'input_sha256');p.question(assessment['question_id'])
    check(assessment['status'] in ('ready','not_ready','unknown'),'invalid decision readiness status')
    string_list(assessment['evidence_refs'],'evidence_refs');string_list(assessment['missing_information'],'missing_information')
    stored=recorded_result(p,assessment['evaluation_id']);packet=stored['packet']
    check(packet['question_id']==assessment['question_id'] and packet['input_sha256']==assessment['input_sha256'],'decision assessment packet mismatch')
    check('note_turns' in packet and 'raw_turns' not in packet,'Create a new evaluation from edited notes before recording a decision.')
    refs={turn['turn_id'] for turn in packet_notes(packet)}|{source['id'] for source in packet['sources']}
    check(set(assessment['evidence_refs'])<=refs,'decision evidence references absent packet source')
    context={'project_id':packet['project_id'],'document_revision':packet['document_revision'],'document_sha256':packet['document_sha256']}
    receipt_path=p.path('.startup101/receipts/'+assessment['evaluation_id']+'.json')
    if receipt_path.exists():
        receipt=readjson(receipt_path)
        if receipt.get('packet')==packet and receipt.get('evaluation')==stored['evaluation'] and receipt.get('document_sha256')==sha(p.doc['source']):
            context={'project_id':packet['project_id'],'document_revision':receipt['document_revision'],'document_sha256':receipt['document_sha256']}
    record=append_sidecar(p,'decisions',assessment['assessment_id'],assessment,{'packet':packet,'evaluation_sha256':digest(stored['evaluation']),'context':context})
    return {'status':'decision_recorded','assessment':record,'stale':decision_stale(p,record)}

def decision_stale(p,record):
    # A byte-identical Markdown file can lose verifiable provenance: receipts,
    # pinned rules, or a referenced evaluation may disappear independently.
    packet=record['packet'];qid=record['payload']['question_id']
    if not p.rubric or not p.requirements:return True
    try:
        evaluation=recorded_result(p,record['payload']['evaluation_id'])
        if evaluation['packet']!=packet or digest(evaluation['evaluation'])!=record['evaluation_sha256']:return True
        states=p.statuses()
    except (Invalid,OSError,KeyError,TypeError,UnicodeError):return True
    own=p.doc['answers'].get(qid)
    if own and own['metadata']['input_sha256']==packet['input_sha256'] and states.get(qid)!='accepted':return True
    for dependency in packet['dependencies']:
        answer=p.doc['answers'].get(dependency['question_id'])
        if not answer or states.get(dependency['question_id'])!='accepted' or answer['metadata']['revision']!=dependency['revision'] or sha(answer['text'])!=dependency['answer_sha256']:return True
    pending=[dependency['question_id'] for dependency in packet['dependencies']]
    if own and own['metadata']['input_sha256']==packet['input_sha256']:pending.append(qid)
    visited=set()
    while pending:
        current_id=pending.pop()
        if current_id in visited:continue
        visited.add(current_id);answer=p.doc['answers'].get(current_id)
        if not answer or states.get(current_id)!='accepted':return True
        try:
            receipt=readjson(p.path('.startup101/receipts/'+answer['metadata']['evaluation_id']+'.json'))
            original=recorded_result(p,answer['metadata']['evaluation_id'])
            if receipt.get('packet')!=original['packet'] or receipt.get('evaluation')!=original['evaluation']:return True
            if current_id==qid and record['context']['document_sha256']!=packet['document_sha256'] and receipt.get('document_sha256')!=record['context']['document_sha256']:return True
        except (Invalid,OSError,KeyError,TypeError,UnicodeError):return True
        pending.extend(dependency['question_id'] for dependency in answer['metadata']['dependencies'])
    draft_record=p.session()['drafts'].get(record['payload']['question_id'])
    current=(draft_record or {}).get('packet')
    changed_turns=bool(draft_record and [turn['turn_id'] for turn in draft_record.get('turns',[])]!=[turn['turn_id'] for turn in packet_notes(record['packet'])])
    return changed_turns or record['context']['document_sha256']!=sha(p.doc['source']) or bool(current and current['input_sha256']!=record['payload']['input_sha256'])

def sidecar_summary(p):
    result={}
    for kind in ('reviews','decisions'):
        records=sidecar_records(p,kind);latest={}
        for record in records:
            payload=record['payload'];qid=payload['question_id']
            if 'note_turns' not in record.get('packet', {}):
                # Older feedback may contain quotations; expose only its status.
                keys = ('question_id','input_sha256','review_id','resolution','assessment_id','status')
                payload = {key:payload[key] for key in keys if key in payload}
            latest[qid]={'payload':payload,'recorded_at':record['recorded_at']}
            if kind=='decisions':latest[qid]['stale']=decision_stale(p,record)
            else:latest[qid]['current_packet']=p.session()['drafts'].get(qid,{}).get('packet',{}).get('input_sha256')==payload['input_sha256']
        result[kind]={'count':len(records),'latest_by_question':latest}
    return result

def set_next(p, qid, expected):
    p.load()
    check(not p.path('.startup101/pending.json').exists(), 'recover pending transaction first')
    project = dict(p.doc['project'])
    check(project['revision'] == expected, 'document revision conflict')
    p.question(qid)
    check(p.statuses().get(qid) != 'accepted', 'next question is already accepted')
    title = p.questions[qid]['question']
    if project.get('next_question_id') != qid or project.get('next_question_text') != title:
        project['next_question_id'] = qid
        project['next_question_text'] = title
        project['revision'] += 1
        start, end = p.doc['project_range']
        lines = markdown_lines(p.doc['source'])
        lines[start:end] = [fence('startup101-project', dumps(project))]
        atomic(p.docpath, ''.join(lines))
    return {'status':'next_marked','revision':project['revision'],'next_question_id':qid,
            'question':p.questions[qid]['question']}

def session_action(p,qid,action,reason):
    check_language(reason)
    p.load();p.question(qid);check(action in ('defer','skip','resume'),'invalid session action')
    valid_string(reason,'reason');check(not p.path('.startup101/pending.json').exists(),'recover pending transaction first')
    session=p.session();record=session['drafts'].setdefault(qid,{'turns':[]})
    event={'type':'session_action','question_id':qid,'action':action,'reason':reason,'at':now()}
    p.event(event);record['state']='active' if action=='resume' else action;record['reason']=reason
    putjson(p.path('.startup101/session.json'),session)
    return {'status':'session_updated',**event}

def accept(p,result,expected):
    p.load(); receiptpath=p.path('.startup101/receipts/'+str(result.get('evaluation_id','invalid'))+'.json')
    check(re.fullmatch(r'[A-Za-z0-9_-]{1,100}',str(result.get('evaluation_id',''))) is not None,'invalid evaluation id')
    if receiptpath.exists():
        receipt=readjson(receiptpath);check(receipt['evaluation']==result,'evaluation id reused with different payload')
        return {'status':'already_committed','revision':receipt['document_revision']}
    check(not p.path('.startup101/pending.json').exists(),'recover pending transaction first')
    check(p.doc['project']['revision']==expected,'document revision conflict')
    qid=result['question_id'];p.question(qid);session=p.session();record=session['drafts'].get(qid,{})
    packet=record.get('packet');check(packet is not None,'missing evaluation packet; run evaluate-input')
    check(packet['document_sha256']==sha(p.doc['source']),'document changed since evaluation packet')
    check(packet['input_sha256']==digest({k:v for k,v in packet.items() if k!='input_sha256'}),'evaluation packet altered')
    validate_result(result,packet);check(result['verdict']=='pass','only pass may be accepted')
    review=acceptance_review(p,packet,result)
    record_evaluation(p,result)
    check(packet['candidate_sha256']==sha(packet['candidate_text']),'candidate hash mismatch')
    for dep in packet['dependencies']:
        a=p.doc['answers'].get(dep['question_id']);check(a and p.statuses().get(dep['question_id'])=='accepted' and a['metadata']['revision']==dep['revision'] and sha(a['text'])==dep['answer_sha256'],'dependency changed')
    old=p.doc['answers'].get(qid);meta={'question_id':qid,'revision':old['metadata']['revision']+1 if old else 1,'status':'accepted','answer_kind':packet['answer_kind'],'evaluation_id':result['evaluation_id'],'answer_sha256':packet['candidate_sha256'],'rubric_version':result['rubric_version'],'question_requirements_version':result['question_requirements_version'],'scores':result['scores'],'claims':result['claims'],'source_turns':[t['turn_id'] for t in packet_notes(packet)],'dependencies':result['dependencies'],'input_sha256':result['input_sha256'],'evaluated_at':result['evaluated_at']}
    project=dict(p.doc['project']);project['revision']+=1
    if project.get('next_question_id') == qid:
        del project['next_question_id']
        project.pop('next_question_text', None)
    block=fence('startup101-answer',dumps(meta))+'\n'+fence('startup101-text',packet['candidate_text'])
    edits=[(*p.doc['project_range'],fence('startup101-project',dumps(project)))]
    if old: edits.append((*p.doc['ranges'][qid],block))
    lines=markdown_lines(p.doc['source'])
    for start,end,replacement in sorted(edits,reverse=True):lines[start:end]=[replacement]
    source=''.join(lines)
    if not old:source+='\n## '+p.questions[qid]['question'].replace('\n',' ')+'\n\n'+block
    parse(source)
    receipt={'transaction_id':uid(),'document_revision':project['revision'],'document_sha256':sha(source),'metadata':meta,'answer_text':packet['candidate_text'],'evaluation':result,'packet':packet,'at':now()}
    if review is not None:receipt['independent_review']=review
    pending={'before_sha256':sha(p.doc['source']),'after_sha256':sha(source),'receipt':receipt}
    putjson(p.path('.startup101/pending.json'),pending)
    atomic(p.docpath,source)
    # From this point the answer is committed, even if ancillary receipt writing fails.
    try:
        finish(p,pending)
    except OSError as error:
        raise Invalid('answer committed; receipt pending recovery: '+str(error)) from error
    return {'status':'committed','revision':project['revision'],'answer_text':packet['candidate_text']}

def finish(p,pending):
    r=pending['receipt'];putjson(p.path('.startup101/receipts/'+r['evaluation']['evaluation_id']+'.json'),r)
    session=p.session();session['drafts'].pop(r['metadata']['question_id'],None);putjson(p.path('.startup101/session.json'),session)
    p.path('.startup101/pending.json').unlink()

def recover(p):
    initpending=p.path('.startup101/init-pending.json')
    if initpending.exists(): return {'status':'initialization_recovered','project':complete_init(p,readjson(initpending))}
    p.load(optional=True);pendingpath=p.path('.startup101/pending.json')
    result={'status':'nothing_pending'}
    if pendingpath.exists():
        pending=readjson(pendingpath);actual=sha(p.doc['source'])
        if actual==pending['after_sha256']:finish(p,pending);result={'status':'committed_recovered'}
        elif actual==pending['before_sha256']:pendingpath.unlink();result={'status':'not_committed_draft_preserved'}
        else:raise Invalid('commit state unknown: document differs from both transaction hashes; preserve files for manual reconciliation')
    events=p.path('.startup101/events.jsonl')
    if events.exists():
        content=text(events);lines=content.splitlines(keepends=True);valid=[]
        for index,line in enumerate(lines):
            try:loads(line)
            except Invalid:
                check(index==len(lines)-1,'corrupt event history before final line')
                atomic(p.path('.startup101/events-tail-'+uid()+'.txt'),line);break
            valid.append(line if line.endswith('\n') else line+'\n')
        atomic(events,''.join(valid))
        session=p.session();known={(qid,t['turn_id']) for qid,d in session['drafts'].items() for t in d['turns']}
        accepted_turns={(qid,t) for qid,a in p.doc['answers'].items() for t in a['metadata']['source_turns']};accepted_at={}
        receipts=p.path('.startup101/receipts')
        if receipts.exists():
            for receipt in receipts.glob('*.json'):
                saved=readjson(receipt);accepted_turns.update((saved['metadata']['question_id'],t) for t in saved['metadata']['source_turns'])
                qid=saved['metadata']['question_id'];accepted_at[qid]=max(accepted_at.get(qid,''),saved['at'])
        for line in valid:
            event=loads(line)
            if event.get('type')=='user_turn' and 'note_sha256' in event and (event['question_id'],event['turn_id']) not in known|accepted_turns:
                known.add((event['question_id'],event['turn_id']))
                turn={k:v for k,v in event.items() if k!='type'};session['drafts'].setdefault(event['question_id'],{'turns':[]})['turns'].append(turn)
        for line in valid:
            event=loads(line)
            if event.get('type')=='session_action' and event['at']>accepted_at.get(event['question_id'],''):
                record=session['drafts'].setdefault(event['question_id'],{'turns':[]})
                record['state']='active' if event['action']=='resume' else event['action'];record['reason']=event['reason']
        putjson(p.path('.startup101/session.json'),session)
    return result

def validate_clusters(clusters,catalog,catalog_sha256):
    """Presentation only: every canonical question remains independently scored."""
    check(isinstance(clusters,dict) and clusters.get('schema_version')==1,'unsupported cluster schema')
    check(clusters.get('source_sha256')==catalog_sha256,'cluster/catalog source mismatch; install a compatible presentation bundle, do not rewrite the pinned catalog')
    questions={q['id']:q for q in catalog['questions']}
    active={qid for qid,q in questions.items() if not q['cautionOnly']}
    caution_ids=set(questions)-active
    cards=clusters.get('cards');cautions=clusters.get('cautions');counts=clusters.get('counts',{})
    check(isinstance(cards,list) and isinstance(cautions,list),'cluster cards/cautions must be lists')
    card_ids=[];assigned=[];other=0
    categories={c['name'] for c in catalog['categories'] if not c.get('cautionOnly')}
    for card in cards:
        check(isinstance(card,dict),'invalid cluster card')
        cid=card.get('id');lead=card.get('lead_question_id');members=card.get('questions')
        check(cid==lead and cid in active,'cluster id must be its canonical lead question')
        check(isinstance(members,list) and members,'empty cluster')
        check(card.get('primary_category') in categories,'unknown primary category')
        primary=[];has_other=False;original_categories=set()
        for member in members:
            check(isinstance(member,dict),'invalid cluster member')
            qid=member.get('question_id');check(qid in active,'cluster contains unknown question or caution')
            q=questions[qid];check(member.get('question')==q['question'],'cluster question wording differs from pinned catalog')
            check(member.get('original_category')==q['category'],'cluster original category differs from pinned catalog')
            side=member.get('side');role=member.get('presentation')
            check(side in ('front','on_the_other_hand'),'unknown cluster side')
            check(role in ('主問題','相近問法，語境仍保留','同一件事的補充檢查','換個角度檢查'),'unknown cluster presentation role')
            if role=='主問題':primary.append(qid);check(side=='front','primary question must be on front')
            check((side=='on_the_other_hand')==(role=='換個角度檢查'),'cluster side/role mismatch')
            has_other|=side=='on_the_other_hand';assigned.append(qid);original_categories.add(q['category'])
        check(primary==[lead],'cluster must have exactly its lead as primary')
        check(set(card.get('categories',[]))==original_categories and card['primary_category'] in original_categories,'cluster categories do not match its members')
        card_ids.append(cid);other+=has_other
    check(len(set(card_ids))==len(card_ids),'duplicate cluster card')
    check(len(assigned)==len(set(assigned)) and set(assigned)==active,'every active question must belong to exactly one cluster')
    attached=[]
    for caution in cautions:
        check(isinstance(caution,dict) and caution.get('question_id') in caution_ids,'unknown cluster caution')
        check(caution.get('question')==questions[caution['question_id']]['question'],'caution wording differs from pinned catalog')
        targets=caution.get('attached_to_ids');check(isinstance(targets,list) and targets and set(targets)<=set(card_ids),'invalid caution attachment')
        attached.append(caution['question_id'])
    check(len(attached)==len(set(attached)) and set(attached)==caution_ids,'every caution must have reminder placement')
    check(counts.get('postits')==len(cards) and counts.get('active_questions')==len(active) and counts.get('cautions')==len(caution_ids) and counts.get('postits_with_other_hand')==other,'cluster count metadata mismatch')
    return clusters

def note_view(p):
    """Only edited Markdown notes are exposed to the canvas."""
    rows = {key:{'id':key, 'text':body, 'source':'note', 'questionIds':list(p.doc['note_questions'][key])}
            for key,body in p.doc['notes'].items()}
    def link(qid, turn):
        row = rows.get(turn['turn_id'])
        if row and turn.get('note_sha256') == sha(row['text']) and qid not in row['questionIds']:
            row['questionIds'].append(qid)
    for qid, record in p.session().get('drafts', {}).items():
        if qid in p.questions:
            for turn in record.get('turns', []):
                link(qid, turn)
    for qid, answer in p.doc['answers'].items():
        path = p.path('.startup101/receipts/' + answer['metadata']['evaluation_id'] + '.json')
        if path.exists():
            receipt = readjson(path)
            if receipt.get('metadata') == answer['metadata']:
                for turn in packet_notes(receipt.get('packet', {})):
                    link(qid, turn)
    return list(rows.values())


def validate_key_points(entries):
    check(isinstance(entries,list),'key points must be an array')
    seen=set()
    for item in entries:
        exact(item,('question_id','role','source_sha256','points'))
        valid_id(item['question_id'],'key points question');valid_hash(item['source_sha256'],'key points source')
        check(item['role'] in ('formal','pending'),'invalid key points role')
        identity=(item['question_id'],item['role'])
        check(identity not in seen,'duplicate key points question/role');seen.add(identity)
        points=item['points']
        check(isinstance(points,list) and 0<=len(points)<=12,'key points require 0–12 items; empty means no existing information to summarize')
        check(all(isinstance(point,str) and point.strip()==point and point and '\n' not in point for point in points),'key points require single-line nonempty text')
        check(len(set(points))==len(points),'duplicate key point')
        for point in points:
            check_language(point)
            if re.search(r'[\u3400-\u9fff]',point):check(len(point)<=30,'Chinese key point exceeds 30 characters; prefer 1–15')
            else:check(len(point.split())<=12 and len(point)<=100,'English key point exceeds 12 words/100 characters')

def key_points_input(p):
    p.load(optional=True)
    entries=[{'question_id':qid,'role':'formal','source_sha256':sha(answer['text']),'text':answer['text']} for qid,answer in p.doc['answers'].items()]
    for qid,item in pending_view(p).items():
        if item.get('text') and item['role']!='history_only':
            entries.append({'question_id':qid,'role':'pending','source_sha256':sha(item['text']),'text':item['text']})
    return {'source_sha256':sha(p.doc['source']),'entries':entries}

def key_points_view(p):
    sources={(item['question_id'],item['role']):item['source_sha256'] for item in key_points_input(p)['entries']}
    result={}
    for item in p.doc['key_points']:
        if sources.get((item['question_id'],item['role']))==item['source_sha256']:
            result.setdefault(item['question_id'],{})[item['role']]={'points':item['points'],'source_sha256':item['source_sha256']}
    return result

def set_key_points(p,payload):
    exact(payload,('source_sha256','entries'));valid_hash(payload['source_sha256'],'document source')
    current=key_points_input(p)
    check(not p.path('.startup101/pending.json').exists(),'recover pending transaction before key points')
    check(current['source_sha256']==payload['source_sha256'],'document changed; reload key points input')
    validate_key_points(payload['entries'])
    sources={(item['question_id'],item['role']):item['source_sha256'] for item in current['entries']}
    for item in payload['entries']:
        check(sources.get((item['question_id'],item['role']))==item['source_sha256'],'key points source changed or unavailable')
    # Merge updates; stale entries are harmless and never projected.
    merged={(item['question_id'],item['role']):item for item in p.doc['key_points']}
    merged.update({(item['question_id'],item['role']):item for item in payload['entries']})
    block='```startup101-key-points\n'+dumps(list(merged.values()))+'\n```\n'
    source=p.doc['source']; span=p.doc['key_points_range']
    if span:
        lines=markdown_lines(source);source=''.join(lines[:span[0]])+block+''.join(lines[span[1]:])
    else:source=source.rstrip('\n')+'\n\n'+block
    parsed=parse(source)
    check(all(parsed[key]==p.doc[key] for key in ('answers','project','notes','transcripts','note_questions')),'key points must not change answers, notes or project metadata')
    atomic(p.docpath,source);p.load(optional=True)
    return {'status':'key_points_saved','entries':len(payload['entries']),'revision':p.doc['project']['revision'],'source_sha256':sha(source)}


def pending_view(p):
    """Resolve current input from Markdown; never use a sidecar as answer text."""
    result={}
    for qid,record in p.session().get('drafts',{}).items():
        if qid not in p.questions or not record.get('turns'):continue
        try:
            turns=[source_note(p,turn) for turn in record['turns']]
        except (Invalid,KeyError,TypeError,ValueError):
            result[qid]={'role':'history_only','text':None,'evaluation':None}
            continue
        text=turns[-1]['excerpt'];packet=record.get('packet');evaluation=None
        role='pending'
        if packet:
            # Rewritten candidates must also exist verbatim in referenced Markdown.
            candidate=packet.get('candidate_text','')
            if candidate and any(candidate==turn['excerpt'] for turn in turns):text=candidate
            elif candidate!=text:role='rewrite_needs_save'
            latest=record.get('last_evaluation')
            current_ids=[turn['turn_id'] for turn in turns]
            packet_ids=[turn['turn_id'] for turn in packet_notes(packet)]
            if (role=='pending' and current_ids==packet_ids and packet.get('candidate_sha256')==sha(text)
                    and packet.get('input_sha256')==digest({k:v for k,v in packet.items() if k!='input_sha256'}) and latest):
                try:
                    check(packet.get('project_id')==p.doc['project']['project_id'] and packet.get('catalog_sha256')==p.doc['project']['catalog_sha256'],'packet project mismatch')
                    check(packet.get('rubric_version')==p.rubric['version'] and packet.get('question_requirements_version')==p.requirements['version'],'packet version mismatch')
                    for dep in packet.get('dependencies',[]):
                        answer=p.doc['answers'].get(dep['question_id'])
                        check(answer and p.statuses().get(dep['question_id'])=='accepted' and answer['metadata']['revision']==dep['revision'] and sha(answer['text'])==dep['answer_sha256'],'dependency changed')
                    validate_result(latest,packet);evaluation=latest
                except (Invalid,KeyError,TypeError,ValueError):pass
        result[qid]={'role':role,'text':display_prose(text),'evaluation':evaluation,'noteIds':[turn['turn_id'] for turn in turns]}
    return result


def render(p,bundle,locale=None,include_html=False):
    p.load(optional=True);check(not p.path('.startup101/pending.json').exists(),'recover pending transaction before render')
    bundle=Path(bundle).resolve();manifestpath=bundle/'manifest.json';check(manifestpath.exists(),'template-unavailable: missing manifest.json')
    manifest=readjson(manifestpath);check(manifest['template_api_version']==1 and 1 in manifest['document_schema_versions'],'template API/schema incompatible')
    warnings=[]
    for asset in manifest.get('assets',[]):
        path=safe(bundle,asset['path']);valid=path.is_file() and sha(path.read_bytes())==asset['sha256']
        if not valid:
            check(not asset.get('required',True),'required template asset missing/checksum mismatch: '+asset['path']);warnings.append(asset['path'])
    clusters=None
    if manifest.get('presentation'):
        clusters=validate_clusters(readjson(safe(bundle,manifest['presentation']['path'])),p.catalog,p.doc['project']['catalog_sha256'])
    entry=safe(bundle,manifest['entry']);check(entry.is_file(),'template-unavailable: entry missing')
    if locale is None:
        view=p.path('.startup101/view.json');locale=readjson(view).get('locale','en') if view.exists() else 'en'
    check(locale in ('en','zh-TW'),'unsupported locale')
    statuses = p.statuses()
    answers = {qid: {'text':display_prose(answer['text']), 'status':statuses[qid],
                     'scores':answer['metadata']['scores'], 'revision':answer['metadata']['revision'],
                     'claims':[{**claim, 'text':display_prose(claim['text'])} for claim in answer['metadata']['claims']]}
               for qid,answer in p.doc['answers'].items()}
    model={'keyPoints':key_points_view(p),'pendingAnswers':pending_view(p),'interviewNotes':note_view(p),'next_question_id':p.marked_next(statuses),'clusters':clusters,'locale':locale,'project':{**p.doc['project'], 'title':display_prose(p.doc['project']['title'])},'categories':[c for c in p.catalog['categories'] if not c.get('cautionOnly')],'questions':[q for q in p.catalog['questions'] if not q['cautionOnly']],'cautions':[q for q in p.catalog['questions'] if q['cautionOnly']],'answers':answers,'readonly':True,'source':{'revision':p.doc['project']['revision'],'sha256':sha(p.doc['source'])},'template_version':manifest['version']}
    serialized=dumps(model).replace('&','\\u0026').replace('<','\\u003c').replace('>','\\u003e').replace('\u2028','\\u2028').replace('\u2029','\\u2029')
    env=Environment(loader=FileSystemLoader(str(bundle)),undefined=StrictUndefined,autoescape=select_autoescape(default=True))
    from markupsafe import Markup
    html=env.get_template(manifest['entry']).render(model=model,model_json=Markup(serialized))
    check('STARTUP_CAMI_READONLY' in html or 'STARTUP101_READONLY' in html,'template must declare STARTUP_CAMI_READONLY readonly adapter')
    output=p.path(p.config['output']);atomic(output,html)
    receipt={'source':model['source'],'template_version':manifest['version'],'generated_at':now(),'inputs':[str(p.docpath),str(p.path('.startup101/catalog.json')),str(p.path('.startup101/requirements.json')),str(p.path('.startup101/rubric.json')),str(p.path('.startup101/receipts')),str(bundle)],'warnings':warnings}
    putjson(p.path('.startup101/render-receipt.json'),receipt)
    return {'status':'rendered','locale':locale,'output':str(output),**receipt,**({'html':html} if include_html else {})}

def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--project');sub=parser.add_subparsers(dest='command',required=True)
    init=sub.add_parser('init');init.add_argument('--title',default='My startup')
    for command in ('inspect','validate','recover','key-points-input'):sub.add_parser(command)
    kp=sub.add_parser('set-key-points');kp.add_argument('--file',required=True)
    nxt=sub.add_parser('set-next');nxt.add_argument('--question',required=True);nxt.add_argument('--expected-revision',type=int,required=True)
    cap=sub.add_parser('note');cap.add_argument('--question',action='append',default=[]);cap.add_argument('--turn-id',required=True);cap.add_argument('--text-file',required=True);cap.add_argument('--expected-revision',type=int,required=True)
    dr=sub.add_parser('draft');dr.add_argument('--turn-id',required=True);dr.add_argument('--question',required=True);dr.add_argument('--text-file');dr.add_argument('--sources-file')
    inp=sub.add_parser('evaluate-input');inp.add_argument('--question',required=True);inp.add_argument('--kind',choices=KINDS,required=True);inp.add_argument('--candidate-file');inp.add_argument('--confirmed',action='store_true');inp.add_argument('--dependency',action='append',default=[]);inp.add_argument('--review-policy',choices=('single','independent'),default='single')
    ac=sub.add_parser('accept');ac.add_argument('--evaluation',required=True);ac.add_argument('--expected-revision',type=int,required=True)
    ev=sub.add_parser('record-evaluation');ev.add_argument('--evaluation',required=True)
    review=sub.add_parser('record-review');review.add_argument('--review',required=True)
    decision=sub.add_parser('record-decision');decision.add_argument('--assessment',required=True)
    action=sub.add_parser('session-action');action.add_argument('--question',required=True);action.add_argument('--action',choices=('defer','skip','resume'),required=True);action.add_argument('--reason',required=True)
    ren=sub.add_parser('render');ren.add_argument('--template-bundle',required=True);ren.add_argument('--locale',choices=('en','zh-TW'));ren.add_argument('--include-html',action='store_true')
    args=parser.parse_args();root=root_for(args.project);p=Project(root)
    try:
        if args.command=='init':result=init_project(root,args.title)
        elif args.command in ('inspect','validate'):result=p.load(optional=True).summary()
        else:
            with lock(root):
                if args.command=='key-points-input':result=key_points_input(p)
                elif args.command=='set-key-points':result=set_key_points(p,readjson(Path(args.file)))
                elif args.command=='set-next':result=set_next(p,args.question,args.expected_revision)
                elif args.command=='note':result=note(p,args.turn_id,text(Path(args.text_file)),args.expected_revision,args.question)
                elif args.command=='draft':result=draft(p,args.question,text(Path(args.text_file)) if args.text_file else None,readjson(Path(args.sources_file)) if args.sources_file else None,args.turn_id)
                elif args.command=='evaluate-input':result=evaluation_input(p,args.question,args.kind,text(Path(args.candidate_file)) if args.candidate_file else None,args.confirmed,args.dependency,args.review_policy)
                elif args.command=='accept':result=accept(p,readjson(Path(args.evaluation)),args.expected_revision)
                elif args.command=='record-evaluation':result=record_evaluation(p,readjson(Path(args.evaluation)))
                elif args.command=='record-review':result=record_review(p,readjson(Path(args.review)))
                elif args.command=='record-decision':result=record_decision(p,readjson(Path(args.assessment)))
                elif args.command=='session-action':result=session_action(p,args.question,args.action,args.reason)
                elif args.command=='recover':result=recover(p)
                else:result=render(p,args.template_bundle,args.locale,args.include_html)
        print(dumps(result));return 0
    except (Invalid,OSError,KeyError,TypeError,UnicodeError,TemplateError) as error:
        print(dumps({'error':str(error),'command':args.command}),file=sys.stderr);return 2

if __name__=='__main__':sys.exit(main())
