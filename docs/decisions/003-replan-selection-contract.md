# 003 重排、選擇與偏好契約增量

## Status

Accepted — 2026-09-12（外層 contract、snapshot、選擇交易與偏好更新已實作）

## Context

現有 API 有 health、trip、preferences、replan，replan 回傳沿用目前行程的 placeholder。已能保存行程與偏好，但完成「選 A → 記住偏好 → 第二次推薦」仍需固定可選 replan identity、候選方案差異、行程版本、選擇 response 與錯誤語意，使 Frontend、A、B 能平行實作。

## Decision

- 維持 `/api` prefix、UTF-8 snake_case JSON；日期、當地 `HH:mm` 與帶 offset datetime 規則見 [API 契約](../api-contract.md)。公開與 A/B 交換模型拒絕未宣告欄位。
- Trip 加入必填 `version >= 1`，成功套用方案後 +1。`ReplanSnapshot.trip_version` 與目前 Trip.version 不同時視為 stale，selection 回 409。
- ReplanResponse 固定含 `status`、UUID/null `replan_id`、`planning_source`、context、三個 plans、`recommended_plan_id`、`preference_insight`、warnings。`planning_source` 與 `weather.source` 是不同資料來源。
- Plan 固定含 A/B/C id/strategy、完整 multi-day items、`feasible`、`changes`、交通／費用 delta、`booking_warnings`、三策略各 0–1 的 features 與 explanation。
- PlanChange.action 固定為 `keep | move | cancel | add`。keep 的 from/to 完整且相同；move 的 from/to 完整且至少日期或時間不同；cancel 只有 from；add 只有 to。跨日移動因此保留原日期與新日期供比較。
- PlanningResult 與 ReplanSnapshot 都保存剛好三個 A/B/C Plan。raw score 不保存、不回 API；只有 feasible plan 可以成為 recommendation 或被選擇。
- `POST /api/selections` request 僅接受 UUID replan_id 與 A/B/C plan_id；200 response 固定含 SelectionRecord、更新後 Trip 與 Preference。後端只讀 snapshot 中的方案與 features，不接受前端自報 Plan 或權重。
- Snapshot 驗證、SelectionRecord 保存、Plan 套用、Trip.version +1 與 Preference 更新必須在同次 runtime 原子交易完成。相同選擇重送冪等回 200且不重複加分；同次改選、不可行或 stale 回 409；snapshot/plan 不存在回 404；storage error 回 503。
- Preference 三權重初始皆 1；選擇後對所選策略 +1，增加 selection_count。B 用 `sum(weight * feature)` 排序，同分固定 A/B/C；這不是模型訓練。
- 完整模型、nullable 規則與端點表集中於 API 契約；Pydantic 位於 `backend/models.py`。Selections route 已完成 snapshot/version/feasible 驗證、行程套用、偏好更新與冪等 response。

## Consequences

- Backend A 維護 API、Pydantic、snapshot 與原子 selection 交易；Backend B 依固定 `ReplanContext → PlanningResult` 提供跨日方案及 features；Frontend 可直接依 OpenAPI 同步 multi-day types、日期分組、比較與選擇狀態。
- 未注入 B 實例時，placeholder replan 不會產生可選 replan_id；只有已保存的 ready snapshot 可被 selections 套用，避免未驗證候選進入目前 Trip。
- 新增驗收涵蓋 schema/OpenAPI、不可行不可套用、stale Trip 409、選擇冪等、偏好重啟後仍存在與第二次排序原因。
- features 計算、完成活動判定、營業／交通 fixture、provider 注入及 runtime 內部 schema version 仍由各 owner 實作；不得自行改變已固定的外層欄位。
