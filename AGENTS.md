# AGENTS.md

## Project

這是一個協助旅客在突發事件發生後，重新安排旅程的黑客松專案。

## Team responsibilities

- Frontend：由目前 repo owner 負責
- Backend：由另外兩位成員負責
- 前後端透過明確的 API contract 協作

## Current stage

- 專案處於需求與架構討論階段
- 前端技術尚未決定
- 未記錄於 `docs/decisions/` 的技術選型，不視為已確定

## Working agreements

- 先理解需求與現有文件，再提出實作
- 不自行假設未決定的技術棧、API schema 或部署方式
- 重要決策記錄於 `docs/decisions/`
- 修改產品流程時，同步更新 `docs/product-flow.md`
- 修改核心名詞或資料關係時，同步更新 `docs/domain-model.md`
- 套件管理工具與開發指令確定後，補充於本文件

## Git and commit rules

- 除非使用者明確要求，否則不主動建立 commit
- commit 前先檢查 `git status` 與 diff，確認沒有混入其他成員或使用者的變更
- 一個 commit 只包含一個可獨立理解的邏輯變更；不要把不相關的 frontend、backend 或文件修改綁在一起
- 使用 Conventional Commits，格式為 `<type>(<scope>): <description>`
- type 使用 `feat`、`fix`、`refactor`、`docs`、`test`、`chore` 其中之一
- scope 非必要；需要時優先使用 `frontend`、`backend`、`agent`、`replanner` 或 `docs`
- description 使用簡短英文祈使句，不加句號
- frontend 變更在 commit 前執行 `npm run lint` 與 `npm run build`
- backend 變更在 commit 前執行後端 unittest
- 若檢查無法執行或未通過，必須明確說明，不得宣稱已驗證
- 不使用 `--no-verify` 跳過檢查
- 不 amend、rebase、force-push 或改寫既有 Git history，除非使用者明確要求
- 不直接 force-push `main`
- 不提交 `.env`、secrets、`node_modules`、`.venv` 或 SQLite runtime 檔案
- 共用檔案發生衝突時保留雙方變更並交由 owner 整合，不以整檔覆蓋處理

## Safety

- 不提交 secrets 或真實憑證
- 不覆寫其他成員未提交的變更
- 執行刪除、force push、hard reset 等破壞性操作前必須詢問
