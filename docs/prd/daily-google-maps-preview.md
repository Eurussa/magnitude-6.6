# PRD：每日 Google Maps 路線預覽

## 文件狀態

- 狀態：可交接
- 日期：2026-09-12
- Owner：Frontend
- 功能類型：既有多日行程頁的唯讀視覺增量
- 依據：`docs/DEVELOPMENT_SPEC.md`、`docs/api-contract.md`、`docs/decisions/006-multi-day-trip-schema.md`、`frontend/AGENTS.md`

## 背景與目標

SmartTrip 已能依 `TripItem.scheduled_date` 顯示東京三日行程，且每個活動已有經緯度與單點 Google Maps Search URL。現在缺少的是「一天之內會移動多大範圍」的快速視覺概覽。

本功能在目前行程頁嵌入一張 Google Maps 每日路線預覽。使用者選擇日期後，預覽只呈現該日活動，讓使用者不離開 SmartTrip 也能理解當天的大致移動範圍；需要進一步查看時，再開啟 Google Maps。

成功結果：Demo 中切換 2026-09-12、2026-09-13、2026-09-14 時，嵌入預覽與外部 Google Maps 路線連結皆只包含所選日期的活動，且不影響原有 timeline、重排與方案套用流程。

## 已確認決策

- 使用 Google Maps Embed API 的 iframe `directions` mode，不安裝 Google Maps JavaScript SDK。
- 地圖只做每日路線範圍預覽，不提供 App 自訂的標記、拖拉、路線編輯或導航操作。
- 日期由使用者明確選擇；不顯示整趟旅程合併路線。
- 使用既有 `TripItem` 的 `scheduled_date`、`name`、`latitude`、`longitude`，不新增或修改後端 API。
- Google Maps API key 已由使用者放在 repository root 的 `.env`；實作者不得讀取、輸出或提交實際 key。
- 保留可在新分頁／Google Maps App 開啟當日路線的連結。

## 範圍

### 包含

- 目前行程頁新增每日路線預覽區塊。
- 顯示 Trip 日期範圍內、實際有活動的日期選擇器。
- 選擇日期時更新 iframe 及外部路線 URL。
- 0、1、2 個以上活動的明確顯示規則。
- API key 缺少時的可理解 fallback。
- 414px 與 375px mobile viewport、鍵盤操作及 iframe lazy loading。
- 實作完成後同步 `docs/product-flow.md` 中的 Google Maps 流程與目前實作描述。

### 不包含

- Google Maps JavaScript SDK、Static Maps API、Routes API、Places API 或新的 dependency。
- 即時交通、交通時間、費用、最佳路線、到站時間或路線最佳化。
- App 自訂地圖互動、Marker、Polyline、導航、定位或權限請求。
- 跨日合併地圖、跨城市或任意旅程。
- 在 A/B/C 方案卡片內各自嵌入地圖；本次只處理目前已套用／載入的 Trip。
- 後端儲存、proxy API 或 API schema 變更。

## 使用流程與 UI 狀態

### 初始載入

1. 使用者開啟 `/trip`。
2. `GET /api/trip` 成功後，前端依 `scheduled_date` 分組。
3. 預設選取日期依序為：行程 timezone 的今天（若該日有可見活動）、第一個尚有可見活動的未來日期、否則第一個有活動的日期。
4. 在多日 timeline 前顯示「當日路線」區塊、日期選擇器、Google Maps iframe 與外部開啟連結。

日期選擇器使用真正的 `button`，每個觸控區至少 44×44px；選取狀態不能只靠顏色，須以 `aria-pressed` 或等價語意表達。三日 Demo 應在 375px 內換行或平均排列，不得造成頁面水平捲動。

### 日期切換

1. 使用者選擇另一個日期。
2. 前端更新 `selectedDate`。
3. 依 `scheduled_date === selectedDate` 過濾並按 `start_time` 排序。
4. iframe URL 與「在 Google Maps 查看當日路線」URL 同步更新，只包含當日活動且維持行程時間順序。
5. 不重新呼叫 SmartTrip backend，不修改 Trip，也不影響 timeline 展開狀態。

### 活動數量規則

