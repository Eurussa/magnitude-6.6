# Product Flow

依據：[共用開發規格](DEVELOPMENT_SPEC.md)與[固定 API／模組契約](api-contract.md)。以下區分「schema／route 已存在」與「完整流程已實作」，不能因為 OpenAPI 已有欄位就把功能視為完成。

## 目標使用者

已有多日行程的自由行旅客，在睡過頭、景點休館或未來某日天氣轉差後，需要快速比較整趟旅程可執行的替代安排。MVP 僅使用單一 `demo-user` 與固定東京三日行程，不包含登入、多人同行、跨城市或任意長期規劃。

## 使用情境

原始展示行程由 Tokyo 三日 JSON 種子初始化至 runtime，後續載入已保存的目前行程。9/12 包含淺草寺、東京國立博物館、午餐、teamLab 與晚餐；9/13 包含明治神宮、原宿／表參道與澀谷；9/14 為東京迪士尼樂園整日。午餐、teamLab 與晚餐為鎖定預約；地點、時間、天氣與交通均為展示 fixture，不代表已查證訂位或即時資料。

- 第一幕：09:00 輸入「睡過頭兩小時」，調整未預約景點並比較保留預約、保留景點與輕鬆程度的取捨。
- 第二幕：接近 9/14 時輸入「後天迪士尼會下大雨，可以和其他天交換嗎？」；mock weather 顯示 9/14 明顯較雨、9/13 較乾。B 的 planning LLM 可將迪士尼整日移至 9/13，並重新分配原本 9/13 的行程，再根據上次選擇排序方案。
- 其他 MVP 事件：休館（closure）；詳細休館 fixture 尚待補充。

## 目前實作

1. 開啟 `/trip`，透過 `GET /api/trip` 載入 runtime 中的目前 multi-day `tokyo-demo`；`GET /api/preferences` 可讀取已保存偏好。首次讀取才由唯讀種子建立 schema version 2 的 `backend/data/runtime/state.json`。
2. 輸入文字，呼叫 `POST /api/replan`；可選 `now` 必須帶 offset，未提供時取行程當地目前時間。
3. Backend A 從同一份 runtime state 讀取多日行程與偏好，解析 placeholder 事件並取得涵蓋 Trip 未來日期區間的正規化天氣 context，再交給 Backend B 的 planner。
4. API 回傳完整 `ReplanResponse`；目前為 `status=placeholder`、null replan/recommendation、`planning_source=unavailable`。事件仍為 `unknown`，A/B/C 都沿用完整多日行程、標示 `feasible=false` 並顯示警告。
5. 可透過 Google Maps Search URL 開啟地點。
6. `POST /api/selections` 已註冊 `SelectionRequest`／`SelectionResponse` 與錯誤 schema，但在 snapshot 與原子套用完成前固定回 501。

天氣 adapter 已移至 A 的 `agent/weather.py` 並接入 context。預設 `WEATHER_MODE=mock` 使用具明確日期且涵蓋三日的 fixture；live 模式以 date range 呼叫 Open-Meteo，失敗時嘗試完整 fixture，仍不可用時標示 unavailable。API 以 `weather.source` 區分來源，並以 `start_date`／`end_date` 表示涵蓋區間；不把降雨機率當作大雨強度。

已提供行程／偏好的內部 JSON 保存介面，重啟會保留已保存內容；沒有 HTTP 任意儲存或重置 endpoint。仍未實作真正的 LLM 事件理解、LLM 行程重排、天氣影響方案、可行性驗證、snapshot、選擇交易、偏好學習或個人化排序，不能將 contract、context 與儲存基礎當作完整 Demo。

## 核心流程（Demo 目標，尚未完整實作）

1. 載入已保存的目前多日行程與使用者偏好，依 `scheduled_date` 分組顯示 timeline 與鎖定預約；首次使用才由固定種子初始化。
2. 旅客輸入事件文字；前端送出 `trip_id`、`message` 與可選的 `now`（帶 offset 的 ISO8601），請求期間顯示 loading。展示日期與已完成活動的判定仍需隨重排實作確認。
3. Backend A 的 Agent 將文字解析成 `delay`、`closure`、`weather` 或 `unknown`，並以 `affected_item_ids`／`affected_dates` 表達跨項目與跨日期影響，再經 Pydantic 驗證；睡過頭兩小時對應 delay 120 分鐘，「後天」依 now 與 Trip timezone 解析。解析失敗須明示 fallback 或錯誤，A 同時取得多日天氣與偏好 context。
4. Backend A 以固定 `ReplanContext` 呼叫 `await Replanner.generate_plans(context)`；Backend B 接收事件、完整多日行程、日期區間天氣 context、偏好與 now，呼叫 planning LLM 產生 A 保留預約、B 保留最多景點、C 最輕鬆。B 擁有 planning prompt 與 structured output，不直接取得天氣或讀寫 runtime。
5. B 將 LLM 回應驗證成結構化方案，檢查日期範圍、項目參照、同日時間、跨日移動與必要限制，並整理各方案的保留／移動／取消、交通增量、費用增量、預約影響、features 與可行性。方案可以整批更新某日項目的 `scheduled_date`，例如交換迪士尼日與原本 9/13 的安排；無效輸出應重試、fallback 或明示錯誤，不可直接當作 ready。A 依這些事實組成可讀說明供前端顯示。
6. B 以 `sum(weight * feature)` 計算內部 score 並排序，同分固定 A/B/C；對外只提供排序後的 plans 與 `recommended_plan_id`，不回傳 raw score。前端顯示推薦方案與偏好原因，僅 `status=ready` 且 `feasible=true` 可選擇套用。
7. 旅客選 A，前端呼叫 `POST /api/selections`，只送 `replan_id` 與 `plan_id`。Backend A 從保存的 snapshot 讀取方案，在同次 runtime JSON 原子更新內保存選擇、套用行程、將 Trip.version +1、增加 `preserve_booking` 權重與 `selection_count`；schema 已固定，snapshot 與交易仍待實作。
8. 前端依 `SelectionResponse` 中的 SelectionRecord、Trip 與 Preference 更新畫面。套用僅改變本服務的行程資料，不執行外部訂位、取消或改訂。
9. 旅客輸入第二個迪士尼雨天事件，A 讀取更新後的多日行程與偏好，取得剩餘 Trip 日期的天氣後交給 B 重新規劃；優先呈現符合保留預約偏好的跨日方案，顯示「根據你上次的選擇…」與選擇次數。
10. 透過 Google Maps link 開啟地點；不需要地圖金鑰，不提供即時交通路由。

