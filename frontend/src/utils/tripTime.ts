import type { TripItem } from '../api/client'

export interface TripClock { date: string; minutes: number }
export interface TripDay { date: string; items: TripItem[] }

function minutesFromTime(time: string) {
  const [hours, minutes] = time.split(':').map(Number)
  return hours * 60 + minutes
}

export function getTripClock(timezone: string, instant = new Date()): TripClock {
  const parts = new Intl.DateTimeFormat('en-CA', {
    day: '2-digit', hour: '2-digit', hourCycle: 'h23', minute: '2-digit', month: '2-digit', timeZone: timezone, year: 'numeric',
  }).formatToParts(instant)
  const part = (type: Intl.DateTimeFormatPartTypes) => parts.find((value) => value.type === type)?.value ?? ''
  return { date: `${part('year')}-${part('month')}-${part('day')}`, minutes: Number(part('hour')) * 60 + Number(part('minute')) }
}

export function groupTripItems(items: TripItem[]): TripDay[] {
  const groups = new Map<string, TripItem[]>()
  for (const item of [...items].sort((a, b) => `${a.scheduled_date}T${a.start_time}`.localeCompare(`${b.scheduled_date}T${b.start_time}`))) {
    const group = groups.get(item.scheduled_date) ?? []
    group.push(item)
    groups.set(item.scheduled_date, group)
  }
  return [...groups].map(([date, dayItems]) => ({ date, items: dayItems }))
}

export function isPastItem(item: TripItem, clock: TripClock) {
  if (item.scheduled_date !== clock.date) return item.scheduled_date < clock.date
  return minutesFromTime(item.start_time) + item.duration_minutes <= clock.minutes
}

export function isCurrentItem(item: TripItem, clock: TripClock) {
  if (item.scheduled_date !== clock.date) return false
  const start = minutesFromTime(item.start_time)
  return clock.minutes >= start && clock.minutes < start + item.duration_minutes
}

export function isNextItem(item: TripItem, clock: TripClock) {
  if (item.scheduled_date > clock.date) return true
  return item.scheduled_date === clock.date && minutesFromTime(item.start_time) > clock.minutes
}

export function formatTripDate(date: string, currentDate: string) {
  const formatted = new Intl.DateTimeFormat('zh-TW', { month: 'numeric', day: 'numeric', weekday: 'short', timeZone: 'UTC' }).format(new Date(`${date}T12:00:00Z`))
  return date === currentDate ? `今天 · ${formatted}` : formatted
}
