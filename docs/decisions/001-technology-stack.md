# 001 Frontend 與 Backend 技術棧

## Status

Accepted — 整理自 [DEVELOPMENT_SPEC.md](../DEVELOPMENT_SPEC.md) 的 Tech Stack 與架構；pnpm 指令依目前專案設定與協作規則。固定單日 MVP 的範圍已由 [ADR 006](006-multi-day-trip-schema.md) 取代。

儲存選項：Superseded by [ADR 004](004-backend-boundaries-runtime-json.md)（2026-09-12），目前使用 runtime JSON、不使用 DB。下方 SQLite 敘述保留為決策歷史；其餘技術棧仍為 Accepted。

## Context

三人需在 5 小時內完成固定東京單日行程的兩次事件 Demo。Frontend 由 repo owner 負責，Backend 分為事件／API 與重排兩個負責範圍，需共用契約並能本機展示。

## Decision

- Frontend 使用 React + Vite + TypeScript + React Router + Tailwind CSS（Vite plugin），以 SPA 提供 `/trip`。
- 使用 Node.js 22.12+、pnpm 11+，版本以 package.json / lockfile 為準；Frontend 安裝與開發使用 pnpm。
- Backend 使用 Python 3.11+、FastAPI、Pydantic v2、httpx、python-dotenv 與 Uvicorn。
- 本機由 Vite :5173 將 `/api` proxy 到 FastAPI :8000；agent/replanner 共用單一後端程序。
- JSON 保存唯讀種子；選擇與偏好可用 Python stdlib SQLite，runtime 檔不提交。完整資料表設計尚未確定。
- MVP 不使用 Next.js/SSR、LangGraph、CrewAI、Leaflet/OSM、Google Maps SDK、OR-Tools 或 PostgreSQL，也不包含正式部署。

## Consequences

- Frontend 與兩位 Backend owner 透過 HTTP API、Pydantic 與 TypeScript types 協作；共用 schema 由 Backend A 整合。
- 本機須啟動前後端；開發與驗證指令見 [AGENTS.md](../../AGENTS.md) 及 [README.md](../../README.md)。
- 目前已有初始化串接，技術棧確定不代表完整重排與偏好功能已完成。
- 正式 hosting、登入、多使用者、跨城市與任意長期規劃留在 MVP 範圍外，不能從此紀錄推定部署方案；多日 Trip schema 依 ADR 006。
