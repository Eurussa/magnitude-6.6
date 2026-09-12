# PRD：重排來源警示與方案差異呈現

## 文件狀態

- 狀態：可交接
- Owner：Frontend
- 日期：2026-09-12
- API 契約：沿用既有契約，不變更 endpoint、request 或 response schema
- 相關規格：[`DEVELOPMENT_SPEC.md`](../../../docs/DEVELOPMENT_SPEC.md)、[`api-contract.md`](../../../docs/api-contract.md)、[`ADR 003`](../../../docs/decisions/003-replan-selection-contract.md)、[`ADR 005`](../../../docs/decisions/005-llm-driven-replanning.md)

## 背景與問題

SmartTrip 的替代方案可能由即時 planning LLM 或離線 fixture 產生，天氣也可能來自即時資料、fixture 或 unavailable 狀態。後端已在 `ReplanResponse` 回傳 `planning_source`、`weather.source`、`warnings` 與 `weather.warnings`，但目前 `src/components/ResultsView.tsx` 只在 `status === 'placeholder'` 時標示示範資料。`status === 'ready'` 使用 fixture 或 fallback 時，畫面看起來可能與即時結果相同。

每個方案也已回傳 `changes`、`additional_travel_minutes`、`additional_cost_jpy` 與 `booking_warnings`。目前 `src/components/PlanCard.tsx` 只顯示 explanation、最終行程與 booking warnings，使用者無法快速比較活動保留、移動、取消、新增，以及交通時間和費用差異。

這與共用規格要求的「fixture/fallback 必須清楚標示」及「方案需呈現代價與預約影響」不一致。

## 目標

完成後，使用者在 A/B/C 結果頁可以：

1. 分辨行程規劃與天氣資料各自來自即時服務、fixture 或 unavailable。
2. 看見後端提供的 fallback／限制警告，不會把展示資料誤認為即時結果。
3. 不展開完整行程也能比較各方案的交通時間、費用及異動數量。
4. 展開方案後能查閱每個活動的保留、移動、取消或新增內容及原因。

## 非目標

- 不修改後端 API、Pydantic schema 或 TypeScript API 型別。
- 不新增第三方 dependency。
- 不重新計算方案可行性、交通時間、費用、天氣或偏好分數。
- 不從 warning 字串反推結構化來源。
- 不顯示 raw preference score 或 `features`。
- 不改變 ready／feasible 才能套用方案的既有規則。
- 不處理 A 的 LLM 推薦文字說明功能；目前 response 沒有獨立的 explanation source，前端只顯示後端給定的 warning。

## 已確認資料契約

本功能只消費 `src/api/client.ts` 已驗證的欄位：

| 欄位 | 型別／單位 | 顯示用途 |
|---|---|---|
| `status` | `placeholder \| ready` | 決定是否可套用及是否沿用既有 placeholder 提示 |
| `planning_source` | `live \| fixture \| unavailable` | 行程規劃來源 |
| `weather.source` | `live \| fixture \| unavailable` | 天氣資料來源；不得與 planning source 混用 |
| `warnings` | `string[]` | context 與 replanner 合併警告 |
| `weather.warnings` | `string[]` | 天氣 adapter 警告 |
| `Plan.changes` | `PlanChange[]` | 每個活動的 keep／move／cancel／add 明細 |
| `additional_travel_minutes` | integer，分鐘，可為負 | 相對原行程的交通時間差 |
| `additional_cost_jpy` | integer，JPY，可為負 | 相對原行程的費用差 |
| `booking_warnings` | `string[]` | 方案層級的預約影響 |

`PlanChange` 的 `from_date`／`from_start_time` 與 `to_date`／`to_start_time` 依 action 可能為 null。前端不得為 null 值補造時間。

## 使用流程與 UI 規則

### 1. 結果來源與警告

當 `ReplanResponse` 顯示後，在事件摘要之前、偏好提示附近呈現「本次資料來源」區塊。行程規劃與天氣是兩個獨立來源，必須各自標示。

來源文案固定如下：

| 欄位值 | 行程規劃 | 天氣資料 |
|---|---|---|
| `live` | `AI 即時產生` | `即時天氣資料` |
| `fixture` | `使用示範方案` | `使用示範天氣` |
| `unavailable` | `目前沒有可用的規劃來源` | `目前沒有可用的天氣資料` |

顯示規則：

