# Domain Model

依據：[共用開發規格](DEVELOPMENT_SPEC.md)與[固定 API／模組契約](api-contract.md)。此文件統一產品名詞、資料關係與規則；可執行 schema 以 `backend/models.py`、`backend/contracts.py`、`/openapi.json` 與 `/docs` 為準。Schema 已固定，但 LLM 重排、snapshot 與 selection 交易仍可尚未實作，兩者必須分開理解。

## 核心名詞

### Traveler / demo-user

使用服務處理多日旅程中當日或未來事件的自由行旅客。MVP 固定為 `demo-user`，無登入、多使用者或同行者模型，API 不需傳 user_id。

### Trip

可涵蓋連續多日的行程，欄位為 `id`、`version`、`city`、`timezone`、`start_date`、`end_date`、`items`。version 為 >=1 的整數，成功套用方案時 +1，供 snapshot 避免覆蓋已變更行程。timezone 驗證為有效 IANA 時區，end_date 不得早於 start_date，item id 在整趟 Trip 中必須唯一。MVP 固定 `tokyo-demo`、Tokyo、Asia/Tokyo 與三日展示資料，但 schema 不限制只能三天；首次讀取由 JSON 種子初始化 runtime，後續 API 讀取已保存的目前行程，不再每次重載種子。RuntimeStore 已提供內部保存介面，透過 selection 套用方案仍未實作。

### TripItem（原 Itinerary Item）

行程中的景點、用餐或活動，前後端統一使用 `TripItem`。

| 欄位 | 意義／規則 |
|---|---|
| id / name | 項目識別碼／顯示名稱 |
| scheduled_date | 活動排定的當地日期，必須落在 Trip 的 start_date 至 end_date 內；整日換日會更新該日所有受影響項目的日期 |
| start_time | scheduled_date 當地的 `HH:mm`，使用 24 小時格式 |
| duration_minutes | 停留分鐘，整數且 > 0 |
| latitude / longitude | 地點座標，供 Google Maps Search URL 使用 |
| priority | 1–5 的優先程度 |
| booking | 是否有預約 |
| movable | 是否允許移動 |
| indoor | 是否為室內活動，供天氣影響判斷 |

`booking=true` 或 `movable=false` 不得靜默跨日期或移動時間；保留最多景點策略也不能解除預約鎖。已完成活動不動。活動是否完成以 `scheduled_date`、`start_time`、Trip timezone 與 now 判定。營業時間、最晚抵達、交通時間與其他限制資料尚須補齊，不代表現行 TripItem 已有對應欄位。

### Event（對應原 Disruption）

由旅客文字解析出的結構化事件：

- `event_type`：`weather`、`delay`、`closure`、`unknown`。
- `delay_minutes`：非負整數且可超過一天；「睡過頭兩小時」對應 delay 120 分鐘，跨日航班延誤也能表達。
- `affected_item_ids`：受影響的零至多個項目識別碼；空陣列表示沒有鎖定特定項目。
- `affected_dates`：受影響的零至多個當地日期，例如「後天迪士尼會下雨」可解析為迪士尼 item id 與後天日期。
- `summary`：事件摘要。

LLM 輸出須經 `Event.model_validate_json`；目前 parser 僅回傳 unknown 與空的 affected arrays。A 的 parser 可根據 message、now 與 Trip timezone 解析相對日期，並以 arrays 表達事件跨越多個日期或項目；B 不重新解析自然語言。

### WeatherContext

Replanner 的多日天氣輸入，與使用者輸入的 weather Event 分開。Backend A 的 `agent/weather.py` 從 `max(now 的行程當地日期, trip.start_date)` 取得至 `trip.end_date`，正規化 Open-Meteo hourly `precipitation_probability` 或展示 fixture，再串入 replan context；Backend B 將完整日期區間提供給 planning LLM 產生跨日方案，目前 placeholder 尚不套用天氣影響。

| 欄位 | 意義／規則 |
|---|---|
| source | `live`、`fixture` 或 `unavailable`；API 使用 `weather.source` |
| start_date / end_date / timezone | 預報涵蓋的行程日期區間與行程時區 |
| hours | 跨越 start_date 至 end_date 的 WeatherHour 列表，每筆包含帶 offset 的 `time` 及 `precipitation_probability`（0–100 或 null） |
| warnings | fixture、fallback 或不可用原因，亦呈現於 replan warnings |

`WEATHER_MODE=mock` 預設使用 `backend/data/weather.json` 中具明確日期的多日 fixture；`live` 以 start_date/end_date 呼叫 Open-Meteo。回應或 fixture 必須涵蓋要求區間的每個日期；timeout、無效或不完整時嘗試完整 fixture，fixture 也不可用則標為 unavailable。未知天氣不能當晴天，fixture 不得冒充即時資料，降雨機率也不能直接解讀為降雨強度。固定 `ReplanRequest` 不含 `weather_override`。

### ReplanContext

