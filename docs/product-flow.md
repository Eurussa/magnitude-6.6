# Product Flow

依據：[共用開發規格](DEVELOPMENT_SPEC.md)。以下區分目前實作與完整 Demo 目標，不能將目標流程視為已實作。

## 目標使用者

已有當日行程的自由行旅客，在睡過頭、景點休館或下雨後，需要快速比較可執行的替代安排。MVP 僅使用單一 `demo-user` 與固定東京單日行程，不包含登入、多人同行或多日最佳化。

## 使用情境

原始展示行程由 Tokyo Day 1 JSON 種子初始化至 runtime，後續載入已保存的目前行程。種子包含：09:00 淺草寺、11:00 東京國立博物館、13:00 午餐、15:00 teamLab、19:00 晚餐。午餐、teamLab 與晚餐為鎖定預約；地點、餐廳時間與交通時間均為展示 fixture，不代表已查證訂位或即時交通。

- 第一幕：09:00 輸入「睡過頭兩小時」，調整未預約景點並比較保留預約、保留景點與輕鬆程度的取捨。
- 第二幕：同日 11:00 輸入「下午開始下大雨」，根據上次選擇排序雨天方案；下午戶外候選 fixture 由 Backend B 補充，室內 teamLab 保持 15:00。
- 其他 MVP 事件：休館（closure）；詳細休館 fixture 尚待補充。

## 目前實作

1. 開啟 `/trip`，透過 `GET /api/trip` 載入 runtime 中的目前 `tokyo-demo`；`GET /api/preferences` 可讀取已保存偏好。首次讀取才由唯讀種子建立 `backend/data/runtime/state.json`。
2. 輸入文字，呼叫 `POST /api/replan`；可選 `now` 必須帶 offset，未提供時取行程當地目前時間。
3. Backend A 從同一份 runtime state 讀取行程與偏好，解析 placeholder 事件並取得正規化天氣 context，再交給 Backend B 的 planner。
4. API 回傳 `status: placeholder`、`event`、`weather`、`preferences`、`plans` 與 `warnings`；事件仍為 `unknown`，A/B/C 都沿用目前行程並顯示警告。
5. 可透過 Google Maps Search URL 開啟地點。

天氣 adapter 已移至 A 的 `agent/weather.py` 並接入 context。預設 `WEATHER_MODE=mock` 使用明確標示的 fixture；live 模式呼叫 Open-Meteo，失敗時嘗試 fixture，仍不可用時標示 unavailable。API 以 `weather.source` 區分來源，不把降雨機率當作大雨強度。

已提供行程／偏好的內部 JSON 保存介面，重啟會保留已保存內容；沒有 HTTP 任意儲存或重置 endpoint。仍未實作真正的 LLM 事件理解、重排、天氣影響排程、可行性驗證、選擇儲存、偏好學習或個人化排序，不能將 context 與儲存基礎當作完整 Demo。

## 核心流程（Demo 目標，尚未完整實作）

1. 載入已保存的目前行程與使用者偏好，顯示 timeline 與鎖定預約；首次使用才由固定種子初始化。
2. 旅客輸入事件文字；前端送出 `trip_id`、`message` 與可選的 `now`（帶 offset 的 ISO8601），請求期間顯示 loading。展示日期與已完成活動的判定仍需隨重排實作確認。
3. Backend A 的 Agent 將文字解析成 `delay`、`closure`、`weather` 或 `unknown`，經 Pydantic 驗證；睡過頭兩小時對應 delay 120 分鐘。解析失敗須明示 fallback 或錯誤，A 同時取得天氣與偏好 context。
4. Backend B 的 Replanner 接收事件、行程、天氣 context、偏好與 now，以 deterministic heuristic 產生 A 保留預約、B 保留最多景點、C 最輕鬆。B 決定天氣如何影響對應時段戶外活動，不直接呼叫外部 API 或讀寫 runtime。
5. B 計算各方案的保留／移動／取消、交通增量、費用增量、預約影響與可行性，A 依這些事實組成可讀說明供前端顯示；不可行要明示，已完成活動與預約鎖不得被偷偷改動。
6. 以 `sum(weight * feature)` 排序，同分固定 A/B/C，顯示推薦方案與偏好原因。僅 `status=ready` 且 `feasible=true` 可選擇套用。
7. 旅客選 A，前端呼叫目標 `POST /api/selections`，只送 `replan_id` 與 `plan_id`。Backend A 從保存的 snapshot 讀取方案，在同次 runtime JSON 原子更新內保存選擇、套用行程、增加 `preserve_booking` 權重與 `selection_count`；這些 snapshot 與選擇欄位仍待實作。
8. 前端依回傳的 Trip 與 Preference 更新畫面。套用僅改變本服務的行程資料，不執行外部訂位、取消或改訂。
9. 旅客輸入第二個雨天事件，A 讀取更新後的行程與偏好，天氣依 now 的行程當地日期對齊後交給 B 重新計算；優先呈現符合保留預約偏好的方案，顯示「根據你上次的選擇…」與選擇次數。
10. 透過 Google Maps link 開啟地點；不需要地圖金鑰，不提供即時交通路由。

