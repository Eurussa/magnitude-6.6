# SmartTrip：三人共用開發規格（5 小時 Hackathon）

## 產品目標
協助自由行旅客遇到睡過頭、休館或下雨時，理解事件、比較可執行替代行程，並從使用者選擇記住偏好。成功標準：一分鐘內展示「原行程 → 事件 → A/B/C → 選擇 → 第二次個人化推薦」。學習是偏好權重更新，不是訓練模型。

## Demo flow
1. 開啟 `/trip`，載入固定 Tokyo 三日 Trip JSON（單一 demo-user）。
2. 輸入「睡過頭兩小時」，Agent 解析成結構化 delay 事件。
3. Replanner 提供 A 保留預約、B 保留最多景點、C 最輕鬆，說明保留／移動／取消、交通增量與預約影響。
4. 選 A；後端保存選擇、套用行程並增加 preserve_booking 權重。
5. 輸入「後天迪士尼會下大雨，可以和其他天交換嗎？」，Open-Meteo 或明確標示的 fixture 提供整段行程天氣 context。
6. Replanner 可將迪士尼整日移到較乾燥日期並重排被交換日期；第二次排序優先呈現保留預約方案，顯示「根據你上次的選擇…」。
7. Google Maps link 開啟地點；不需要地圖金鑰。

## Must Have 與 Out of Scope
Must Have：固定多日行程、可跨日期影響的文字事件、Pydantic 事件驗證、LLM structured-output 跨日行程重排、A/B/C 方案、多日天氣影響戶外活動、鎖定預約、代價說明、選擇持久化、deterministic 偏好排序、loading/error 狀態、可離線展示的 fixture。

Out of Scope：Next.js/SSR、LangGraph、CrewAI、Leaflet/OSM、Google Maps SDK、OR-Tools、PostgreSQL；也不做登入、多使用者、跨城市／任意長期規劃、拖拉編輯、真實訂位取消、即時交通路由、Places 搜尋、模型訓練或正式部署。

## Tech Stack 與架構
- Frontend：React + Vite + TypeScript + React Router + Tailwind CSS（Vite plugin）；Node 22.12+。
- Backend：Python 3.11+、FastAPI、Pydantic v2、httpx、python-dotenv、Uvicorn。
- 單一 FastAPI server，`agent/` 與 `replanner/` 是 Python module，不是兩個服務。
- 使用 runtime JSON，不使用 DB。`data/trip.json` 與 `preferences.json` 是唯讀種子；首次讀取初始化 `data/runtime/state.json`（schema_version=2、multi-day trip、preferences），後續由 A 讀寫，不提交 runtime。Version 1 不自動猜測日期或靜默遷移。
- RuntimeStore 以單程序鎖保護更新，暫存檔寫入並 fsync 後以原子 replace 取代狀態；限單一 worker。損壞或無法讀寫時明確報錯，不靜默覆蓋已保存資料。
- LLM：透過 httpx 呼叫支援 JSON Schema structured output 的 provider；A 用於事件解析與推薦說明，B 用於產生 A/B/C 重排行程。共用 provider/model 設定由 A 整合，planning prompt 與規劃呼叫由 B 負責；金鑰只在後端。
- 天氣：Open-Meteo hourly precipitation_probability；取得 Trip 尚未結束的日期區間，以 Asia/Tokyo 對齊時間，失敗時顯示 fixture/fallback 標籤，不冒充即時資料。
- Google Maps Search URL 以座標開啟地點，交通時間使用 fixture，不宣稱是即時導航。

```text
React SPA :5173 -- /api proxy --> FastAPI :8000
                                  |-- agent/context.py
                                  |     |-- parser.py + prompts.py
                                  |     |-- weather.py → Open-Meteo / fixture
                                  |     └-- preference.py + runtime.py → runtime JSON
                                  |-- replanner/planner.py → planning LLM
                                  |                    └── scoring.py
                                  └-- agent/explanation.py + Pydantic → JSON response
```

