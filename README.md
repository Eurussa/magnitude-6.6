# magnitude-6.6

Sea x OpenAI Taiwan Hackathon 2026

## SmartTrip — 5 小時 Hackathon 初始化

三人共用規格與分工：[docs/DEVELOPMENT_SPEC.md](docs/DEVELOPMENT_SPEC.md)；固定 API 與 A/B 介面：[docs/api-contract.md](docs/api-contract.md)。

目前可啟動前後端、查看東京三日行程、開啟 Google Maps、送出事件並取得 A/B/C **placeholder**。完整 Pydantic/OpenAPI schema 與 `POST /api/selections` 路由已建立；Backend B 的 LLM 跨日重排模組也已完成，但 `main.py` 尚未改接它，selections 仍固定回 501。尚未完成 LLM 事件解析、snapshot、方案套用與偏好學習。

### 環境與啟動

需要 Node.js 22.12+（`.nvmrc` 指定 22）、pnpm 11+、Python 3.11+。

在 repository 根目錄：

```sh
cp .env.example .env
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r backend/requirements.lock.txt
python -m uvicorn backend.main:app --reload --host 127.0.0.1 --port 8000
```

另一個 terminal：

```sh
cd frontend
pnpm install --frozen-lockfile
pnpm dev
```

開啟 http://localhost:5173；API 文件 http://127.0.0.1:8000/docs。
Vite 將 `/api` 轉送至 8000；production build 僅產生靜態檔，正式 hosting 需另外配置 SPA fallback 與 `/api` reverse proxy。

根目錄 `.env` 供 Agent 與 Backend B 共用 `LLM_` 設定，安全範例見根目錄 `.env.example`。真實 key 只供後端使用，勿提交或放入 VITE\_ 變數。`WEATHER_MODE=mock` 使用涵蓋 Trip 未來日期區間、明確標示來源的天氣 fixture；`live` 呼叫 Open-Meteo date range 並在失敗時標示 fallback。天氣已傳入 context，A 改接 `LLMReplanner` 後才會反映於 HTTP 回應。

後端先使用 JSON，不使用 DB。唯讀種子在 `backend/data/trip.json`、`preferences.json`；首次讀取時建立 `backend/data/runtime/state.json`，schema version 2 包含多日 Trip、目前行程與偏好，後續讀寫都透過 A 的 RuntimeStore。原子 replace 與單程序鎖保護更新；僅支援單一 worker，不要使用 `--workers` 啟動多程序。runtime 已忽略版控，資料損壞或舊 schema 不會被靜默重置。升級後若仍有開發用 version 1 state，先停止服務並移除自己的 `state.json`，下次讀取由多日種子重建。

### 驗證

```sh
# repo root, virtualenv activated
python -m unittest discover -s backend/tests -v
# frontend
cd frontend
pnpm build
pnpm lint
```

```sh
curl http://127.0.0.1:8000/api/health
curl http://127.0.0.1:8000/api/preferences
curl -X POST http://127.0.0.1:8000/api/replan \
  -H 'Content-Type: application/json' \
  -d '{"trip_id":"tokyo-demo","message":"後天迪士尼會下大雨，可以和其他天交換嗎？","now":"2026-09-12T09:00:00+09:00"}'

# route/schema 已存在；在 selection workflow 完成前預期回 501
curl -X POST http://127.0.0.1:8000/api/selections \
  -H 'Content-Type: application/json' \
  -d '{"replan_id":"7e3d2ca1-b499-4d06-8702-83a482ca30e6","plan_id":"A"}'
```

### 結構與協作

- `frontend/`：Frontend owner，React SPA。
- `backend/agent/`：Backend A，parser / prompts、context、weather、preference / runtime、explanation；A 同時維護 `main.py` / `models.py`，整合單一 FastAPI。
- `backend/replanner/`：Backend B，planning prompt、LLM candidate plans、structured output 驗證、可行性與 scoring / impact；實作 `Replanner.generate_plans(ReplanContext) -> PlanningResult`，不直接取得天氣或讀寫 runtime。
- `backend/data/`：B 管行程、候選、交通 fixture；A 管偏好種子、天氣 fixture 與 runtime。
- `backend/tests/`：API、天氣 context、runtime JSON 與 replanner provider／驗證／排序測試。

`weather.py` 已從 `replanner/` 移至 `agent/`；取得多日天氣由 A 負責，天氣如何影響跨日行程由 B 的 planning LLM 處理。天氣與儲存邊界見 [ADR 004](docs/decisions/004-backend-boundaries-runtime-json.md)，LLM 重排與 deterministic preference scoring 見 [ADR 005](docs/decisions/005-llm-driven-replanning.md)，多日 Trip/Event/Weather schema 見 [ADR 006](docs/decisions/006-multi-day-trip-schema.md)。

後端 API schema 已固定為多日：Trip 有 `version`、`start_date`／`end_date`，每個 TripItem 有 `scheduled_date`，Event 使用 arrays，Plan 包含 changes/impact/features，ReplanResponse 包含 snapshot identity 與 recommendation，SelectionResponse 回傳 selection、更新後 Trip 與 Preference。`frontend/` 由 frontend owner 依契約另行同步，本次未修改其中任何檔案。

從 main 分出 `feat/frontend`、`feat/agent`、`feat/replanner`，小步合併；共用 API 改動先同步規格。不要提交金鑰、虛擬環境或 runtime 資料。

技術參考：[Vite 環境要求](https://vite.dev/guide/)、[Tailwind Vite 整合](https://tailwindcss.com/docs/installation/using-vite)、[Open-Meteo 文件](https://open-meteo.com/en/docs)。使用即時天氣時顯示 Open-Meteo 資料來源。
