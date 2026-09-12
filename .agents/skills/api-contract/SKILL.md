---
name: api-contract
description: 定義、審查或同步前後端 API 契約及 Backend A/B 模組介面，釐清欄位、驗證、錯誤與相容性。用於新增或變更 endpoint、request/response schema、契約落差及串接交接；僅消費既有 API 且契約無疑義時不必啟用。
---

# API Contract

使用繁體中文，欄位與型別保留程式名稱。產出讓 Frontend、Backend A、Backend B 能各自實作並一致串接的契約，區分現行行為、已確認目標與待確認提案。

## 查證現行契約

1. 讀取適用的 `AGENTS.md`、`docs/DEVELOPMENT_SPEC.md` 與相關 `docs/decisions/`；路徑以專案根目錄為基準。確認最新 ownership 與決策狀態，不把 Proposed 當 Accepted。
2. 以目前服務的 `/openapi.json`、`/docs` 核對 HTTP schema，再檢查 `backend/main.py`、`backend/models.py`、相關測試及前端 client／TypeScript types。用搜尋找出前端檔案，不預設檔名。
3. 服務未啟動時可從程式與測試查證，或在可用環境匯出 OpenAPI；明示是本機程式推導，未驗證執行中的服務。不要為讀取 schema 呼叫會改寫 runtime 的業務 endpoint。
4. 記錄規格、Pydantic、OpenAPI、TypeScript、fixtures 與行為之間的差異。提案附來源與確認狀態，不把希望新增的欄位混進現行 JSON 範例。

## HTTP 契約交付內容

沿用既有規格或決策文件，集中定義同一份契約。對本次受影響的 endpoint 記錄：

- HTTP method、完整路徑、用途、呼叫時機、是否寫入狀態。
- path／query／body 各自欄位；成功 HTTP status、response 與前端收到後的行為。
- 現行與目標差異、相容性影響、需要同步的呼叫端及 owner。

每個欄位寫清楚巢狀路徑、JSON 型別、必填／可省略、nullable、預設值及限制。限制依欄位包含 enum、範圍、格式、單位、時區及參照關係；request 與 response 各自說明保證。

省略與 `null` 分開定義：TypeScript 的可省略屬性與 nullable 型別不同，Pydantic 的 nullable 註記也不等於存在預設值。說明未知值、空陣列與無結果的語意。

提供符合對應狀態 schema 的完整 request／response JSON 範例，不在 JSON 中放註解或省略號。成功範例涵蓋前端需要的資料；錯誤表包含「觸發條件 → HTTP status → response body → 前端處理」，僅涵蓋本次相關錯誤。

不要自行統一所有錯誤格式。查明現行業務錯誤、FastAPI validation error 與自訂 handler 的差異；格式變更列為契約增量。

## 狀態與寫入語意

只在本次介面涉及時補齊：

- 前置狀態、成功後狀態，以及失敗時必須保持不變的資料。
- 重試與重複請求：用哪個識別值判定重複、回什麼結果、是否再次產生副作用。
- 同次改選、未知 ID、不可行方案及過期版本的處理；未確認錯誤碼保留為提案。
- 須一起更新的資料及失敗一致性。儲存方式與保證引用已接受決策，不另行引入 DB，不把單程序原子寫入宣稱為跨服務交易。
- fixture、fallback、unavailable 的表示及消費端行為，避免未知值被當作成功或正常狀態。

SmartTrip 沿用 `/api` 與 snake_case JSON。檢查本次契約是否遵守預約／已完成活動限制、只有 ready 且 feasible 可套用，以及偏好不得因重送重複加分等已確認規則；不要新增未確認的身分、版本或錯誤欄位。

## Backend A/B 模組介面

涉及內部介面時，另外列出模組、owner、完整函式 signature、sync／async、輸入輸出共用型別、例外與副作用。HTTP DTO 和內部 context 不必相同，轉換責任須明示。

依最新專案分工指定誰取得／驗證 context、誰計算方案事實、誰保存狀態及組成 HTTP 回應。不要將內部介面誤寫成第二個 HTTP service，也不要越過 owner 邊界修改演算法。

## 確認、同步與驗證

1. 先列契約差異及影響，沿用已有確認。對未確認的共用欄位，整理交由三人確認的內容，不自行宣稱已通知或已取得同意，也不自行傳訊。
2. 契約已確認且本次要求包含實作時，由 Backend A 同步共用規格與 Pydantic、Frontend 同步 TypeScript／client、Backend B 同步受影響的模組與 fixtures。依現有授權與角色執行，不因本 skill 擴大修改範圍。
3. 驗證範例與 schema 一致，核對必填、nullable、enum、單位／時區及錯誤分支。契約測試驗證消費端可觀察的行為；涉及寫入時才加入重送、失敗一致性或過期狀態等相關案例。
4. 有 frontend 程式變更時，在 `frontend/` 執行 `pnpm lint`、`pnpm build`；有 backend 程式變更時，在 repo 根目錄啟用 virtualenv 後執行 `python -m unittest discover -s backend/tests -v`。純契約草案核對文件與範例即可，不宣稱未執行的 runtime 測試已通過。

交付現行／目標差異、文件與程式位置、驗證結果及未決事項。提案契約不可標示為已上線或可直接串接。
