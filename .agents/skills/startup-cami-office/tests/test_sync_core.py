"""Synthetic full-catalog checks for explicit Markdown -> active YAML imports."""
import json
import re
from pathlib import Path
from copy import deepcopy
import sys
import pytest
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import sync_core as core
import startup_cami_yaml as storage
import startup_cami as runtime


@pytest.fixture
def package(tmp_path):
    db, _ = storage.load(runtime.TEMPLATES / 'startup-cami.yaml', roundtrip=False)
    db['project']['name'] = 'Synthetic core import'
    storage.save(tmp_path / 'startup-cami.yaml', db, None)
    groups = [[] for _ in range(20)]
    for index, (qid, question) in enumerate(db['questions'].items()):
        groups[index % 20].append({'id': qid, 'question': question['prompt']['zh-TW'],
                                  'question_en': question['prompt']['en'], 'role': '共用回答'})
    rows = []; markdown = ['# Synthetic reviewed core answers']
    for index, sources in enumerate(groups):
        category_index = index // 2
        if index % 2 == 0:
            markdown.append(f'## 主題 {category_index}｜Topic {category_index}')
        zh = f'核心問題 {index}？'; en = f'Core question {index}?'
        rows.append({'category': f'主題 {category_index}', 'category_en': f'Topic {category_index}',
                     'core_question': zh, 'core_question_en': en, 'source_questions': sources})
        markdown.extend([f'### {zh}', en, '#### Headlines｜中文', '- 大家一起做決定',
                         '#### Headlines｜English', '- Decide together.',
                         '#### Answer｜中文', f'第 {index} 個完整答案。\n\n**細節**\n\n- 保留原文',
                         '#### Answer｜English', f'Complete answer {index}.\n\n**Detail**\n\n- Keep this text.',
                         '#### 換句話問', '- 換句話問？／Another way to ask?',
                         '#### 追問', '- 下一步？／What next?', '教材要求的補充追問：',
                         '- 怎麼測？／How to test?', '---'])
    text = '\n\n'.join(markdown) + '\n'
    md = tmp_path / 'answers.md'; md.write_text(text)
    mapping = tmp_path / 'mapping.json'
    mapping.write_text(json.dumps({'questions': [{'id': qid} for qid in db['questions']],
                                   'editing': {'format': 'startup101-core-questions/1', 'source_questions': 351,
                                               'core_mapping': rows}}, ensure_ascii=False))
    return tmp_path, md, mapping, db


def apply(package):
    root, md, mapping, _ = package
    return core.sync(root, md, mapping, storage.sha((root/'startup-cami.yaml').read_bytes()), apply=True)


def test_exact_bilingual_import_idempotence_and_projection(package, monkeypatch):
    root, md, mapping, before = package
    initial = (root/'startup-cami.yaml').read_bytes()
    preview = core.sync(root, md, mapping, storage.sha(initial))
    assert preview['status'] == 'validated' and (root/'startup-cami.yaml').read_bytes() == initial
    result = apply(package)
    db, source_hash = storage.load(root/'startup-cami.yaml', roundtrip=False)
    for name in before:
        if name != 'project':
            assert db[name] == before[name]
    assert db['project']['revision'] == before['project']['revision'] + 1
    assert len(db['core_canvas']['questions']) == 20
    parsed = core.parse_markdown(md.read_text())[1]
    for imported, original in zip(db['core_canvas']['questions'].values(), parsed):
        assert imported['answer']['en'] == original['sections']['Answer｜English']
        assert imported['answer']['zh-TW'] == original['sections']['Answer｜中文']
        assert imported['headlines']['en'] == ['Decide together.']
        assert len(imported['followups']) == 2
        assert imported['status'] == 'saved'
    current = (root/'startup-cami.yaml').read_bytes()
    assert core.sync(root, md, mapping, source_hash, apply=True)['status'] == 'unchanged'
    assert (root/'startup-cami.yaml').read_bytes() == current
    p = runtime.Project(root).load(readonly=True)
    monkeypatch.setattr(p, 'statuses', lambda: (_ for _ in ()).throw(AssertionError('legacy status called')))
    for locale in ('en', 'zh-TW'):
        model = runtime.projection(p, locale)
        assert len(model['questions']) == len(model['clusters']['cards']) == 20
        assert len(model['categories']) == 10
        assert model['interviewNotes'] == [] and model['pendingAnswers'] == {}
        assert all(a['status']=='saved' and a['scores'] is None for a in model['answers'].values())
        first = next(iter(db['core_canvas']['questions']))
        assert model['answers'][first]['text'] == db['core_canvas']['questions'][first]['answer'][locale]
    assert p.summary()['archived_source_question_count'] == 351
    with pytest.raises(runtime.Invalid, match='Active core Canvas'):
        p.save()


