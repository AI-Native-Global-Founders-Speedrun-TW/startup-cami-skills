---
name: startup101-evaluate
description: 嚴格評估Startup 101受支援packet的完整單題回答，質疑前提與證據、逐維 scoring，給出一針見血的 feedback。判斷回答是否清楚可記錄而非預測創業成功；唯讀輸入，不改答案、不寫正式 YAML。
---
# Startup 101 Evaluate

保留 gstack-ceo 式前提質疑、具體行為與反證要求；不沿用人格評比、固定追打次數或工程完整性分數。這些判準已內化於本 bundle，執行不需安裝 gstack。

# SOP

## Phase 1 -- 評估當前候選
1. READ 先讀相鄰 `../startup101-office/references/核心問答與舊題模式.md`（模式與資料分工）。核心模式沒有受支援的評估packet與accept時，直接交回office說明此能力未支援，不構造可接受的EvaluationResult、不把原題分數套給核心；只有舊題模式的有效packet才繼續。讀取相鄰 `../startup101-office/references/決策判斷與誠實回答.md`（決策判斷與獨立複核）；盲審時不得讀第一份 verdict、分數或結論。讀取 office 的 EvaluationPacket、對應專案 YAML 的 rules.rubric（四維評分判準）與當前題 requirements（逐題通過要求）；讀取 `rules/回答評分與放行.md`（評分與證據規則）及相鄰 `../startup101-office/contracts/runtime-contract.json`（執行資料契約）。
2. THINK 評估對象是完整候選，不能用headlines代替。長度、條數與外觀不改scoring；只收到headlines時請office補正文，不能猜分。按本題核對候選、packet 內筆記識別與整理稿段落；分清顧問親見、客戶轉述、產品構想與預期數字。筆記是創辦人提供的內容經整理後的紀錄，不能當作逐字引文、外部查核或其他題目已通過。引用不足時請 office 補足筆記上下文。feedback、評估與證據引用只用繁體中文或英文，不將原話另存。核對來源與依賴是否足夠，逐項判斷 required parts、四維分數、主張證據及矛盾；缺 packet 資訊回 needs_context 且 scores/score_reasons 為 null，不自行補造或把未知打成零分。
3. WRITE 依契約產生 EvaluationResult JSON；以 `templates/feedback.md`（回饋骨架）與 `templates/feedback.example.md`（回饋範例）生成 pass/revise 的短回饋；needs_context 改讀 `templates/context-feedback.md`（缺資料回饋骨架）與 `templates/context-feedback.example.md`（缺資料回饋範例），交給 office 統一呈現，不另外開一串問題。

## Phase 2 -- 校準並交回
1. READ 首次評估、rubric 升級或 verdict 邊界不清時讀取 `references/校準案例.md`（評分校準案例），對照已載入判準，不把示例數字當真實證據。
2. THINK 檢查分數與理由是否一致、是否因拒絕 AI 而扣分、是否把假設當事實；完整答案立即給 pass，不為嚴厲而找錯；這只是本 evaluator 的評估，最終接受由 office 依複核 gate 判斷。另向 office 交代對當前決策的證據、缺少資訊與什麼會改判，不新增成功分數。
3. WRITE 將校準後的唯一 EvaluationResult 交回 office；pass 的 next_question 為 null，非阻斷建議不得混成 blocker。