事件 LLM 輸出須經 `Event.model_validate_json`，planning LLM 輸出須經對應的 Pydantic schema 與方案限制驗證；timeout、格式錯誤或無效方案應重試、使用明確標示的 fixture/fallback，或回傳 503。LLM 負責產生跨日重排行程，Python 負責 orchestration、驗證及 deterministic preference scoring。預設 `WEATHER_MODE=mock` 使用涵蓋 demo 三日的天氣 fixture；`live` 呼叫 Open-Meteo date range，失敗時明示 fallback。`agent/weather.py` 已串入多日 context，但 placeholder planner 尚未呼叫 planning LLM。

## 目前交付範圍
已實作：health/trip/preferences/replan/selections API、完整外層 Pydantic/OpenAPI schema、多日 JSON fixture、runtime JSON、多日 weather context、Frontend 既有串接與 Google Maps。Backend A 已完成本機多日事件 fallback parser、B Protocol 注入邊界、snapshot 保存與 selection 原子交易；仍不開放 HTTP 任意儲存或重置 endpoint。

未注入 Backend B 實例時，Replan 回傳 `status: placeholder`，三方案沿用完整多日行程。注入符合固定 Protocol 的 B 實例後，A 會保存 snapshot 並回 ready，之後可選擇可行方案。**尚未實作外部 LLM 事件 adapter 與 B 的 LLM 跨日行程重排。** 外層契約與 A 的選擇交易已完成，未實作狀態不代表欄位仍待決定。

## API contract
完整且固定的欄位、enum、nullable 規則、錯誤碼、選擇交易語意及 A/B module 介面見 [Backend API 與模組契約](api-contract.md)。即時可執行 schema 以 `/openapi.json`、互動文件 `/docs` 為準。

| Method / path | Request | Response／目前狀態 |
|---|---|---|
| GET `/api/health` | 無 | 200 `{"status":"ok"}` |
| GET `/api/trip` | 無 | 200 runtime `Trip`；503 storage error |
| GET `/api/preferences` | 無 | 200 runtime `Preference`；503 storage error |
| POST `/api/replan` | `ReplanRequest` | 200 `ReplanResponse`；未注入 B 時為 placeholder；422/503 |
| POST `/api/selections` | `SelectionRequest` | 200 `SelectionResponse`；404/409/422/503 |

```json
{"trip_id":"tokyo-demo","message":"後天迪士尼會下大雨，可以和其他天交換嗎？","now":"2026-09-12T09:00:00+09:00"}
```

trip_id 目前僅接受 tokyo-demo；message 1–2000 字、不可全空白。可選 `now` 須為帶 offset 的 ISO8601；未提供時使用目前行程當地時間。天氣從 `max(now 的行程當地日期, trip.start_date)` 取得至 `trip.end_date`；mock 資料是具明確日期的多日展示 fixture。

```json
{
  "status":"placeholder",
  "replan_id":null,
  "planning_source":"unavailable",
  "event":{"event_type":"weather","delay_minutes":0,"affected_item_ids":["item-9"],"affected_dates":["2026-09-14"],"summary":"後天迪士尼會下大雨，可以和其他天交換嗎？"},
  "plans":[
    {"id":"A","strategy":"preserve_booking","title":"保留預約","items":[],"feasible":false,"changes":[],"additional_travel_minutes":0,"additional_cost_jpy":0,"booking_warnings":[],"features":{"preserve_booking":0,"maximize_attractions":0,"relaxed":0},"explanation":""},
    {"id":"B","strategy":"maximize_attractions","title":"保留最多景點","items":[],"feasible":false,"changes":[],"additional_travel_minutes":0,"additional_cost_jpy":0,"booking_warnings":[],"features":{"preserve_booking":0,"maximize_attractions":0,"relaxed":0},"explanation":""},
    {"id":"C","strategy":"relaxed","title":"最輕鬆","items":[],"feasible":false,"changes":[],"additional_travel_minutes":0,"additional_cost_jpy":0,"booking_warnings":[],"features":{"preserve_booking":0,"maximize_attractions":0,"relaxed":0},"explanation":""}
  ],
  "recommended_plan_id":null,
  "preference_insight":null,
  "warnings":["Placeholder：尚未計算重排"]
}
```
上例省略必填的 `weather`、`preferences` 與完整 items 內容。ready 回應必須有 UUID `replan_id`、`planning_source: live|fixture`、三個完整 Plan，以及指向 feasible plan 的 recommendation（若存在可行方案）。placeholder 不可被選擇。