- `ready` 結果固定顯示兩個來源，不因 warnings 為空而隱藏。
- 任一來源為 `fixture` 或 `unavailable` 時，區塊使用 warning 視覺層級，並有文字說明，不能只靠顏色或圖示。
- 兩個來源皆為 `live` 且沒有 warning 時，使用低權重資訊樣式，避免搶過方案內容。
- `placeholder` 保留既有「示範方案，尚未由後端完成重排」提示，不得顯示成可執行的 ready 結果。
- warnings 來源使用 `result.warnings` 與 `result.weather.warnings` 的聯集，以完全相同字串去重，保留首次出現順序。
- 空字串不顯示；非空 warning 逐筆列出，不合併改寫後端語意。
- 本區塊可使用 `role="status"`。不要讓同一 warning 同時存在多個 live region，避免螢幕閱讀器重複播報。

### 2. 方案收合摘要

每張 `PlanCard` 在 explanation 下方、操作按鈕之前固定顯示以下摘要：

- 交通時間差
- 費用差
- `keep`、`move`、`cancel`、`add` 各 action 的數量
- 有 `booking_warnings` 時顯示預約提醒數量；完整文字沿用既有警告區塊

數值文案規則：

| 數值 | 交通時間 | 費用 |
|---|---|---|
| 大於 0 | `交通 +20 分鐘` | `費用 +¥1,200` |
| 等於 0 | `交通時間不變` | `費用不變` |
| 小於 0 | `交通節省 20 分鐘` | `費用節省 ¥1,200` |

- JPY 使用 `Intl.NumberFormat('zh-TW')` 或等效格式加千分位，不顯示小數。
- 負值顯示絕對值並使用「節省」，不要顯示成 `+-20`。
- action 數量即使為 0 仍保留，讓三張卡的比較欄位一致，例如：`保留 5・移動 2・取消 0・新增 1`。
- 不得把負數一律視為好、正數一律視為壞；只陳述增減，不自行產生評價。

### 3. 展開後的完整異動

沿用目前「查看行程／收起行程」按鈕及同一個 expanded state。展開後先顯示「方案異動」，再顯示既有「方案中的行程」。不增加第二組互相競爭的 accordion。

異動排序固定為：`move` → `cancel` → `add` → `keep`；同 action 內維持後端陣列順序。每筆顯示活動名稱、時間變化與 `reason`：

- `keep`：`保留｜活動名稱｜9/12 12:00`
- `move`：`移動｜活動名稱｜9/12 09:00 → 9/13 18:30`
- `cancel`：`取消｜活動名稱｜原訂 9/12 09:00`
- `add`：`新增｜活動名稱｜9/13 15:00`

日期以 `M/D` 顯示、時間沿用行程 timezone 的 `HH:mm`，不得套用瀏覽器本地時區換算。缺少契約允許為 null 的 from/to 時段時，只顯示存在的一側，不補造值。

活動名稱 lookup 規則：

1. 先從重排前的 `Trip.items` 以 `item_id` 查找，確保被取消的活動仍可顯示名稱。
2. 找不到時再從該方案的 `plan.items` 查找，支援 add 項目。
3. 仍找不到時顯示 `活動 ${item_id}`，不得隱藏該 change 或顯示空白。

為此 `TripPage` 必須將重排前的 `trip.items` 傳給 `ResultsView`，再傳給 `PlanCard`。不修改 response schema，也不直接使用 array index 當 key。

### 4. 可行性與操作

- `status === 'ready'`、`replan_id !== null`、`plan.feasible === true` 且沒有正在套用其他方案時，才可套用。
- 來源為 fixture 不會自動禁止套用；ready fixture 已由後端驗證並保存 snapshot，是否可套用仍以 `status` 與 `feasible` 為準。
- `placeholder`、unavailable planning 或不可行方案維持不可套用。
- 顯示來源、warning 或 changes 不得改變現有 apply loading、error、返回及重新描述狀況流程。

## 響應式與無障礙要求

- 維持 mobile-only 單欄版面，主要驗收寬度為 414px 與 375px。
- 來源名稱、warning、活動名稱、reason 與金額必須換行，不得造成水平捲動。
- 不以 tooltip 或 hover 承載必要資訊。
- action、來源與警告均需有可讀文字，不能只靠顏色或 emoji。
- 既有按鈕需維持至少 44×44px、可見 focus、`aria-expanded` 與 `aria-controls`。
- 展開內容加入異動明細後，`aria-controls` 指向的容器必須包含異動與完整行程。
- 動畫繼續遵守 `prefers-reduced-motion`；本功能不要求新增動畫。

## 實作交接

