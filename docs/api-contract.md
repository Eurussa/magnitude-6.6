# Backend API 與模組契約

本文件是 Backend A、Backend B 與 Frontend 的固定外層契約。可執行定義位於 `backend/models.py`、`backend/contracts.py`、`/openapi.json` 與 `/docs`；若文字與程式不一致，以 Pydantic／OpenAPI 為準並立即修正本文件。`agent/` 與 `replanner/` 內部 prompt、provider client、重試及演算法不在此契約內。

## 共通規則

- API prefix 為 `/api`，JSON 使用 UTF-8 與 `snake_case`。
- 日期為 `YYYY-MM-DD`；活動時間為行程當地 24 小時 `HH:mm`；datetime 必須是含 UTC offset 的 ISO 8601。
- 除 `ReplanRequest.trip_id`／`now` 明示可省略外，所有欄位都必須出現在 JSON；nullable 欄位也必須送 key，沒有值時明確送 null。
- 公開 request、response 與 A/B 交換模型禁止未宣告欄位；request schema 錯誤由 FastAPI 回傳 422。
- Trip、Plan 都是完整的多日資料，不是單日資料或局部 patch。呼叫端依 `scheduled_date` 分組顯示。
- A/B/C 是固定方案 ID 與策略：A=`preserve_booking`、B=`maximize_attractions`、C=`relaxed`。陣列順序是 B 依內部分數排出的顯示順序，不能用陣列位置推斷策略。
- raw preference score 只存在 Backend B 內部，不進入任何 API model。
- `planning_source` 表示重排方案來自即時 LLM 或 fixture；`weather.source` 表示天氣來源，兩者不可混用。

## HTTP endpoints

| Method / path | Request | 200 response | 其他回應 |
|---|---|---|---|
| `GET /api/health` | 無 | `{"status":"ok"}` | — |
| `GET /api/trip` | 無 | `Trip` | 503 `ErrorResponse` |
| `GET /api/preferences` | 無 | `Preference` | 503 `ErrorResponse` |
| `POST /api/replan` | `ReplanRequest` | `ReplanResponse` | 422 validation；503 `ErrorResponse` |
| `POST /api/selections` | `SelectionRequest` | `SelectionResponse` | 404 snapshot/plan 不存在；409 不可行、已改選或 Trip 版本衝突；422 validation；501 契約已有但流程尚未實作；503 storage |

除 FastAPI 標準 422 validation body 外，應用程式錯誤使用 `ErrorResponse = {"detail": string}`，不得回傳金鑰或 provider 敏感內容。

## 行程與 context models

### `Trip`

| 欄位 | 型別 | 規則 |
|---|---|---|
| `id` | string | MVP 為 `tokyo-demo` |
| `version` | integer | 必填且 >= 1；成功套用方案後 +1 |
| `city` | string | 展示值為 Tokyo |
| `timezone` | string | 有效 IANA timezone，Demo 為 `Asia/Tokyo` |
| `start_date` / `end_date` | date | end 不得早於 start |
| `items` | `TripItem[]` | item id 在整趟 Trip 唯一，日期須在範圍內 |

### `TripItem`

`id: string`、`name: string`、`scheduled_date: date`、`start_time: HH:mm`、`duration_minutes: integer > 0`、`latitude: number`、`longitude: number`、`priority: integer 1..5`、`booking: boolean`、`movable: boolean`、`indoor: boolean`。

### `Event`

`event_type` 為 `weather | delay | closure | unknown`；`delay_minutes` 是可跨日的非負整數；`affected_item_ids: string[]` 與 `affected_dates: date[]` 可同時包含多筆；`summary: string`。A 解析自然語言並產生 Event，B 不重新解析 message。

### `WeatherContext`

`source: live | fixture | unavailable`、`start_date: date`、`end_date: date`、`timezone: string`、`hours: WeatherHour[]`、`warnings: string[]`。`WeatherHour.time` 必須帶 offset 且位於區間內；`precipitation_probability` 是 `0..100 | null`，null 不得當作晴天。

### `Preference`

`user_id` 固定為 `demo-user`；`weights` 包含 `preserve_booking`、`maximize_attractions`、`relaxed` 三個有限非負 number；`selection_count` 是非負 integer。

### `ReplanRequest`

| 欄位 | 型別 | 規則 |
|---|---|---|
| `trip_id` | `tokyo-demo` | 可省略，預設 `tokyo-demo` |
| `message` | string | 必填，1–2000 字且不可全空白 |
| `now` | offset datetime or null | 可省略；提供時必須帶 offset，A 轉為 Trip timezone |

### `ReplanContext`（A → B）

必填 `trip: Trip`、`event: Event`、`weather: WeatherContext`、`preferences: Preference`、`now: offset datetime`。這是 B 唯一需要的業務輸入；B 不收原始 message、不取得天氣、不讀寫 runtime。

## 方案 models

### `PlanChange`

欄位為 `item_id`、`action`、`from_date`、`from_start_time`、`to_date`、`to_start_time`、`reason`。reason 必填且不可全空白。日期與時間必須成對出現：

| action | from | to | 意義 |
|---|---|---|---|
| `keep` | 必填 | 必填且與 from 相同 | 保留在原時段 |
| `move` | 必填 | 必填且至少日期或時間不同 | 同日或跨日移動 |
| `cancel` | 必填 | 必須為 null | 從結果行程移除 |
| `add` | 必須為 null | 必填 | 加入可信 fixture/catalog 中的項目；不得讓 LLM 虛構不可驗證地點 |