## 資料模型與模組介面
| Model | 欄位 / 規則 |
|---|---|
| Trip | id, version>=1, city, timezone, start_date, end_date, items；MVP 固定 tokyo-demo，日期範圍可涵蓋多天 |
| TripItem | id, name, scheduled_date, start_time(HH:mm), duration_minutes>0, latitude, longitude, priority(1–5), booking, movable, indoor；scheduled_date 必須在 Trip 範圍內 |
| Event | event_type, delay_minutes, affected_item_ids[], affected_dates[], summary；可影響多個日期或項目 |
| Preference | 固定 demo-user，weights{preserve_booking,maximize_attractions,relaxed} 為有限非負數，selection_count 為非負整數 |
| WeatherContext | source, start_date, end_date, timezone, hours{time,precipitation_probability}, warnings；涵蓋 Trip 尚未結束的日期區間，time 帶 offset，機率 0–100 或未知 |
| ReplanContext | trip, event, weather, preferences, now；由 A 組裝，B 接收 |
| Plan | 固定 A/B/C id 與 strategy、完整 items、feasible、changes、交通／費用 delta、booking_warnings、features、explanation |
| PlanningResult | source、排序後且剛好三個的 plans、recommended_plan_id、warnings；raw score 僅供 B 內部排序，不對外回傳 |
| Runtime state | schema_version=2, multi-day trip, preferences；由種子延遲初始化，A 單次原子寫入 |
| Selection | request 僅 replan_id/plan_id；record 加 created_at；response 回 selection、更新後 Trip 與 Preference |
| ReplanSnapshot | replan_id, trip_id, trip_version, planning_source, plans, recommended_plan_id, created_at；拒絕套用已過期版本 |

固定 A/B 介面為 `await Replanner.generate_plans(context: ReplanContext) -> PlanningResult`，Protocol 位於 `backend/contracts.py`。A 的 main 已支援注入並呼叫上述 async 介面；未注入時舊 `candidate_plans(...)` 僅產生不可選 placeholder。A 組裝 context、在本機解析 fallback Event、取得天氣、保存 snapshot、補 explanation/insight 並組 response；B 擁有 planning prompt／LLM 呼叫、結構化 Plan、驗證、impact/features 與 deterministic 排序。B 不呼叫 Open-Meteo、不直接讀寫 JSON，也不依賴 `agent/`。

A 的 RuntimeStore 提供行程／偏好讀寫、通用原子 state transition 與 `save_replan_snapshot()`；runtime state 保存 snapshot 及冪等 selection response。`/api/selections` 在同一把單程序鎖內驗證版本、套用方案、將 Trip.version +1、更新 Preference 並保存 SelectionRecord。

重排與驗證規則：planning LLM 依完整多日 context 產生方案，可將某日的所有可移動活動換到另一日期並重排受影響日期；已完成活動不動，booking=true 或 movable=false 不得靜默移動。B 對 structured output 進行 schema、日期範圍、項目參照、同日時間衝突、跨日移動、fixture 交通時間、營業時間與最晚抵達等必要驗證；無效方案應重試或明示不可行，不能直接當作 ready。保留最多景點策略也不能偷偷解除預約鎖。天氣只影響對應日期／時段的戶外活動，未知天氣不能當晴天。

偏好更新已實作：起始三權重皆 1；選擇方案後對其策略 +1 並增加 selection_count，重送不重複計分。B 仍負責用 `sum(weight * feature)` 排序（同分固定 A/B/C）；A 顯示依已保存選擇產生的原因，不聲稱選一次就能推論所有旅遊偏好。

## 三人明確分工
| Owner | 擁有範圍 | 驗收 |
|---|---|---|
| Frontend | frontend/，timeline/event/cards/comparison/loading/error，API types、Google Maps link、選擇按鈕、偏好提示 | 兩次事件流程可操作，錯誤可恢復；只有 ready 且 feasible 才可套用 |
| Backend A | agent/（parser / prompts、context、weather、preference / runtime、explanation）、main.py、models.py；偏好種子、天氣 fixture、runtime JSON；後續 snapshot / selection 交易 | structured output 驗證、Open-Meteo / fallback、時間對齊、JSON 持久化、推薦解釋、選擇冪等；維護 API 契約 |
| Backend B | replanner/ 的 planning prompt、LLM 呼叫、multi-day candidate structured output、方案驗證、scoring / impact；data/ 中多日行程、候選、交通、營業時間與 planning fallback fixture | LLM 產生三種不同跨日方案、輸出可驗證、整日換日與受影響日期可重排、限制與多日天氣納入規劃、代價與方案特徵可檢查、偏好排序穩定 |

