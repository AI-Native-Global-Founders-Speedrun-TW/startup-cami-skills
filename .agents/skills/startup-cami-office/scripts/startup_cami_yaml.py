# /// script
# requires-python = ">=3.11"
# dependencies = ["ruamel.yaml==0.18.16", "jsonschema==4.25.1"]
# ///
"""Strict round-trip storage for the single Cami Startup Canvas YAML database."""
from pathlib import Path
from io import StringIO
import contextlib
import hashlib
import json
import os
import tempfile
import uuid
from ruamel.yaml import YAML
from ruamel.yaml.tokens import AliasToken, AnchorToken, TagToken, ScalarToken, KeyToken
from jsonschema import Draft202012Validator

SCHEMA = Path(__file__).resolve().parents[1] / 'templates/startup-cami.schema.json'
DOCUMENT = 'startup-cami.yaml'
STATE_DIR = '.startup-cami'
# Legacy names from before the rename to Cami Startup Canvas. Projects created
# earlier only have startup101.yaml with machine state under .startup101/. They are
# read and written in place, with their own journal and lock, until the explicit
# `migrate-name --apply` command moves them to the current names.
LEGACY_DOCUMENT = 'startup101.yaml'
LEGACY_STATE_DIR = '.startup101'
class Invalid(ValueError): pass


def document_path(root):
    """Return the project's YAML database path: current name first, legacy name as fallback."""
    root = Path(root)
    current, legacy = root / DOCUMENT, root / LEGACY_DOCUMENT
    if current.exists() and legacy.exists():
        same = current.read_bytes() == legacy.read_bytes()
        raise Invalid(f'Both {DOCUMENT} and legacy {LEGACY_DOCUMENT} exist; '
                      + ('run migrate-name --apply to finish the interrupted rename' if same
                         else 'keep one source of truth before continuing (nothing was changed)'))
    return legacy if legacy.exists() else current


def is_legacy(path):
    return Path(path).name == LEGACY_DOCUMENT


def state_dir(path):
    """Machine-state directory that belongs to a database file (legacy file -> legacy directory)."""
    path = Path(path)
    return path.parent / (LEGACY_STATE_DIR if is_legacy(path) else STATE_DIR)


def journal_path(path):
    return state_dir(path) / 'yaml-pending.json'


@contextlib.contextmanager
def lock_directory(directory, timeout=0):
    import portalocker
    directory = Path(directory); directory.mkdir(parents=True, exist_ok=True)
    try:
        with portalocker.Lock(str(directory / 'write.lock'), mode='a+', timeout=timeout): yield
    except portalocker.exceptions.LockException as error:
        raise Invalid('project locked by another writer; retry after it exits') from error


def lock(root, timeout=0):
    """Exclusive project writer lock in the state directory of the active database."""
    return lock_directory(state_dir(document_path(root)), timeout)

def sha(value):
    return hashlib.sha256(value.encode('utf-8') if isinstance(value,str) else value).hexdigest()

def validate_headlines(items, label='headlines'):
    """Validate storage shape only; wording and useful length belong to the AI."""
    if not isinstance(items, list) or len(items) > 12:
        raise Invalid(label + ': expected 0–12 headlines')
    for item in items:
        if not isinstance(item, str) or not item or item != item.strip() or item.splitlines() != [item]:
            raise Invalid(label + ': each headline must be a trimmed nonempty single-line string')
        if len(item) > 1000:
            raise Invalid(label + ': headline exceeds 1000-character storage limit')
    if len(set(items)) != len(items):
        raise Invalid(label + ': duplicate headline')
    return items

def codec(roundtrip=True):
    yaml=YAML(typ='rt' if roundtrip else 'safe');yaml.allow_duplicate_keys=False;yaml.preserve_quotes=True
    yaml.representer.ignore_aliases=lambda data: True
    yaml.width=1000000000;yaml.indent(mapping=2,sequence=4,offset=2)
    return yaml

