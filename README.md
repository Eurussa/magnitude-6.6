# magnitude-6.6
Sea x OpenAI Taiwan Hackathon 2026

## SmartTrip — 5 小時 Hackathon 初始化

三人共用規格與分工：[docs/DEVELOPMENT_SPEC.md](docs/DEVELOPMENT_SPEC.md)。

目前可啟動前後端、查看東京行程、開啟 Google Maps、送出事件並取得 A/B/C **placeholder**。尚未完成 LLM、真正重排、天氣串接與偏好學習；完整 Demo 是接下來三人的開發目標。

### 環境與啟動
需要 Node.js 22.12+（`.nvmrc` 指定 22）、npm、Python 3.11+。

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
npm ci
npm run dev
```

開啟 http://localhost:5173；API 文件 http://127.0.0.1:8000/docs。
Vite 將 `/api` 轉送至 8000；production build 僅產生靜態檔，正式 hosting 需另外配置 SPA fallback 與 `/api` reverse proxy。

`.env` 放在 repo 根目錄，由後端明確載入；初始化不需要 key。未來 LLM key/model 僅供後端使用，勿放入 VITE_ 變數。WEATHER_MODE 預留 mock/live 設定，目前 placeholder 不使用外部天氣。種子資料在 backend/data/；runtime 寫入 backend/data/runtime/ 或 SQLite，已忽略版控。

### 驗證

```sh
# repo root, virtualenv activated
python -m unittest discover -s backend/tests -v
# frontend
cd frontend
npm run build
npm run lint
```

```sh
curl http://127.0.0.1:8000/api/health
curl -X POST http://127.0.0.1:8000/api/replan \
  -H 'Content-Type: application/json' \
  -d '{"trip_id":"tokyo-demo","message":"下午開始下大雨"}'
```

### 結構與協作

- `frontend/`：Frontend owner，React SPA。
- `backend/agent/`：Backend A，事件理解與偏好；A 同時維護 main.py / models.py。
- `backend/replanner/`、`backend/data/`：Backend B，排程、評分、天氣與 fixture。
- `backend/tests/`：最小 API 契約測試。

從 main 分出 `feat/frontend`、`feat/agent`、`feat/replanner`，小步合併；共用 API 改動先同步規格。不要提交金鑰、虛擬環境或 runtime 資料。

技術參考：[Vite 環境要求](https://vite.dev/guide/)、[Tailwind Vite 整合](https://tailwindcss.com/docs/installation/using-vite)、[Open-Meteo 文件](https://open-meteo.com/en/docs)。使用即時天氣時顯示 Open-Meteo 資料來源。