def test_history_conflict_and_independent_yaml_edit(package):
    root, md, mapping, _ = package
    apply(package)
    before, old_hash = storage.load(root/'startup-cami.yaml', roundtrip=False)
    old_core = deepcopy(before['core_canvas'])
    md.write_text(md.read_text().replace('Complete answer 0.', 'Revised complete answer 0.'))
    with pytest.raises(storage.Invalid, match='hash conflict'):
        core.sync(root, md, mapping, '0'*64, apply=True)
    core.sync(root, md, mapping, old_hash, apply=True)
    after, _ = storage.load(root/'startup-cami.yaml', roundtrip=False)
    assert after['core_canvas']['revision'] == 2
    assert after['core_canvas']['history'] == [{k:v for k,v in old_core.items() if k!='history'}]
    raw = (root/'startup-cami.yaml').read_text()
    (root/'startup-cami.yaml').write_text(raw.replace('Revised complete answer 0.', 'Independent edit.'))
    with pytest.raises(storage.Invalid, match='content hash mismatch'):
        apply(package)


def test_blank_core_then_fill_one_question(package):
    root, md, _, _ = package
    full = md.read_text()
    blank = re.sub(r'^(#### (?:Headlines|Answer)｜[^\n]+)\n.*?(?=^#{2,4} |\Z)',
                   r'\1\n\n', full, flags=re.M | re.S)
    md.write_text(blank)
    apply(package)
    project = runtime.Project(root).load(readonly=True)
    summary = project.summary()
    first = summary['next_question_id']
    assert summary['question_count'] == 20 and summary['saved_count'] == 0
    assert first and set(summary['current_statuses'].values()) == {'empty'}
    model = runtime.projection(project, 'zh-TW')
    assert model['next_question_id'] == first and len(model['questions']) == 20
    assert not model['answers'] and not model['keyPoints']

    next_question = '### 核心問題 1？'
    mixed = full.split(next_question, 1)[0] + next_question + blank.split(next_question, 1)[1]
    md.write_text(mixed)
    apply(package)
    project = runtime.Project(root).load(readonly=True)
    assert project.summary()['saved_count'] == 1
    assert project.summary()['next_question_id'] != first
    assert list(runtime.projection(project, 'en')['answers']) == [first]
    current = (root/'startup-cami.yaml').read_bytes()
    md.write_text(blank)
    with pytest.raises(storage.Invalid, match='clear a saved answer'):
        apply(package)
    assert (root/'startup-cami.yaml').read_bytes() == current


@pytest.mark.parametrize('mutation', ['missing', 'duplicate', 'identity', 'coverage'])
def test_reject_malformed_or_incomplete_import(package, mutation):
    root, md, mapping, _ = package
    before = (root/'startup-cami.yaml').read_bytes()
    if mutation == 'missing':
        md.write_text(md.read_text().replace('#### Answer｜English', '#### Unsupported', 1))
    elif mutation == 'duplicate':
        md.write_text(md.read_text().replace('#### Answer｜English', '#### Headlines｜English', 1))
    else:
        data = json.loads(mapping.read_text())
        if mutation == 'identity':
            data['editing']['core_mapping'][0]['source_questions'][0]['question_en'] = 'Wrong original question'
        else:
            data['editing']['core_mapping'][0]['source_questions'].pop()
        mapping.write_text(json.dumps(data, ensure_ascii=False))
    with pytest.raises(storage.Invalid):
        apply(package)
    assert (root/'startup-cami.yaml').read_bytes() == before


def test_source_edit_during_encode_cannot_commit(package, monkeypatch):
    root, md, mapping, _ = package
    before = (root/'startup-cami.yaml').read_bytes()
    original_encode = storage.encode
    def edit_during_encode(db):
        encoded = original_encode(db)
        md.write_text(md.read_text() + '\nUser edit while syncing.\n')
        return encoded
    monkeypatch.setattr(storage, 'encode', edit_during_encode)
    with pytest.raises(storage.Invalid, match='Import source changed'):
        apply(package)
    assert (root/'startup-cami.yaml').read_bytes() == before
    assert not (root/'.startup-cami/yaml-pending.json').exists()


def test_empty_headlines_preserve_answer_without_gap_stickies(package):
    root,md,mapping,before=package
    md.write_text(md.read_text().replace('- 大家一起做決定','',1).replace('- Decide together.','',1))
    apply(package)
    db,_=storage.load(root/'startup-cami.yaml',roundtrip=False)
    qid=next(iter(db['core_canvas']['questions']));question=db['core_canvas']['questions'][qid]
    assert question['headlines']=={'en':[],'zh-TW':[]}
    assert question['answer']['en'].startswith('Complete answer 0.')
    assert question['answer']['zh-TW'].startswith('第 0 個完整答案。')
    assert db['questions']==before['questions'] and db['records']==before['records']
    project=runtime.Project(root).load(readonly=True)
    assert runtime.projection(project,'en')['keyPoints'][qid]['formal']['points']==[]


def test_core_headline_translation_counts_must_match(package):
    root,md,mapping,_=package
    before=(root/'startup-cami.yaml').read_bytes()
    md.write_text(md.read_text().replace('- Decide together.','',1))
    with pytest.raises(storage.Invalid,match='bilingual headline counts must match'):
        apply(package)
    assert (root/'startup-cami.yaml').read_bytes()==before
