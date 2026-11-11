# Startup 101 本地 Next app

由 startup101-office 的 setup.py（安裝腳本）複製至使用者指定位置，附上 runtime 與本地設定。不要直接在 skill 的 assets 目錄啟動。執行 npm run dev 時僅監聽 127.0.0.1。app/api/canvas/route.js（唯讀渲染入口）呼叫既有 Python renderer；app/page.js（本地畫面）每 1.5 秒重新讀取 hash，資料變更才更新。失敗顯示錯誤並持續重試。
