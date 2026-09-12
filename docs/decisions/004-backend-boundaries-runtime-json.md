# 004 Backend 分工與 runtime JSON

## Status

Accepted — 2026-09-12；其中 Backend B 的 deterministic replanning 與「不呼叫 LLM」決策已由 [ADR 005](005-llm-driven-replanning.md) 取代，單日 Trip 與 runtime schema version 1 已由 [ADR 006](006-multi-day-trip-schema.md) 取代。天氣 ownership、runtime JSON 與其餘責任邊界仍有效。

取代 [ADR 001](001-technology-stack.md) 中的 SQLite 儲存選項，以及 [ADR 002](002-planning-boundaries.md) 的天氣 ownership／初始化進度敘述；排程方式後續由 ADR 005 更新。[ADR 003](003-replan-selection-contract.md) 已固定選擇與學習的外層契約，已完成的 context／儲存基礎以本紀錄及現行 schema 為準。

## Context

三人需在五小時內整合可展示的旅程重排 MVP。Repository 已採 React / Vite / TypeScript（pnpm）與 Python / FastAPI；舊文件把 Open-Meteo 分給 Backend B，偏好儲存則仍在 JSON / SQLite 間未定。此次確認 A 負責 context，B 負責 deterministic replanning，後端先使用 runtime JSON、不使用 DB。

## Decision

- 保留既有前端與後端技術棧，只啟動單一 FastAPI server。`agent/`、`replanner/` 是同一程序中的 Python modules。
- Backend A 擁有 `agent/parser.py`、`prompts.py`、`weather.py`、`preference.py`、`runtime.py`、`context.py`、`explanation.py`，並整合 `main.py`、`models.py` 與 API contract。
- 將 `replanner/weather.py` 移至 `agent/weather.py`。此檔負責 Open-Meteo、timeout / fallback、資料來源及日期時區正規化，不負責決定行程如何調整。五小時版本不另設 `services/`；外部 adapter 有多個使用者時再評估抽出。
- Backend B 擁有 `replanner/planner.py`、`scoring.py`：接收 trip、event、weather、preferences、now，產生 deterministic candidates、檢查可行性並計算 scoring / impact。B 不直接讀寫 JSON、不呼叫 Open-Meteo 或 LLM。
- B 回傳可檢查的方案事實與代價，A 產生使用者可讀說明；LLM 不決定方案可行性或直接修改排程。
- `backend/data/trip.json`、`preferences.json` 是唯讀種子。B 管行程、候選、交通及營業時間 fixture；A 管偏好、天氣 fixture 與可變 runtime 狀態，不把整個 `data/` 指派給單一 owner。
- 可變資料集中於 `backend/data/runtime/state.json`，目前含 `schema_version=1`、`trip`、`preferences`。A 的 RuntimeStore 在首次讀取時由種子初始化；後續驗證並讀寫 runtime，不覆寫種子。
- 每次狀態更新先完整寫入同目錄暫存檔、fsync，再以原子 replace 取代狀態檔，單程序鎖保護 read-modify-write；失敗時報錯，不靜默重置資料。
- 只部署單一 worker。鎖定方式不支援多程序並行寫入，也不宣稱具有跨服務資料庫交易保證。runtime 不納入 Git；開發／Demo 重置須先停止服務，再移除自己的 runtime 狀態，下次讀取由種子初始化。
- 選擇流程使用 `/api/selections` 與 `replan_id` / `plan_id`。伺服器保存候選 snapshot 後才接受選擇，套用行程、偏好與選擇紀錄在同次 runtime 更新完成；相同選擇重送回保存的 response，不重複加分。

## Consequences

A/B 可各自以固定輸入開發，整合依賴共用模型與函式介面；沒有第二個 server 或 DB 的設定成本。內部保存介面可讓偏好與目前行程跨重新啟動保留，種子仍可重置 Demo；本次沒有開放任意 HTTP 儲存或重置 endpoint。

單檔 JSON 適用單使用者 Hackathon 展示，資料量增加時重寫成本會上升；多 worker、正式多使用者與大量歷史紀錄皆不在此決策範圍。事件 LLM、儲存與選擇交易完成不代表 B 的真實跨日重排完成；以 API 實作狀態及測試為準。
