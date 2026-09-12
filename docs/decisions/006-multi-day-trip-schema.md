# 006 Multi-day Trip、Event 與 Weather schema

## Status

Accepted — 2026-09-12

取代 [ADR 001](001-technology-stack.md) 的固定單日 MVP 範圍，以及 [ADR 004](004-backend-boundaries-runtime-json.md) 的 runtime schema version 1。LLM 重排責任仍依 [ADR 005](005-llm-driven-replanning.md)。

## Context

行程事件可能影響不只當天。Demo 情境中，旅客在日期接近時發現原定 2026-09-14 前往東京迪士尼樂園，但該日預報高機率降雨；合理方案可能把迪士尼整日移至較乾燥的 9/13，並將原本 9/13 的活動重新分配到其他日期。只有 `start_time`、沒有日期的單日 schema 無法表達這種重排，也無法把多日天氣正確交給 planning LLM。

## Decision

- `Trip` 增加必填 `version >= 1`、`start_date` 與 `end_date`，保留扁平 `items`。version 在成功套用 Plan 後 +1，供 snapshot 拒絕 stale selection；扁平結構延續既有 item-based Plan、Selection 與前端資料流，也能用 `scheduled_date` 分組成天，不新增巢狀 `TripDay`。
- `TripItem` 增加 `scheduled_date`，`start_time` 維持行程當地 24 小時 `HH:mm`。scheduled_date 必須位於 Trip date range，item id 在整趟 Trip 內唯一。
- 整日換日以同時更新該日所有受影響 TripItem 的 `scheduled_date` 表達。Plan 仍回傳完整 items；未出現在結果中的活動需由 changes 明示取消，不能只回傳局部 patch。
- `Event` 將單一 nullable `affected_item_id` 改為 `affected_item_ids: list[str]`，並增加 `affected_dates: list[date]`；`delay_minutes` 改為無單日上限的非負整數。A 的 parser 依 message、now 與 Trip timezone 解析「後天」等相對日期，B 只消費結構化結果。
- `WeatherContext` 將單一 `date` 改為 `start_date`／`end_date`，hours 可跨多天且每筆 time 帶 offset。A 從 `max(now 的行程當地日期, trip.start_date)` 取得到 `trip.end_date`；live 與 fixture 都必須涵蓋要求區間中的每個日期。
- `ReplanContext` 將完整 multi-day Trip、Event、WeatherContext、Preference 與 now 交給 B。Planning LLM 可跨日產生方案，B 驗證日期範圍、同日衝突、跨日限制及完整 item reference。
- `/api/trip` 與 `/api/replan` 沿用既有 route；`trip_id` 在 MVP 仍只接受 `tokyo-demo`，但該 Trip 與 Plan 可包含多天。這是「單一展示旅程」，不是「單日行程」。
- RuntimeState 升級為 `schema_version=2`。Version 1 沒有可靠的 item 日期，後端不猜測或靜默覆蓋；開發／Demo 升級時停止服務並移除自己的 ignored runtime state，再由 version 2 種子初始化。
- `backend/data/trip.json` 提供 2026-09-12 至 9/14 三日行程；`weather.json` 提供同日期區間，9/14 迪士尼日明顯較雨、9/13 較乾的展示資料。
- Frontend owner 後續同步 TypeScript types，並將 Trip 與 Plan items 依 scheduled_date 分組顯示。此次變更不修改 `frontend/` 下的任何檔案。

## Consequences

Replanner 能收到並回傳完整多日行程，事件與天氣也能明確指出受影響日期；迪士尼整日換日與交換日大幅重排可由相同 schema 表達。扁平 items 讓現有 runtime 與 Plan 結構保持簡單，但呼叫端若要顯示日程，必須自行依 scheduled_date 排序與分組。

這是 breaking API/schema change。現有 frontend types 仍是單日版本，需由 frontend owner 更新後才會正確顯示日期；舊 runtime version 1 也不能直接載入。B 的 Planning LLM 已能產生與驗證跨日方案，但目前 `main.py` placeholder 仍只會複製完整多日 Trip，須待 A 改接 async Protocol 才能由 HTTP 使用。
