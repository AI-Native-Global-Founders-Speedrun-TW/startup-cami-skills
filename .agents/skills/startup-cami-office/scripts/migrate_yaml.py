# /// script
# requires-python = ">=3.11"
# dependencies = ["ruamel.yaml==0.18.16", "jsonschema==4.25.1", "markdown-it-py==3.0.0", "jinja2==3.1.6", "portalocker==3.2.0", "opencc-python-reimplemented==0.1.7"]
# ///
"""Lossless legacy import. Default is read-only; --apply makes a backed-up cutover."""
from __future__ import annotations
import argparse
import base64
import copy
import fnmatch
import gzip
import json
import os
from pathlib import Path, PurePosixPath
import sys
import tempfile
import uuid
import legacy_runtime as old

TEMPLATES = Path(__file__).resolve().parents[1] / 'templates'
# Legacy names: Markdown-era projects (from before the rename to Cami Startup Canvas)
# keep startup101.md and machine state under .startup101/, and their archived
# formats are identified as startup101-markdown-v1 / startup101-records-v1. These
# names are read-only inputs and stored format identifiers; never rename them.

class ArchivePath:
    """Read-only path facade: legacy verification never materializes another database."""
    def __init__(self, files, name): self.files, self.name = files, str(name)
    def read_bytes(self): return self.files[self.name]
    def exists(self): return self.name in self.files or any(k.startswith(self.name.rstrip('/')+'/') for k in self.files)
    def glob(self, pattern):
        prefix = self.name.rstrip('/')+'/'
        return [ArchivePath(self.files,k) for k in sorted(self.files) if k.startswith(prefix) and '/' not in k[len(prefix):] and fnmatch.fnmatch(k[len(prefix):],pattern)]
    def __str__(self): return self.name
    def __lt__(self, other): return self.name < other.name


def archive_files(db):
    archive=db.get('legacy_archive')
    old.check(archive and archive['format']=='startup101-markdown-v1', 'missing legacy archive')
    files={};bundle=None;spans=[]
    if archive.get('encoding'):
        old.check(archive['encoding']=='gzip+base64','unsupported archive bundle encoding')
        try:bundle=gzip.decompress(base64.b64decode(archive['content'],validate=True))
        except Exception as error:raise old.Invalid('invalid legacy archive bundle') from error
    for name, item in archive['files'].items():
        path=PurePosixPath(name)
        old.check(not path.is_absolute() and '..' not in path.parts and '\\' not in name, 'unsafe legacy archive path')
        if bundle is not None:
            start=item['offset'];length=item['length']
            old.check(type(start) is int and type(length) is int and start>=0 and length>=0 and start+length<=len(bundle),'invalid archive file range')
            raw=bundle[start:start+length];spans.append((start,start+length))
        else:
            old.check(item['encoding'] in ('base64','gzip+base64'),'unsupported legacy encoding')
            try:
                raw=base64.b64decode(item['content'],validate=True)
                if item['encoding']=='gzip+base64':raw=gzip.decompress(raw)
            except Exception as error: raise old.Invalid('invalid legacy base64: '+name) from error
        old.check(old.sha(raw)==item['sha256'],'legacy archive checksum mismatch: '+name)
        files[name]=raw
    if bundle is not None:
        end=0
        for start,stop in sorted(spans):
            old.check(start==end,'archive has overlapping or missing byte ranges');end=stop
        old.check(end==len(bundle),'archive has unindexed trailing bytes')
    return files


class ArchiveProject(old.Project):
    def __init__(self, files): self.files=files; self.root=Path('/__startup_cami_archive__')
    def path(self,name): return ArchivePath(self.files,name)


def expand_legacy_packet(packet,legacy):
    result={k:v for k,v in packet.items() if k!='field_refs'}
    for key,ref in packet.get('field_refs',{}).items():result[key]=legacy['shared_content'][ref]
    return result


