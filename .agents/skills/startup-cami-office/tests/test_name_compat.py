"""Compatibility with projects created before the rename (startup101.yaml + .startup101/)."""
import json
import shutil
import sys
from pathlib import Path
import pytest
SKILL = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SKILL / 'scripts'))
import startup_cami as r
import startup_cami_yaml as s


def run(argv, capsys, monkeypatch):
    monkeypatch.setattr(sys, 'argv', ['startup_cami.py', *argv])
    code = r.main(); out = capsys.readouterr()
    return code, json.loads(out.out) if code == 0 else json.loads(out.err)


@pytest.fixture
def legacy(tmp_path):
    """A project exactly as the pre-rename runtime left it: only startup101.yaml."""
    r.init_project(tmp_path, 'Legacy project')
    (tmp_path / 'startup-cami.yaml').rename(tmp_path / 'startup101.yaml')
    shutil.rmtree(tmp_path / '.startup-cami', ignore_errors=True)
    (tmp_path / '.startup101').mkdir()
    (tmp_path / '.startup101/view.json').write_text('{"app_dir": "view", "port": 3010, "locale": "en"}\n')
    return tmp_path


def test_init_uses_current_names(tmp_path, capsys, monkeypatch):
    code, result = run(['--project', str(tmp_path), 'init', '--title', 'New'], capsys, monkeypatch)
    assert code == 0 and result['document'] == 'startup-cami.yaml' and result['legacy_document_name'] is False
    assert (tmp_path / 'startup-cami.yaml').is_file() and not (tmp_path / 'startup101.yaml').exists()
    assert (tmp_path / '.startup-cami/write.lock').exists() and not (tmp_path / '.startup101').exists()


def test_legacy_project_is_read_and_written_in_place(legacy, capsys, monkeypatch):
    before = (legacy / 'startup101.yaml').read_bytes()
    code, summary = run(['--project', str(legacy), 'inspect'], capsys, monkeypatch)
    assert code == 0 and summary['document'] == 'startup101.yaml' and summary['legacy_document_name'] is True
    assert summary['source_sha256'] == s.sha(before) and summary['question_count'] == 351
    qid = next(iter(r.Project(legacy).load(readonly=True).questions))
    code, result = run(['--project', str(legacy), 'set-next', '--question', qid, '--expected-revision', str(summary['project']['revision']),
                        '--expected-source-sha256', summary['source_sha256']], capsys, monkeypatch)
    assert code == 0 and result['status'] == 'next_question_set'
    assert (legacy / 'startup101.yaml').read_bytes() != before and not (legacy / 'startup-cami.yaml').exists()
    assert (legacy / '.startup101/write.lock').exists() and not (legacy / '.startup-cami').exists()
    assert r.Project(legacy).load().db['session']['next_question'] == qid
    # The recovery journal of a legacy project stays in .startup101/.
    p = r.Project(legacy).load(); current = p.docpath.read_bytes(); after = current + b'\n# replay\n'
    journal = legacy / '.startup101/yaml-pending.json'
    s.atomic(journal, json.dumps({'before': s.sha(current), 'after': s.sha(after), 'content': after.decode()}).encode())
    assert r.Project(legacy).load().summary()['pending_transaction'] is True
    code, result = run(['--project', str(legacy), 'recover'], capsys, monkeypatch)
    assert code == 0 and result['status'] == 'recovered' and (legacy / 'startup101.yaml').read_bytes() == after


def test_legacy_project_renders_with_current_and_old_bundles(legacy, tmp_path_factory):
    p = r.Project(legacy).load(readonly=True)
    result = r.render(p, SKILL / 'assets/studio-template')
    html = (legacy / 'startup-cami.html').read_text()
    assert result['source']['sha256'] == s.sha((legacy / 'startup101.yaml').read_bytes())
    assert 'window.STARTUP_CAMI_MODEL = ' in html and 'STARTUP_CAMI_READONLY' in html
    # A template bundle installed before the rename only declares the legacy marker.
    old = tmp_path_factory.mktemp('old-bundle')
    (old / 'canvas.html.jinja').write_text('<!-- STARTUP101_READONLY --><script>{{ model_json }}</script>')
    (old / 'manifest.json').write_text(json.dumps({'template_api_version': 1, 'document_schema_versions': [2], 'version': 'old', 'entry': 'canvas.html.jinja', 'assets': []}))
    assert r.render(p, old, include_html=True)['template_version'] == 'old'