| 當日可見活動數 | 畫面行為 |
|---|---|
| 0 | 日期不出現在選擇器；若所有日期皆無活動，整個預覽顯示「目前沒有可顯示的當日路線」，不 render iframe 或外部連結。 |
| 1 | 使用 Embed API `place` mode 顯示該活動位置；外部連結使用既有 Google Maps Search URL，文案改為「在 Google Maps 查看地點」。 |
| 2 以上 | 使用 Embed API `directions` mode；第一筆為 origin、最後一筆為 destination、中間項目依時間順序作為 waypoints。外部連結使用 Maps URL directions action。 |

### 設定缺少與載入限制

- 若 `VITE_GOOGLE_MAPS_EMBED_API_KEY` 未設定或為空字串，不 render iframe，顯示「地圖預覽目前無法載入」；無需 key 的 Google Maps 外部連結仍可使用。
- iframe 是跨來源內容，前端不能可靠讀取 Google 內部錯誤狀態；本次不製作虛假的 iframe timeout／retry 判斷。瀏覽器或 Google 顯示載入錯誤時，使用者仍可使用下方外部連結。
- iframe 使用 `loading="lazy"`、有描述所選日期的 `title`，尺寸不得低於 Google Embed API 要求的 200×200px。
- iframe 不得遮住或攔截頁面主要 CTA；mobile 頁面維持單一垂直捲動容器。

## 資料與介面

本功能只消費固定的既有 `Trip`／`TripItem` 契約，不新增 API 欄位：

```ts
interface TripItem {
  id: string
  name: string
  scheduled_date: string // YYYY-MM-DD，Trip timezone 的日期
  start_time: string // HH:mm，Trip timezone 的當地時間
  latitude: number
  longitude: number
}
```

分日與排序以 `scheduled_date`、`start_time` 為準，不把 `HH:mm` 轉成瀏覽器當地 timezone。前端目前已有 `groupTripItems`、`formatTripDate` 等工具，應沿用而非建立第二套日期邏輯。

### 環境變數

預期使用：

```env
VITE_GOOGLE_MAPS_EMBED_API_KEY=
```

repository root `.env` 已被 `.gitignore` 排除。因 Vite 預設只讀 `frontend/` 下的 env，實作者需在既有 `frontend/vite.config.ts` 設定 `envDir: '..'`，並在 root `.env.example` 加入空白範例值。不得將實際 key 寫入程式、PRD、`.env.example` 或 Git。

`VITE_` 變數會進入 client bundle，這不是後端 secret。Google Cloud 中必須將此 key 限制為 Maps Embed API，並設定 Demo 網域與本機開發來源的 HTTP referrer restriction。不得把 LLM/provider key 改成 `VITE_` 變數。

### Google Maps URL 組成

- Embed：`https://www.google.com/maps/embed/v1/place` 或 `https://www.google.com/maps/embed/v1/directions`。
- External：`https://www.google.com/maps/search/?api=1` 或 `https://www.google.com/maps/dir/?api=1`。
- 所有動態 query value 必須使用 `URL`／`URLSearchParams` 編碼，不以字串串接未編碼的活動名稱。
- origin／destination 優先使用既有座標；中繼點使用 Google Embed API 支援的地點名稱，並加上 Trip city 降低歧義。若實作前驗證 Embed API 接受座標 waypoints，才可一致改用座標；不得依賴未查證的 URL 參數。
- 不指定或宣稱即時交通模式；本功能只呈現 Google Maps 回傳的大致路線範圍。

## 實作交接

| 任務 ID／owner | 依賴 | 修改範圍 | 實作要求 | 驗證 |
|---|---|---|---|---|
| MAP-01／Frontend | root `.env` 已有受限制的 Embed key | `frontend/vite.config.ts`、root `.env.example` | 讓 Vite 讀 repository root env；只公開 `VITE_` 前綴；範例檔只放空值 | `frontend/` 執行 `pnpm build`；檢查 build output 沒有其他 root secrets 的值 |
| MAP-02／Frontend | 既有 `TripItem` 多日契約與日期工具 | 預計新增 `frontend/src/components/DailyRouteMap.tsx`；必要時新增單一 `frontend/src/utils/googleMaps.ts` | 建立日期選擇、0/1/2+ 活動分支、Embed URL 與外部 URL；不加入 dependency、不呼叫 backend | 以三日 fixture 切換日期，確認 iframe／外連 query 只含該日活動且順序正確 |
| MAP-03／Frontend | MAP-02 | `frontend/src/pages/TripPage.tsx`；必要時小幅調整 `frontend/src/components/MultiDaySchedule.tsx` | 將預覽放在目前行程標題與 multi-day schedule 之間；只傳目前 `visibleItems`，確保套用方案後不把已隱藏的過去活動重新放回地圖 | 驗證初次載入、套用後 `hidePastItems`、空行程、單一活動與日期切換 |
| MAP-04／Frontend | MAP-01～03 | `docs/product-flow.md` | 將既有「只使用 Maps Search URL、不需 key」更新為「Embed 每日預覽需受限制 key，外部 Maps URL 不需 key」；不宣稱即時導航 | 檢查文件、程式與環境設定一致 |
| MAP-05／Frontend | MAP-01～04 | 無固定新增檔案 | 執行完整 frontend 檢查與 mobile browser QA | `frontend/` 執行 `pnpm lint`、`pnpm build`；以 414px、375px 驗證無水平溢出、按鈕 44px、鍵盤 focus、日期切換與外連 |