## 例外流程

| 情況 | 行為與契約 |
|---|---|
| 空白、過長訊息、未知行程或未帶 offset 的 now | 目前 API 回傳 422；message 必須 1–2000 字且不可全空白，trip_id 僅接受 tokyo-demo |
| 行程載入失敗、網路中斷或 API 失敗 | 顯示 error，允許重試；不得將失敗呈現為已套用成功 |
| runtime JSON 損壞或讀寫失敗 | 目前 API 回傳 503，不以種子靜默覆蓋已保存資料 |
| LLM timeout 或非法 JSON | 目標為驗證失敗後回傳可辨識的 fallback，或供應商不可用時回 503；不直接使用未驗證內容 |
| 天氣 timeout 或不可用 | 目前以 `weather.source` 與 warnings 明示 `fixture` 或 `unavailable`；不能冒充即時資料，也不能將未知天氣當晴天 |
| 方案仍是 placeholder | 顯示警告，不開放套用 |
| 無可行替代方案或預約限制無解 | 目標為明示不可行並禁止套用；不可為增加景點數解除預約鎖 |
| 重複提交同一選擇 | 目標為冪等處理，不重複加分 |
| 同次 replan 改選其他方案／選擇不可行方案 | 目標 API 回傳 409 |
| 找不到方案 | 目標 API 回傳 404 |
| snapshot 的原行程版本已過期 | 目標為後端拒絕套用；錯誤碼與重新取得方案的 UI 細節待共同確認 |

錯誤不得洩漏金鑰或供應商敏感內容。人工協助、價格即時變動追蹤與外部交易失敗處理不在目前 Demo 流程內。

## 儲存與執行邊界

單一 FastAPI server 使用一個共用 RuntimeStore；`agent/` 與 `replanner/` 是同一程序的 modules。Runtime JSON 只支援單一 worker，A 使用程序鎖保護讀寫，先寫入並 fsync 暫存檔，再原子 replace 狀態檔。唯讀種子保留，runtime 不提交，不使用 DB；Demo 重置時先停服務，再移除自己的 state.json，由下一次讀取重新初始化。

`data/` 依內容分工：A 管偏好種子、天氣 fixture 與 runtime；B 管行程、候選、交通與營業時間 fixture。完整欄位、選擇限制與責任邊界見 [Domain Model](domain-model.md)。

## Demo 驗收

- 一分鐘內完成「原行程 → delay → A/B/C → 選 A → weather → 第二次個人化推薦」，整體彩排預留兩分鐘。
- 三方案呈現不同取捨；鎖定時間不變、不可行不可套用。
- 天氣影響下午戶外候選，15:00 室內 teamLab 保持不動，來源標籤清楚；離線 fixture 可完整展示。
- 選擇後可看到偏好原因與次數；相同選擇重送不重複計分，重啟後偏好仍存在。
- 驗證空字串／未知行程 422、LLM 非法 JSON、天氣 timeout 與前端錯誤恢復。

目前測試涵蓋 API 契約、runtime JSON 保存與錯誤處理、天氣 context 與 fallback，以及 placeholder 未改動預約資料；完整事件解析、真實重排、方案選擇及學習迴圈仍為待完成驗收。

## 待確認事項

- Backend A/B 與 Frontend 共同確認 Demo 日期與完成活動判定、`weather_override`、方案比較欄位與 selections 的完整增量 schema；既有可選 now 與 weather.source 沿用現行 API。
- Backend B 補下午戶外候選、交通時間、營業時間與最晚抵達資料，讓雨天替代與可行性有可測試的 fixture。
- 共同確認 unknown 事件的後續互動、過期方案錯誤回應，以及離線解析 fallback 的具體內容；規格目前只定義原則。