def test_root_discovery_and_init_respect_legacy_file(legacy, monkeypatch):
    nested = legacy / 'notes/deep'; nested.mkdir(parents=True); monkeypatch.chdir(nested)
    assert r.root_for(None) == legacy.resolve()
    with pytest.raises(r.Invalid, match='startup101.yaml already exists'):
        r.init_project(legacy, 'Second database')
    assert not (legacy / 'startup-cami.yaml').exists()


def test_two_databases_are_rejected_without_writes(legacy, capsys, monkeypatch):
    legacy_bytes = (legacy / 'startup101.yaml').read_bytes()
    (legacy / 'startup-cami.yaml').write_bytes(legacy_bytes + b'\n# diverged\n')
    code, error = run(['--project', str(legacy), 'inspect'], capsys, monkeypatch)
    assert code == 2 and 'Both startup-cami.yaml and legacy startup101.yaml exist' in error['error']
    code, error = run(['--project', str(legacy), 'migrate-name', '--apply'], capsys, monkeypatch)
    assert code == 2 and 'different content' in error['error']
    assert (legacy / 'startup101.yaml').read_bytes() == legacy_bytes


def test_migrate_name_preview_then_apply(legacy, capsys, monkeypatch):
    raw = (legacy / 'startup101.yaml').read_bytes()
    code, preview = run(['--project', str(legacy), 'migrate-name'], capsys, monkeypatch)
    assert code == 0 and preview['status'] == 'preview' and preview['copies_view_config'] is True
    assert (legacy / 'startup101.yaml').read_bytes() == raw and not (legacy / 'startup-cami.yaml').exists()
    code, result = run(['--project', str(legacy), 'migrate-name', '--apply'], capsys, monkeypatch)
    assert code == 0 and result['status'] == 'migrated'
    assert (legacy / 'startup-cami.yaml').read_bytes() == raw and not (legacy / 'startup101.yaml').exists()
    assert Path(result['backup']).read_bytes() == raw and Path(result['backup']).is_relative_to(legacy / '.startup-cami/recovery')
    assert (legacy / '.startup-cami/view.json').read_text() == (legacy / '.startup101/view.json').read_text()
    code, summary = run(['--project', str(legacy), 'inspect'], capsys, monkeypatch)
    assert code == 0 and summary['document'] == 'startup-cami.yaml' and summary['source_sha256'] == s.sha(raw)
    code, again = run(['--project', str(legacy), 'migrate-name', '--apply'], capsys, monkeypatch)
    assert code == 0 and again['status'] == 'current'


def test_migrate_name_finishes_an_interrupted_move(legacy):
    raw = (legacy / 'startup101.yaml').read_bytes(); (legacy / 'startup-cami.yaml').write_bytes(raw)
    with pytest.raises(s.Invalid, match='migrate-name --apply'):r.Project(legacy)
    result = s.migrate_name(legacy, apply=True)
    assert result['status'] == 'migrated' and not (legacy / 'startup101.yaml').exists()
    assert r.Project(legacy).load().docpath.name == 'startup-cami.yaml'


def test_migrate_name_refuses_pending_or_invalid_legacy(legacy):
    (legacy / '.startup101/yaml-pending.json').write_text('{}')
    with pytest.raises(s.Invalid, match='recover'):s.migrate_name(legacy, apply=True)
    (legacy / '.startup101/yaml-pending.json').unlink()
    (legacy / 'startup101.yaml').write_text('not: [valid')
    with pytest.raises(s.Invalid):s.migrate_name(legacy, apply=True)
    assert not (legacy / 'startup-cami.yaml').exists()