MAP-01 與 MAP-02 可並行；MAP-03 依賴 MAP-02；MAP-04、MAP-05 最後進行。本功能不需要 Backend A 或 Backend B 工作。

## 驗收案例

### AC-01：預設日期

Given Trip 含 2026-09-12 至 2026-09-14 的活動，且行程 timezone 的今天是 2026-09-12
When `/trip` 載入成功
Then 日期選擇器預設選取 2026-09-12，預覽只使用 9/12 的可見活動。

### AC-02：切換日期

Given 9/13 與 9/14 都有活動
When 使用者選擇 9/14
Then iframe、標題與外部 Google Maps URL 都更新為 9/14，且不含 9/12、9/13 活動。

### AC-03：順序

Given 當日 API items 並非依時間排序
When 建立路線
Then origin、waypoints、destination 仍依 `start_time` 升冪排列，不改寫原始 Trip。

### AC-04：單一活動

Given 所選日期只有一個活動
When 顯示預覽
Then 使用 place mode 顯示該位置，外部 CTA 文案為「在 Google Maps 查看地點」。

### AC-05：缺少 key

Given `VITE_GOOGLE_MAPS_EMBED_API_KEY` 未設定
When 預覽區塊 render
Then 不產生含空 key 的 iframe，顯示可理解的 fallback，且無需 key 的 Google Maps 外部連結仍可點擊。

### AC-06：套用方案後

Given 使用者成功套用 ready 且 feasible 的方案，頁面只保留現在及未來活動
When 回到目前行程
Then 日期與地圖由 `SelectionResponse.trip` 的可見活動重新計算，不顯示已被隱藏的過去活動。

### AC-07：Mobile 與 accessibility

Given 375px 或 414px viewport
When 使用觸控或鍵盤操作日期選擇與外部 CTA
Then 頁面沒有水平溢出，控制項至少 44×44px、focus 可見、選取日期具可讀語意，iframe 有具體 `title`。

## 實作限制與風險

- Maps Embed API 目前免費且不限制 request 數，但仍要求有效 API key 與 billing account；Google Cloud 設定不屬於程式碼可驗收範圍。
- client-side Embed key 可被看見，安全邊界是 API restriction 與 HTTP referrer restriction，不得把它描述為私密後端憑證。
- Google Maps 算出的路線、時間或交通模式不是 SmartTrip fixture，也不得回寫到行程、方案 impact 或偏好。
- iframe 為第三方內容；網路中斷時無法離線顯示地圖。本功能不得破壞既有離線 fixture 的核心重排 Demo，外部連結與原 timeline 必須仍可用。
- 共用規格目前把 Google Maps 限定為不需 key 的外部 Search URL。此 PRD 是新增提案的確認紀錄；功能實作完成後需依 MAP-04 同步產品流程，避免文件繼續宣稱沒有嵌入預覽。

## 本次文件驗證

- 已查證現有 frontend 具 `TripItem.scheduled_date`、多日分組工具與 `MultiDaySchedule`。
- 已查證目前 `vite.config.ts` 尚未設定 `envDir`。
- 已查證 root `.gitignore` 排除 `.env`／`.env.*`，並保留 `.env.example`。
- 本次只建立 PRD，未修改產品程式，未執行 `pnpm lint`／`pnpm build`，也未驗證使用者的實際 API key 或 Google Cloud restriction。
