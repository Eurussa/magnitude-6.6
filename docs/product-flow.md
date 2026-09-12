# Product Flow

依據：[共用開發規格](DEVELOPMENT_SPEC.md)。以下區分初始化現況與完整 Demo 目標，不能將目標流程視為已實作。

## 目標使用者

已有當日行程的自由行旅客，在睡過頭、景點休館或下雨後，需要快速比較可執行的替代安排。MVP 僅使用單一 `demo-user` 與固定東京單日行程，不包含登入、多人同行或多日最佳化。

## 使用情境

原行程由 Tokyo Day 1 JSON 載入：09:00 淺草寺、11:00 東京國立博物館、13:00 午餐、15:00 teamLab、19:00 晚餐。午餐、teamLab 與晚餐為鎖定預約；地點、餐廳時間與交通時間均為展示 fixture，不代表已查證訂位或即時交通。

- 第一幕：09:00 輸入「睡過頭兩小時」，調整未預約景點並比較保留預約、保留景點與輕鬆程度的取捨。
- 第二幕：同日 11:00 輸入「下午開始下大雨」，根據上次選擇排序雨天方案；下午戶外候選 fixture 由 Backend B 補充，室內 teamLab 保持 15:00。
- 其他 MVP 事件：休館（closure）；詳細休館 fixture 尚待補充。

## 初始化現況

1. 開啟 `/trip`，透過 `GET /api/trip` 載入 `tokyo-demo`。
2. 輸入文字，呼叫 `POST /api/replan`。
3. API 回傳 `status: placeholder`，事件為 `unknown`，A/B/C 都沿用原行程並顯示警告。
4. 可透過 Google Maps Search URL 開啟地點。

目前沒有真正的事件解析、重排、天氣套用、選擇儲存或個人化排序。獨立天氣 adapter 尚未接入此流程。

## 核心流程（Demo 目標，尚未完整實作）

1. 載入固定行程與使用者偏好，顯示 timeline 與鎖定預約。
2. 旅客輸入事件文字；前端送出 `trip_id`、`message` 與目標契約的 `now`（帶 offset 的 ISO8601），請求期間顯示 loading。
3. Agent 將文字解析成 `delay`、`closure`、`weather` 或 `unknown`，經 Pydantic 驗證；睡過頭兩小時對應 delay 120 分鐘。解析失敗須明示 fallback 或錯誤。
4. Replanner 結合事件、行程、天氣 context 與偏好，以 deterministic heuristic 產生 A 保留預約、B 保留最多景點、C 最輕鬆。天氣只影響對應時段的戶外活動。
5. 顯示各方案的保留／移動／取消與原因、交通增量、費用增量、預約影響與可行性；不可行要明示，已完成活動與預約鎖不得被偷偷改動。
6. 以 `sum(weight * feature)` 排序，同分固定 A/B/C，顯示推薦方案與偏好原因。僅 `status=ready` 且 `feasible=true` 可選擇套用。
7. 旅客選 A，前端呼叫目標 `POST /api/selections`，只送 `replan_id` 與 `plan_id`。後端從保存的 snapshot 讀取方案，於同一交易保存選擇、套用行程、增加 `preserve_booking` 權重與 `selection_count`。
8. 前端依回傳的 Trip 與 Preference 更新畫面。套用僅改變本服務的行程資料，不執行外部訂位、取消或改訂。
9. 旅客輸入第二個雨天事件，對更新後的行程重新計算；優先呈現符合保留預約偏好的方案，顯示「根據你上次的選擇…」與選擇次數。
10. 透過 Google Maps link 開啟地點；不需要地圖金鑰，不提供即時交通路由。

## 例外流程

| 情況 | 行為與契約 |
|---|---|
| 空白、過長訊息或未知行程 | 目前 API 回傳 422；message 必須 1–2000 字且不可全空白，trip_id 僅接受 tokyo-demo |
| 行程載入失敗、網路中斷或 API 失敗 | 顯示 error，允許重試；不得將失敗呈現為已套用成功 |
| LLM timeout 或非法 JSON | 驗證失敗後回傳可辨識的 fallback，或供應商不可用時回 503；不直接使用未驗證內容 |
| 天氣 timeout 或不可用 | 明示 `fixture` 或 `unavailable`；不能冒充即時資料，也不能將未知天氣當晴天 |
| 方案仍是 placeholder | 顯示警告，不開放套用 |
| 無可行替代方案或預約限制無解 | 明示不可行並禁止套用；不可為增加景點數解除預約鎖 |
| 重複提交同一選擇 | 目標為冪等處理，不重複加分 |
| 同次 replan 改選其他方案／選擇不可行方案 | 目標 API 回傳 409 |
| 找不到方案 | 目標 API 回傳 404 |
| snapshot 的原行程版本已過期 | 後端拒絕套用；錯誤碼與重新取得方案的 UI 細節待共同確認 |

錯誤不得洩漏金鑰或供應商敏感內容。人工協助、價格即時變動追蹤與外部交易失敗處理不在目前 Demo 流程內。

## Demo 驗收

- 一分鐘內完成「原行程 → delay → A/B/C → 選 A → weather → 第二次個人化推薦」，整體彩排預留兩分鐘。
- 三方案呈現不同取捨；鎖定時間不變、不可行不可套用。
- 天氣影響下午戶外候選，15:00 室內 teamLab 保持不動，來源標籤清楚；離線 fixture 可完整展示。
- 選擇後可看到偏好原因與次數；相同選擇重送不重複計分，重啟後偏好仍存在。
- 驗證空字串／未知行程 422、LLM 非法 JSON、天氣 timeout 與前端錯誤恢復。

初始化只驗證既有 API 契約及 placeholder 未改動預約資料，其餘為待完成驗收。

## 待確認事項

- Backend A/B 與 Frontend 共同確認 `now`、`weather_override`、方案比較欄位與 selections 的完整增量 schema。
- Backend B 補下午戶外候選、交通時間、營業時間與最晚抵達資料，讓雨天替代與可行性有可測試的 fixture。
- 共同確認 unknown 事件的後續互動、過期方案錯誤回應，以及離線解析 fallback 的具體內容；規格目前只定義原則。
