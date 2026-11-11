# /// script
# requires-python = ">=3.11"
# dependencies = ["ruamel.yaml==0.18.16", "jsonschema==4.25.1", "portalocker==3.2.0"]
# ///
"""Explicitly import the reviewed bilingual core-question Markdown into YAML.

The YAML is the only runtime data source. This importer never evaluates answers
or changes the original question records. Use --apply with a fresh source hash;
without --apply the command only validates and previews the import.
"""
import argparse
from copy import deepcopy
from datetime import datetime, timezone
import json
from pathlib import Path
import re
import sys
import portalocker
import startup101_yaml as storage

SECTIONS = ('Headlines｜中文', 'Headlines｜English', 'Answer｜中文',
            'Answer｜English', '換句話問', '追問')


def digest(value):
    return storage.sha(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':')))


def content_hash(core):
    return digest({name: core[name] for name in ('categories', 'questions')})


def need(condition, message):
    if not condition:
        raise storage.Invalid(message)


def parse_markdown(text):
    """Parse only explicit headings; never infer question identity by position."""
    need('\r' not in text, 'Markdown must use LF line endings')
    need(not re.search(r'<!--', text), 'Markdown contains unsupported hidden comments')
    matches = list(re.finditer(r'^(#{2,4}) (.+?)\s*$', text, re.M))
    categories = []
    questions = []
    category = None
    question = None
    for index, match in enumerate(matches):
        level, title = len(match[1]), match[2]
        body = text[match.end():matches[index+1].start() if index+1 < len(matches) else len(text)]
        # A horizontal rule between questions is presentation, not answer text.
        body = re.sub(r'\n---\s*\Z', '', body).strip('\n')
        if level == 2:
            need('｜' in title, f'Category needs Chinese and English titles: {title}')
            zh, en = title.split('｜', 1)
            category = {'en': en.strip(), 'zh-TW': zh.strip()}
            need(all(category.values()), 'Empty category title')
            categories.append(category)
            question = None
        elif level == 3:
            need(category is not None, 'Question appears before a category')
            need(body.strip() and '\n' not in body.strip(), f'Expected one English prompt under: {title}')
            question = {'category': category, 'prompt': {'zh-TW': title, 'en': body.strip()}, 'sections': {}}
            questions.append(question)
        else:
            need(question is not None, f'Section appears before a question: {title}')
            need(title in SECTIONS, f'Unknown question section: {title}')
            need(title not in question['sections'], f'Duplicate section {title}: {question["prompt"]["zh-TW"]}')
            question['sections'][title] = body
    need(len(categories) == 10 and len(questions) == 20, 'Expected exactly ten Cami topics and twenty core questions')
    need(len({x['en'] for x in categories}) == 10 and len({x['zh-TW'] for x in categories}) == 10, 'Duplicate category')
    need(len({q['prompt']['zh-TW'] for q in questions}) == 20, 'Duplicate core question')
    for question in questions:
        need(set(question['sections']) == set(SECTIONS), f'Missing required section: {question["prompt"]["zh-TW"]}')
    return categories, questions


def headline_list(body, title):
    lines = [line for line in body.splitlines() if line.strip()]
    need(all(line.startswith('- ') and line[2:].strip() for line in lines), f'{title}: expected headline bullets only')
    items = [line[2:] for line in lines]
    return storage.validate_headlines(items, title)


def bilingual_list(body):
    result = []
    for line in body.splitlines():
        if not line.startswith('- '):
            continue
        need('／' in line, f'Question bullet needs both languages: {line}')
        zh, en = line[2:].split('／', 1)
        need(zh.strip() and en.strip(), 'Question bullet has an empty translation')
        result.append({'zh-TW': zh.strip(), 'en': en.strip()})
    return result