README / 共用 schema 與共用 LLM provider 設定由 A 整合；要改欄位先通知三人，先更新本文件與 Pydantic，再由 Frontend 更新 TS。B 不直接修改 agent/；A 不改 B 的 planning prompt、驗證或 scoring，雙方使用約定函式／client 介面。`data/` 依內容分工，不整包交給 B。A 取得與整理天氣，B 將天氣納入 LLM 重排；B 回傳已驗證的 plans、impact / features、排序與 `recommended_plan_id`，A 產生使用者可讀解釋。raw score 僅供 B 內部排序，不加入 API response。

## Git workflow
以遠端 main 為整合分支。三人由最新 main 建 `feat/frontend`、`feat/agent`、`feat/replanner`；每 30–45 分鐘提交可執行的小變更，經一位同伴檢查後合併。不要 force-push main；不要提交 .env、node_modules、.venv 或 runtime 資料。共用檔衝突由 owner 處理，禁止以整檔覆蓋解決。

合併前在 `frontend/` 跑 `pnpm build`、`pnpm lint`，並執行後端 unittest。初始 commit 基於原有 Initial commit，並非重寫 git 歷史。

## 5 小時時程
| 時間 | Frontend | Backend A | Backend B | 里程碑 |
|---|---|---|---|---|
| 0:00–0:30 | 啟動 UI、同步多日 types | 凍結 multi-day schema / routes | 確認 multi-day fixture / 函式介面 | 三人共用契約 |
| 0:30–1:00 | timeline、事件與卡片 | parser + orchestration | 固定 A/B/C 回應 | 首次端到端 |
| 1:00–2:00 | 比較 / 選擇 UI | event structured output + fallback | planning prompt、LLM structured output、方案驗證 | 第一事件可用 |
| 2:00–3:00 | weather badge、偏好面板 | weather context + selections + JSON persistence | 天氣 context 納入規劃 + deterministic ranking | 學習迴圈 |
| 3:00–4:00 | 整合、錯誤狀態 | 契約與選擇測試 | 無解/天氣/鎖定測試 | 第二事件推薦改變 |
| 4:00–4:30 | 修 bug、易讀性 | 穩定離線模式 | 固定 demo fixture | feature freeze |
| 4:30–5:00 | 一起彩排 | 清空 runtime 重演 | 確認備援場景 | 兩分鐘 Demo |

## Demo scenario / 驗收
原行程為 2026-09-12 至 2026-09-14：第一天含淺草寺、東京國立博物館、午餐🔒、teamLab🔒與晚餐🔒；第二天含明治神宮、原宿／表參道與澀谷；第三天為東京迪士尼樂園整日。地點、時間與預約狀態皆為展示 fixture，不代表已查證訂位。

第一幕：第一天 09:00 睡過頭兩小時，取消或調整未預約景點以保留午餐與 teamLab，A/B/C 展示不同取捨。選 A，記住偏好。第二幕：接近 9/14 時發現迪士尼當日高機率降雨；planning LLM 可把迪士尼整日移至較乾燥的 9/13，並將原本 9/13 的行程重新分配到其他可用日期。呈現跨日變更、偏好原因與 Google Maps。

必測：空字串 422、未知行程 422、事件／planning LLM 非法 JSON、planning LLM timeout、天氣 timeout、鎖定時間不變、不可行不可套用、相同輸入的偏好排序穩定、重複選擇不重複計分、再次啟動偏好仍存在。目前測試涵蓋 API 契約、本機事件 fallback、runtime JSON、天氣 context、ready snapshot、stale 拒絕與選擇冪等；外部 LLM 事件解析及 B 的 LLM 行程重排仍為後續開發驗收目標。
