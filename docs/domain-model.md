# Domain Model

依據：[共用開發規格](DEVELOPMENT_SPEC.md)。此文件統一產品名詞、資料關係與規則，不另行定義 API 或資料庫 schema。現行可執行 schema 以 `backend/models.py`、`/openapi.json` 與 `/docs` 為準；標為「目標」的內容尚未實作或仍待共同確認。

## 核心名詞

### Traveler / demo-user

使用服務處理當日行程異常的自由行旅客。MVP 固定為 `demo-user`，無登入、多使用者或同行者模型，API 不需傳 user_id。

### Trip

單日行程，欄位為 `id`、`city`、`timezone`、`items`。MVP 固定 `tokyo-demo`、Tokyo、Asia/Tokyo，由 JSON 種子載入。套用選定方案後更新行程屬於目標功能，目前每次 API 仍載入種子。

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

### Weather context（目標整合）

Replanner 的天氣輸入，與使用者輸入的 weather Event 分開。使用 Open-Meteo hourly `precipitation_probability`，以 Asia/Tokyo 對齊，只影響相應時段戶外活動。

目標回應用 `weather_source` 表示 `live`、`fixture` 或 `unavailable`；未知天氣不能當晴天，fixture 不得冒充即時資料。adapter 已存在但未串入 replan；完整 context 與 Demo 專用 weather_override schema 尚未定義。

### Plan（對應原 Recovery Option）

同次重排的一個候選方案。現有欄位：`id`、`strategy`、`title`、`items`、`explanation`。

| id | strategy | title |
|---|---|---|
| A | preserve_booking | 保留預約 |
| B | maximize_attractions | 保留最多景點 |
| C | relaxed | 最輕鬆 |

初始化三方案皆沿用原行程，尚未驗證可行性。目標增量如下：

| 欄位 | 目標意義 |
|---|---|
| feasible | 可行性；false 時不得套用 |
| changes | 每項 `item_id/action/reason`，說明保留、移動、取消；action enum 尚待確認 |
| additional_travel_minutes | 交通增量，依 fixture 計算，不宣稱即時導航 |
| additional_cost_jpy | 費用增量，以日圓表示；計算所需 fixture 待補 |
| booking_warnings | 預約影響與限制 |
| features | preserve_booking、maximize_attractions、relaxed 三種特徵，各 0–1，供偏好評分 |

原本的 Impact 概念由 `changes`、交通／費用增量與 booking_warnings 表達，目前沒有獨立 Impact model。方案需檢查時間不重疊、fixture 交通時間、營業時間與最晚抵達；無解必須明示不可行。

### ReplanResponse / Replan snapshot

現有回應為 `status: placeholder`、`event`、`plans`、`warnings`。目標完成時為 `status: ready`，增加 `replan_id`（UUID）、`recommended_plan_id`、`preference_insight`、`weather_source`。

目標 snapshot 保存 `replan_id`、原行程版本、plans、created_at，供後端確認選擇與讀取方案特徵。A/B/C 的 id 只在同次 replan 內識別方案，選擇須同時提供 replan_id。若原行程版本已過期，拒絕套用。

目標 ReplanRequest 增加帶 offset 的 ISO8601 `now` 與可選的 Demo `weather_override`；行程版本表示方式、snapshot 有效期與完整 schema 尚待確認。

### Selection（目標；取代獨立 Recovery Plan 概念）

旅客對一次 replan 的選擇紀錄，目標欄位為 `replan_id UNIQUE`、`plan_id`、`created_at`。選定 Plan 後直接套用為更新後的 Trip，規格未定義另一個 RecoveryPlan model，也不執行外部預訂或取消。

- `POST /api/selections` 僅接受 replan_id 與 plan_id；後端讀取保存的方案特徵，不信任前端自報權重。
- 保存選擇、套用行程、更新權重必須在同一交易完成。
- 相同選擇重送不重複加分；同次改選回 409，找不到方案回 404，不可行方案回 409。
- 成功回傳更新後的 Trip 與 Preference；過期版本拒絕套用，錯誤碼待確認。

### Preference（目標持久化）

欄位為 `user_id`、`weights`、`selection_count`。現有 JSON 僅提供初始 fixture：demo-user、三權重皆 1、selection_count 為 0，尚無 Preference Pydantic model 或 endpoint。

最小版每次有效選擇將所選方案 strategy 對應權重 +1，並增加 selection_count；例如第一次選 A 後權重為 preserve_booking=2、maximize_attractions=1、relaxed=1，次數為 1。

方案分數為 `sum(weight * feature)`，同分固定 A/B/C，顯示排序原因與選擇次數。這是偏好權重更新，不是模型訓練，也不能宣稱一次選擇足以推論所有旅遊偏好。目標 `GET /api/preferences` 回傳 Preference；偏好需在重啟後保留。

## 概念關係

- MVP 只有一位 demo-user、一個固定單日 Trip 與一組 Preference。
- Trip 包含多個 TripItem；ReplanRequest 對該 Trip 提供事件文字與目標 now。
- 事件解析產生 Event；Replanner 結合 Trip、Event、Weather context 與 Preference 產生 A/B/C Plan。
- 每次重排目標保存一份 snapshot，包含三個候選 Plan 與原行程版本。
- 每份 snapshot 最多有一筆有效 Selection；選擇後更新 Trip 與 Preference，下一次事件使用更新結果。
- JSON 種子唯讀；選擇、偏好與行程套用所需 runtime 應分開保存，可使用 stdlib SQLite，runtime 檔不提交。

## 待確認事項

- A/B 在擴充 planner 前共同確認 event/weather/preferences 參數，並由 A 同步 main.py；現有介面為 `parse_event(message: str) -> Event`、`candidate_plans(trip: Trip) -> list[Plan]`，`fetch_weather(latitude, longitude) -> dict` 為 async。
- now 對應的 Demo 日期、完成活動判定、營業／抵達限制、候選景點與交通／費用 fixture 的格式。
- changes.action、weather_override、features 計算方式與目標回應欄位的完整型別及 nullable 規則。
- snapshot 行程版本、過期判定與錯誤碼；SQLite schema 與 runtime 儲存細節。這些不能由文件自行推定。