def parse(raw,roundtrip=True):
    if isinstance(raw,bytes):raw=raw.decode('utf-8')
    try:
        previous=None
        for token in codec(False).scan(raw):
            if isinstance(previous,KeyToken) and isinstance(token,ScalarToken) and token.value=='<<':
                raise Invalid(f'YAML merge keys are forbidden at line {token.start_mark.line+1}')
            if isinstance(token,(AliasToken,AnchorToken,TagToken)):
                raise Invalid(f'YAML aliases, anchors and explicit tags are forbidden at line {token.start_mark.line+1}')
            previous=token
        blocks=[]
        if roundtrip:
            # C-parser node marks identify actual paths; IDs and multiline text may
            # legitimately contain the word "legacy" elsewhere in this document.
            node=codec(False).compose(raw)
            def child(mapping,key):
                if getattr(mapping,'id',None)!='mapping':return None
                return next(((k,v) for k,v in mapping.value if k.value==key),None)
            for path in (('records','legacy'),('legacy_archive',)):
                current=node;pair=None
                for key in path:
                    pair=child(current,key)
                    if pair is None:break
                    current=pair[1]
                if pair is None:continue
                keynode,value=pair;indent=2*(len(path)-1)
                if keynode.start_mark.column!=indent or getattr(value,'flow_style',True):continue
                if value.end_mark.index==len(raw) and value.end_mark.column:continue
                start=keynode.start_mark.index-indent
                end=value.end_mark.index-value.end_mark.column
                if end<=start or not raw[start:end].endswith('\n'):continue
                body=raw[start:end]
                placeholder=' '*indent+path[-1]+': {}\n'
                blocks.append((path,start,end,body,placeholder))
        if blocks:
            plain=codec(False).load(raw);validate(plain)
            masked=raw
            for path,start,end,body,placeholder in sorted(blocks,key=lambda row:row[1],reverse=True):masked=masked[:start]+placeholder+masked[end:]
            db=codec().load(masked);frozen=[]
            for path,start,end,body,placeholder in blocks:
                source=plain;target=db
                for key in path[:-1]:source=source[key];target=target[key]
                value=source[path[-1]];target[path[-1]]=value
                frozen.append((path,body,sha(json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(',',':')))))
            if db!=plain:raise Invalid('round-trip preservation differs from validated YAML')
            db._startup_cami_frozen=frozen
            return db
        db=codec(roundtrip).load(raw)
    except Invalid:raise
    except Exception as e:raise Invalid(str(e)) from e
    validate(db)
    return db

