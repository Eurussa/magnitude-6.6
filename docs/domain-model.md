# Domain Model

此文件記錄五小時 MVP 的共用名詞；精確欄位見 `DEVELOPMENT_SPEC.md` 與 `backend/models.py`，可執行 API 以 `/openapi.json` 為準。未來概念不代表已實作。

## 核心名詞

| 名詞 | MVP 定義與責任 |
|---|---|
| Traveler | 固定 `demo-user`；不做登入、多人同行或多使用者隔離 |
| Trip | 固定 Tokyo 單日行程；種子初始化目前行程，後續重排應接續已套用版本 |
| TripItem / Itinerary Item | 行程項目，含時間、位置、室內外與預約／移動限制；fixture 由 B 維護 |
| Event / Disruption | A 從使用者文字解析並驗證的 weather、delay、closure 或 unknown 事件；LLM 解析仍待實作 |
| WeatherContext | A 取得並整理的 Open-Meteo 或 fixture 資料，包含來源、日期、時區與逐時降雨機率；B 判斷受影響活動 |
| Candidate Plan / Recovery Option | B 生成的 A/B/C 替代方案；只有通過可行性檢查的 ready 方案才可套用 |
| Impact / Changes（目標） | B 計算的保留、移動、取消與交通／預約代價；A 依事實產生推薦解釋 |
| Preference | A 管理三個權重 `preserve_booking`、`maximize_attractions`、`relaxed` 及 `selection_count`；初始權重皆為 1 |
| Replan snapshot（目標） | 由伺服器保存的一次重排、原行程版本與候選方案，以 `replan_id` 辨識 |
| Selection（目標） | 使用者以 `replan_id` / `plan_id` 選擇已保存方案，A 驗證並保存；同次重複選擇不重複增加權重 |
| Applied Plan / Recovery Plan（目標） | 通過驗證並套用後的目前 Trip；不代表已執行真實訂位或改訂 |

## 目標資料流

1. A 載入目前 Trip、Preference，解析 Event 並取得 WeatherContext，組成 ReplanContext。
2. B 以相同輸入生成可重現的候選方案，檢查限制並計算 impact 與偏好分數。
3. A 組成說明、保存 snapshot，回傳候選方案供旅客比較。
4. 選擇流程完成後，A 從伺服器 snapshot 讀取特徵，同次更新目前 Trip、Preference 與 Selection。
5. 下一次重排讀取更新後的 Trip 與 Preference；不由前端自報權重或任意覆寫行程。

## 儲存邊界與現況

- `backend/data/trip.json` 與 `preferences.json` 是唯讀種子；runtime 使用 `backend/data/runtime/state.json`，目前包含 schema_version、trip、preferences，不使用 DB、不納入 Git。
- A 負責可變狀態驗證、單程序鎖與原子寫入；B 的演算法只接收模型，不直接存取檔案。服務只使用單一 worker。
- 目前提供 trip / preferences 的內部保存介面與 HTTP 讀取；沒有 HTTP 任意儲存／重置介面，沒有 snapshot 或選擇 endpoint。
- 未來套用選擇必須拒絕不可行／過期方案，並保證相同選擇重送不重複學習。
- 目前仍是 placeholder 解析及方案；儲存與 context 介面不代表方案已可行或偏好學習已完成。

## 明確不做與後續待辦

本次不做多旅客、多日最佳化、真實訂位、即時價格或訂位失效追蹤。行程日期、事件影響時間窗、候選營業時間、交通 fixture 與方案版本欄位需隨真實重排實作補齊並同步共用 schema；目前以 request.now 的行程當地日期取得天氣，未提供時取當地目前時間，這不表示無日期的展示行程就是實際當日行程。
