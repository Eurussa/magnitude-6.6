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
- 使用 runtime JSON，不使用 DB。`data/trip.json` 與 `preferences.json` 是唯讀種子；首次讀取初始化 `data/runtime/state.json`（schema_version、trip、preferences），後續由 A 讀寫，不提交 runtime。
- RuntimeStore 以單程序鎖保護更新，暫存檔寫入並 fsync 後以原子 replace 取代狀態；限單一 worker。損壞或無法讀寫時明確報錯，不靜默覆蓋已保存資料。
- LLM：透過 httpx 呼叫支援 JSON Schema structured output 的 provider，僅解析事件與說明；金鑰只在後端。
- 天氣：Open-Meteo hourly precipitation_probability；以 Asia/Tokyo 對齊時間，失敗時顯示 fixture/fallback 標籤，不冒充即時資料。
- Google Maps Search URL 以座標開啟地點，交通時間使用 fixture，不宣稱是即時導航。

```text
React SPA :5173 -- /api proxy --> FastAPI :8000
                                  |-- agent/context.py
                                  |     |-- parser.py + prompts.py
                                  |     |-- weather.py → Open-Meteo / fixture
                                  |     └-- preference.py + runtime.py → runtime JSON
                                  |-- replanner/planner.py + scoring.py
                                  └-- agent/explanation.py + Pydantic → JSON response
```

LLM 輸出須經 `Event.model_validate_json`；timeout/格式錯誤時回傳可辨識的 fallback，禁止直接採信模型產生的可行行程。預設 `WEATHER_MODE=mock` 使用明確標示的 fixture；`live` 呼叫 Open-Meteo，失敗時明示 fallback。`agent/weather.py` 已串入 context，但 placeholder planner 尚未依天氣調整行程。

## 目前交付範圍
已實作：`GET /api/health`、`GET /api/trip`、`GET /api/preferences`、`POST /api/replan`、JSON fixture、runtime JSON 行程／偏好讀寫、天氣 context、前端串接、Google Maps link 與相關測試。RuntimeStore 提供內部保存介面，本次不開放 HTTP 儲存或重置 endpoint。

Replan 固定回傳 `status: placeholder`，三方案沿用目前行程；事件類型為 unknown。**尚未實作真正 LLM 解析、重排、天氣影響排程、選擇 endpoint 或偏好學習。** 以下目標契約提供後續平行開發；不得將儲存與 context 基礎視為完整 Demo。

## API contract
API prefix `/api`；JSON UTF-8、snake_case；即時可執行 schema 以 `/openapi.json`、互動文件 `/docs` 為準。時間皆為行程當地時間，分鐘是整數。

### 已實作
| Method / path | Request | Response |
|---|---|---|
| GET /health | 無 | 200 `{"status":"ok"}` |
| GET /trip | 無 | 200 runtime 中的 Trip |
| GET /preferences | 無 | 200 runtime 中的 Preference |
| POST /replan | 下例 | 200 ReplanResponse；驗證失敗 422 |

```json
{"trip_id":"tokyo-demo","message":"下午開始下大雨"}
```

trip_id 目前僅接受 tokyo-demo；message 1–2000 字、不可全空白。可選 `now` 須為帶 offset 的 ISO8601；未提供時使用目前行程當地時間。天氣日期以 now 換算至行程時區，mock 資料是套用至該日的展示 fixture。

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
上例省略 `weather`、`preferences` 與 items 內容；實際 API 同時回傳 WeatherContext、Preference 及完整目前行程。Event enum：weather/delay/closure/unknown，delay_minutes 0–1440。`weather.source` 為 live / fixture / unavailable；降雨機率不能直接解讀為降雨強度。runtime 讀寫失敗回 503。

### 第一小時共同確認的目標增量（尚未實作）
- ReplanRequest 已提供 `now`；後續若需要 `weather_override`（僅 Demo），由三人一起確認 schema。
- ReplanResponse 後續增加 `replan_id`（UUID）、`recommended_plan_id`、`preference_insight`；天氣來源沿用既有 `weather.source`（live/fixture/unavailable），完成時計為 status=ready。
- Plan 增加 `feasible`、`changes`（item_id/action/reason）、`additional_travel_minutes`、`additional_cost_jpy`、`booking_warnings`、`features`（三種策略各 0–1）。不可行方案不可套用。
- `POST /selections` body `{"replan_id":"UUID","plan_id":"A"}` → 200 `{"trip":Trip,"preferences":Preference}`。後端從保存的方案讀特徵，不能接受前端自報權重。重複相同選擇不重複加分；同次改選回 409；找不到方案 404；不可行 409。
- 外部供應商不可用：明示 fallback 或 503 `{"detail":"..."}`；前端顯示錯誤並允許重試。不得洩漏 key 或原始供應商敏感內容。

## 資料模型與模組介面
| Model | 欄位 / 規則 |
|---|---|
| Trip | id, city, timezone, items；MVP 固定 tokyo-demo |
| TripItem | id, name, start_time(HH:mm), duration_minutes>0, latitude, longitude, priority(1–5), booking, movable, indoor |
| Event | event_type, delay_minutes, affected_item_id(nullable), summary |
| Preference | 固定 demo-user，weights{preserve_booking,maximize_attractions,relaxed} 為有限非負數，selection_count 為非負整數 |
| WeatherContext | source, date, timezone, hours{time,precipitation_probability}, warnings；time 帶 offset，機率 0–100 或未知 |
| ReplanContext | trip, event, weather, preferences, now；由 A 組裝，B 接收 |
| Runtime state | schema_version=1, trip, preferences；由種子延遲初始化，A 單次原子寫入 |
| Selection（目標） | 每個 replan_id 最多一次選擇，plan_id, created_at；與行程套用、權重更新在同次 runtime 原子更新完成 |
| Replan snapshot（目標） | replan_id, 原行程版本, plans, created_at；拒絕套用已過期版本 |

