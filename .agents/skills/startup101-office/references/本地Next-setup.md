# 本地 Next app setup

正式資料仍是 startup project 的 YAML。Next app 不提供回答寫入 API，不自行評分；Python renderer 繼續負責 parse、validate、判斷有效狀態與 HTML 產生。瀏覽器每 1.5 秒讀取本地 endpoint，HTML hash 變動才替換畫面。YAML 格式無效或服務中斷時保留最後成功畫面並明確提示尚未更新；首次載入失敗則顯示錯誤。恢復後採用新資料，保留目前選題、閱讀位置與焦點，不把舊畫面當成最新資料。

## 首次與續跑

首次詢問 Next app 要架在哪。使用者已指定就不再問；建議 `<project>/view`。保存位置在專案 `.startup101/view.json`（畫面設定）。先由 office 初始化正式專案，再執行：

```text
uv run <skill>/scripts/setup.py --project <project> --app-dir <chosen-directory> --port 3010
```

setup 會複製 `assets/next-app/`（本地網頁）、既有 runtime 與模板，執行 npm ci，保存 project 相對路徑與啟動資訊。一般重跑同一位置與同一 project 不覆寫內容；需要同步新版時明確加 `--upgrade`，依回傳的 `backup_dir` 保留被覆寫檔案備份，核對 `bundle_version`、`available_bundle_version` 與 `upgrade_available`。升級只更新 app、runtime 與 template，保留專案 YAML、固定版本題庫、語言、來源位置及本地設定；非空的無關資料夾或不同 project 一律拒絕。失敗可重跑 npm ci；不刪使用者檔案。`--no-install` 只給測試或離線準備，不表示安裝完成。

在 setup 回傳的 start_cwd 執行 start 陣列，等價於：

```text
npm run dev -- --port 3010
```

服務只 bind 127.0.0.1；不使用公開 tunnel，不部署雲端，不上傳答案。啟動前若 port 已被其他服務占用，選空閒 port 並回報，不能終止未知服務。使用者結束本地 app 時停止這個 process；下次依保存位置啟動即可。換電腦需重新 npm ci、確保 uv 可執行；可在 startup101.local.json（本地路徑設定）把 uv 改為新機路徑或 uv。

依 [Next 官方安裝文件](https://nextjs.org/docs/app/getting-started/installation)，需要 Node.js >=20.9 與 npm。首次 npm ci 與 uv 依賴下載需要網路；執行後的回答只在本機讀取。若缺 uv，先安裝 uv，再重跑；不猜測 Python import 逐個安裝。Next、React 固定版本與 package-lock 隨 skill 打包。修改 app 程式使用 Next dev hot reload；YAML 由本地 polling 自動更新，不依賴 Next 是否追蹤外部檔案。

## 維護與測試

`tests/test_setup.py`（安裝邊界測試）驗證資料夾保護與續跑；Next build 檢查頁面與 route 編譯；HTTP 測試應在暫存專案驗證 YAML 變更、無效文件、恢復、外來 Origin 拒絕及來源檔未被 endpoint 改寫。不能拿假的 accepted 回答填進使用者專案。

## English／繁體中文與預設語言

setup 預設 `--locale auto`，依 startup project 的本地文件主要語言選擇 English 或繁體中文；`--locale en`、`--locale zh-TW` 可指定。已保存的語言優先於重新偵測。新建立的示範資料夾沒有實質內容時，可明確傳 `--language-source <既有專案根目錄>`，不自行遍歷任意上層。

偵測只讀 Markdown／純文字／MDX／RST prose，排除隱藏目錄、vendor、node_modules、runtime、assets、view、程式碼區塊、生成的題庫與索引、巢狀 Git repo。正式startup101.yaml（共用正式資料）在舊題模式只計questions.answer；核心模式採用project.language的既有專案語言，不把封存的舊答案或中英成對內容各計一次。不計生成問句、固定規則與metadata。最多取樣 200 個有文字內容的檔案、總計 1 MB、每檔 32 KB；以中文字元折算兩字一單位與英文詞數比較。資訊少於 30 單位或差距低於 15% 時標為不明確，預設 English；輸出原因與計數，不聲稱是精確語言辨識。

瀏覽器選單可隨時切換 English／繁體中文。Next app 只把 display locale 存在 localStorage，沒有保存答案；下次優先採用這項顯示偏好。題目與範例的翻譯保存在獨立 locale 資料，canonical 題庫及正式回答不改寫。使用者的回答、claims、來源證據保留原文。既有衍生示範仍標示不是簡報原文；翻譯術語依 Cami 原始解析教材，另外保留來源引文與頁碼。

`render --locale en|zh-TW` 可輸出指定語言；不指定則採用 YAML 的 project.language；Next endpoint 會明確傳入畫面選定的語言。`--include-html` 讓本地 Next endpoint 直接取得同一次 render 的 HTML，避免另一個語言 request 在讀檔前改寫衍生輸出。

## About 頁面

本地 Next app 的 `/about`（專案介紹頁）可由主畫面 About 入口開啟，提供 English／繁體中文與返回 canvas 的連結。Cami 與 aifounders.tw 同等呈現：教材貢獻自 Cami 的簡報，Skill 由 aifounders.tw 社群投入製作。頁面附公開資料來源，不讀取回答、不新增寫入 API；獨立 HTML 快照不因此需要啟動服務。

About 支援 `?locale=en` 或 `?locale=zh-TW` 明確指定；未指定時採既有顯示偏好，再回到 setup 預設。頁面切換語言沿用同一 display locale 設定，不改正式回答。

## 核心問答與升級驗收

setup 依專案 YAML 安裝畫面。若要從指定的 20 題核心 Canvas 開始，先依使用方式同步空白核心編輯稿，再確認 inspect 回傳 20 題及預期已填數。核心模式用逐題保存的答案計算已填進度。兩種模式及目前能力依[核心問答與舊題模式](核心問答與舊題模式.md)。

每次更新renderer、schema或template後用--upgrade同步安裝複本，依[Canvas驗收](Canvas驗收.md)檢查；只複製skill說明不能更新已安裝Python。升級不得重寫專案正文、headlines、rubric或歷史。
