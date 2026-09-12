# Product Flow

## 目標使用者與情境

自由行旅客在既定旅程中遇到睡過頭、休館或下雨，希望快速比較調整方式。五小時 MVP 固定單一 `demo-user` 與 Tokyo 單日 JSON 行程，不需要匯入行程、登入或多人協作。

## 目標 Demo 流程

1. 開啟行程頁，後端從 runtime 讀取目前 Trip；首次由唯讀種子初始化。
2. 輸入「睡過頭兩小時」。Backend A 解析並驗證事件，組裝天氣與偏好 context。
3. Backend B 生成 A 保留預約、B 保留最多景點、C 最輕鬆的 deterministic candidates，檢查可行性並計算 impact / scoring。
4. A 依方案事實組成說明，保存候選 snapshot；前端呈現時間、取捨、預約影響、來源與錯誤狀態。
5. 使用者選擇 ready 且 feasible 的方案；目標 API `/api/selections` 傳送 `replan_id` 與 `plan_id`。A 從保存方案取得特徵，同次保存目前 Trip、選擇與更新後偏好。
6. 輸入「下午開始下大雨」，A 提供時間對齊且清楚標示 live / fixture / unavailable 的天氣 context；B 僅調整對應時段戶外活動並保留預約限制。
7. 第二次排序使用保存偏好，顯示推薦理由；使用者可透過 Google Maps link 查看地點。

本服務提供建議並更新 Demo 行程，不代訂、不改訂、不取消真實預約。偏好學習是三策略權重更新，不是訓練模型。

## 現況與完成界線

已可查看目前行程、讀取偏好、輸入事件、顯示沿用目前行程的 placeholder A/B/C 及開啟 Google Maps。此次架構調整建立 A/B context 介面、天氣 fixture / live adapter 與 runtime JSON 行程／偏好讀寫；LLM 事件理解、真正 deterministic 重排、可行性驗證、選擇 endpoint 與第二次個人化推薦仍是後續實作目標。前端不能將 placeholder 當作可套用方案。

完成標準是一分鐘內展示「原行程 → 事件 → 不同方案 → 選擇 → 第二次個人化推薦」，並在重啟後保留偏好。詳細目標與測試見 `DEVELOPMENT_SPEC.md`。

## 例外流程

- 輸入空白或未知行程：顯示驗證錯誤，保留使用者輸入供修正。
- LLM 格式錯誤／timeout：目標為明示解析 fallback；不可把原文包裝成已成功理解的事件。
- 天氣不可用：顯示 fixture / fallback 或錯誤；未知天氣不能解讀為晴天，fixture 不冒充即時預報。
- 無可行替代方案：目標為說明限制，不允許套用不可行方案或靜默改動預約鎖。
- 候選已過期或同次改選：目標選擇 API 拒絕並提示重新取得方案；相同選擇重送不重複加權。
- runtime JSON 無法讀寫或內容損壞：回傳服務錯誤，不以種子靜默覆蓋已保存資料。
- 網路失敗：顯示可重試狀態，避免重複套用；離線展示使用明確標示的 fixture。