`changes` 對原 Trip 每個 item id 必須剛好有一筆 keep/move/cancel；add 則為額外項目。keep/move 的 item 必須存在於結果 items，cancel 必須不存在，add 必須存在。真正要套用的結果以 `Plan.items` 完整清單為準；兩者不一致時方案不得標示為 feasible。這些需要原 Trip 的交叉驗證由 B 在 replanner 內完成，不塞進共用 Pydantic 欄位驗證。

### `PlanFeatures`

`preserve_booking`、`maximize_attractions`、`relaxed` 均為 0..1 的有限 number。這是 selection 更新偏好與 B 內部排序所需的可保存特徵，不是 raw score。

### `Plan`

| 欄位 | 型別／規則 |
|---|---|
| `id` | `A | B | C` |
| `strategy` | A/B/C 對應的固定 strategy |
| `title` | string |
| `items` | 完整 multi-day `TripItem[]`，item id 不重複 |
| `feasible` | boolean；只有 true 可選擇 |
| `changes` | `PlanChange[]` |
| `additional_travel_minutes` | integer delta；可為負，負值表示節省 |
| `additional_cost_jpy` | integer delta；可為負，負值表示節省 |
| `booking_warnings` | string[] |
| `features` | `PlanFeatures` |
| `explanation` | string；B 可留空，由 A 根據已驗證事實補上 |

### `PlanningResult`（B → A）

`source: live | fixture`、`plans: Plan[3]`、`recommended_plan_id: A | B | C | null`、`warnings: string[]`。plans 必須剛好含 A/B/C 各一份並使用固定 strategy，陣列已依 B 的 deterministic internal score 排序。只要至少一個方案 feasible，就必須推薦其中一個；全都不可行時 recommendation 為 null。

程式介面固定為：

```python
class Replanner(Protocol):
    async def generate_plans(self, context: ReplanContext, /) -> PlanningResult: ...
```

此介面定義於 `backend/contracts.py`。B 已以 `LLMReplanner.generate_plans` 實作；`candidate_plans(...)` 只保留為相容既有主流程的 placeholder。由 A 在 `main.py` 注入／呼叫 async Protocol，不在 main 內加入排程邏輯。

## Replan response 與 snapshot

### `ReplanResponse`

| 欄位 | 型別／規則 |
|---|---|
| `status` | `placeholder | ready` |
| `replan_id` | UUID or null |
| `planning_source` | `live | fixture | unavailable` |
| `event` / `weather` / `preferences` | 本次使用的已驗證 context |
| `plans` | `Plan[3]` |
| `recommended_plan_id` | `A | B | C | null`；非 null 時必須指向 feasible plan |
| `preference_insight` | string or null |
| `warnings` | string[]；合併 context 與 replanner warnings |

`ready` 必須有 `replan_id`，planning_source 不得為 unavailable；至少一個方案 feasible 時必須有 recommendation。`placeholder` 的 replan_id 必須為 null、planning_source 必須為 unavailable，不能提供可選 snapshot。現在的 `/api/replan` 固定回 placeholder；A/B 完成整合後才切 ready。

### `ReplanSnapshot`（runtime internal）

`replan_id: UUID`、`trip_id: string`、`trip_version: integer >= 1`、`planning_source: live | fixture`、`plans: Plan[3]`、`recommended_plan_id: A | B | C | null`、`created_at: offset datetime`。A 在回 ready 前保存 snapshot；selection 只能使用 snapshot 內方案，不能接受前端回傳整份 Plan 或 features。

## Selection models 與交易語意

`SelectionRequest` 僅有 `replan_id: UUID` 與 `plan_id: A | B | C`。

`SelectionRecord` 有 `replan_id`、`plan_id`、`created_at: offset datetime`。

`SelectionResponse` 為：

```json
{
  "selection": {
    "replan_id": "7e3d2ca1-b499-4d06-8702-83a482ca30e6",
    "plan_id": "A",
    "created_at": "2026-09-12T10:05:00+09:00"
  },
  "trip": {"id": "tokyo-demo", "version": 2, "items": []},
  "preferences": {
    "user_id": "demo-user",
    "weights": {"preserve_booking": 2, "maximize_attractions": 1, "relaxed": 1},
    "selection_count": 1
  }
}
```

上例省略 Trip 其他必填欄位，只說明 response 形狀。成功選擇必須在一次 runtime 原子交易中：檢查 snapshot 與 `trip_version`、保存 SelectionRecord、以 `Plan.items` 更新 Trip 並將 version +1、依 snapshot 內 PlanFeatures 更新 Preference。相同 `replan_id + plan_id` 重送回相同成功結果且不得再次加權；相同 replan_id 改選、選擇 infeasible plan 或 Trip 版本過期回 409；snapshot 或 plan 不存在回 404。

目前 `POST /api/selections` 已註冊 request/response/error schema，但固定回 501。Backend A 完成 snapshot 與原子交易前，Frontend 不得把方案選擇視為可用功能。

## A/B orchestration

```text
Frontend ReplanRequest
  → A: load Trip + Preference, parse Event, load Weather, normalize now
  → ReplanContext
  → B: planning LLM → validate → impact/features → internal score/order
  → PlanningResult
  → A: save ReplanSnapshot, add explanations/insight, merge warnings
  → ready ReplanResponse
  → Frontend SelectionRequest
  → A: validate snapshot/version, atomically apply selection
  → SelectionResponse
```

A 可用假的 `PlanningResult` 開發 orchestration；B 可用假的 `ReplanContext` 開發 replanner。雙方不得 import 對方 package 的內部函式；共用邊界只依賴 `backend.models` 與 `backend.contracts`。