def expand_legacy_record(record, legacy):
    if 'packet_ref' not in record:return record
    result={k:v for k,v in record.items() if k!='packet_ref'}
    result['packet']=expand_legacy_packet(legacy['packets'][record['packet_ref']],legacy)
    return result


def legacy_project(db):
    """Original legacy state, validated against its original bytes (no live sidecars)."""
    files=archive_files(db)
    structured=db.get('records',{}).get('legacy')
    if structured:
        packets={}
        for kind in ('evaluations','reviews','decisions','receipts'):
            expected={PurePosixPath(name).stem:old.loads(raw.decode()) for name,raw in files.items() if name.startswith('.startup101/'+kind+'/') and name.endswith('.json')}
            old.check({k:expand_legacy_record(v,structured) for k,v in structured[kind].items()}==expected,'structured legacy '+kind+' differs from archived originals')
            for record in expected.values():
                if record.get('packet'):packets[old.digest(record['packet'])]=record['packet']
        session=old.loads(files['.startup101/session.json'].decode())
        stored_session=copy.deepcopy(structured['session'])
        stored_session['drafts']={k:expand_legacy_record(v,structured) for k,v in stored_session.get('drafts',{}).items()}
        old.check(stored_session==session,'structured legacy session differs from archived original')
        for record in session.get('drafts',{}).values():
            if record.get('packet'):packets[old.digest(record['packet'])]=record['packet']
        old.check({k:expand_legacy_packet(v,structured) for k,v in structured['packets'].items()}==packets,'structured legacy packets differ from archived originals')
        events=[old.loads(line) for line in files.get('.startup101/events.jsonl',b'').decode().splitlines() if line.strip()]
        old.check(structured['events']==events,'structured legacy events differ from archived originals')
    return ArchiveProject(files).load(optional=True)


def legacy_statuses(db, project=None):
    if not db.get('legacy_archive'): return {}
    project=copy.deepcopy(project) if project is not None else legacy_project(db)
    # Recheck note/dependency edits against today's YAML, while preserving old receipt metadata.
    project.doc['notes']={k:v['text'] for k,v in db['notes'].items()}
    for qid, entry in list(project.doc['answers'].items()):
        snapshot=db['questions'].get(qid,{}).get('accepted_version')
        if not snapshot or snapshot.get('receipt_id') != 'legacy:'+entry['metadata']['evaluation_id']:
            del project.doc['answers'][qid]
        else:
            entry['text']=snapshot['answer']
            if snapshot['revision'] != entry['metadata']['revision'] or snapshot['answer_hash'] != entry['metadata']['answer_sha256']:
                entry['text']+='\n[invalid legacy snapshot]'
    states=project.statuses()
    for qid,state in list(states.items()):
        if state!='accepted': continue
        meta=project.doc['answers'][qid]['metadata']
        receipt=old.readjson(project.path('.startup101/receipts/'+meta['evaluation_id']+'.json'))
        try:
            packet=receipt['packet'];result=receipt['evaluation']
            old.check(packet['input_sha256']==old.digest({k:v for k,v in packet.items() if k!='input_sha256'}),'legacy packet hash mismatch')
            old.check(result['verdict']=='pass' and result['evaluation_id']==meta['evaluation_id'],'legacy receipt is not a pass')
            for key in ('scores','dependencies','claims','input_sha256','question_id','rubric_version','question_requirements_version'):
                old.check(result[key]==meta[key],'legacy evaluation differs from receipt metadata')
            old.check(result['candidate_sha256']==meta['answer_sha256']==packet['candidate_sha256'],'legacy candidate hash mismatch')
            # Earlier schema omitted score_reasons; retain its historical gate without fabricating reasons.
            if 'score_reasons' in result: old.validate_result(result,packet)
            if packet.get('review_policy')=='independent':old.acceptance_review(project,packet,result)
        except (ValueError,KeyError,TypeError): states[qid]='unverifiable'
    changed=True
    while changed:
        changed=False
        for qid,state in list(states.items()):
            if state=='accepted' and any(states.get(d['question_id'])!='accepted' for d in project.doc['answers'][qid]['metadata']['dependencies']):
                states[qid]='needs_review';changed=True
    return states


