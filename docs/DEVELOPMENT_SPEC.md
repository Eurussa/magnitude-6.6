# SmartTrip：三人共用開發規格（5 小時 Hackathon）

## 產品目標
協助自由行旅客遇到睡過頭、休館或下雨時，理解事件、比較可執行替代行程，並從使用者選擇記住偏好。成功標準：一分鐘內展示「原行程 → 事件 → A/B/C → 選擇 → 第二次個人化推薦」。學習是偏好權重更新，不是訓練模型。

## Demo flow
1. 開啟 `/trip`，載入 Tokyo Day 1 JSON（單一 demo-user）。
2. 輸入「睡過頭兩小時」，Agent 解析成結構化 delay 事件。
3. Replanner 提供 A 保留預約、B 保留最多景點、C 最輕鬆，說明保留／移動／取消、交通增量與預約影響。
4. 選 A；後端保存選擇、套用行程並增加 preserve_booking 權重。
5. 輸入「下午開始下大雨」，Open-Meteo 或明確標示的 fixture 提供天氣 context。
6. 第二次排序優先呈現保留預約方案，顯示「根據你上次的選擇…」。
7. Google Maps link 開啟地點；不需要地圖金鑰。

## Must Have 與 Out of Scope
Must Have：固定單日行程、文字事件、Pydantic 事件驗證、簡單 deterministic heuristic、A/B/C 方案、天氣影響戶外活動、鎖定預約、代價說明、選擇持久化、偏好排序、loading/error 狀態、可離線展示的 fixture。

Out of Scope：Next.js/SSR、LangGraph、CrewAI、Leaflet/OSM、Google Maps SDK、OR-Tools、PostgreSQL；也不做登入、多使用者、多日最佳化、拖拉編輯、真實訂位取消、即時交通路由、Places 搜尋、模型訓練或正式部署。

## Tech Stack 與架構
- Frontend：React + Vite + TypeScript + React Router + Tailwind CSS（Vite plugin）；Node 22.12+。
- Backend：Python 3.11+、FastAPI、Pydantic v2、httpx、python-dotenv、Uvicorn。
- 單一 FastAPI server，`agent/` 與 `replanner/` 是 Python module，不是兩個服務。
- JSON 存放唯讀種子資料；選擇與偏好可用 SQLite（stdlib sqlite3），runtime 檔不提交。
- LLM：透過 httpx 呼叫支援 JSON Schema structured output 的 provider，僅解析事件與說明；金鑰只在後端。
- 天氣：Open-Meteo hourly precipitation_probability；以 Asia/Tokyo 對齊時間，失敗時顯示 fixture/fallback 標籤，不冒充即時資料。
- Google Maps Search URL 以座標開啟地點，交通時間使用 fixture，不宣稱是即時導航。

```text
React SPA :5173 -- /api proxy --> FastAPI :8000
                                  |-- agent/parser.py + prompts.py
                                  |-- replanner/weather.py → Open-Meteo
                                  |-- replanner/planner.py + scoring.py
                                  |-- agent/preference.py → SQLite / JSON
                                  └-- Pydantic → JSON response
```

LLM 輸出須經 `Event.model_validate_json`；timeout/格式錯誤時回傳可辨識的 fallback，禁止直接採信模型產生的可行行程。程式初始化預設不連外；`weather.py` 已提供獨立 adapter，尚未串入 replan。

## 初始化交付範圍
已實作：`GET /api/health`、`GET /api/trip`、`POST /api/replan`、JSON fixture、前端串接、Google Maps link、API 測試。

Replan 固定回傳 `status: placeholder`，三方案沿用原行程；事件類型為 unknown。**尚未實作真正 LLM 解析、重排、天氣套用、選擇 endpoint 或偏好持久化。** 以下目標契約提供三人後續平行開發；不得將 placeholder 視為完整 Demo。

## API contract
API prefix `/api`；JSON UTF-8、snake_case；即時可執行 schema 以 `/openapi.json`、互動文件 `/docs` 為準。時間皆為行程當地時間，分鐘是整數。

### 已實作
| Method / path | Request | Response |
|---|---|---|
| GET /health | 無 | 200 `{"status":"ok"}` |
| GET /trip | 無 | 200 Trip |
| POST /replan | 下例 | 200 ReplanResponse；驗證失敗 422 |

```json
{"trip_id":"tokyo-demo","message":"下午開始下大雨"}
```

trip_id 目前僅接受 tokyo-demo；message 1–2000 字、不可全空白。

```json
{
  "status":"placeholder",
  "event":{"event_type":"unknown","delay_minutes":0,"affected_item_id":null,"summary":"下午開始下大雨"},
  "plans":[
    {"id":"A","strategy":"preserve_booking","title":"保留預約","items":[],"explanation":"初始化佔位方案"},
    {"id":"B","strategy":"maximize_attractions","title":"保留最多景點","items":[],"explanation":"初始化佔位方案"},
    {"id":"C","strategy":"relaxed","title":"最輕鬆","items":[],"explanation":"初始化佔位方案"}
  ],
  "warnings":["Placeholder：尚未計算重排"]
}
```
上例 items 省略內容，實際 API 回傳完整原行程。Event enum：weather/delay/closure/unknown，delay_minutes 0–1440。

