# Backend development guidelines

## Scope

- 本文件適用於 `backend/` 及其子目錄，並補充 repository 根目錄的 `AGENTS.md`；根目錄的產品範圍、分工、Git 與安全規範仍然有效。
- 共用需求以 `docs/DEVELOPMENT_SPEC.md`、固定外層契約以 `docs/api-contract.md` 為準；實際 schema 以 FastAPI 產生的 `/openapi.json` 為準。
- 本文件只規範程式碼品質與協作方式，不定義 planner、scoring、weather、LLM parsing 或 preference learning 的商業規則。這些規則由 Backend A/B 協議後記錄於共用規格或 `docs/decisions/`。

## Runtime and dependencies

- 使用 Python 3.11+，並從 repository 根目錄以 package 形式執行後端與測試。
- 優先使用 Python standard library；新增第三方套件前，先確認現有依賴無法合理完成需求。
- 新增、移除或升級套件時，同步更新 `requirements.txt` 與 `requirements.lock.txt`，不得只修改其中一份。
- secrets 與環境差異放在根目錄 `.env`；只提交安全的範例值至 `.env.example`。

## Module boundaries

- `main.py` 負責 FastAPI app、route 與高階 orchestration，不放大型演算法、provider-specific parsing 或 persistence 細節。
- `models.py` 是共用 Pydantic request/response schema 的來源，`contracts.py` 定義 A/B 的 `ReplanContext → PlanningResult` Protocol；不要在 route 或 owner package 內重複定義相同 payload。
- `agent/` 與 `replanner/` 的責任和 owner 依根目錄 `AGENTS.md`。跨 owner 的介面變更先同步，不直接把另一個 module 的內部實作複製過來。
- module 之間透過清楚、有型別的函式或 class 介面合作，避免 circular imports 與對 private implementation 的依賴。
- 將外部服務、時間與持久化等 side effects 留在邊界，使核心邏輯能以固定輸入做單元測試。

## Python style

- 遵循 PEP 8，使用 4 spaces indentation；新寫的行以不超過 100 characters 為原則。
- function、variable 與 module 使用 `snake_case`，class 使用 `PascalCase`，常數使用 `UPPER_SNAKE_CASE`。
- imports 依 standard library、third-party、local application 分組，各組之間空一行；不使用 wildcard imports。
- 所有新增或修改的函式都標註參數與回傳型別。使用 Python 3.11 語法，例如 `list[str]` 與 `str | None`。
- 優先使用 `pathlib.Path` 處理檔案路徑，避免依賴目前 working directory 的隱含相對路徑。
- 不使用 mutable default arguments、bare `except`、靜默吞掉例外或沒有理由的 `# type: ignore`。
- 函式保持單一責任；當 route、adapter 或 service 同時處理多個階段時，拆成具名且可測試的 helper。
- docstring 說明公開 module/class/function 的責任或不直觀的限制，不重述程式碼本身。
- 不為了順手整理而格式化或重構與目前任務無關的檔案。

## FastAPI and Pydantic

- 業務 request/response 使用 Pydantic model，route 明確宣告 `response_model`；簡單 health response 可以使用具體型別的 dict。
- 欄位限制放在 model 中並使用 Pydantic v2 API，不在多個 endpoint 重複相同驗證。
- JSON 欄位維持 `snake_case`，時間、enum、nullable 與數值範圍必須在 schema 中表達清楚。
- route 只處理 HTTP concerns 與 orchestration；可重用的解析、計算、provider 或 storage 邏輯放回所屬 module。
- 預期中的 client 或 dependency 錯誤應轉成一致且可理解的 HTTP error；不要回傳 stack trace、secret、prompt 或未清理的 provider payload。
- API 欄位、狀態碼或 route 變更時，同步更新 Pydantic model、API tests 與 `docs/DEVELOPMENT_SPEC.md`，並通知 frontend owner 更新 TypeScript types。
- 不破壞既有 API contract；必要的 breaking change 必須先取得團隊共識。

## External I/O and configuration

- HTTP 呼叫使用 `httpx`，設定明確 timeout，並處理 timeout、連線失敗、非成功狀態與無效 payload。
- 在 `async def` call path 中不得執行 blocking network I/O；使用 async client，或將無法避免的 blocking 工作移出 event loop。
- 不在 module import 時進行網路呼叫、資料寫入或其他不可預期的初始化。
- 所有外部資料在進入核心邏輯前先驗證；外部文字與模型輸出一律視為不可信輸入。
- configuration 在 application boundary 載入並以明確介面傳遞；不要在各 module 重複呼叫 `load_dotenv()`。
- fixture/seed data 保持唯讀。執行期資料寫入已被 Git 忽略的 runtime 路徑，不得修改 seed 來保存狀態。
- 使用 `logging` 記錄可操作的診斷資訊；不要使用臨時 `print()`，也不要記錄 API keys、authorization headers 或完整敏感 payload。

## Tests

- 測試使用 standard-library `unittest`，放在 `backend/tests/`，檔名為 `test_*.py`。
- 測試必須 deterministic、可離線執行，且不依賴測試順序、真實時間、真實 LLM、即時天氣服務或其他網路資源。
- 外部服務、clock 與 storage boundary 應使用 mock、temporary location 或固定 fixture。
- 新功能至少涵蓋主要成功路徑與重要失敗路徑；bug fix 必須加入能重現問題的 regression test。
- 測試 observable behavior，不鎖死 private helper 的實作細節。
- 完成 backend 變更後，從 repository 根目錄執行：

```sh
python -m unittest discover -s backend/tests -v
```

- 若修改 API schema，另外啟動 app 檢查 `/openapi.json`，確認實際輸出與文件一致。
- 無法執行或未通過任何檢查時，必須清楚回報，不得宣稱已驗證。

## Change discipline

- 開始修改前先閱讀相關 module、測試與規格，並查看 `git status`，避免覆寫他人的未提交變更。
- 變更保持小而聚焦；共用介面與 refactor 不和無關功能混在同一個變更中。
- 完成後檢查 diff，確認沒有 secrets、runtime data、debug code 或非預期的 API 變更。
- 除非任務需要，不新增 framework、抽象層或通用基礎設施。