def legacy_projection(db):
    return legacy_project(db)


def legacy_sidecar_summary(db, project=None):
    if not db.get('legacy_archive'):return {'reviews':{'count':0,'latest_by_question':{}},'decisions':{'count':0,'latest_by_question':{}}}
    project=project or legacy_project(db)
    summary=old.sidecar_summary(project)
    baseline=old.pending_view(project)
    revision_changed=db['project']['revision']!=project.doc['project']['revision']
    for kind in ('reviews','decisions'):
        for qid,item in summary[kind]['latest_by_question'].items():
            question=db['questions'].get(qid)
            before=baseline.get(qid,{}).get('text') or project.doc['answers'].get(qid,{}).get('text','')
            changed=revision_changed or not question or old.display_prose(question['answer'])!=old.display_prose(before)
            if question:
                changed=changed or any(nid not in db['notes'] or db['notes'][nid]['text']!=project.doc['notes'].get(nid) for nid in question['note_refs'])
            if changed:
                if kind=='decisions':item['stale']=True
                else:item['current_packet']=False
    return summary


def legacy_pending_view(db):
    """Legacy draft assessment from structured records; only current matching inputs qualify."""
    result={}
    for qid,record in db['records'].get('legacy',{}).get('session',{}).get('drafts',{}).items():
        if qid not in db['questions'] or not record.get('turns'): continue
        record=expand_legacy_record(record,db['records']['legacy'])
        question=db['questions'][qid];packet=record.get('packet');evaluation=record.get('last_evaluation');valid=False
        try:
            old.check(packet and evaluation,'no legacy assessment')
            old.check(packet['input_sha256']==old.digest({k:v for k,v in packet.items() if k!='input_sha256'}),'packet changed')
            old.check(old.sha(question['answer'])==packet['candidate_sha256'],'answer changed')
            old.check([t['turn_id'] for t in record['turns']]==[t['turn_id'] for t in old.packet_notes(packet)],'turns changed')
            for turn in old.packet_notes(packet):
                old.check(old.sha(db['notes'][turn['turn_id']]['text'])==turn['note_sha256'],'note changed')
            for dep in packet['dependencies']:
                snapshot=db['questions'][dep['question_id']]['accepted_version']
                old.check(snapshot and snapshot['revision']==dep['revision'] and snapshot['answer_hash']==dep['answer_sha256'],'dependency changed')
            old.validate_result(evaluation,packet);valid=True
        except (ValueError,KeyError,TypeError): pass
        result[qid]={'role':'pending','text':old.display_prose(question['answer']),'evaluation':evaluation if valid else None,'noteIds':question['note_refs']}
    return result


def _snapshot(text, meta, points):
    return {'answer':text,'answer_hash':old.sha(text),'revision':meta['revision'],
            'key_points':{'items':points,'answer_hash':old.sha(text)},
            'note_refs':meta['source_turns'], 'receipt_id':'legacy:'+meta['evaluation_id'],
            'saved_at':meta['evaluated_at'],'kind':'accepted'}