| 任務 ID／owner | 依賴 | 修改範圍 | 實作要求 | 驗證 |
|---|---|---|---|---|
| FE-1／Frontend | 現有 `ReplanResponse` | `src/components/ResultsView.tsx`；可視需要新增小型 presentation component | 顯示 planning/weather source；合併並去重 warnings；保留 placeholder 語意 | ready live、ready fixture、weather unavailable、重複 warning、無 warning |
| FE-2／Frontend | FE-1 非阻塞，可同時進行 | `src/pages/TripPage.tsx`、`src/components/ResultsView.tsx`、`src/components/PlanCard.tsx` | 將原始 Trip items 傳入卡片；顯示 delta 與 action counts；展開顯示完整 changes | keep/move/cancel/add、正零負 delta、取消與新增名稱 lookup |
| FE-3／Frontend | FE-1、FE-2 | 視重用需要放在 `src/utils/`；不得新增 dependency | 抽出純函式處理來源 label、warning 去重、delta 格式與 change lookup；避免 JSX 內重複分支 | lint、build、瀏覽器窄螢幕與鍵盤檢查 |

FE-1 與 FE-2 可平行實作；FE-3 是整合與整理，不應擴張成無關重構。

## 驗收條件

1. **Given** ready response 的 `planning_source` 為 `fixture`，**When** 結果頁顯示，**Then** 使用者在方案列表之前看見「使用示範方案」，且方案是否可套用仍只由 ready／feasible 決定。
2. **Given** `weather.source` 為 `fixture` 或 `unavailable`，**When** 結果頁顯示，**Then** 使用者分別看見「使用示範天氣」或「目前沒有可用的天氣資料」，不會被呈現為即時天氣。
3. **Given** 相同警告同時存在於 `warnings` 與 `weather.warnings`，**When** 頁面顯示，**Then** 完全相同的文字只出現一次。
4. **Given** planning/weather 都是 live 且 warnings 為空，**When** 結果頁顯示，**Then** 仍可辨識兩個來源，但來源資訊不使用錯誤樣式。
5. **Given** 某方案交通為 `-15` 分鐘、費用為 `1200` JPY，**When** 卡片收合，**Then** 顯示「交通節省 15 分鐘」及「費用 +¥1,200」。
6. **Given** 方案 changes 包含 keep、move、cancel、add，**When** 卡片收合，**Then** 四種 action 數量都可見；**When** 展開卡片，**Then** 每筆異動的活動名稱、有效 from/to 時段與 reason 都可見。
7. **Given** cancel item 不存在於 `plan.items`，**When** 顯示異動，**Then** 前端可由重排前 Trip 找到活動名稱；若兩邊都找不到，顯示 `活動 ${item_id}`。
8. **Given** `status === 'placeholder'` 或方案 `feasible === false`，**When** 使用者查看卡片，**Then** 套用按鈕維持 disabled，新增資訊不會解鎖操作。
9. **Given** 375px 或 414px viewport、長 warning、長活動名稱與長 reason，**When** 捲動及展開三張方案卡，**Then** 頁面沒有水平溢出，最後一筆內容與操作按鈕可到達。
10. **Given** 鍵盤或螢幕閱讀器操作，**When** 展開或收起方案，**Then** button 的 expanded/control 關係正確，來源與 warning 不會被重複播報。

## 接手者需執行的驗證

在 `frontend/` 執行：

```bash
pnpm lint
pnpm build
```

瀏覽器手動驗收：

- 414px 與 375px 直向 viewport。
- ready live、ready planning fixture、weather fixture、weather unavailable。
- warnings 空陣列、單筆、跨陣列重複及長文字。
- 四種 change action、未知 item id、正／零／負 delta。
- 方案展開／收起、鍵盤 focus、套用 loading／disabled 與 apply error。

專案目前沒有 test script，不得宣稱已執行不存在的自動化測試。

## 實作現況與文件差異

- API types 與 runtime validation 已包含本功能需要的全部欄位，屬於「程式已實作」。
- ready 結果來源／warning 顯示、delta 摘要與 changes 明細屬於「需求已確認但前端未實作」。
- `docs/product-flow.md` 前段仍保留舊 placeholder／501 進度敘述，但同檔後段與 `docs/DEVELOPMENT_SPEC.md` 已說明 ready replan、snapshot 和 selection 已完成。實作者應以現行程式、固定 API 契約及較新的完成狀態為準，不得退回 placeholder-only 行為。

## 未決事項

無阻塞未決事項。若未來產品要求精確區分「LLM explanation」與「deterministic explanation fallback」，需由 Backend A 另提 API 契約變更；本 PRD 不以解析 warning 字串替代該欄位。
