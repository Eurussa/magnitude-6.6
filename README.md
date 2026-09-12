# magnitude-6.6

Sea x OpenAI Taiwan Hackathon 2026

## SmartTrip — 5 小時 Hackathon 初始化

三人共用規格與分工：[docs/DEVELOPMENT_SPEC.md](docs/DEVELOPMENT_SPEC.md)。

目前可啟動前後端、查看東京行程、開啟 Google Maps、送出事件並取得 A/B/C **placeholder**。已串接 A 負責的天氣 context 與 runtime JSON 行程／偏好讀寫；尚未完成 LLM、真正重排、方案選擇與偏好學習，完整 Demo 仍是後續開發目標。

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

`.env` 放在 repo 根目錄，由後端明確載入；預設模式不需要 key。未來 LLM key/model 僅供後端使用，勿放入 VITE\_ 變數。`WEATHER_MODE=mock` 使用明確標示的天氣 fixture；`live` 呼叫 Open-Meteo 並在失敗時標示 fallback。天氣已傳入 planner，但 placeholder 尚未依天氣調整行程。

後端先使用 JSON，不使用 DB。唯讀種子在 `backend/data/trip.json`、`preferences.json`；首次讀取時建立 `backend/data/runtime/state.json`，包含版本、目前行程與偏好，後續讀寫都透過 A 的 RuntimeStore。原子 replace 與單程序鎖保護更新；僅支援單一 worker，不要使用 `--workers` 啟動多程序。runtime 已忽略版控，資料損壞或寫入失敗會報錯，不靜默重置。Demo 重置時先停止服務，再移除自己的 `state.json`，下次讀取由種子重建。

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
  -d '{"trip_id":"tokyo-demo","message":"下午開始下大雨"}'
```

### 結構與協作

- `frontend/`：Frontend owner，React SPA。
- `backend/agent/`：Backend A，parser / prompts、context、weather、preference / runtime、explanation；A 同時維護 `main.py` / `models.py`，整合單一 FastAPI。
- `backend/replanner/`：Backend B，deterministic 排程、candidate plans、可行性與 scoring / impact；只接受 context，不直接存取外部 API 或 runtime。
- `backend/data/`：B 管行程、候選、交通 fixture；A 管偏好種子、天氣 fixture 與 runtime。
- `backend/tests/`：API、天氣 context 與 runtime JSON 測試。

`weather.py` 已從 `replanner/` 移至 `agent/`；取得天氣由 A 負責，天氣如何影響行程由 B 負責。完整責任邊界與儲存決策見 [ADR 001](docs/decisions/001-backend-boundaries-runtime-json.md)。

從 main 分出 `feat/frontend`、`feat/agent`、`feat/replanner`，小步合併；共用 API 改動先同步規格。不要提交金鑰、虛擬環境或 runtime 資料。

技術參考：[Vite 環境要求](https://vite.dev/guide/)、[Tailwind Vite 整合](https://tailwindcss.com/docs/installation/using-vite)、[Open-Meteo 文件](https://open-meteo.com/en/docs)。使用即時天氣時顯示 Open-Meteo 資料來源。
