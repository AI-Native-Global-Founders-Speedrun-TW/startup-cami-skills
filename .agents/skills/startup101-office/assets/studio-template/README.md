# Studio 唯讀 HTML 樣板

此 bundle 由 web/build_template.py 產生；修改源 UI 後重建，不手改生成檔。

入口 canvas.html.jinja（畫布樣板）只取 model_json。它必須由 renderer 做 HTML script-safe JSON 序列化並標記可信輸出；其他內容不得使用 safe 或再次編譯為 template。

資料契約：project、categories、questions、cautions、answers（以 question id 為 key，含 text/status/scores/claims/revision）、readonly=true、source（revision/sha256）、template_version、locale、clusters、interviewNotes（整理後的詳細筆記與相關題識別）、pendingAnswers（來源核對過的待評估正文）、keyPoints（原題與 formal／pending 分開，來源 hash 相符的短重點）。catalog 原題與正式回答來自專案 pinned 資料；clusters 是獨立呈現對照，只有來源 checksum 相容才載入，132 張卡片的座標由 presentation 重新排版，不改正式題庫。沒有網路請求、儲存或回寫操作。

coreMode=true 時，使用同份 YAML 的核心問答呈現層：categories 與 questions 決定使用中的十項主題、20 張卡片；coreContent.categories、question.prompt、answer.textI18n 與 keyPoints.formal.pointsI18n 提供完整中英文內容。alternateQuestions 與 followups 收在題目面板，不另計填答數。saved 只代表答案已保存，進度依有無回答計算，不沿用原題分數或宣稱新回答已通過；未啟用 coreMode 的專案沿用原有132張卡片／351題與有效評估進度。

CSS、JavaScript、SVG 插畫均內嵌；file URL 不需 host service。答案使用 escaped HTML 呈現，範例不當成答案。上下文下載是衍生文字，不是正式 YAML 備份。重新產生 HTML 才會反映 YAML 的修改。
