# AGENTS.md

## Project

這是一個協助旅客在突發事件發生後，重新安排旅程的黑客松專案。

## Team responsibilities

- Frontend：由目前 repo owner 負責
- Backend A：`agent/` 的事件解析、context、天氣、偏好讀寫與推薦解釋；整合 `main.py` 與 `models.py`
- Backend B：`replanner/` 的 deterministic candidates、可行性、scoring / impact；維護行程、候選與交通 fixture
- `data/` 依內容分工：A 管偏好、天氣與 runtime JSON，B 管行程與排程 fixture；不是整包由 B 擁有
- 前後端透過明確的 API contract 協作

## Current stage

- 已有 React / Vite / TypeScript 前端、單一 FastAPI 後端與 placeholder replan；完整 Demo 仍在開發
- 後端先使用 runtime JSON，不使用 DB；唯讀種子與可變狀態分開，服務限單 worker
- 已確認架構見 `docs/decisions/001-backend-boundaries-runtime-json.md`；新增技術選型仍須記錄於 `docs/decisions/`

## Working agreements

- 先理解需求與現有文件，再提出實作
- 不自行假設未決定的技術棧、API schema 或部署方式
- Frontend 套件管理一律使用 pnpm，不使用 npm 或 yarn
- 重要決策記錄於 `docs/decisions/`
- 修改產品流程時，同步更新 `docs/product-flow.md`
- 修改核心名詞或資料關係時，同步更新 `docs/domain-model.md`
- 前端使用 `pnpm dev`；後端使用 `python -m uvicorn backend.main:app --reload`，不啟用多 worker
- B 只接收已驗證的 event / weather / preferences，不呼叫外部 API、不讀寫 runtime；A 不在 orchestration 內實作排程演算法

## Git and commit rules

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
