# Backend B Replanner

`LLMReplanner` 實作固定的 `ReplanContext → PlanningResult` async Protocol。Planning LLM 只決定可信 item id 的日期與時間；Python 從原 Trip／候選 fixture 補回不可變欄位，再檢查日期、已完成活動、預約／不可移動鎖、營業時間、交通間隔、事件與多日天氣，最後衍生 changes、交通／費用 delta、features 與 deterministic recommendation。

## Shared configuration

複製 repository root 的 `.env.example` 為 root `.env`。Agent 與 Replanner 共用這組 `LLM_` 設定；真正的 `.env` 已由 `.gitignore` 排除，請勿將金鑰放入前端變數、測試或 commit。

```text
LLM_API_KEY=...
LLM_BASE_URL=https://api.openai.com/v1
LLM_MODEL=gpt-5.4-mini
LLM_TIMEOUT_SECONDS=8
```

有 `LLM_API_KEY` 時 Replanner 使用 `live` mode；沒有 key 時使用 `fixture` mode。

`fixture` mode 不呼叫網路。`live` mode 透過 `httpx.AsyncClient` 呼叫 OpenAI `POST /v1/responses`，設定 `store=false` 並使用 strict JSON Schema Structured Outputs。送給模型的 planning facts 會預先整理固定項目、活動結束時間、完整交通矩陣、事件限制與高風險天氣時段。方案限制失敗時保留已驗證方案，下一次只要求修復失敗方案；預設最多嘗試三次，之後才使用明確標示 `source=fixture` 的 demo fallback。

參考：[Responses API](https://developers.openai.com/api/reference/cli/resources/responses/methods/create)、[Structured Outputs](https://developers.openai.com/api/docs/guides/structured-outputs)。

## Integration boundary

Backend A 在 application boundary 建立一次 instance 並注入，不要在 route 內重複載入設定：

```python
replanner = LLMReplanner.from_settings()
planning = await replanner.generate_plans(context)
```

A 負責 context、runtime、snapshot、使用者可讀 explanation 與 HTTP error；B 不 import `agent/`、不讀寫 runtime，也不取得天氣。舊的同步 `candidate_plans(...)` 只供尚未改接的 placeholder route 使用。
