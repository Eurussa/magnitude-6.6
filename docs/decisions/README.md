# Architecture Decision Records

此目錄用來記錄會影響團隊實作的重要決策。

## 目前決策

以下依 [DEVELOPMENT_SPEC.md](../DEVELOPMENT_SPEC.md) 整理，不代表相關功能皆已實作。規格已明確採用的技術、架構與外層契約標為 Accepted。

| 紀錄 | Status | 範圍 |
|---|---|---|
| [001 Frontend 與 Backend 技術棧](001-technology-stack.md) | Accepted；儲存由 004、單日範圍由 006 取代 | React SPA、FastAPI、執行環境、套件管理與 MVP 排除項目 |
| [002 事件解析、排程與外部資料邊界](002-planning-boundaries.md) | Superseded in part；天氣由 004、LLM 重排由 005 取代 | 舊排程邊界、天氣與地圖 fixture |
| [003 重排、選擇與偏好契約增量](003-replan-selection-contract.md) | Accepted；selection 已實作 | ready/feasible、snapshot、Trip version、選擇冪等、權重更新與持久化 |
| [004 Backend 分工與 runtime JSON](004-backend-boundaries-runtime-json.md) | Accepted；B 排程由 005、runtime schema version 1 由 006 取代 | A context／weather／儲存與 B 排程邊界、單 worker 原子 JSON、已完成與待實作介面 |
| [005 LLM-driven 行程重排與偏好排序](005-llm-driven-replanning.md) | Accepted | B 的 planning LLM、structured output 驗證與 deterministic preference scoring |
| [006 Multi-day Trip、Event 與 Weather schema](006-multi-day-trip-schema.md) | Accepted | 多日日期模型、跨日事件／方案、多日天氣與 runtime version 2 |

技術選型、contract 狀態與實作進度分開記錄；LLM 的事件解析、推薦說明、行程重排責任及外層 schema 已確定，provider/model 由 server-side `.env` 設定。Backend A 已完成事件 structured output／明確 fallback warning、replanner 503 邊界、deterministic 說明 fallback、snapshot 與 selection 交易；Backend B 已使用可設定的 OpenAI Responses API（預設 model `gpt-5.4-mini`）完成重排模組，並已由 `main.py` 串接。Frontend 已依 [API 契約](../api-contract.md) 同步 types。A 的 LLM 推薦說明仍待實作。

## 維護方式

- 重要變更新增 ADR，或補充尚未確認的 Proposed 紀錄；不可把討論中的方案直接標為 Accepted。
- Accepted 的決策被替換時保留原紀錄、標為 Superseded，並連結新的 ADR。
- 產品流程與資料關係分別同步 [product-flow.md](../product-flow.md) 與 [domain-model.md](../domain-model.md)。
- API schema 由 Backend A 整合；固定契約見 `docs/api-contract.md`，可執行契約以 `/openapi.json`、`/docs` 為準。

## 檔名格式

```text
NNN-short-title.md
```

例如：

```text
001-technology-stack.md
002-planning-boundaries.md
```

## 紀錄模板

```md
# NNN 決策名稱

## Status

Proposed | Accepted | Superseded

## Context

為什麼需要做這個決策？有哪些限制？

## Decision

最後決定採用什麼方式？

## Consequences

這個決策帶來哪些好處、成本與後續影響？
```