A 的 `agent/context.py` 從同一份 runtime state 讀取 multi-day Trip 與 Preference，組成 `trip`、`event`、`weather`、`preferences`、`now`，再交給 B。`now` 目前是 request 的可選欄位，提供時須為帶 offset 的 ISO8601；未提供時取行程當地目前時間。Trip 與每個 TripItem 都有明確日期，不再把所有活動假設成 now 當日。

### Plan（對應原 Recovery Option）

同次重排的一個候選方案，包含整趟 Trip 重排後的完整多日項目。每個 item 的 `scheduled_date` 表示重排後日期。

| id | strategy | title |
|---|---|---|
| A | preserve_booking | 保留預約 |
| B | maximize_attractions | 保留最多景點 |
| C | relaxed | 最輕鬆 |

目前 placeholder 的三方案皆沿用 runtime 行程且 `feasible=false`。固定欄位如下：

| 欄位 | 意義 |
|---|---|
| id / strategy / title / items | 固定 A/B/C 策略、顯示名稱與重排後完整 multi-day 行程 |
| feasible | 可行性；false 時不得套用 |
| changes | `PlanChange[]`，原 Trip 每個 item 各一筆 keep/move/cancel，額外項目用 add；from/to 日期時間的固定 nullable 規則見 API 契約 |
| additional_travel_minutes | 交通分鐘 delta，可為負；依 fixture 計算，不宣稱即時導航 |
| additional_cost_jpy | 日圓費用 delta，可為負；計算所需 fixture 待補 |
| booking_warnings | 預約影響與限制 |
| features | preserve_booking、maximize_attractions、relaxed 三種特徵，各 0–1，供偏好評分 |
| explanation | A 根據已驗證方案事實產生的可讀說明；B 可先留空 |

原本的 Impact 概念由 `changes`、交通／費用增量與 booking_warnings 表達，目前沒有獨立 Impact model。Backend B 的 planning LLM 產生候選方案，B 再驗證並整理這些事實與 features；Backend A 的 `agent/explanation.py` 依此產生使用者可讀說明。方案需檢查 item 日期位於 Trip 範圍、同日時間不重疊、跨日移動限制、fixture 交通時間、營業時間與最晚抵達；無效輸出應重試、fallback 或明示不可行。

### ReplanResponse / Replan snapshot

固定回應欄位為 `status`、`replan_id`、`planning_source`、`event`、`weather`、`preferences`、`plans`、`recommended_plan_id`、`preference_insight`、`warnings`。目前回 `status=placeholder`、null replan/recommendation、`planning_source=unavailable`；完成後回 ready、UUID replan_id 與 live/fixture planning source。天氣來源另由 `weather.source` 表達。

B 回傳的 `PlanningResult` 包含 `source`、排序後且剛好三個的 plans、`recommended_plan_id` 與 warnings。只要至少一個 plan feasible，就必須推薦其中一個；全都不可行時 recommendation 為 null。偏好 raw score 不屬於 `Plan`、`PlanningResult` 或 API response，只存在於 B 的 scoring 過程。

`ReplanSnapshot` 固定保存 `replan_id`、`trip_id`、`trip_version`、`planning_source`、plans、`recommended_plan_id`、`created_at`，供後端確認選擇與讀取方案特徵。A/B/C 的 id 只在同次 replan 內識別方案，選擇須同時提供 replan_id。若 Trip.version 已不同，回 409 拒絕套用。

ReplanRequest 已提供可選、帶 offset 的 ISO8601 `now`。此次尚未保存 snapshot；snapshot 自動過期時間不在 MVP 契約，先只用 trip_version 判斷 stale。

### Selection（取代獨立 Recovery Plan 概念）

旅客對一次 replan 的選擇紀錄，欄位為 `replan_id`、`plan_id`、`created_at`；每個 replan_id 最多一筆有效選擇，由 runtime 更新邏輯保證唯一。選定 Plan 後直接套用為更新後的 Trip，規格未定義另一個 RecoveryPlan model，也不執行外部預訂或取消。

- `POST /api/selections` 僅接受 replan_id 與 plan_id；後端讀取保存的方案特徵，不信任前端自報權重。
- Backend A 必須在同次 runtime 原子更新內保存選擇、套用行程、將 Trip.version +1 並更新權重；不能分成多次獨立寫入。目前 endpoint 已註冊 schema 但固定回 501，尚未實作 snapshot 或交易。
- 相同選擇重送不重複加分；同次改選回 409，找不到方案回 404，不可行方案回 409。
- 成功回傳 `selection`、更新後的 Trip 與 Preference；過期 Trip version 回 409。

### Preference

已提供 Preference Pydantic model、`GET /api/preferences` 與 Backend A 的內部保存介面。欄位為固定 `user_id: demo-user`、`weights`、`selection_count`；三權重為有限非負數，selection_count 為非負整數。唯讀種子 `backend/data/preferences.json` 的三權重皆為 1、selection_count 為 0；首次初始化後讀取 runtime 值，已保存的偏好可跨重啟保留。

偏好學習仍為目標功能：每次有效選擇將所選方案 strategy 對應權重 +1，並增加 selection_count；例如第一次選 A 後權重為 preserve_booking=2、maximize_attractions=1、relaxed=1，次數為 1。