def migrate_project(root):
    """Return (database, invariant report); never writes any file."""
    root=Path(root).resolve(); project=old.Project(root).load()
    old.check(not project.path('.startup101/pending.json').exists(),'recover legacy transaction before migration')
    from ruamel.yaml import YAML
    db=YAML(typ='safe').load((TEMPLATES/'startup-cami.yaml').read_text())
    old.check(set(db['questions'])=={q for q,v in project.questions.items() if not v['cautionOnly']},'template question catalog differs')
    old.check(db['rules']['rubric']==project.rubric,'rubric differs from pinned legacy rubric')
    old.check(project.catalog==old.readjson(old.ASSETS/'catalog.json'),'pinned catalog definitions/layout differ from bundled template version')
    old.check(project.requirements==old.readjson(old.ASSETS/'requirements.json'),'pinned requirements differ from bundled template version')
    for qid,q in db['questions'].items():
        old.check(q['requirements']==project.requirement(qid),'template requirements differ: '+qid)
    files={}
    paths=[project.docpath]+[p for p in (root/'.startup101').rglob('*') if p.is_file() and p.name not in ('write.lock','view.json','render-receipt.json') and not any(x in p.parts for x in ('cache','recovery','node_modules'))]
    for path in paths:
        old.check(not path.is_symlink(),'cannot migrate symlink: '+str(path))
        raw=path.read_bytes(); files[str(path.relative_to(root))]={'encoding':'gzip+base64','content':base64.b64encode(gzip.compress(raw,mtime=0)).decode(),'sha256':old.sha(raw)}
    parts=[];indexed={};offset=0
    for name,item in sorted(files.items()):
        raw=gzip.decompress(base64.b64decode(item['content']));parts.append(raw)
        indexed[name]={'offset':offset,'length':len(raw),'sha256':item['sha256']};offset+=len(raw)
    db['legacy_archive']={'format':'startup101-markdown-v1','encoding':'gzip+base64','content':base64.b64encode(gzip.compress(b''.join(parts),mtime=0)).decode(),'files':indexed}
    meta=project.doc['project']
    db['project'].update(id=meta['project_id'],name=meta['title'],revision=meta['revision'])
    local=project.path('.startup101/view.json')
    settings=old.readjson(local) if local.exists() else {}
    db['project']['language']=settings.get('locale',settings.get('language')) or ('zh-TW' if any('\u4e00'<=c<='\u9fff' for c in project.doc['source']) else 'en')
    db['session']['next_question']=meta.get('next_question_id')
    notes=old.note_view(project)
    db['notes']={n['id']:{'text':n['text'],'question_ids':n['questionIds'],'created_at':None,'content_hash':old.sha(n['text'])} for n in notes}
    # Preserve every original note byte; display conversion is never used for persisted data.
    for nid,body in project.doc['notes'].items(): db['notes'][nid]['text']=body;db['notes'][nid]['content_hash']=old.sha(body)
    pending=old.pending_view(project); points=old.key_points_view(project); session=project.session()
    legacy={'format':'startup101-records-v1','packets':{},'evaluations':{},'reviews':{},'decisions':{},'receipts':{},'session':copy.deepcopy(session),'events':[]}
    for kind in ('evaluations','reviews','decisions','receipts'):
        for path in project.path('.startup101/'+kind).glob('*.json'):
            record=old.readjson(path);legacy[kind][path.stem]=record
            packet=record.get('packet')
            if packet: legacy['packets'][old.digest(packet)]=copy.deepcopy(packet)
    for record in session.get('drafts',{}).values():
        packet=record.get('packet')
        if packet: legacy['packets'][old.digest(packet)]=copy.deepcopy(packet)
    events=project.path('.startup101/events.jsonl')
    if events.exists():legacy['events']=[old.loads(line) for line in old.text(events).splitlines() if line.strip()]
    for kind in ('evaluations','reviews','decisions','receipts'):
        for record in legacy[kind].values():
            if record.get('packet'):record['packet_ref']=old.digest(record.pop('packet'))
    for record in legacy['session'].get('drafts',{}).values():
        if record.get('packet'):record['packet_ref']=old.digest(record.pop('packet'))
    legacy['shared_content']={}
    for packet in legacy['packets'].values():
        refs={}
        for key in ('question','requirements','rubric','sources','note_turns','raw_turns','related_answers'):
            if key in packet:
                value=packet.pop(key);ref=old.digest(value);legacy['shared_content'][ref]=value;refs[key]=ref
        packet['field_refs']=refs
    db['records']['legacy']=legacy
    for qid,q in db['questions'].items():
        formal=project.doc['answers'].get(qid)
        if formal:
            q['accepted_version']=_snapshot(formal['text'],formal['metadata'],points.get(qid,{}).get('formal',{}).get('points',[]))
            q['answer']=formal['text'];q['key_points']=copy.deepcopy(q['accepted_version']['key_points']);q['note_refs']=list(formal['metadata']['source_turns'])
        draft=pending.get(qid)
        if draft and draft.get('text') is not None:
            record=session['drafts'][qid]; turns=[old.source_note(project,t) for t in record['turns']]
            candidate=record.get('packet',{}).get('candidate_text')
            body=candidate if candidate is not None and any(candidate==t['excerpt'] for t in turns) else turns[-1]['excerpt']
            q['answer']=body;q['note_refs']=[t['turn_id'] for t in record['turns']]
            q['key_points']={'items':points.get(qid,{}).get('pending',{}).get('points',[]),'answer_hash':old.sha(body)}
        record=session.get('drafts',{}).get(qid,{})
        q['source_refs']=[old.digest(source) for source in record.get('sources',[])]
        if record.get('review_policy_lock'): db['session']['review_policy_locks'][qid]=record['review_policy_lock']
        state=record.get('state')
        if isinstance(state,str) and state in ('skip','defer','active'):
            action='resume' if state=='active' else state
            event=next((e for e in reversed(legacy['events']) if e.get('type')=='session_action' and e.get('question_id')==qid),{})
            db['session']['actions'][qid]={'action':action,'reason':record.get('reason',''),'updated_at':event.get('at')}
        if isinstance(state,dict) and state.get('action') in ('skip','defer','resume'):
            db['session']['actions'][qid]={'action':state['action'],'reason':state['reason'],'updated_at':state.get('at',state.get('updated_at'))}
        if draft and draft.get('text') is not None:
            old.check(old.display_prose(q['answer'])==draft['text'],'pending display changed: '+qid)
    # Retain distinct source versions under content-derived keys; never merge divergent evidence.
    for record in session.get('drafts',{}).values():
        for source in record.get('sources',[]):
            db['sources'][old.digest(source)]=copy.deepcopy(source)
    # Earlier accepted receipts remain accessible as immutable answer history.
    for path in project.path('.startup101/receipts').glob('*.json'):
        receipt=old.readjson(path); metadata=receipt.get('metadata',{}); qid=metadata.get('question_id')
        if qid not in db['questions'] or not isinstance(receipt.get('answer_text'),str): continue
        current=db['questions'][qid]['accepted_version']
        if current and current['receipt_id']=='legacy:'+metadata.get('evaluation_id',''): continue
        if old.sha(receipt['answer_text']) != metadata.get('answer_sha256'): continue
        db['questions'][qid]['history'].append(_snapshot(receipt['answer_text'],metadata,[]))
    states=project.statuses(); migrated=legacy_statuses(db)
    old.check(states==migrated,'migration changed formal statuses')
    report={'formal_answers':len(project.doc['answers']),'statuses':{s:list(states.values()).count(s) for s in sorted(set(states.values()))},'pending_answers':sum(bool(p.get('text')) for p in pending.values()),'notes':len(db['notes']),'key_points':sum(len(v.get('points',[])) for q in points.values() for v in q.values()),'archive_files':len(files),'archive_sha256':old.digest({k:v['sha256'] for k,v in files.items()}),'preserved_statuses':True,'preserved_formal_answers':all(db['questions'][qid]['accepted_version']['answer']==a['text'] for qid,a in project.doc['answers'].items()),'preserved_pending_display':True,'preserved_notes':all(db['notes'][nid]['text']==body for nid,body in project.doc['notes'].items()),'preserved_rubric':True,'preserved_requirements':True,'preserved_catalog':True,'dry_run':True}
    from ruamel.yaml.scalarstring import LiteralScalarString
    for question in db['questions'].values():
        question['answer']=LiteralScalarString(question['answer'])
        for snapshot in ([question['accepted_version']] if question['accepted_version'] else [])+question['history']:
            snapshot['answer']=LiteralScalarString(snapshot['answer'])
    for note in db['notes'].values():note['text']=LiteralScalarString(note['text'])
    return db, report