目前 module 邊界：`parse_event(message: str) -> Event` 仍是 placeholder；A 的 context 組裝 trip / event / weather / preferences / now，再呼叫 B 的 `candidate_plans(trip, *, event, weather, preferences, now) -> list[Plan]`。天氣 adapter 位於 `agent/weather.py`，產出共用 WeatherContext；A 的 `explanation.py` 負責使用者可讀說明。B 不呼叫外部 API、不直接讀寫 JSON，也不依賴 `agent/`。

A 的 RuntimeStore 提供 `get_trip()`、`get_preferences()`、`save_trip()`、`save_preferences()`、`save_state(trip, preferences)`，保留種子並集中管理 runtime 寫入。此次不保存候選 snapshot 或選擇紀錄；後續實作 `/selections` 時再擴充 state schema 與版本／冪等檢查。

排程規則：已完成活動不動；booking=true 或 movable=false 不得靜默移動。依 fixture 交通時間檢查不重疊、營業時間与最晚抵達。無解要明確標為不可行；保留最多景點策略也不能偷偷解除預約鎖。天氣只影響對應時段戶外活動，未知天氣不能當晴天。

偏好學習目標（尚未實作）：起始三權重皆 1；選擇方案後對其策略 +1；用 `sum(weight * feature)` 排序（同分固定 A/B/C）；顯示 selection_count 與原因。不聲稱選一次就能推論所有旅遊偏好。

## 三人明確分工
| Owner | 擁有範圍 | 驗收 |
|---|---|---|
| Frontend | frontend/，timeline/event/cards/comparison/loading/error，API types、Google Maps link、選擇按鈕、偏好提示 | 兩次事件流程可操作，錯誤可恢復；只有 ready 且 feasible 才可套用 |
| Backend A | agent/（parser / prompts、context、weather、preference / runtime、explanation）、main.py、models.py；偏好種子、天氣 fixture、runtime JSON；後續 selections API | structured output 驗證、Open-Meteo / fallback、時間對齊、JSON 持久化、推薦解釋；後續選擇冪等；維護 API 契約 |
| Backend B | replanner/ 的 deterministic heuristic、candidates、可行性、scoring / impact；data/ 中行程、候選、交通與營業時間 fixture | 三種不同且可行的方案、預約鎖、天氣影響、可檢查的代價與方案特徵 |

README / 共用 schema 由 A 整合；要改欄位先通知三人，先更新本文件與 Pydantic，再由 Frontend 更新 TS。B 不直接修改 agent/；A 不改 B 的演算法，使用約定函式介面。`data/` 依內容分工，不整包交給 B。A 取得與整理天氣，B 決定天氣如何影響排程；B 回傳 impact / features 等事實，A 產生解釋。

## Git workflow
以遠端 main 為整合分支。三人由最新 main 建 `feat/frontend`、`feat/agent`、`feat/replanner`；每 30–45 分鐘提交可執行的小變更，經一位同伴檢查後合併。不要 force-push main；不要提交 .env、node_modules、.venv 或 runtime 資料。共用檔衝突由 owner 處理，禁止以整檔覆蓋解決。

合併前在 `frontend/` 跑 `pnpm build`、`pnpm lint`，並執行後端 unittest。初始 commit 基於原有 Initial commit，並非重寫 git 歷史。

## 5 小時時程
| 時間 | Frontend | Backend A | Backend B | 里程碑 |
|---|---|---|---|---|
| 0:00–0:30 | 啟動 UI、確認 types | 凍結 schema / routes | 確認 fixture / 函式介面 | 三人共用契約 |
| 0:30–1:00 | timeline、事件與卡片 | parser + orchestration | 固定 A/B/C 回應 | 首次端到端 |
| 1:00–2:00 | 比較 / 選擇 UI | structured output + fallback | delay/closure heuristic、預約檢查 | 第一事件可用 |
| 2:00–3:00 | weather badge、偏好面板 | weather context + selections + JSON persistence | 天氣影響排程 + ranking | 學習迴圈 |
| 3:00–4:00 | 整合、錯誤狀態 | 契約與選擇測試 | 無解/天氣/鎖定測試 | 第二事件推薦改變 |
| 4:00–4:30 | 修 bug、易讀性 | 穩定離線模式 | 固定 demo fixture | feature freeze |
| 4:30–5:00 | 一起彩排 | 清空 runtime 重演 | 確認備援場景 | 兩分鐘 Demo |

## Demo scenario / 驗收
原行程：09:00 淺草寺、11:00 東京國立博物館、13:00 午餐🔒、15:00 teamLab🔒、19:00 晚餐🔒；地點與餐廳時間為展示 fixture，不是已查證訂位。

第一幕：09:00 睡過頭兩小時，取消或調整未預約景點以保留午餐與 teamLab，A/B/C 展示不同取捨。選 A，記住偏好。第二幕：同日 11:00 收到下午大雨事件，以 fixture 中下午戶外候選景點測試雨天替代（Backend B 補候選資料）；鎖定的室內 teamLab 保持 15:00。呈現偏好原因與 Google Maps。

必測：空字串 422、未知行程 422、LLM 非法 JSON、天氣 timeout、鎖定時間不變、不可行不可套用、重複選擇不重複計分、再次啟動偏好仍存在。目前測試涵蓋 API 契約、runtime JSON 及天氣 context，placeholder 不改動預約資料；LLM、真正重排、選擇與學習迴圈仍為後續開發驗收目標。
