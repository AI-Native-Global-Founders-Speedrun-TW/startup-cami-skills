# /// script
# requires-python = ">=3.10"
# dependencies = []
# ///
"""將既有唯讀 Studio UI 打包成離線 Jinja 樣板。輸入是 web 資產，不含使用者答案。

uv run web/build_template.py --output <bundle-directory>
重新建置不改題庫或正式 YAML。
"""
import argparse
import hashlib
import json
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    web = Path(__file__).resolve().parent
    locale_dir=Path(__file__).resolve().parents[1]/'.agents/skills/startup-cami-office/assets/locales'
    translations={locale:json.loads((locale_dir/(locale+'.json')).read_text()) for locale in ('en','zh-TW')}
    payload=json.dumps(translations,ensure_ascii=False).replace('<','\\u003c').replace('>','\\u003e').replace('&','\\u0026')
    (web/'i18n-data.js').write_text('window.STARTUP_CAMI_TRANSLATIONS = '+payload+';\n',encoding='utf8')
    cluster_source=locale_dir.parent/'clusters.json'
    clusters=json.loads(cluster_source.read_text())
    cluster_json=json.dumps(clusters,ensure_ascii=False).replace('<','\\u003c').replace('>','\\u003e').replace('&','\\u0026')
    (web/'clusters-data.js').write_text('window.STARTUP_CAMI_CLUSTERS = window.STARTUP_CAMI_MODEL?.clusters || '+cluster_json+';\n',encoding='utf8')
    html = (web / 'index.html').read_text(encoding='utf-8')
    about = (web / 'offline-about.html').read_text()
    html = html.replace('</body>', about + '</body>')
    marker = '<!-- STARTUP_CAMI_READONLY: only renderer-supplied YAML snapshot data -->\n<script>window.STARTUP_CAMI_MODEL = {% endraw %}{{ model_json }}{% raw %};</script>\n<script>window.STARTUP_CAMI_LOCALE=window.STARTUP_CAMI_MODEL.locale || "en";</script>\n'
    html=html.replace('<script src="i18n-data.js"></script>',marker+'<script src="i18n-data.js"></script>')
    for name in ['styles.css', 'art.js', 'data.js', 'i18n-data.js', 'i18n.js', 'clusters-data.js', 'app.js']:
        contents = (web / name).read_text(encoding='utf-8')
        if name == 'data.js':
            data = json.loads(contents.split('window.STUDIO_DATA = ', 1)[1].rsplit(';', 1)[0])
            # 保留路徑與插畫設定；題目及位置以 renderer 傳入的 pinned catalog 為準。
            data['questions'] = []
            data['categories'] = [{k: c[k] for k in ('name', 'art', 'landmark')} for c in data['categories']]
            contents = 'window.STUDIO_DATA = ' + json.dumps(data, ensure_ascii=False).replace('<', '\\u003c') + ';'
        if name.endswith('.css'):
            html = html.replace(f'<link rel="stylesheet" href="{name}">', '<style>\n' + contents + '\n</style>')
        else:
            html = html.replace(f'<script src="{name}"></script>', '<script>\n' + contents + '\n</script>')
    if 'window.STARTUP_CAMI_MODEL = ' not in html:
        raise ValueError('Could not locate the i18n script insertion point')
    template = '{% raw %}' + html + '{% endraw %}'
    args.output.mkdir(parents=True, exist_ok=True)
    entry = args.output / 'canvas.html.jinja'
    entry.write_text(template, encoding='utf-8')
    cluster_entry=args.output/'clusters.json'
    cluster_entry.write_bytes(cluster_source.read_bytes())
    manifest = {
        'template_api_version': 1, 'version': 'studio-readonly-9-all-headlines',
        'entry': entry.name, 'document_schema_versions': [2],
        'readonly': True, 'offline': True,
        'presentation': {'path':'clusters.json','schema_version':1,'source_sha256':clusters['source_sha256']},
        'assets': [{'path': entry.name, 'sha256': hashlib.sha256(entry.read_bytes()).hexdigest(), 'required': True}, {'path':cluster_entry.name,'sha256':hashlib.sha256(cluster_entry.read_bytes()).hexdigest(),'required':True}],
    }
    (args.output / 'manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    (args.output / 'README.md').write_text('''# Studio 唯讀 HTML 樣板

此 bundle 由 web/build_template.py 產生；修改源 UI 後重建，不手改生成檔。

入口 canvas.html.jinja（畫布樣板）只取 model_json。它必須由 renderer 做 HTML script-safe JSON 序列化並標記可信輸出；其他內容不得使用 safe 或再次編譯為 template。

資料契約：project、categories、questions、cautions、answers（以 question id 為 key，含 text/status/scores/claims/revision）、readonly=true、source（revision/sha256）、template_version、locale、clusters、interviewNotes（整理後的詳細筆記與相關題識別）、pendingAnswers（來源核對過的待評估正文）、keyPoints（原題與 formal／pending 分開，來源 hash 相符的短重點）。catalog 原題與正式回答來自專案 pinned 資料；clusters 是獨立呈現對照，只有來源 checksum 相容才載入，132 張卡片的座標由 presentation 重新排版，不改正式題庫。沒有網路請求、儲存或回寫操作。

coreMode=true 時，使用同份 YAML 的核心問答呈現層：categories 與 questions 決定使用中的十項主題、20 張卡片；coreContent.categories、question.prompt、answer.textI18n 與 keyPoints.formal.pointsI18n 提供完整中英文內容。alternateQuestions 與 followups 收在題目面板，不另計填答數。saved 只代表答案已保存，進度依有無回答計算，不沿用原題分數或宣稱新回答已通過；未啟用 coreMode 的專案沿用原有132張卡片／351題與有效評估進度。

CSS、JavaScript、SVG 插畫均內嵌；file URL 不需 host service。答案使用 escaped HTML 呈現，範例不當成答案。上下文下載是衍生文字，不是正式 YAML 備份。重新產生 HTML 才會反映 YAML 的修改。
''', encoding='utf-8')
    print(json.dumps({'bundle':str(args.output), 'entry':entry.name, 'bytes':entry.stat().st_size}))


if __name__ == '__main__':
    main()
