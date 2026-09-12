import type { TripItem } from '../api/client'
import { formatTripDate, getTripClock, groupTripItems, isNextItem, isPastItem } from '../utils/tripTime'
import { TripTimeline } from './TripTimeline'

interface MultiDayScheduleProps {
  items: TripItem[]
  timezone: string
  showMaps?: boolean
}

export function MultiDaySchedule({ items, timezone, showMaps = true }: MultiDayScheduleProps) {
  const clock = getTripClock(timezone)
  const days = groupTripItems(items)
  const nextItemId = items
    .filter((item) => isNextItem(item, clock))
    .sort((a, b) => `${a.scheduled_date}T${a.start_time}`.localeCompare(`${b.scheduled_date}T${b.start_time}`))[0]?.id

  if (days.length === 0) {
    return <p className="py-8 text-center text-sm text-[#5d7187]">目前時間之後沒有其他行程。</p>
  }

  return (
    <div className="mt-4 space-y-3">
      {days.map((day) => {
        const isToday = day.date === clock.date
        if (isToday) {
          const earlierItems = day.items.filter((item) => isPastItem(item, clock))
          const activeAndLaterItems = day.items.filter((item) => !isPastItem(item, clock))
          return (
            <section className="rounded-3xl bg-white" key={day.date}>
              <div className="flex min-h-12 items-center justify-between gap-3 px-2">
                <h3 className="font-bold text-[#10234a]">{formatTripDate(day.date, clock.date)}</h3>
                <span className="text-xs font-semibold text-[#5d7187]">{day.items.length} 個活動</span>
              </div>
              {earlierItems.length > 0 && (
                <details className="group mb-2 rounded-2xl bg-[#f5f8fa]">
                  <summary className="flex min-h-12 cursor-pointer list-none items-center justify-between gap-3 rounded-2xl px-3 text-sm font-semibold text-[#5d7187] focus-visible:outline-none">
                    <span>較早行程</span>
                    <span className="flex items-center gap-2">
                      {earlierItems.length} 筆
                      <span aria-hidden="true" className="text-base transition group-open:rotate-180">⌄</span>
                    </span>
                  </summary>
                  <div className="border-t border-[#e2eaf0] px-1 pt-1">
                    <TripTimeline clock={clock} items={earlierItems} showMaps={showMaps} />
                  </div>
                </details>
              )}
              <TripTimeline clock={clock} items={activeAndLaterItems} nextItemId={nextItemId} showMaps={showMaps} />
            </section>
          )
        }

        return (
          <details className="group rounded-2xl border border-[#d7e2ea] bg-white" key={day.date}>
            <summary className="flex min-h-14 cursor-pointer list-none items-center justify-between gap-3 rounded-2xl px-4 font-bold text-[#173b57] focus-visible:outline-none">
              <span>{formatTripDate(day.date, clock.date)}</span>
              <span className="flex items-center gap-2 text-xs font-semibold text-[#5d7187]">
                {day.items.length} 個活動
                <span aria-hidden="true" className="text-lg transition group-open:rotate-180">⌄</span>
              </span>
            </summary>
            <div className="border-t border-[#e2eaf0] px-2 pt-1">
              <TripTimeline clock={clock} items={day.items} nextItemId={nextItemId} showMaps={showMaps} />
            </div>
          </details>
        )
      })}
    </div>
  )
}