def validate(db):
    schema=json.loads(SCHEMA.read_text())
    error=next(Draft202012Validator(schema).iter_errors(db),None)
    if error:
        raise Invalid('/'+'/'.join(str(v) for v in error.absolute_path)+': '+error.message)
    def require(ok,path):
        if not ok:raise Invalid(path)
    qs=db['questions'];records=db['records'];notes=db['notes'];cards=db['canvas']['cards']
    require(db['session']['next_question'] is None or db['session']['next_question'] in qs,'session.next_question: unknown question')
    for qid,q in qs.items():
        validate_headlines(q['key_points']['items'],f'questions.{qid}.key_points')
        for snap in ([q['accepted_version']] if q['accepted_version'] else [])+q['history']:
            validate_headlines(snap['key_points']['items'],f'questions.{qid}.history.key_points')
        require(q['requirements']['question_id']==qid,f'questions.{qid}.requirements.question_id mismatch')
        for nid in q['note_refs']:require(nid in notes,f'questions.{qid}.note_refs: unknown note {nid}')
        for rid in q['decision_refs']:require(rid in records['decisions'],f'questions.{qid}.decision_refs: unknown decision')
        rev=q['review']
        if rev:
            require(rev['packet_id'] in records['packets'],f'questions.{qid}.review.packet_id: missing packet')
            require(records['packets'][rev['packet_id']]['question_id']==qid,f'questions.{qid}.review: wrong question')
            for eid in rev['evaluation_ids']:require(eid in records['evaluations'],f'questions.{qid}.review: missing evaluation')
            packet=records['packets'][rev['packet_id']]
            for eid in rev['evaluation_ids']:require(records['evaluations'][eid]['input_sha256']==packet['input_hash'],f'questions.{qid}.review: evaluation packet mismatch')
            if rev['resolution_id']:require(rev['resolution_id'] in records['reviews'],f'questions.{qid}.review: missing resolution')
            if rev['resolution_id']:require(records['reviews'][rev['resolution_id']]['input_sha256']==packet['input_hash'],f'questions.{qid}.review: resolution packet mismatch')
            if rev['acceptance_receipt_id']:require(rev['acceptance_receipt_id'] in records['receipts'],f'questions.{qid}.review: missing receipt')
            if rev['acceptance_receipt_id']:require(records['receipts'][rev['acceptance_receipt_id']]['packet_id']==rev['packet_id'],f'questions.{qid}.review: receipt packet mismatch')
        for snap in ([q['accepted_version']] if q['accepted_version'] else [])+q['history']:
            require(snap['answer_hash']==sha(snap['answer']),f'questions.{qid}: snapshot answer hash mismatch')
            rid=snap['receipt_id']
            if rid and not rid.startswith('legacy:'):require(rid in records['receipts'],f'questions.{qid}: missing snapshot receipt')
            if rid and rid.startswith('legacy:'):require(db.get('legacy_archive') is not None,f'questions.{qid}: missing legacy archive')
    categories=db['canvas']['categories']
    require(set(db['canvas']['category_order'])==set(categories) and len(db['canvas']['category_order'])==len(categories),'canvas.category_order: duplicate or missing category')
    for category,entry in categories.items():
        for cid in entry['cards']:
            require(cid in cards and cards[cid]['primary_category']==category,'canvas.categories: card category mismatch')
    for cid,c in cards.items():
        require(c['lead_question_id']==cid and cid in qs,'canvas.cards: lead must identify card')
        require(c['primary_category'] in categories and cid in categories[c['primary_category']]['cards'],'canvas.cards: missing category placement')
        require(set(c['categories'])<=set(categories),'canvas.cards: unknown category')
    for entry in db['canvas']['cautions'].values():
        require(set(entry['attached_to_ids'])<=set(cards),'canvas.cautions: missing card')
    for name in ('actions','review_policy_locks'):
        require(set(db['session'][name])<=set(qs),'session.'+name+': unknown question')
    for qid,q in qs.items():
        require(set(q['source_refs'])<=set(db['sources']),f'questions.{qid}.source_refs: missing source')
    packets_by_hash={p['input_hash']:p for p in records['packets'].values()}
    for eid,ev in records['evaluations'].items():
        require(eid==ev['evaluation_id'],'records.evaluations: identifier mismatch')
        packet=packets_by_hash.get(ev['input_sha256'])
        require(packet is not None and packet['question_id']==ev['question_id'] and packet['answer_hash']==ev['candidate_sha256'],'records.evaluations: packet mismatch')
    for rid,rev in records['reviews'].items():
        require(rid==rev['review_id'],'records.reviews: identifier mismatch')
        packet=packets_by_hash.get(rev['input_sha256'])
        require(packet is not None and packet['question_id']==rev['question_id'],'records.reviews: packet mismatch')
        for eid in rev['evaluation_ids']:
            ev=records['evaluations'].get(eid)
            require(ev is not None and ev['input_sha256']==rev['input_sha256'],'records.reviews: evaluation mismatch')
    for aid,decision in records['decisions'].items():
        require(aid==decision['assessment_id'],'records.decisions: identifier mismatch')
        ev=records['evaluations'].get(decision['evaluation_id'])
        require(ev is not None and ev['input_sha256']==decision['input_sha256'] and ev['question_id']==decision['question_id'],'records.decisions: evaluation mismatch')
    assigned=[]
    for cid,c in cards.items():
        for member in c['questions']:
            qid=member['question_id'];require(qid in qs,f'canvas.cards.{cid}: unknown question');assigned.append(qid)
    require(len(assigned)==len(set(assigned)) and set(assigned)==set(qs),'canvas.cards: questions must occur exactly once')
    for nid,n in notes.items():
        for qid in n['question_ids']:require(qid in qs,f'notes.{nid}: unknown question')
    for pid,p in records['packets'].items():
        require(p['question_id'] in qs,f'records.packets.{pid}: unknown question')
        for span in p['note_spans']:require(span['note_id'] in notes,f'records.packets.{pid}: missing note')
        for sid in p['source_refs']:require(sid in db['sources'],f'records.packets.{pid}: missing source')
        for dep in p['dependencies']:require(dep['question_id'] in qs,f'records.packets.{pid}: missing dependency')
    for rid,r in records['receipts'].items():
        require(r['packet_id'] in records['packets'],f'records.receipts.{rid}: missing packet')
        for eid in r['evaluation_ids']:require(eid in records['evaluations'],f'records.receipts.{rid}: missing evaluation')
        packet=records['packets'][r['packet_id']]
        require(packet['question_id']==r['question_id'] and packet['answer_hash']==r['answer_hash'],f'records.receipts.{rid}: packet mismatch')
        for eid in r['evaluation_ids']:
            require(records['evaluations'][eid]['input_sha256']==packet['input_hash'],f'records.receipts.{rid}: evaluation packet mismatch')
        if r['resolution_id']:require(r['resolution_id'] in records['reviews'],f'records.receipts.{rid}: missing review')
    if db.get('core_canvas'):
        core=db['core_canvas']
        require(len(core['history'])==core['revision']-1,'core_canvas.history: revision chain incomplete')
        for index,layer in enumerate([*core['history'],core],start=1):
            require(layer['revision']==index,'core_canvas.history: revisions must increase consecutively')
            payload={name:layer[name] for name in ('categories','questions')}
            checksum=sha(json.dumps(payload,ensure_ascii=False,sort_keys=True,separators=(',',':')))
            require(checksum==layer['content_sha256'],'core_canvas: content hash mismatch; reconcile independent YAML changes before importing')
            cqs=layer['questions'];placed=[];sources=[]
            names=[c['id'] for c in layer['categories']]
            require(len(names)==len(set(names)),'core_canvas.categories: duplicate category')
            for category in layer['categories']:
                require(category['id']==category['title']['en'],'core_canvas.categories: identity/title mismatch')
                for qid in category['questions']:
                    require(qid in cqs and cqs[qid]['category']==category['id'],'core_canvas.categories: question placement mismatch')
                    placed.append(qid)
            require(len(placed)==len(set(placed)) and set(placed)==set(cqs),'core_canvas.categories: each core question must occur exactly once')
            for qid,q in cqs.items():
                if q['status']=='empty':
                    require(not any(q['answer'].values()) and not any(q['headlines'].values()),
                            'Empty core question cannot contain answers or headlines')
                else:
                    require(all(value.strip() for value in q['answer'].values()),
                            'Saved core question needs both answer languages')
                require(len(q['headlines']['en'])==len(q['headlines']['zh-TW']),'core_canvas.questions: bilingual headline counts must match')
                for locale,items in q['headlines'].items():
                    validate_headlines(items,f'core_canvas.questions.{qid}.headlines.{locale}')
                refs=q['source_questions']
                # Legacy identity seed: persisted core question IDs are derived from it; never rename.
                require(qid==sha('startup101-core/1\n'+'\n'.join(sorted(r['question_id'] for r in refs)))[:16],'core_canvas.questions: stable identity mismatch')
                for ref in refs:
                    sid=ref['question_id']
                    require(sid in qs and ref['prompt']==qs[sid]['prompt'],'core_canvas.questions: original source question identity mismatch')
                    sources.append(sid)
            require(len(sources)==len(set(sources)) and set(sources)==set(qs),'core_canvas.questions: original questions must occur exactly once')
    return db

