export interface TripItem {
  id: string; name: string; start_time: string; duration_minutes: number
  latitude: number; longitude: number; priority: number
  booking: boolean; movable: boolean; indoor: boolean
}
export interface Trip { id: string; city: string; timezone: string; items: TripItem[] }
export interface ReplanResponse {
  status: 'placeholder'
  event: { event_type: 'weather' | 'delay' | 'closure' | 'unknown'; delay_minutes: number; affected_item_id: string | null; summary: string }
  plans: { id: string; strategy: 'preserve_booking' | 'maximize_attractions' | 'relaxed'; title: string; items: TripItem[]; explanation: string }[]
  warnings: string[]
}
async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const response = await fetch(`/api${path}`, { ...options, signal: AbortSignal.timeout(20000) })
  if (!response.ok) throw new Error(`API ${response.status}：請確認後端已啟動或輸入格式正確。`)
  return response.json() as Promise<T>
}
export const getTrip = () => request<Trip>('/trip')
export const replan = (message: string) => request<ReplanResponse>('/replan', {
  method: 'POST', headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({ trip_id: 'tokyo-demo', message }),
})
