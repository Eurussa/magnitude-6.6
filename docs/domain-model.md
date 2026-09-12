# Domain Model

此文件記錄團隊共用的產品名詞與概念關係，不代表最終 API schema 或資料庫設計。

## 核心名詞

### Traveler

使用本服務處理旅程異常的人。

### Trip

旅客為特定目的安排的一段完整旅程，可包含多個交通、住宿或活動項目。

### Itinerary Item

旅程中的單一項目，例如航班、鐵路、住宿或活動。

### Disruption

影響原定旅程的突發事件，例如取消、延誤、錯過轉乘或目的地狀況改變。

### Impact

突發事件對後續行程造成的具體影響。

### Recovery Option

針對旅程異常提出的一個可行替代方案。

### Recovery Plan

旅客選定後，準備執行或已執行的重新安排方案。

## 概念關係

- 一位 Traveler 可以有多個 Trip。
- 一個 Trip 可以包含多個 Itinerary Item。
- 一個 Disruption 可以影響一個或多個 Itinerary Item。
- 一個 Disruption 可以產生多個 Recovery Option。
- 旅客可從 Recovery Option 中選擇一個形成 Recovery Plan。

## 待確認事項

- Trip 是否允許多位 Traveler？
- Recovery Option 是否包含價格、抵達時間、風險與限制？
- 系統是否需要保存方案失效或價格變動紀錄？
- Disruption 的資料來源為何？
- 哪些名詞需要與後端或外部服務的用語保持一致？
