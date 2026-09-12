# Domain Model

依據：[共用開發規格](DEVELOPMENT_SPEC.md)。此文件統一產品名詞、資料關係與規則，不另行定義 API 或資料庫 schema。現行可執行 schema 以 `backend/models.py`、`/openapi.json` 與 `/docs` 為準；標為「目標」的內容尚未實作或仍待共同確認。

## 核心名詞

### Traveler / demo-user

使用服務處理當日行程異常的自由行旅客。MVP 固定為 `demo-user`，無登入、多使用者或同行者模型，API 不需傳 user_id。

### Trip

單日行程，欄位為 `id`、`city`、`timezone`、`items`，timezone 驗證為有效 IANA 時區。MVP 固定 `tokyo-demo`、Tokyo、Asia/Tokyo；首次讀取由 JSON 種子初始化 runtime，後續 API 讀取已保存的目前行程，不再每次重載種子。RuntimeStore 已提供內部保存介面，透過選擇 endpoint 套用方案仍屬目標功能。

### TripItem（原 Itinerary Item）

行程中的景點、用餐或活動，前後端統一使用 `TripItem`。

| 欄位 | 意義／規則 |
|---|---|
| id / name | 項目識別碼／顯示名稱 |
| start_time | 行程當地時間 `HH:mm`；現行 model 為 string，格式語意依規格 |
| duration_minutes | 停留分鐘，整數且 > 0 |
| latitude / longitude | 地點座標，供 Google Maps Search URL 使用 |
| priority | 1–5 的優先程度 |
| booking | 是否有預約 |
| movable | 是否允許移動 |
| indoor | 是否為室內活動，供天氣影響判斷 |

`booking=true` 或 `movable=false` 不得靜默移動；保留最多景點策略也不能解除預約鎖。已完成活動不動。營業時間、最晚抵達、交通時間與完成判定所需資料尚須補齊，不代表現行 TripItem 已有對應欄位。

### Event（對應原 Disruption）

由旅客文字解析出的結構化事件：

- `event_type`：`weather`、`delay`、`closure`、`unknown`。
- `delay_minutes`：0–1440 的整數；「睡過頭兩小時」的目標解析為 delay 120 分鐘。
- `affected_item_id`：可為 null 的受影響項目識別碼。
- `summary`：事件摘要。

LLM 輸出須經 `Event.model_validate_json`；目前 parser 僅回傳 unknown。Event 目前只有單一 nullable 項目參照，但事件可能影響多個後續活動，影響結果由各 Plan 說明；不自行新增 affected_item_ids。

### WeatherContext

Replanner 的天氣輸入，與使用者輸入的 weather Event 分開。Backend A 的 `agent/weather.py` 取得並正規化 Open-Meteo hourly `precipitation_probability` 或展示 fixture，已串入 replan context；Backend B 未來依此判斷相應時段戶外活動，目前 placeholder 尚不套用天氣影響。

| 欄位 | 意義／規則 |
|---|---|
| source | `live`、`fixture` 或 `unavailable`；API 使用 `weather.source` |
| date / timezone | 預報適用日期及行程時區；將 request.now 換算至行程時區後取日期 |
| hours | WeatherHour 列表，每筆包含帶 offset 的 `time` 及 `precipitation_probability`（0–100 或 null） |
| warnings | fixture、fallback 或不可用原因，亦呈現於 replan warnings |

`WEATHER_MODE=mock` 預設使用 `backend/data/weather.json`，將逐時 fixture 套用至該日期；`live` 呼叫 Open-Meteo，timeout、無效或無可用預報時嘗試 fixture，fixture 也不可用則標為 unavailable。未知天氣不能當晴天，fixture 不得冒充即時資料，降雨機率也不能直接解讀為降雨強度。Demo 專用 weather_override schema 仍待確認。

### ReplanContext

