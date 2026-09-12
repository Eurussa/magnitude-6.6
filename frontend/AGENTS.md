# Frontend development rules

適用於 `frontend/`。共用分工、Git、commit 與安全規則沿用根目錄 `AGENTS.md`。
產品範圍與前後端協作以 `../docs/DEVELOPMENT_SPEC.md` 為準。

## 開發原則

- 使用既有 React、Vite、TypeScript、React Router 與 Tailwind CSS；套件版本以 `package.json` 與 `pnpm-lock.yaml` 為準。
- 套件操作使用 pnpm。新增 dependency 前先說明用途，優先使用既有工具完成需求。
- 以可展示的完整流程為優先，避免為尚未出現的需求建立抽象層。
- 規則適用於新增或修改的程式；不要只為符合規則而重構無關檔案。
- 預設以繁體中文撰寫使用者介面文案，命名與 API 欄位使用英文。

## 檔案與元件

- `src/main.tsx` 負責應用入口；`src/App.tsx` 負責路由與應用組裝。
- 畫面變大時，將頁面拆至 `src/pages/`、獨立 UI 拆至 `src/components/`；有實際需要才建立目錄。
- API 呼叫集中於 `src/api/`，沿用 `src/api/client.ts` 作為入口；component 不直接呼叫 `fetch`。
- React component 與其檔名使用 PascalCase，hook 使用 `use` 前綴；其他函式與變數使用 camelCase。
- 使用 function component 與 hooks。Props 明確定義型別，不使用 `any` 掩蓋型別問題。
- list key 使用穩定 ID；可重排的行程或方案不使用 array index 作為 key。
- 註解簡潔，只解釋原因或限制，不重述程式行為。

## 狀態與 async

- 狀態先放在使用它的 component；需要跨元件共享時提升到最近共同父層。
- 可由既有資料推導的值直接計算，不用額外 state 或 effect 同步。
- 使用者操作造成的請求放在 event handler；effect 用於初始載入或與外部系統同步。
- 請求須處理 loading、成功、空結果與錯誤；錯誤後提供可理解的重試方式。
- 區分初始行程載入、重排與套用方案的狀態，避免錯誤或 loading 互相覆蓋。
- 處理 component 卸載與請求競態，避免較舊的回應覆蓋新的結果。
- 送出重排或套用方案期間防止重複提交；不要在 effect 中自動套用方案。

## API 與產品行為

- 使用相對 `/api` 路徑，沿用 Vite proxy；不在 component 寫死後端 host。
- request/response 型別遵循後端實際契約，保留 snake_case 欄位；未實作的目標欄位不可假設一定存在。
- TypeScript assertion 不等於 runtime validation；不要用 `as` 假裝已驗證外部資料。
- API 欄位或行為不符時明確回報差異，依根目錄分工協調；不為配合畫面自行修改後端契約。
- `placeholder`、fixture 與 fallback 必須清楚標示，不呈現為真實完成的重排或即時資料。
- 只有後端回傳 `status: ready` 且方案 `feasible: true` 時才開放套用；缺少欄位時保持不可套用。
- 套用成功後，依後端回傳結果更新行程與偏好；前端不自行增加偏好權重或假造成功狀態。
- 以 Trip 的 timezone 解讀時間，不把行程的 `HH:mm` 當成瀏覽器本地時區的絕對時間。
- 保留預約鎖定、不可移動與方案警告的可見資訊；未知資料不得顯示成零成本、無風險或晴天。
- Google Maps 使用既有座標 Search URL；外部新分頁連結加上 `rel="noopener noreferrer"`。

## 樣式與可用性

- 優先使用 Tailwind utilities；全域基礎樣式放在 `src/index.css`，避免新增影響所有元件的寬泛 selector。
- 沿用既有配色、間距與互動樣式；重複 UI 出現時再抽共用元件。
- 本產品是 mobile app only；以 414px 寬度為主要設計基準、375px 為最窄完整驗收寬度，不為 desktop 另外設計多欄版面。App 容器使用 `width: 100%; max-width: 414px`，桌面瀏覽時置中呈現，但不能因此改變資訊層級或操作流程。
- 維持單欄、上下自然捲動；禁止頁面產生水平捲動。長文字、API 錯誤與地名必須能換行，不能撐破 viewport。
- 不複製其他專案的 design tokens、顏色、字級、間距或元件外觀；只沿用與 mobile 操作有關的 UX 原則。
- 使用語意化 HTML；互動使用 button/link，表單欄位具備 label。
- 保留鍵盤操作與可見 focus；錯誤使用適當的 alert，async 結果用適當的 live region 通知。
- 不只靠顏色或 emoji 傳達鎖定、錯誤、推薦或不可行狀態，需有文字說明。

## Mobile UX 規則

- 主要操作依單手使用安排；當下最重要的 CTA 要容易找到，避免同一畫面出現多個同等權重的主要按鈕。
- 可點擊區域至少 44×44px。不能只靠 hover 顯示資訊或操作；pressed、disabled、loading 與 selected 狀態都要在觸控環境可辨識。
- 固定或 sticky 的 header、底部 CTA、bottom sheet 必須處理 `env(safe-area-inset-top)` 與 `env(safe-area-inset-bottom)`，內容區要預留相應空間，最後一筆內容不可被遮住。
- 每個畫面只保留一個主要垂直捲動容器；bottom sheet 或 modal 內有長內容時才使用自己的捲動區，並限制高度，避免 body 與面板同時捲動。
- 表單要考慮手機軟體鍵盤：聚焦後欄位與送出按鈕仍需可見或可捲到，送出期間防止重複點擊，失敗後保留使用者輸入。
- 重排行程屬於需要等待的主要操作；送出後立即提供進度回饋，成功、空結果、不可行與錯誤要有明確且可恢復的下一步。
- A/B/C 方案在手機上採垂直排列；先顯示策略、推薦與可行性，再顯示異動、時間／費用與預約影響。比較不能依賴三欄同時可見。
- modal 與 bottom sheet 必須有明確關閉方式；支援返回鍵／Escape，且關閉前若會遺失已輸入內容，需先提示使用者。
- 動畫只用來說明狀態與層級，避免阻礙操作；遵守 `prefers-reduced-motion`。
- 驗收至少檢查 414px 主要基準與 375px 最窄完整支援寬度，以及直向捲動、軟體鍵盤、safe area、長文案與連續快速點擊。低於 375px 不要求維持相同視覺密度，但不得水平溢出或阻斷主要流程；桌面寬度只需確認 mobile viewport 置中且功能正常。

## 驗證與交付

- 修改前端程式、設定或 dependency 後，在 `frontend/` 執行 `pnpm lint` 與 `pnpm build`；build 已包含 TypeScript 檢查。
- 純文件修改檢查 diff 與內容一致性即可。
- UI 或互動變更需在可用的瀏覽器環境檢查相關流程、loading/error、鍵盤操作及窄螢幕排版。
- 依改動範圍驗證已實作功能；後端仍為 placeholder 時，不宣稱完整兩次事件 Demo 已通過。
- 目前沒有 test script；不要宣稱已執行不存在的測試。無法執行的檢查與阻礙須在交付時說明。
- 交付時說明變更與驗證結果；commit 行為遵守根目錄規則。
