export type PlanId = 'A' | 'B' | 'C'
export type PlanStrategy = 'preserve_booking' | 'maximize_attractions' | 'relaxed'

export interface TripItem {
  id: string
  name: string
  scheduled_date: string
  start_time: string
  duration_minutes: number
  latitude: number
  longitude: number
  priority: number
  booking: boolean
  movable: boolean
  indoor: boolean
}

export interface Trip {
  id: string
  version: number
  city: string
  timezone: string
  start_date: string
  end_date: string
  items: TripItem[]
}

export interface Preference {
  user_id: 'demo-user'
  weights: Record<PlanStrategy, number>
  selection_count: number
}

export interface WeatherContext {
  source: 'live' | 'fixture' | 'unavailable'
  start_date: string
  end_date: string
  timezone: string
  hours: { time: string; precipitation_probability: number | null }[]
  warnings: string[]
}

export interface PlanChange {
  item_id: string
  action: 'keep' | 'move' | 'cancel' | 'add'
  from_date: string | null
  from_start_time: string | null
  to_date: string | null
  to_start_time: string | null
  reason: string
}

export interface PlanFeatures {
  preserve_booking: number
  maximize_attractions: number
  relaxed: number
}

export interface Plan {
  id: PlanId
  strategy: PlanStrategy
  title: string
  items: TripItem[]
  feasible: boolean
  changes: PlanChange[]
  additional_travel_minutes: number
  additional_cost_jpy: number
  booking_warnings: string[]
  features: PlanFeatures
  explanation: string
}

export interface ReplanResponse {
  status: 'placeholder' | 'ready'
  replan_id: string | null
  planning_source: 'live' | 'fixture' | 'unavailable'
  event: {
    event_type: 'weather' | 'delay' | 'closure' | 'unknown'
    delay_minutes: number
    affected_item_ids: string[]
    affected_dates: string[]
    summary: string
  }
  weather: WeatherContext
  preferences: Preference
  plans: Plan[]
  recommended_plan_id: PlanId | null
  preference_insight: string | null
  warnings: string[]
}

export interface SelectionResponse {
  selection: { replan_id: string; plan_id: PlanId; created_at: string }
  trip: Trip
  preferences: Preference
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value)
}

function record(value: unknown, label: string) {
  if (!isRecord(value)) throw new Error(`${label} 格式不正確。`)
  return value
}

function stringValue(value: unknown, label: string) {
  if (typeof value !== 'string') throw new Error(`${label} 格式不正確。`)
  return value
}

function numberValue(value: unknown, label: string) {
  if (typeof value !== 'number' || !Number.isFinite(value)) throw new Error(`${label} 格式不正確。`)
  return value
}

function booleanValue(value: unknown, label: string) {
  if (typeof value !== 'boolean') throw new Error(`${label} 格式不正確。`)
  return value
}

function stringArray(value: unknown, label: string) {
  if (!Array.isArray(value) || !value.every((item) => typeof item === 'string')) throw new Error(`${label} 格式不正確。`)
  return value
}

function nullableString(value: unknown, label: string) {
  if (value === null) return null
  return stringValue(value, label)
}

function oneOf<const T extends string>(value: unknown, allowed: readonly T[], label: string): T {
  if (typeof value !== 'string' || !allowed.some((item) => item === value)) throw new Error(`${label} 格式不正確。`)
  return value as T
}

function parseTripItem(value: unknown): TripItem {
  const item = record(value, '行程項目')
  return {
    id: stringValue(item.id, '行程項目 id'), name: stringValue(item.name, '行程項目名稱'),
    scheduled_date: stringValue(item.scheduled_date, '行程日期'), start_time: stringValue(item.start_time, '行程時間'),
    duration_minutes: numberValue(item.duration_minutes, '行程長度'), latitude: numberValue(item.latitude, '緯度'),
    longitude: numberValue(item.longitude, '經度'), priority: numberValue(item.priority, '優先度'),
    booking: booleanValue(item.booking, '預約狀態'), movable: booleanValue(item.movable, '移動狀態'),
    indoor: booleanValue(item.indoor, '室內狀態'),
  }
}

function parseTrip(value: unknown): Trip {
  const trip = record(value, '行程')
  if (!Array.isArray(trip.items)) throw new Error('行程項目格式不正確。')
  return {
    id: stringValue(trip.id, '行程 id'), version: numberValue(trip.version, '行程版本'),
    city: stringValue(trip.city, '城市'), timezone: stringValue(trip.timezone, '行程時區'),
    start_date: stringValue(trip.start_date, '行程開始日期'), end_date: stringValue(trip.end_date, '行程結束日期'),
    items: trip.items.map(parseTripItem),
  }
}

function parsePreference(value: unknown): Preference {
  const preference = record(value, '偏好')
  const weights = record(preference.weights, '偏好權重')
  return {
    user_id: oneOf(preference.user_id, ['demo-user'], '使用者'),
    weights: {
      preserve_booking: numberValue(weights.preserve_booking, '保留預約權重'),
      maximize_attractions: numberValue(weights.maximize_attractions, '保留景點權重'),
      relaxed: numberValue(weights.relaxed, '輕鬆權重'),
    },
    selection_count: numberValue(preference.selection_count, '選擇次數'),
  }
}