## 例外流程

| 情況 | 行為與契約 |
|---|---|
| 空白、過長訊息、未知行程或未帶 offset 的 now | 目前 API 回傳 422；message 必須 1–2000 字且不可全空白，trip_id 僅接受 tokyo-demo |
| 行程載入失敗、網路中斷或 API 失敗 | 顯示 error，允許重試；不得將失敗呈現為已套用成功 |
| runtime JSON 損壞或讀寫失敗 | 目前 API 回傳 503，不以種子靜默覆蓋已保存資料 |
| 事件或 planning LLM timeout／非法 JSON | 驗證失敗後重試、回傳可辨識且明確標示的 fallback，或供應商不可用時回 503；不直接使用未驗證內容 |
| 多日天氣 timeout、不完整或不可用 | 目前以 `weather.source` 與 warnings 明示 `fixture` 或 `unavailable`；date range 必須涵蓋要求的每個日期，不能冒充即時資料，也不能將未知天氣當晴天 |
| 方案仍是 placeholder | 顯示警告，不開放套用 |
| 無可行替代方案或預約限制無解 | 目標為明示不可行並禁止套用；不可為增加景點數解除預約鎖 |
| selection 功能尚未實作 | 目前 `POST /api/selections` 回傳 501；Frontend 不得顯示為套用成功 |
| 重複提交同一選擇 | 完成後以同一成功結果冪等回 200，不重複加分 |
| 同次 replan 改選其他方案／選擇不可行方案 | 409 |
| snapshot 或 plan 不存在 | 404 |
| snapshot 的 Trip.version 已過期 | 409，Frontend 重新呼叫 replan 取得新方案 |

錯誤不得洩漏金鑰或供應商敏感內容。人工協助、價格即時變動追蹤與外部交易失敗處理不在目前 Demo 流程內。

## 儲存與執行邊界

單一 FastAPI server 使用一個共用 RuntimeStore；`agent/` 與 `replanner/` 是同一程序的 modules。Runtime JSON schema version 2 保存 multi-day Trip，只支援單一 worker；A 使用程序鎖保護讀寫，先寫入並 fsync 暫存檔，再原子 replace 狀態檔。Version 1 不自動猜測活動日期；開發／Demo 升級時先停服務，再移除自己的舊 state.json，由多日種子重新初始化。唯讀種子保留，runtime 不提交，不使用 DB。

`data/` 依內容分工：A 管偏好種子、天氣 fixture 與 runtime；B 管行程、候選、交通與營業時間 fixture。完整欄位、選擇限制與責任邊界見 [Domain Model](domain-model.md)。

## Demo 驗收

- 一分鐘內完成「多日原行程 → delay → A/B/C → 選 A → 迪士尼雨天 → 第二次跨日個人化推薦」，整體彩排預留兩分鐘。
- 三方案呈現不同跨日取捨；鎖定日期／時間不變、不可行不可套用。
- 天氣影響 9/14 迪士尼，至少一個方案能將迪士尼整日移到較乾燥日期並合理重排交換日；來源與日期區間標籤清楚，離線 fixture 可完整展示。
- 選擇後可看到偏好原因與次數；相同選擇重送不重複計分，重啟後偏好仍存在。
- 驗證空字串／未知行程 422、事件與 planning LLM 非法 JSON／timeout、天氣 timeout 與前端錯誤恢復。

目前後端測試涵蓋 multi-day schema、API 契約、runtime JSON 保存與錯誤處理、多日天氣 context 與 fallback，以及 placeholder 未改動完整行程；完整事件解析、planning LLM 跨日重排、方案選擇及學習迴圈仍為待完成驗收。

## 待確認事項

- 外層 API 與 A/B module schema 已固定；若新增 `weather_override` 或欄位，必須視為契約變更，由 A/B/Frontend 共同確認並先更新文件／Pydantic。
- Backend B 補下午戶外候選、交通時間、營業時間、最晚抵達資料與 planning fallback，使雨天替代、LLM 輸出驗證與可行性可離線測試。
- 共同確認 unknown 事件的後續互動、完成活動判定與離線解析 fallback 的具體內容；404/409/501/503 外層錯誤語意已固定。
- Frontend owner 需依外層契約同步 multi-day types，並按 scheduled_date 分組呈現 Trip／Plan；本次不修改 `frontend/`。
