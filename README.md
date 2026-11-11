# Cami Startup Canvas

用 AI 陪創業者把問題想清楚，將回答、headlines 與評估保存在本地 YAML，再透過 Canvas 閱讀。介面支援繁體中文與英文。

[▶ 在 YouTube 觀看影片](https://www.youtube.com/watch?v=eubF-YPKhfU)

## 包含哪些 Skills

| Skill | 使用時機與工作 |
| --- | --- |
| [startup-cami-office](.agents/skills/startup-cami-office/SKILL.md) | 開始或繼續問答，整理回答、保存 YAML、同步與啟動 Canvas |
| [startup-cami-facilitation](.agents/skills/startup-cami-facilitation/SKILL.md) | 沿用已有回答，找出下一個值得釐清的問題 |
| [startup-cami-evaluate](.agents/skills/startup-cami-evaluate/SKILL.md) | 評估受支援格式的完整回答，檢查清楚程度、具體內容與證據 |

流程為 office 定位與保存 → facilitation 引導回答 → evaluate 評估支援的題型 → office 保存與同步 Canvas。

Office 維護共同資料，讓引導與評估接續同一份回答。Facilitation 負責提問，evaluate 負責評估。核心問答顯示「已填」，原題模式另有正式評估流程。

## 安裝到 AI 工具

需要 Python 3.11 以上、[uv](https://docs.astral.sh/uv/getting-started/installation/)、Node.js 20.9 以上與 npm。

```sh
git clone git@github.com:AI-Native-Global-Founders-Speedrun-TW/startup-cami-skills.git
cd startup-cami-skills
```

在支援專案 skills 的 AI 工具中開啟這個 repository，讓它載入 `.agents/skills/` 下的三支 skills。三個目錄須放在同一層，供彼此讀取相鄰 skill。

要用在另一個專案，可以將三個目錄一起複製或連結到該專案的 `.agents/skills/`，再依 AI 工具設定重新載入 skills。

## 直接對 AI 說什麼

開始新專案時，可以輸入：

> 使用 /startup-cami-office。我的創業專案是「專案名稱」，請把資料放在 ./my-startup，Canvas 放在 ./my-startup/view。請用繁體中文帶我開始，先沿用已提供的內容，再問下一個最值得釐清的問題。

繼續填答時，可以輸入：

> 使用 /startup-cami-office，繼續 ./my-startup 的問答。先讀已保存的答案，把我這輪回答補進相關題目，再同步 Canvas。

修改便條紙時，可以輸入：

> 使用 /startup-cami-office，修改這一題的中英文 headlines 和完整答案，保留我的意思，完成後同步 YAML 與 Canvas。

AI host 負責對話與判讀，Python scripts 負責資料驗證、保存與畫面產生。

## 手動建立與啟動 Canvas

在 repository 根目錄執行：

```sh
uv run .agents/skills/startup-cami-office/scripts/startup_cami.py --project ./my-startup init --title "我的創業專案"
uv run .agents/skills/startup-cami-office/scripts/setup.py --project ./my-startup --app-dir ./my-startup/view --port 3010
cd my-startup/view
npm run dev -- --port 3010
```

開啟 http://127.0.0.1:3010/ 。專案的 `startup-cami.yaml` 保存回答，Canvas 會自動重新讀取。完整答案可點開閱讀，headlines 顯示在長方形便條紙上。

下次啟動進入 `my-startup/view`，再次執行 `npm run dev -- --port 3010`。

## 題庫與資料

預設 init 建立完整基礎題庫的空白 YAML。已有核心問答編輯稿與 mapping 的專案，可使用 `sync_core.py` 同步中英文 headlines 與答案。詳細命令與支援模式見 [使用方式](.agents/skills/startup-cami-office/references/使用方式.md)。

自己的 startup 專案資料夾請放在個人工作區。這個 repository 提供可重用的 skills、範本與 Canvas 程式。

### 改名前建立的專案

改名前建立的專案只有 `startup101.yaml`（機器狀態在 `.startup101/`），仍可照常使用：沒有 `startup-cami.yaml` 時，scripts 直接讀寫這份舊檔，Canvas 也讀取它。要改成新檔名時，先預覽再套用：

```sh
uv run .agents/skills/startup-cami-office/scripts/startup_cami.py --project ./my-startup migrate-name
uv run .agents/skills/startup-cami-office/scripts/startup_cami.py --project ./my-startup migrate-name --apply
```

套用後內容原樣改存為 `startup-cami.yaml`，舊檔移到 `.startup-cami/recovery/` 保存，不會刪除。已安裝的 Canvas 再執行一次 setup 的 `--upgrade`。兩個檔案同時存在時，scripts 會拒絕執行，先保留其中一份。細節見 [使用方式](.agents/skills/startup-cami-office/references/使用方式.md)。

## 修改 Canvas

畫布源碼在 `web/`，本地 Next app 範本在 `.agents/skills/startup-cami-office/assets/next-app/`。修改畫布後重新建置：

```sh
uv run web/build_template.py --output .agents/skills/startup-cami-office/assets/studio-template
```

既有專案要帶入新版 runtime 與畫面，依 [本地 Next setup](.agents/skills/startup-cami-office/references/本地Next-setup.md) 執行 setup 的 `--upgrade`。

## 致謝

感謝 [Cami Lu 呂緗柔](https://www.linkedin.com/in/camillialu/)。Cami 做投資，同時也做加速器，[STARTUP101](https://www.startup101.biz/) 是她的產出之一。

Skills 與 Canvas 由 [AI-Native Global Founders Speedrun Taiwan 社群](https://aifounders.tw/) 投入製作。

## 授權

原創軟體及其說明文件採 [MIT License](LICENSE)，允許使用、修改與散布，並要求保留著作權與授權聲明。教材、課程衍生內容、名稱、商標及其他第三方內容的權利由各權利人保有。
