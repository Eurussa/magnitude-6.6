# 005 LLM-driven 行程重排與偏好排序

## Status

Accepted — 2026-09-12

取代 [ADR 002](002-planning-boundaries.md) 與 [ADR 004](004-backend-boundaries-runtime-json.md) 中由 deterministic Python heuristic 產生候選行程，以及 Backend B 不呼叫 LLM 的決策。ADR 004 的天氣 ownership、runtime JSON 與其他模組邊界仍有效。

## Context

先前設計由 Backend B 以固定 Python 規則產生 A/B/C 行程，LLM 僅解析事件與產生說明。團隊確認產品的核心 AI 能力應包含行程規劃本身：Backend B 必須把結構化的完整多日行程、事件、日期區間天氣、偏好與目前時間提供給 planning LLM，由模型產生三個不同的跨日重排方案，而不是由 Python 規則決定如何移動或取消活動。

候選行程由 LLM 產生仍需要穩定的輸出契約、失敗處理與可重現的偏好排序。使用者第二次重排時應能可靠地看到上一次選擇影響推薦結果，因此 candidate generation 與 preference ranking 採不同責任。

## Decision

- Backend A 組裝已驗證的 `ReplanContext`，包含 `Trip`、`Event`、`WeatherContext`、`Preference` 與 `now`，並呼叫固定的 `await Replanner.generate_plans(context) -> PlanningResult` Protocol。A 繼續負責事件解析、天氣取得、runtime、使用者可讀推薦說明，以及共用 LLM provider/model/key 設定的整合。
- Backend B 擁有 replanner 的 planning prompt、LLM 呼叫與 planning structured-output schema。B 將完整 multi-day context 提供給 planning LLM，要求產生 A 保留預約、B 保留最多景點、C 最輕鬆三個候選方案；事件可影響多個日期，方案可整日換日並重排其他受影響日期。
- Python 不以 heuristic 產生或決定候選行程。B 使用 Python 進行 orchestration、Pydantic 驗證、日期範圍、項目參照與重複檢查，以及同日時間、跨日移動、預約、交通／營業 fixture 等必要限制驗證；無效輸出不得直接標示為 ready。
- planning LLM timeout、無效 JSON 或不符合限制時，B 應採有限次重試、明確標示的 planning fixture/fallback，或回傳可恢復的 provider error。測試不得呼叫真實 LLM。
- B 可以呼叫設定好的 LLM provider，但不呼叫 Open-Meteo 等 context provider、不讀寫 runtime，也不依賴 `agent/` 的內部實作。A/B 透過共用 model 與明確的 LLM client/config 介面整合。
- B 從已驗證方案整理 impact 與三種 preference features，使用 `sum(weight * feature)` 計算 deterministic internal score。相同輸入應得到穩定排序，同分依固定 A/B/C 順序處理。`PlanningResult` 固定回傳 source、排序後且剛好三個的 A/B/C plans、recommended_plan_id 與 warnings。
- raw score 不加入 API response。B 對外提供排序後的 plans 與 `recommended_plan_id`；A 根據方案事實、偏好與推薦結果產生使用者可讀的個人化說明。
- LLM 產生的活動、時間與說明均視為不可信輸入；只有通過 schema 與必要限制驗證的方案才能成為可套用方案。

## Consequences

行程重排能展示真正的生成式 AI 規劃能力，B 也能獨立調整 prompt、structured output 與重試策略。偏好排序維持 deterministic，可讓 Demo 的第二次推薦穩定反映先前選擇，而不必向前端暴露難以解釋的 raw score。

此設計增加 LLM latency、成本與非決定性，也需要 provider mock、planning fixture、schema 驗證與錯誤恢復測試。A/B 必須共同確認共用 LLM client/config、planning output model 與 API 整合；在這些功能完成前，現有 `candidate_plans` 仍是 placeholder，不得宣稱已完成 LLM 重排。
