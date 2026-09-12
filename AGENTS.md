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

## Safety

- 不提交 secrets 或真實憑證
- 不覆寫其他成員未提交的變更
- 執行刪除、force push、hard reset 等破壞性操作前必須詢問