固定方案排序公式為 `sum(weight * feature)`，同分固定 A/B/C，顯示排序原因與選擇次數。這是偏好權重更新，不是模型訓練，也不能宣稱一次選擇足以推論所有旅遊偏好；目前 placeholder 不計算評分或更新權重。

### Runtime state 與儲存邊界

`backend/data/runtime/state.json` 目前包含 `schema_version: 2`、multi-day `trip`、`preferences`；不使用 DB，runtime 不納入 Git。Version 1 缺少可靠日期資料，不自動猜測或靜默遷移；開發／Demo 可先停止服務、移除自己的舊 state，再由種子初始化。`backend/data/trip.json` 與 `preferences.json` 保持唯讀，只在首次讀取且 state 不存在時用於初始化。

Backend A 的 RuntimeStore 提供 `load_state()`、`get_trip()`、`get_preferences()`、`save_trip()`、`save_preferences()`、`save_state(trip, preferences)`；共用一個 store 的程序鎖保護讀寫，先驗證狀態、完整寫入同目錄暫存檔並 fsync，再以原子 replace 取代 state。只支援單一程序／worker，不提供跨程序交易保證。資料損壞或讀寫失敗回報 503，不靜默以種子覆蓋既有資料。

目前沒有 HTTP 任意儲存或重置 endpoint，沒有 snapshot／選擇紀錄。未來選擇流程須擴充版本與冪等檢查；不能因為已有 JSON 保存介面而宣稱學習迴圈完成。

## 模組責任與已確認介面

- 單一 FastAPI server；`agent/` 和 `replanner/` 是 Python modules，不是兩個服務。
- Backend A 擁有 agent 的 parser / prompts、context、weather、preference / runtime、explanation，以及 `main.py`、`models.py` 的整合。天氣 adapter 已從 `replanner/weather.py` 移至 `agent/weather.py`；現階段不另建 services/。
- Backend B 擁有 `replanner/planner.py`、planning prompt、LLM multi-day candidate generation、structured output 與限制驗證，以及 `scoring.py` 的 deterministic preference ranking / impact；只接收共用模型，可呼叫設定好的 LLM provider，但不讀寫 runtime、不取得天氣，也不依賴 `agent/`。
- `data/` 依內容分工：B 管多日行程、候選、交通與營業時間 fixture；A 管偏好種子、多日天氣 fixture 與 runtime。
- `parse_event(message, *, trip, now) -> Event` 仍為 placeholder，但已接收解析相對日期所需的 multi-day Trip 與 now；`candidate_plans(...)` 也只為既有主流程提供 placeholder。正式 B 介面已固定為 `await Replanner.generate_plans(context: ReplanContext) -> PlanningResult`，Protocol 位於 `backend/contracts.py`；共用 LLM client 的注入細節不屬於外層契約。`get_weather(trip, *, now) -> WeatherContext` 與 `fetch_weather(latitude, longitude, *, timezone, start_date, end_date) -> WeatherContext` 均為 async。
- B 的 planning LLM 產生 A/B/C 行程，B 驗證後回傳可檢查的方案事實、排序與 `recommended_plan_id`；A 組成推薦解釋。raw score 僅供 B 內部 deterministic 排序，不加入 API response。

## 概念關係

- MVP 只有一位 demo-user、一個固定多日 Trip 與一組 Preference。
- Trip 以 start_date/end_date 定義日期範圍，包含分布在多個 scheduled_date 的 TripItem；ReplanRequest 對整趟 Trip 提供事件文字與可選 now。
- A 解析可能影響多個日期／項目的 Event 並組裝 ReplanContext；B 接收 Trip、Event、multi-day WeatherContext、Preference 與 now，呼叫 planning LLM，產生、驗證並排序不同的跨日 A/B/C Plan。
- 每次 ready 重排保存一份 snapshot，包含三個候選 Plan 與原行程版本。
- 每份 snapshot 最多有一筆有效 Selection；選擇後更新 Trip 與 Preference，下一次事件使用更新結果。
- JSON 種子唯讀；目前行程與偏好集中於 runtime JSON，未來選擇及 snapshot 亦須與種子分開，runtime 檔不提交。

## 待確認事項

- 外層模型與 planner 參數已固定；後續變更須由 A/B/Frontend 共同確認，先改 API 契約與 ADR，再同步 Pydantic/OpenAPI 與 frontend types。
- 完成活動判定、跨日營業／抵達限制、候選景點與交通／費用 fixture 的完整格式。
- features 的實際計算方式、LLM provider/model、重試與 fallback 細節由各 backend package 實作；不得改變 0..1 的外層欄位契約。
- 選擇與 snapshot 納入 runtime JSON 後的內部 schema version 與升級方式，由 Backend A 實作時決定；外部 404/409/501/503 語意已固定。
- Frontend owner 需同步 TripItem.scheduled_date、Trip date range、Event arrays、WeatherContext date range，並將 timeline 依日期分組；本次不修改 `frontend/`。