def apply(root, db):
    import startup_cami_yaml as storage
    root=Path(root).resolve(); target=root/storage.DOCUMENT
    old.check(not target.exists(),storage.DOCUMENT+' already exists; refusing overwrite')
    old.check(not (root/storage.LEGACY_DOCUMENT).exists(),'legacy '+storage.LEGACY_DOCUMENT+' already exists; refusing a second YAML database')
    storage.validate(db); raw=storage.encode(db)
    reparsed=storage.parse(raw,roundtrip=False)
    old.check(reparsed==db,'YAML serialization changed data; cutover refused')
    old.check(legacy_statuses(reparsed)==legacy_statuses(db),'YAML serialization changed acceptance; cutover refused')
    # Re-read all inputs under the legacy lock before either backup or cutover.
    with old.lock(root):
        files=archive_files(db)
        for name, content in files.items(): old.check((root/name).read_bytes()==content,'legacy data changed during migration: '+name)
        backup=root/'.startup101'/'recovery'/('yaml-migration-'+uuid.uuid4().hex)
        backup.mkdir(parents=True)
        manifest={'target_sha256':old.sha(raw),'files':{k:old.sha(v) for k,v in files.items()}}
        for name,content in files.items():
            dest=backup/name;dest.parent.mkdir(parents=True,exist_ok=True);dest.write_bytes(content)
        old.putjson(backup/'manifest.json',manifest)
        # Publish complete bytes atomically and exclusively. A crash never exposes a partial YAML.
        fd, temporary=tempfile.mkstemp(prefix='.startup-cami-migration-',dir=root)
        try:
            with os.fdopen(fd,'wb') as stream: stream.write(raw);stream.flush();os.fsync(stream.fileno())
            os.link(temporary,target)
            directory_fd=os.open(root,os.O_RDONLY)
            try: os.fsync(directory_fd)
            finally: os.close(directory_fd)
        finally:
            if os.path.exists(temporary): os.unlink(temporary)
        for name,content in files.items():
            path=root/name
            old.check(path.read_bytes()==content,'legacy file changed during cutover: '+name)
            path.unlink()
        return str(backup)


