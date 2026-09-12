# 002 事件解析、排程與外部資料邊界

## Status

Accepted — 整理自 [DEVELOPMENT_SPEC.md](../DEVELOPMENT_SPEC.md) 的架構、排程規則與分工；多數目標能力尚未實作。

## Context

Demo 需要從自然語言理解睡過頭、休館與下雨，同時讓方案遵守預約與時間限制，並能在外部服務失效時展示。事件理解與行程可行性需有明確的責任邊界。

## Decision

- 單一 FastAPI server 協調 Python modules。Backend A 擁有 agent、main.py、models.py、LLM 設定、偏好與 selections；Backend B 擁有 replanner、天氣 adapter、fixtures、heuristic 與 scoring。
- LLM 透過 httpx 呼叫支援 JSON Schema structured output 的 provider，只處理事件解析與說明。provider/model 尚未指定；金鑰僅存後端。
- 事件輸出必須經 `Event.model_validate_json`，timeout 或格式錯誤明示 fallback；不直接採信模型生成的可行行程。
- Replanner 用 deterministic heuristic 產生 A 保留預約、B 保留最多景點、C 最輕鬆，檢查 fixture 交通時間、時間不重疊、營業時間與最晚抵達。
- 已完成活動不動；booking=true 或 movable=false 不得靜默移動，B 策略也不能解除預約鎖。無解明示不可行。
- 天氣使用 Open-Meteo hourly precipitation_probability，以 Asia/Tokyo 對齊，只影響對應時段的戶外活動。失效時明示 fixture/fallback 或 unavailable，不把未知視為晴天。
- 地點使用座標 Google Maps Search URL，不需地圖金鑰；交通時間採 fixture，不提供即時路由。
- 初始化預設不連外，離線 fixture 為必要展示能力。

## Consequences

- LLM、天氣 adapter 與排程能分工開發，但 A/B 必須先約定 event/weather/preferences 的 planner 介面並同步 main.py。
- 方案需提供可行性、變更原因、交通／費用增量與預約影響，Frontend 才能呈現可比較的取捨。
- Backend B 尚需補下午戶外候選與限制 fixture；現有 weather adapter 尚未串入 replan。
- 目前 replan 仍為 unknown + placeholder，不能當作已驗證的可行方案。錯誤需可恢復且不洩漏 key 或供應商敏感資訊。