def load(path,roundtrip=True):
    raw=Path(path).read_bytes();return parse(raw,roundtrip=roundtrip),sha(raw)

def encode(db):
    validate(db);frozen=getattr(db,'_startup_cami_frozen',[]);replaced=[]
    try:
        for index,(path,body,checksum) in enumerate(frozen):
            target=db
            for key in path[:-1]:target=target[key]
            value=target[path[-1]]
            if sha(json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(',',':')))!=checksum:
                raise Invalid('immutable legacy provenance changed; explicit migration is required')
            marker='STARTUP_CAMI_FROZEN_'+uuid.uuid4().hex
            replaced.append((target,path[-1],value,marker,body,len(path)-1))
            target[path[-1]]=marker
        stream=StringIO();codec().dump(db,stream);text=stream.getvalue()
        for target,key,value,marker,body,indent in replaced:
            needle='  '*indent+key+': '+marker+'\n'
            if text.count(needle)!=1:raise Invalid('could not preserve immutable provenance block')
            text=text.replace(needle,body,1)
        # Verify the complete emitted document, including preserved node boundaries.
        for target,key,value,*_ in replaced:target[key]=value
        if codec(False).load(text)!=db:raise Invalid('preserved YAML output changed database semantics')
        return text.encode('utf-8')
    finally:
        for target,key,value,*_ in replaced:target[key]=value


def atomic(path,raw):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    fd,tmp=tempfile.mkstemp(prefix='.'+path.name+'.',dir=path.parent)
    try:
        with os.fdopen(fd,'wb') as f:f.write(raw);f.flush();os.fsync(f.fileno())
        os.replace(tmp,path)
        dfd=os.open(path.parent,os.O_RDONLY)
        try:os.fsync(dfd)
        finally:os.close(dfd)
    finally:
        if os.path.exists(tmp):os.unlink(tmp)

