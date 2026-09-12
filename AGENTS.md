# AGENTS.md

## Project

SmartTrip 是一個 5 小時、三人協作的黑客松專案，協助自由行旅客遇到睡過頭、休館或下雨時，比較替代行程，並從選擇更新偏好權重。

- 共用規格：`docs/DEVELOPMENT_SPEC.md`，產品範圍、API 目標與驗收以此為依據。
- 成功標準：一分鐘內展示「原行程 → 事件 → A/B/C → 選擇 → 第二次個人化推薦」。
- MVP 固定單一 `demo-user`、`tokyo-demo` 單日行程；不做登入、多使用者、多日最佳化、真實訂位取消或正式部署。

## Team responsibilities

- Frontend（repo owner）：`frontend/`，timeline、事件輸入、方案比較、loading/error、API types、選擇按鈕、偏好提示與 Google Maps link。
- Backend A：`backend/agent/` 的事件解析、context、天氣、偏好讀寫與推薦解釋；整合 `backend/main.py`、`backend/models.py`、LLM 設定、README 與共用 schema，後續負責 selections API。
- Backend B：`backend/replanner/` 的 deterministic candidates、可行性、scoring / impact；維護行程、候選與交通 fixture。
- `backend/data/` 依內容分工：A 管偏好、天氣與 runtime JSON，B 管行程與排程 fixture。
- API 欄位變更先通知三人，由 A 同步開發規格與 Pydantic，再由 Frontend 更新 TypeScript。A/B 先約定 module 介面；B 不直接修改 agent，A 不直接修改 B 的演算法。

## Current stage

- 已有 health/trip/preferences/replan API、JSON fixture、前端串接、Google Maps link、天氣 context 與 runtime JSON 行程／偏好讀寫。
- Replan 仍回傳 `status: placeholder`、`unknown` 事件與沿用目前行程的三方案，不能視為可執行的重排。
- 尚未實作真正 LLM 解析、重排、天氣影響排程、選擇 endpoint 與偏好學習；儲存與 context 基礎不代表完整 Demo。
- 技術棧與責任邊界整理於 `docs/decisions/`；最新 JSON 與 A/B 分工決策為 `004-backend-boundaries-runtime-json.md`。目標 API 增量仍須三人共同確認，不得視為已上線契約。

## Stack and development commands

- Frontend：React + Vite + TypeScript + React Router + Tailwind CSS（Vite plugin）；Node.js 22.12+、pnpm 11+，套件版本以 `frontend/package.json` 與 lockfile 為準。
- Backend：Python 3.11+、FastAPI、Pydantic v2、httpx、python-dotenv、Uvicorn；單一 server，agent/replanner 為 Python module。
- JSON 為唯讀種子；目前行程與偏好存於 `backend/data/runtime/state.json`，不使用 DB、runtime 不提交，只使用單一 worker。
- 在 repo 根目錄建立並啟用 `.venv` 後，執行 `python -m pip install -r backend/requirements.lock.txt`；以 `python -m uvicorn backend.main:app --reload --host 127.0.0.1 --port 8000` 啟動後端，不啟用多 worker。
- 在 `frontend/` 執行 `pnpm install --frozen-lockfile`、`pnpm dev`；Vite :5173 將 `/api` proxy 至 FastAPI :8000。
- 前端檢查：在 `frontend/` 執行 `pnpm lint`、`pnpm build`。
- 後端檢查：在 repo 根目錄、啟用 virtualenv 後執行 `python -m unittest discover -s backend/tests -v`。
- `.env` 位於 repo 根目錄，預設 mock 模式不需金鑰；LLM 金鑰只放後端，不使用 `VITE_` 變數傳給瀏覽器。

## Working agreements

- 先理解需求與現有文件，再提出實作
- 不自行假設未決定的技術棧、API schema 或部署方式
- Frontend 套件管理一律使用 pnpm，不使用 npm 或 yarn
- 重要決策記錄於 `docs/decisions/`
- 修改產品流程時，同步更新 `docs/product-flow.md`
- 修改核心名詞或資料關係時，同步更新 `docs/domain-model.md`
- B 只接收已驗證的 event / weather / preferences，不呼叫外部 API、不讀寫 runtime；A 不在 orchestration 內實作排程演算法。
- API 使用 `/api`、snake_case JSON；目前可執行 schema 以 `/openapi.json` 與 `/docs` 為準，目標增量見開發規格。
- LLM 僅解析事件與產生說明，輸出經 `Event.model_validate_json` 驗證；可行性由 deterministic heuristic 檢查，不直接採信模型產生的行程。
- 已完成活動不動；`booking=true` 或 `movable=false` 不得靜默移動，也不能為保留景點而解除預約鎖。只有 `ready` 且 `feasible` 的方案可套用。
- 天氣只影響對應時段的戶外活動，以行程時區（Demo 為 Asia/Tokyo）對齊；fixture/fallback 必須標示來源，未知天氣不能當晴天。交通時間為 fixture，Google Maps 使用座標 Search URL。
- 偏好學習是權重更新，不是模型訓練；未來選擇、套用行程與更新權重須在同次 runtime 原子更新完成，重複相同選擇不得重複加分。
- 不加入規格排除的 Next.js/SSR、LangGraph、CrewAI、Leaflet/OSM、Google Maps SDK、OR-Tools 或 PostgreSQL。

## Git and commit rules

- 遠端 `main` 為整合分支；團隊分支為 `feat/frontend`、`feat/agent`、`feat/replanner`。依規格每 30–45 分鐘整合可執行的小變更，經一位同伴檢查後合併；這不代表授權 agent 自行 commit。
- 合併前需通過前端 lint/build 與後端 unittest。
- 除非使用者明確要求，否則不主動建立 commit
- commit 前先檢查 `git status` 與 diff，確認沒有混入其他成員或使用者的變更
- 一個 commit 只包含一個可獨立理解的邏輯變更；不要把不相關的 frontend、backend 或文件修改綁在一起
- 使用 Conventional Commits，格式為 `<type>(<scope>): <description>`
- type 使用 `feat`、`fix`、`refactor`、`docs`、`test`、`chore` 其中之一
- scope 非必要；需要時優先使用 `frontend`、`backend`、`agent`、`replanner` 或 `docs`
- description 使用簡短英文祈使句，不加句號
- frontend 變更在 commit 前於 `frontend/` 執行 `pnpm lint` 與 `pnpm build`
- backend 變更在 commit 前執行後端 unittest
- 若檢查無法執行或未通過，必須明確說明，不得宣稱已驗證
- 不使用 `--no-verify` 跳過檢查
- 不 amend、rebase、force-push 或改寫既有 Git history，除非使用者明確要求
- 不直接 force-push `main`
- 不提交 `.env`、secrets、`node_modules`、`.venv`、`backend/data/runtime/` 或資料庫 runtime 檔案
- 共用檔案發生衝突時保留雙方變更並交由 owner 整合，不以整檔覆蓋處理

## Safety

- 不提交 secrets 或真實憑證
- 不覆寫其他成員未提交的變更
- 執行刪除、force push、hard reset 等破壞性操作前必須詢問