A 的 `agent/context.py` 從同一份 runtime state 讀取 Trip 與 Preference，組成 `trip`、`event`、`weather`、`preferences`、`now`，再交給 B。`now` 目前是 request 的可選欄位，提供時須為帶 offset 的 ISO8601；未提供時取行程當地目前時間。這是展示日期的預設，不表示無日期的 Trip 就是實際當日行程。

### Plan（對應原 Recovery Option）

同次重排的一個候選方案。現有欄位：`id`、`strategy`、`title`、`items`、`explanation`。

| id | strategy | title |
|---|---|---|
| A | preserve_booking | 保留預約 |
| B | maximize_attractions | 保留最多景點 |
| C | relaxed | 最輕鬆 |

目前三方案皆沿用 runtime 的目前行程，尚未驗證可行性。目標增量如下：

| 欄位 | 目標意義 |
|---|---|
| feasible | 可行性；false 時不得套用 |
| changes | 每項 `item_id/action/reason`，說明保留、移動、取消；action enum 尚待確認 |
| additional_travel_minutes | 交通增量，依 fixture 計算，不宣稱即時導航 |
| additional_cost_jpy | 費用增量，以日圓表示；計算所需 fixture 待補 |
| booking_warnings | 預約影響與限制 |
| features | preserve_booking、maximize_attractions、relaxed 三種特徵，各 0–1，供偏好評分 |

原本的 Impact 概念由 `changes`、交通／費用增量與 booking_warnings 表達，目前沒有獨立 Impact model。Backend B 負責計算這些事實與 features，Backend A 的 `agent/explanation.py` 依此產生使用者可讀說明。方案需檢查時間不重疊、fixture 交通時間、營業時間與最晚抵達；無解必須明示不可行。

### ReplanResponse / Replan snapshot

現有回應為 `status: placeholder`、`event`、`weather`、`preferences`、`plans`、`warnings`。目標完成時為 `status: ready`，增加 `replan_id`（UUID）、`recommended_plan_id`、`preference_insight`；天氣來源沿用 `weather.source`，不另加重複的 weather_source 欄位。

目標 snapshot 保存 `replan_id`、原行程版本、plans、created_at，供後端確認選擇與讀取方案特徵。A/B/C 的 id 只在同次 replan 內識別方案，選擇須同時提供 replan_id。若原行程版本已過期，拒絕套用。

ReplanRequest 已提供可選、帶 offset 的 ISO8601 `now`；Demo `weather_override`、行程版本表示方式、snapshot 有效期與完整 schema 尚待確認。此次尚未保存 snapshot。

### Selection（目標；取代獨立 Recovery Plan 概念）

旅客對一次 replan 的選擇紀錄，目標欄位為 `replan_id`、`plan_id`、`created_at`；每個 replan_id 最多一筆有效選擇，由 runtime 更新邏輯保證唯一。選定 Plan 後直接套用為更新後的 Trip，規格未定義另一個 RecoveryPlan model，也不執行外部預訂或取消。

- `POST /api/selections` 僅接受 replan_id 與 plan_id；後端讀取保存的方案特徵，不信任前端自報權重。
- Backend A 必須在同次 runtime 原子更新內保存選擇、套用行程、更新權重；不能分成多次獨立寫入。此次尚未實作選擇 endpoint 或選擇紀錄，後續需擴充 state schema。
- 相同選擇重送不重複加分；同次改選回 409，找不到方案回 404，不可行方案回 409。
- 成功回傳更新後的 Trip 與 Preference；過期版本拒絕套用，錯誤碼待確認。

### Preference

已提供 Preference Pydantic model、`GET /api/preferences` 與 Backend A 的內部保存介面。欄位為固定 `user_id: demo-user`、`weights`、`selection_count`；三權重為有限非負數，selection_count 為非負整數。唯讀種子 `backend/data/preferences.json` 的三權重皆為 1、selection_count 為 0；首次初始化後讀取 runtime 值，已保存的偏好可跨重啟保留。

偏好學習仍為目標功能：每次有效選擇將所選方案 strategy 對應權重 +1，並增加 selection_count；例如第一次選 A 後權重為 preserve_booking=2、maximize_attractions=1、relaxed=1，次數為 1。

