# Architecture Decision Records

此目錄用來記錄會影響團隊實作的重要決策。

## 目前決策

以下依 [DEVELOPMENT_SPEC.md](../DEVELOPMENT_SPEC.md) 整理，不代表相關功能皆已實作。規格已明確採用的技術與架構標為 Accepted；仍要求三人共同確認的 API 增量標為 Proposed。

| 紀錄 | Status | 範圍 |
|---|---|---|
| [001 Frontend 與 Backend 技術棧](001-technology-stack.md) | Accepted | React SPA、FastAPI、執行環境、套件管理與 MVP 排除項目 |
| [002 事件解析、排程與外部資料邊界](002-planning-boundaries.md) | Accepted | 單一 server、LLM 驗證、deterministic heuristic、天氣與地圖 fixture |
| [003 重排、選擇與偏好契約增量](003-replan-selection-contract.md) | Proposed | ready/feasible、snapshot、選擇冪等、權重更新與持久化 |

技術選型狀態與實作進度分開記錄；例如 LLM 的職責已確定，但 provider/model 尚未選定，真正解析仍未實作。目標契約確認後，由 owner 同步規格、Pydantic、Frontend types 與對應 ADR 狀態。

## 維護方式

- 重要變更新增 ADR，或補充尚未確認的 Proposed 紀錄；不可把討論中的方案直接標為 Accepted。
- Accepted 的決策被替換時保留原紀錄、標為 Superseded，並連結新的 ADR。
- 產品流程與資料關係分別同步 [product-flow.md](../product-flow.md) 與 [domain-model.md](../domain-model.md)。
- API schema 由 Backend A 整合；目前可執行契約以 `/openapi.json`、`/docs` 為準，目標契約以開發規格標示。

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
