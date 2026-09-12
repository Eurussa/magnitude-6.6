# 003 重排、選擇與偏好契約增量

## Status

Proposed — [DEVELOPMENT_SPEC.md](../DEVELOPMENT_SPEC.md) 的方案選擇與偏好學習增量仍待共同確認及實作。`now`、天氣 context、Preference model / GET 與 runtime JSON 讀寫基礎已依 [ADR 004](004-backend-boundaries-runtime-json.md) 完成；此紀錄不將其餘目標 schema 視為已凍結。

## Context

現有 API 有 health、trip、preferences、replan，replan 回傳沿用目前行程的 placeholder。已能保存行程與偏好，但完成「選 A → 記住偏好 → 第二次推薦」仍需辨識候選方案、避免重複計分，並確保行程與偏好一起更新。

## Decision

以下為規格要求共同確認的目標：

- 維持 `/api` prefix、UTF-8 snake_case JSON，使用行程當地時間，分鐘為整數。單一 demo-user 不由前端指定 user_id。
- ReplanRequest 已有可選、帶 offset 的 ISO8601 `now`；僅供 Demo 的 `weather_override` 仍待確認。
- ReplanResponse 後續增加 UUID `replan_id`、`recommended_plan_id`、`preference_insight`；來源沿用已實作的 `weather.source`（live/fixture/unavailable），完成後 `status=ready`。
- Plan 增加 `feasible`、`changes`（item_id/action/reason）、`additional_travel_minutes`、`additional_cost_jpy`、`booking_warnings`、三策略各 0–1 的 `features`。
- 保存含原行程版本與 plans 的 replan snapshot，拒絕套用過期版本；只有 ready 且 feasible 可套用。
- `POST /api/selections` 接收 replan_id、plan_id，回傳 Trip 與 Preference；後端只讀保存的方案特徵，不接受前端自報權重。
- Selection 的 replan_id 唯一，選擇、套用行程與權重更新在同次 runtime 原子更新完成。相同選擇重送不重複加分；同次改選 409、方案不存在 404、不可行 409。
- Preference 三權重初始皆 1；選擇後對所選策略 +1，增加 selection_count。用 `sum(weight * feature)` 排序，同分固定 A/B/C，並顯示原因；這不是模型訓練。
- `GET /api/preferences` 已提供保存的偏好，runtime JSON 的 trip / preferences 讀寫已完成，JSON 種子唯讀、不使用 DB；保存選擇與 snapshot 仍待擴充 state schema。
- 外部供應商不可用時明示 fallback 或 503 `{"detail":"..."}`，Frontend 顯示 error 並允許重試。

## Consequences

- Backend A 維護 API、Pydantic 與持久化；Backend B 提供方案及 features；Frontend 同步 types、比較畫面與選擇狀態。
- 新增驗收涵蓋不可行不可套用、選擇冪等、偏好重啟後仍存在與第二次排序原因。
- 完整 changes.action enum、weather_override 結構、其餘回應型別／nullable、features 計算、行程版本／過期錯誤碼及選擇／snapshot 的 runtime schema 仍待共同確認。
- 確認後需同步開發規格、Pydantic、Frontend types 與此 ADR 狀態。現行契約仍以 `/openapi.json`、`/docs` 為準。