目標方案分數為 `sum(weight * feature)`，同分固定 A/B/C，顯示排序原因與選擇次數。這是偏好權重更新，不是模型訓練，也不能宣稱一次選擇足以推論所有旅遊偏好；目前 placeholder 不計算評分或更新權重。

### Runtime state 與儲存邊界

`backend/data/runtime/state.json` 目前包含 `schema_version: 1`、`trip`、`preferences`；不使用 DB，runtime 不納入 Git。`backend/data/trip.json` 與 `preferences.json` 保持唯讀，只在首次讀取且 state 不存在時用於初始化。

Backend A 的 RuntimeStore 提供 `load_state()`、`get_trip()`、`get_preferences()`、`save_trip()`、`save_preferences()`、`save_state(trip, preferences)`；共用一個 store 的程序鎖保護讀寫，先驗證狀態、完整寫入同目錄暫存檔並 fsync，再以原子 replace 取代 state。只支援單一程序／worker，不提供跨程序交易保證。資料損壞或讀寫失敗回報 503，不靜默以種子覆蓋既有資料。

目前沒有 HTTP 任意儲存或重置 endpoint，沒有 snapshot／選擇紀錄。未來選擇流程須擴充版本與冪等檢查；不能因為已有 JSON 保存介面而宣稱學習迴圈完成。

## 模組責任與已確認介面

- 單一 FastAPI server；`agent/` 和 `replanner/` 是 Python modules，不是兩個服務。
- Backend A 擁有 agent 的 parser / prompts、context、weather、preference / runtime、explanation，以及 `main.py`、`models.py` 的整合。天氣 adapter 已從 `replanner/weather.py` 移至 `agent/weather.py`；現階段不另建 services/。
- Backend B 擁有 `replanner/planner.py`、`scoring.py` 的 deterministic candidates、可行性、scoring / impact；只接收共用模型，不讀寫 runtime，也不呼叫外部 API 或 LLM。
- `data/` 依內容分工：B 管行程、候選、交通與營業時間 fixture；A 管偏好種子、天氣 fixture 與 runtime。
- `parse_event(message: str) -> Event` 仍為 placeholder；`candidate_plans(trip, *, event, weather, preferences, now) -> list[Plan]` 已接收完整 context。`get_weather(trip, *, now) -> WeatherContext` 與 `fetch_weather(latitude, longitude, *, timezone, day) -> WeatherContext` 均為 async。
- B 回傳可檢查的方案事實，A 組成推薦解釋；LLM 不決定可行性或直接修改排程。

## 概念關係

- MVP 只有一位 demo-user、一個固定單日 Trip 與一組 Preference。
- Trip 包含多個 TripItem；ReplanRequest 對該 Trip 提供事件文字與可選 now。
- A 解析事件並組裝 ReplanContext；B 接收 Trip、Event、WeatherContext、Preference 與 now，目標為產生不同且可行的 A/B/C Plan。
- 每次重排目標保存一份 snapshot，包含三個候選 Plan 與原行程版本。
- 每份 snapshot 最多有一筆有效 Selection；選擇後更新 Trip 與 Preference，下一次事件使用更新結果。
- JSON 種子唯讀；目前行程與偏好集中於 runtime JSON，未來選擇及 snapshot 亦須與種子分開，runtime 檔不提交。

## 待確認事項

- 後續擴充共用模型或 planner 參數時，由 A/B 共同確認並由 A 同步 main.py 與 API contract。
- now 對應的 Demo 日期、完成活動判定、營業／抵達限制、候選景點與交通／費用 fixture 的格式。
- changes.action、weather_override、features 計算方式與目標回應欄位的完整型別及 nullable 規則。
- snapshot 行程版本、過期判定與錯誤碼；選擇與 snapshot 納入 runtime JSON 後的 schema 版本與升級方式。這些不能由文件自行推定。