def save(path,db,expected_hash,source_guards=()):
    path=Path(path);raw=encode(db)
    def check_sources():
        for source,expected in source_guards:
            if sha(Path(source).read_bytes())!=expected:
                raise Invalid('Import source changed during sync: '+str(source)+'; reload before writing')
    check_sources()
    current=sha(path.read_bytes()) if path.exists() else None
    if current!=expected_hash:raise Invalid('YAML source changed; reload before writing')
    # Recovery journal is machine state, never an alternate editable data source.
    journal=journal_path(path)
    if journal.exists():raise Invalid('recover pending YAML transaction first')
    atomic(journal,json.dumps({'before':current,'after':sha(raw),'content':raw.decode('utf-8')},ensure_ascii=False).encode())
    if (sha(path.read_bytes()) if path.exists() else None)!=expected_hash:
        journal.unlink();raise Invalid('YAML source changed during write; reload')
    try:check_sources()
    except (Invalid,OSError):
        journal.unlink();raise
    atomic(path,raw);journal.unlink()
    return sha(raw)

def recover(path):
    path=Path(path);journal=journal_path(path)
    if not journal.exists():return {'status':'clean'}
    tx=json.loads(journal.read_text());raw=tx['content'].encode();parse(raw)
    if sha(raw)!=tx['after']:raise Invalid('recovery content hash mismatch')
    current=sha(path.read_bytes()) if path.exists() else None
    if current==tx['after']:journal.unlink();return {'status':'recovered'}
    if current!=tx['before']:raise Invalid('recovery conflict: edited YAML preserved; resolve explicitly')
    atomic(path,raw);journal.unlink();return {'status':'recovered'}


def migrate_name(root, apply=False):
    """Explicitly move a legacy startup101.yaml project to the current file names.

    Preview by default. With apply, the YAML bytes are published unchanged as
    startup-cami.yaml (exclusive create), the local view setting is copied to
    .startup-cami/view.json, and the legacy file is moved, not deleted, into
    .startup-cami/recovery/name-migration-*/. The legacy .startup101/ directory is
    left untouched. Rerunning after an interruption finishes the same move.
    """
    root = Path(root).resolve()
    legacy, current = root / LEGACY_DOCUMENT, root / DOCUMENT
    legacy_state, state = root / LEGACY_STATE_DIR, root / STATE_DIR
    if not legacy.exists():
        if current.exists():return {'status': 'current', 'document': str(current)}
        raise Invalid(f'No {DOCUMENT} or legacy {LEGACY_DOCUMENT} found in project')
    raw = legacy.read_bytes(); parse(raw, roundtrip=False)
    if (legacy_state / 'yaml-pending.json').exists():raise Invalid('recover pending YAML transaction first')
    if current.exists() and current.read_bytes() != raw:
        raise Invalid(f'Both {DOCUMENT} and legacy {LEGACY_DOCUMENT} exist with different content; keep one source of truth first (nothing was changed)')
    copy_view = (legacy_state / 'view.json').is_file() and not (state / 'view.json').exists()
    result = {'status': 'preview', 'from': str(legacy), 'to': str(current), 'source_sha256': sha(raw),
              'copies_view_config': copy_view, 'legacy_state_dir_kept': str(legacy_state)}
    if not apply:return result
    with lock_directory(legacy_state, timeout=0), lock_directory(state, timeout=0):
        if legacy.read_bytes() != raw:raise Invalid('legacy YAML changed during rename; inspect again')
        if (legacy_state / 'yaml-pending.json').exists() or (state / 'yaml-pending.json').exists():
            raise Invalid('recover pending YAML transaction first')
        if not current.exists():
            fd, temporary = tempfile.mkstemp(prefix='.' + DOCUMENT + '.', dir=root)
            try:
                with os.fdopen(fd, 'wb') as stream:stream.write(raw);stream.flush();os.fsync(stream.fileno())
                os.link(temporary, current)
            finally:
                if os.path.exists(temporary):os.unlink(temporary)
        if current.read_bytes() != raw:raise Invalid(f'{DOCUMENT} differs from legacy YAML; legacy file kept')
        if copy_view:atomic(state / 'view.json', (legacy_state / 'view.json').read_bytes())
        backup = state / 'recovery' / ('name-migration-' + uuid.uuid4().hex); backup.mkdir(parents=True)
        atomic(backup / 'manifest.json', (json.dumps({'from': LEGACY_DOCUMENT, 'to': DOCUMENT, 'sha256': sha(raw)}, indent=2) + '\n').encode())
        os.replace(legacy, backup / LEGACY_DOCUMENT)
        directory = os.open(root, os.O_RDONLY)
        try:os.fsync(directory)
        finally:os.close(directory)
    return {**result, 'status': 'migrated', 'backup': str(backup / LEGACY_DOCUMENT)}
