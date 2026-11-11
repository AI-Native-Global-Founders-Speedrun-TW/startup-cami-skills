# Startup 101 Canvas

用 AI 陪創業者把問題想清楚，將回答、headlines 與評估保存在本地 YAML，再透過 Canvas 閱讀。介面支援繁體中文與英文。

## 包含哪些 Skills

| Skill | 使用時機與工作 |
| --- | --- |
| [startup101-office](.agents/skills/startup101-office/SKILL.md) | 開始或繼續問答，整理回答、保存 YAML、同步與啟動 Canvas |
| [startup101-facilitation](.agents/skills/startup101-facilitation/SKILL.md) | 沿用已有回答，找出下一個值得釐清的問題 |
| [startup101-evaluate](.agents/skills/startup101-evaluate/SKILL.md) | 評估受支援格式的完整回答，檢查清楚程度、具體內容與證據 |

流程為 office 定位與保存 → facilitation 引導回答 → evaluate 評估支援的題型 → office 保存與同步 Canvas。

Office 維護共同資料，讓引導與評估接續同一份回答。Facilitation 負責提問，evaluate 負責評估。核心問答顯示「已填」，原題模式另有正式評估流程。

## 安裝到 AI 工具

需要 Python 3.11 以上、[uv](https://docs.astral.sh/uv/getting-started/installation/)、Node.js 20.9 以上與 npm。

```sh
git clone git@github.com:AI-Native-Global-Founders-Speedrun-TW/startup101-cami-skills.git
cd startup101-cami-skills
```

在支援專案 skills 的 AI 工具中開啟這個 repository，讓它載入 `.agents/skills/` 下的三支 skills。三個目錄須放在同一層，供彼此讀取相鄰 skill。

要用在另一個專案，可以將三個目錄一起複製或連結到該專案的 `.agents/skills/`，再依 AI 工具設定重新載入 skills。

## 直接對 AI 說什麼

開始新專案時，可以輸入：

> 使用 /startup101-office。我的創業專案是「專案名稱」，請把資料放在 ./my-startup，Canvas 放在 ./my-startup/view。請用繁體中文帶我開始，先沿用已提供的內容，再問下一個最值得釐清的問題。

繼續填答時，可以輸入：

> 使用 /startup101-office，繼續 ./my-startup 的問答。先讀已保存的答案，把我這輪回答補進相關題目，再同步 Canvas。

修改便條紙時，可以輸入：

> 使用 /startup101-office，修改這一題的中英文 headlines 和完整答案，保留我的意思，完成後同步 YAML 與 Canvas。

AI host 負責對話與判讀，Python scripts 負責資料驗證、保存與畫面產生。

## 手動建立與啟動 Canvas

在 repository 根目錄執行：

```sh
uv run .agents/skills/startup101-office/scripts/startup101.py --project ./my-startup init --title "我的創業專案"
uv run .agents/skills/startup101-office/scripts/setup.py --project ./my-startup --app-dir ./my-startup/view --port 3010
cd my-startup/view
npm run dev -- --port 3010
```

開啟 http://127.0.0.1:3010/ 。專案的 `startup101.yaml` 保存回答，Canvas 會自動重新讀取。完整答案可點開閱讀，headlines 顯示在長方形便條紙上。

下次啟動進入 `my-startup/view`，再次執行 `npm run dev -- --port 3010`。

## 題庫與資料

預設 init 建立完整基礎題庫的空白 YAML。已有核心問答編輯稿與 mapping 的專案，可使用 `sync_core.py` 同步中英文 headlines 與答案。詳細命令與支援模式見 [使用方式](.agents/skills/startup101-office/references/使用方式.md)。

自己的 startup 專案資料夾請放在個人工作區。這個 repository 提供可重用的 skills、範本與 Canvas 程式。

## 修改 Canvas

畫布源碼在 `web/`，本地 Next app 範本在 `.agents/skills/startup101-office/assets/next-app/`。修改畫布後重新建置：

```sh
uv run web/build_template.py --output .agents/skills/startup101-office/assets/studio-template
```

既有專案要帶入新版 runtime 與畫面，依 [本地 Next setup](.agents/skills/startup101-office/references/本地Next-setup.md) 執行 setup 的 `--upgrade`。

## 致謝

感謝 [Cami Lu 呂緗柔](https://www.linkedin.com/in/camillialu/) 提供創業教學與實務 know-how，成為這份問答與 Canvas 的知識基礎。感謝 [STARTUP101 新創101](https://www.startup101.biz/) 持續提供新創輔導、加速資源，並鏈結企業與投資人。

Skills 與 Canvas 由 [AI-Native Global Founders Speedrun Taiwan 社群](https://aifounders.tw/) 投入製作。

## 授權

原創軟體及其說明文件採 [MIT License](LICENSE)，允許使用、修改與散布，並要求保留著作權與授權聲明。教材、課程衍生內容、名稱、商標及其他第三方內容的權利由各權利人保有。