def rollback(root, backup):
    import startup_cami_yaml as storage
    root=Path(root).resolve();backup=Path(backup).resolve();target=root/storage.DOCUMENT
    old.check(backup.is_relative_to(root/'.startup101/recovery'),'backup must be inside project recovery')
    manifest=old.readjson(backup/'manifest.json')
    with old.lock(root):
        old.check(not target.exists() or old.sha(target.read_bytes())==manifest['target_sha256'],'YAML changed since migration; refusing rollback that would lose edits')
        for name,checksum in manifest['files'].items():
            old.safe(root,name);body=(backup/name).read_bytes();old.check(old.sha(body)==checksum,'backup checksum mismatch')
            old.check(not (root/name).exists() or (root/name).read_bytes()==body,'legacy path changed: '+name)
        for name in manifest['files']:
            dest=root/name
            if not dest.exists():
                dest.parent.mkdir(parents=True,exist_ok=True);dest.write_bytes((backup/name).read_bytes())
        if target.exists(): target.unlink()


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--project',type=Path,required=True);parser.add_argument('--apply',action='store_true');parser.add_argument('--dry-run',action='store_true');parser.add_argument('--rollback',type=Path);args=parser.parse_args()
    old.check(not (args.apply and args.dry_run),'choose either --apply or --dry-run')
    if args.rollback: rollback(args.project,args.rollback);print('{"rolled_back":true}');return
    db,report=migrate_project(args.project)
    if args.apply: report.update(backup=apply(args.project,db),dry_run=False)
    print(json.dumps(report,ensure_ascii=False,indent=2))

if __name__=='__main__':
    try: main()
    except (ValueError,OSError,KeyError) as error: print(str(error),file=sys.stderr);sys.exit(2)