### 第一小時共同確認的目標增量（尚未實作）
- ReplanRequest 增加 `now`（ISO8601 帶 offset）、可選 `weather_override`（僅 Demo）。
- ReplanResponse 增加 `replan_id`（UUID）、`recommended_plan_id`、`preference_insight`、`weather_source`（live/fixture/unavailable）；完成時計為 status=ready。
- Plan 增加 `feasible`、`changes`（item_id/action/reason）、`additional_travel_minutes`、`additional_cost_jpy`、`booking_warnings`、`features`（三種策略各 0–1）。不可行方案不可套用。
- `POST /selections` body `{"replan_id":"UUID","plan_id":"A"}` → 200 `{"trip":Trip,"preferences":Preference}`。後端從保存的方案讀特徵，不能接受前端自報權重。重複相同選擇不重複加分；同次改選回 409；找不到方案 404；不可行 409。
- `GET /preferences` → 200 Preference。單一 demo-user，不需要傳 user_id。
- 外部供應商不可用：明示 fallback 或 503 `{"detail":"..."}`；前端顯示錯誤並允許重試。不得洩漏 key 或原始供應商敏感內容。

## 資料模型與模組介面
| Model | 欄位 / 規則 |
|---|---|
| Trip | id, city, timezone, items；MVP 固定 tokyo-demo |
| TripItem | id, name, start_time(HH:mm), duration_minutes>0, latitude, longitude, priority(1–5), booking, movable, indoor |
| Event | event_type, delay_minutes, affected_item_id(nullable), summary |
| Preference | user_id, weights{preserve_booking,maximize_attractions,relaxed}, selection_count |
| Selection（目標） | replan_id UNIQUE, plan_id, created_at；與行程套用、權重更新同一交易 |
| Replan snapshot（目標） | replan_id, 原行程版本, plans, created_at；拒絕套用已過期版本 |

初始化 module 介面：`parse_event(message: str) -> Event`；`candidate_plans(trip: Trip) -> list[Plan]`；`fetch_weather(latitude, longitude) -> dict` 是 async。A/B 在第 0–30 分鐘一起擴充 planner 的 event/weather/preferences 參數並同步 main.py；不要各自猜契約。

排程規則：已完成活動不動；booking=true 或 movable=false 不得靜默移動。依 fixture 交通時間檢查不重疊、營業時間与最晚抵達。無解要明確標為不可行；保留最多景點策略也不能偷偷解除預約鎖。天氣只影響對應時段戶外活動，未知天氣不能當晴天。

偏好最小版：起始三權重皆 1；選擇方案後對其策略 +1；用 `sum(weight * feature)` 排序（同分固定 A/B/C）；顯示 selection_count 與原因。不聲稱選一次就能推論所有旅遊偏好。

## 三人明確分工
| Owner | 擁有範圍 | 驗收 |
|---|---|---|
| Frontend | frontend/，timeline/event/cards/comparison/loading/error，API types、Google Maps link、選擇按鈕、偏好提示 | 兩次事件流程可操作，錯誤可恢復；只有 ready 且 feasible 才可套用 |
| Backend A | agent/、main.py、models.py、偏好 SQLite 與 selections API、LLM 設定 | structured output 驗證、fallback、選擇冪等、偏好持久化；維護 API 契約 |
| Backend B | replanner/、data/ fixtures、天氣 adapter、heuristic、scoring | 三種不同且可行的方案、預約鎖、天氣影響、代價與原因 |

README / 共用 schema 由 A 整合；要改欄位先通知三人，先更新本文件與 Pydantic，再由 Frontend 更新 TS。B 不直接修改 agent/；A 不改 B 的演算法，使用約定函式介面。

## Git workflow
以遠端 main 為整合分支。三人由最新 main 建 `feat/frontend`、`feat/agent`、`feat/replanner`；每 30–45 分鐘提交可執行的小變更，經一位同伴檢查後合併。不要 force-push main；不要提交 .env、node_modules、.venv、SQLite runtime。共用檔衝突由 owner 處理，禁止以整檔覆蓋解決。

合併前在 `frontend/` 跑 `pnpm build`、`pnpm lint`，並執行後端 unittest。初始 commit 基於原有 Initial commit，並非重寫 git 歷史。

## 5 小時時程
| 時間 | Frontend | Backend A | Backend B | 里程碑 |
|---|---|---|---|---|
| 0:00–0:30 | 啟動 UI、確認 types | 凍結 schema / routes | 確認 fixture / 函式介面 | 三人共用契約 |
| 0:30–1:00 | timeline、事件與卡片 | parser + orchestration | 固定 A/B/C 回應 | 首次端到端 |
| 1:00–2:00 | 比較 / 選擇 UI | structured output + fallback | delay/closure heuristic、預約檢查 | 第一事件可用 |
| 2:00–3:00 | weather badge、偏好面板 | selections + persistence | 天氣 + ranking | 學習迴圈 |
| 3:00–4:00 | 整合、錯誤狀態 | 契約與選擇測試 | 無解/天氣/鎖定測試 | 第二事件推薦改變 |
| 4:00–4:30 | 修 bug、易讀性 | 穩定離線模式 | 固定 demo fixture | feature freeze |
| 4:30–5:00 | 一起彩排 | 清空 runtime 重演 | 確認備援場景 | 兩分鐘 Demo |

## Demo scenario / 驗收
原行程：09:00 淺草寺、11:00 東京國立博物館、13:00 午餐🔒、15:00 teamLab🔒、19:00 晚餐🔒；地點與餐廳時間為展示 fixture，不是已查證訂位。

第一幕：09:00 睡過頭兩小時，取消或調整未預約景點以保留午餐與 teamLab，A/B/C 展示不同取捨。選 A，記住偏好。第二幕：同日 11:00 收到下午大雨事件，以 fixture 中下午戶外候選景點測試雨天替代（Backend B 補候選資料）；鎖定的室內 teamLab 保持 15:00。呈現偏好原因與 Google Maps。

必測：空字串 422、未知行程 422、LLM 非法 JSON、天氣 timeout、鎖定時間不變、不可行不可套用、重複選擇不重複計分、再次啟動偏好仍存在。初始化僅驗證前三條 API 契約及預約資料未被 placeholder 改動；其餘為五小時內開發驗收目標。
