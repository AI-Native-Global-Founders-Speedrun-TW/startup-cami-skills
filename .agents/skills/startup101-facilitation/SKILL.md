---
name: startup101-facilitation
description: 為 Startup 101 創業題庫依全題回答分布找下一個bottleneck，一次追問一個部分。先辨識核心或舊題模式，依目前問題與已存上下文協助使用者說清楚，收到 evaluator 回饋後只追問最關鍵一件事；不評分、不代使用者編造證據、不寫正式 YAML。
---
# Startup 101 Facilitation

本skill可由office調度。單獨收到有內容的回答先交回office：舊題模式整理並保存筆記後再追問；核心模式先交office霰彈式拆解至適合題目，再依更新後的分布釐清，由office明確同步，不呼叫舊note命令。原始來訊只留在對話中。已初始化專案以startup101.yaml為正式來源；先依相鄰office的模式reference判斷讀core_canvas或原questions，不把核心的來源原題當成目前必答題。Bundle只供kickoff，核心模式目前不提供正式評估與接受。

# SOP

## Phase 1 -- 準備當前問題
1. READ 讀取相鄰 `../startup101-office/references/核心問答與舊題模式.md`（模式與資料分工）、`../startup101-office/references/決策判斷與誠實回答.md`（決策與獨立複核）及 `rules/單題引導與推進.md`（單題追問判準）；核心模式讀office交付的全題回答分布、本輪片段歸屬及候選核心prompt、完整答案與追問，舊題模式才讀原題definition、requirements、audience及筆記。卡片位置依 `../startup101-office/references/post-it與原題對照.md`（問題歸屬）核對。
2. THINK 使用者選題優先；依模式reference從全題分布找下一個bottleneck，沿用已有完整內容，只選最影響當前意思或決策的一個待答部分。核心模式的換句話問／追問補入同一答案，不重新拆問來源題；舊題模式按原題與有效依賴恢復，不用同卡主問題替換所選原題。Caution只作提醒。
3. WRITE 依 `templates/question-prompt.md`（單題提示骨架）及 `templates/question-prompt.example.md`（單題提示範例）先用一句話說明為何選這個bottleneck，再顯示目前問題的英文與一個待答部分；引導使用繁體中文或英文。範例明標非使用者事實，不自行生成另一份headlines。

## Phase 2 -- 推進回答
1. READ 核心模式讀office拆解及同步後的全題分布、相關正文與使用者修改，不要求不存在的舊題筆記或評估packet；舊題模式讀office已存筆記及evaluator引用、阻擋理由與唯一追問。已有回答不重問，沒有實際評估不宣稱pass。
2. THINK 依已載入規則區分補充、撤回、改寫與未知；沿用各核心或原題識別。核心新補充整份交回office拆解到適合題目，再更新分布；舊題其他案例可對應別題時，交回相同筆記識別及相關段落，不重寫另一份筆記。不為湊便條紙追問。
3. WRITE 發出一個能改變判斷的追問，或把已充分內容交回office保存；只有外部行動能取得資訊時提出一個實驗及關鍵觀察，不無限追問。矛盾附前後文先釐清，不代為撤回；停止或延後交回office控制。核心內容可充分供編輯，不代表已正式評分或接受。