function parseWeather(value: unknown): WeatherContext {
  const weather = record(value, '天氣資料')
  if (!Array.isArray(weather.hours)) throw new Error('天氣時段格式不正確。')
  return {
    source: oneOf(weather.source, ['live', 'fixture', 'unavailable'], '天氣來源'),
    start_date: stringValue(weather.start_date, '天氣開始日期'), end_date: stringValue(weather.end_date, '天氣結束日期'),
    timezone: stringValue(weather.timezone, '天氣時區'),
    hours: weather.hours.map((value) => {
      const hour = record(value, '天氣時段')
      return { time: stringValue(hour.time, '天氣時間'), precipitation_probability: hour.precipitation_probability === null ? null : numberValue(hour.precipitation_probability, '降雨機率') }
    }),
    warnings: stringArray(weather.warnings, '天氣警告'),
  }
}

function parsePlan(value: unknown): Plan {
  const plan = record(value, '替代方案')
  if (!Array.isArray(plan.items) || !Array.isArray(plan.changes)) throw new Error('替代方案內容格式不正確。')
  const features = record(plan.features, '方案特徵')
  return {
    id: oneOf(plan.id, ['A', 'B', 'C'], '方案 id'),
    strategy: oneOf(plan.strategy, ['preserve_booking', 'maximize_attractions', 'relaxed'], '方案策略'),
    title: stringValue(plan.title, '方案名稱'), items: plan.items.map(parseTripItem),
    feasible: booleanValue(plan.feasible, '方案可行性'),
    changes: plan.changes.map((value) => {
      const change = record(value, '方案異動')
      return {
        item_id: stringValue(change.item_id, '異動項目 id'), action: oneOf(change.action, ['keep', 'move', 'cancel', 'add'], '異動類型'),
        from_date: nullableString(change.from_date, '異動原日期'), from_start_time: nullableString(change.from_start_time, '異動原時間'),
        to_date: nullableString(change.to_date, '異動新日期'), to_start_time: nullableString(change.to_start_time, '異動新時間'),
        reason: stringValue(change.reason, '異動原因'),
      }
    }),
    additional_travel_minutes: numberValue(plan.additional_travel_minutes, '交通時間差'),
    additional_cost_jpy: numberValue(plan.additional_cost_jpy, '費用差'),
    booking_warnings: stringArray(plan.booking_warnings, '預約提醒'),
    features: {
      preserve_booking: numberValue(features.preserve_booking, '保留預約特徵'),
      maximize_attractions: numberValue(features.maximize_attractions, '保留景點特徵'),
      relaxed: numberValue(features.relaxed, '輕鬆特徵'),
    },
    explanation: stringValue(plan.explanation, '方案說明'),
  }
}

function parseReplanResponse(value: unknown): ReplanResponse {
  const response = record(value, '重排結果')
  const event = record(response.event, '事件')
  if (!Array.isArray(response.plans)) throw new Error('替代方案格式不正確。')
  return {
    status: oneOf(response.status, ['placeholder', 'ready'], '重排狀態'),
    replan_id: nullableString(response.replan_id, '重排 id'),
    planning_source: oneOf(response.planning_source, ['live', 'fixture', 'unavailable'], '方案來源'),
    event: {
      event_type: oneOf(event.event_type, ['weather', 'delay', 'closure', 'unknown'], '事件類型'),
      delay_minutes: numberValue(event.delay_minutes, '延遲時間'), affected_item_ids: stringArray(event.affected_item_ids, '受影響項目'),
      affected_dates: stringArray(event.affected_dates, '受影響日期'), summary: stringValue(event.summary, '事件摘要'),
    },
    weather: parseWeather(response.weather), preferences: parsePreference(response.preferences), plans: response.plans.map(parsePlan),
    recommended_plan_id: response.recommended_plan_id === null ? null : oneOf(response.recommended_plan_id, ['A', 'B', 'C'], '推薦方案'),
    preference_insight: nullableString(response.preference_insight, '偏好提示'), warnings: stringArray(response.warnings, '重排警告'),
  }
}

function parseSelectionResponse(value: unknown): SelectionResponse {
  const response = record(value, '套用結果')
  const selection = record(response.selection, '選擇紀錄')
  return {
    selection: { replan_id: stringValue(selection.replan_id, '重排 id'), plan_id: oneOf(selection.plan_id, ['A', 'B', 'C'], '方案 id'), created_at: stringValue(selection.created_at, '套用時間') },
    trip: parseTrip(response.trip), preferences: parsePreference(response.preferences),
  }
}

async function request(path: string, options?: RequestInit): Promise<unknown> {
  const response = await fetch(`/api${path}`, { ...options, signal: AbortSignal.timeout(20000) })
  const body: unknown = await response.json().catch(() => null)
  if (!response.ok) {
    const detail = isRecord(body) && typeof body.detail === 'string' ? body.detail : `API ${response.status}`
    throw new Error(detail)
  }
  return body
}

export const getTrip = async () => parseTrip(await request('/trip'))
export const getPreferences = async () => parsePreference(await request('/preferences'))
export const replan = async (message: string, now?: string) => parseReplanResponse(await request('/replan', {
  method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ trip_id: 'tokyo-demo', message, now }),
}))
export const selectPlan = async (replanId: string, planId: PlanId) => parseSelectionResponse(await request('/selections', {
  method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ replan_id: replanId, plan_id: planId }),
}))