def build_core(text, mapping, db, mapping_hash):
    categories, parsed = parse_markdown(text)
    editing = mapping.get('editing', {})
    need(editing.get('format') == 'startup101-core-questions/1', 'Unsupported core mapping format')
    rows = editing.get('core_mapping', [])
    need(len(rows) == 20, 'Mapping must contain twenty core questions')
    by_title = {r['core_question']: r for r in rows}
    need(len(by_title) == 20, 'Duplicate core question in mapping')
    need(set(by_title) == {q['prompt']['zh-TW'] for q in parsed}, 'Markdown core questions differ from mapping; update the explicit mapping before importing renamed questions')
    expected_ids = set(db['questions'])
    exported_ids = [q['id'] for q in mapping['questions']]
    need(len(exported_ids) == len(set(exported_ids)) and set(exported_ids) == expected_ids, 'Export mapping does not cover the original question database exactly once')
    assigned = []
    core = {'format_version': 1, 'revision': 1,
            'source_markdown_sha256': storage.sha(text), 'source_mapping_sha256': mapping_hash,
            'synced_at': datetime.now(timezone.utc).isoformat(),
            'categories': [{'id': c['en'], 'title': c, 'questions': []} for c in categories],
            'questions': {}, 'history': []}
    category_lookup = {c['id']: c for c in core['categories']}
    for question in parsed:
        prompt = question['prompt']; row = by_title[prompt['zh-TW']]
        need(prompt['en'] == row['core_question_en'], f'English core prompt differs from mapping: {prompt["zh-TW"]}')
        need(question['category'] == {'en': row['category_en'], 'zh-TW': row['category']}, 'Core question category differs from mapping')
        sources = []
        for source in row['source_questions']:
            sid = source['id']; need(sid in expected_ids, f'Unknown original source question: {sid}')
            original = db['questions'][sid]['prompt']
            need(original == {'en': source['question_en'], 'zh-TW': source['question']}, f'Original question identity changed: {sid}')
            need(source['role'] in ('共用回答', '追問', '評估條件'), 'Unknown source-question role')
            sources.append({'question_id': sid, 'role': source['role'], 'prompt': deepcopy(original)})
            assigned.append(sid)
        need(sources, 'Core question has no original source question')
        qid = storage.sha('startup101-core/1\n' + '\n'.join(sorted(s['question_id'] for s in sources)))[:16]
        need(qid not in core['questions'], 'Duplicate core question identity')
        sections = question['sections']
        answer = {'zh-TW': sections['Answer｜中文'], 'en': sections['Answer｜English']}
        filled = {bool(value.strip()) for value in answer.values()}
        need(len(filled) == 1, f'Provide both answer languages or leave both blank: {prompt["zh-TW"]}')
        saved = filled == {True}
        if not saved:
            answer = {'zh-TW': '', 'en': ''}
        headlines = {'zh-TW': headline_list(sections['Headlines｜中文'], prompt['zh-TW']),
                     'en': headline_list(sections['Headlines｜English'], prompt['en'])}
        need(saved or not any(headlines.values()), f'Blank answer cannot have headlines: {prompt["zh-TW"]}')
        core['questions'][qid] = {
            'category': row['category_en'], 'prompt': prompt, 'answer': answer,
            'headlines': headlines,
            'alternate_questions': bilingual_list(sections['換句話問']),
            'followups': bilingual_list(sections['追問']),
            'alternate_markdown': sections['換句話問'], 'followups_markdown': sections['追問'],
            'source_questions': sources, 'status': 'saved' if saved else 'empty'}
        category_lookup[row['category_en']]['questions'].append(qid)
    need(len(assigned) == len(set(assigned)) and set(assigned) == expected_ids, 'Core mapping must own all original questions exactly once')
    need(editing.get('source_questions') == len(assigned), 'Mapping source question count differs')
    core['content_sha256'] = content_hash(core)
    return core


def sync(project, markdown, mapping_path, expected_hash, apply=False):
    """Validate under a lock and atomically replace only the active core layer."""
    project = Path(project).resolve()
    path = project / 'startup101.yaml'
    lock_path = project / '.startup101' / 'write.lock'
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    with portalocker.Lock(str(lock_path), timeout=30):
        db, source_hash = storage.load(path, roundtrip=apply)
        need(expected_hash == source_hash, 'YAML source hash conflict; inspect again before syncing')
        raw = Path(markdown).read_bytes()
        text = raw.decode('utf-8')
        mapping_raw = Path(mapping_path).read_bytes()
        core = build_core(text, json.loads(mapping_raw), db, storage.sha(mapping_raw))
        old = db.get('core_canvas')
        if old:
            need(old['content_sha256'] == content_hash(old), 'Active YAML core content changed independently; reconcile it before importing Markdown')
            for qid, question in old['questions'].items():
                if question['status'] == 'saved':
                    need(core['questions'].get(qid, {}).get('status') == 'saved',
                         f'Import would clear a saved answer: {question["prompt"]["zh-TW"]}')
            if all(core[k] == old[k] for k in ('source_markdown_sha256', 'source_mapping_sha256', 'content_sha256')):
                return {'status': 'unchanged', 'source_sha256': source_hash, 'revision': db['project']['revision'], 'core_revision': old['revision'], 'questions': 20, 'categories': 10}
            core['revision'] = old['revision'] + 1
            core['history'] = [*deepcopy(old['history']), {k: deepcopy(v) for k, v in old.items() if k != 'history'}]
        db['core_canvas'] = core
        storage.validate(db)
        result = {'status': 'validated', 'source_sha256': source_hash, 'revision': db['project']['revision'],
                  'core_revision': core['revision'], 'questions': 20, 'categories': 10,
                  'source_questions_preserved': len(db['questions']), 'content_sha256': core['content_sha256']}
        if apply:
            db['project']['revision'] += 1
            guards=((Path(markdown),storage.sha(raw)),(Path(mapping_path),storage.sha(mapping_raw)))
            for source,expected in guards:
                need(storage.sha(source.read_bytes())==expected,'Import source changed during sync; reload before writing')
            result.update(status='synced', source_sha256=storage.save(path, db, source_hash, source_guards=guards), revision=db['project']['revision'])
        return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--project', required=True)
    parser.add_argument('--markdown', required=True)
    parser.add_argument('--mapping', required=True)
    parser.add_argument('--expected-source-sha256', required=True)
    parser.add_argument('--apply', action='store_true')
    args = parser.parse_args()
    try:
        result = sync(args.project, args.markdown, args.mapping, args.expected_source_sha256, args.apply)
        print(json.dumps(result, ensure_ascii=False))
        return 0
    except (storage.Invalid, OSError, KeyError, TypeError, ValueError) as error:
        print(json.dumps({'error': str(error)}, ensure_ascii=False), file=sys.stderr)
        return 2


if __name__ == '__main__':
    sys.exit(main())
