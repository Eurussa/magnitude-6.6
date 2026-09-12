import type { TripItem } from '../api/client'
import { formatDuration, formatTripDate, getTripClock, groupTripItems, isCurrentItem, isNextItem, isPastItem } from '../utils/tripTime'

interface PlanSchedulePreviewProps {
  items: TripItem[]
  timezone: string
}

export function PlanSchedulePreview({ items, timezone }: PlanSchedulePreviewProps) {
  const clock = getTripClock(timezone)
  const upcomingItems = items.filter((item) => !isPastItem(item, clock))
  const days = groupTripItems(upcomingItems)
  const nextItemId = upcomingItems
    .filter((item) => isNextItem(item, clock))
    .sort((a, b) => `${a.scheduled_date}T${a.start_time}`.localeCompare(`${b.scheduled_date}T${b.start_time}`))[0]?.id

  if (days.length === 0) {
    return <p className="rounded-2xl bg-white px-4 py-6 text-center text-sm text-[#5d7187]">目前時間之後沒有其他行程。</p>
  }

  return (
    <div className="mt-3 space-y-3">
      {days.map((day) => (
        <section className="overflow-hidden rounded-2xl border border-[#d7e2ea] bg-white" key={day.date}>
          <div className="flex min-h-12 items-center justify-between gap-3 bg-[#e8f2f5] px-4">
            <h3 className="font-bold text-[#173b57]">{formatTripDate(day.date, clock.date)}</h3>
            <span className="text-xs font-semibold text-[#5d7187]">{day.items.length} 個活動</span>
          </div>
          <ol className="divide-y divide-[#e7edf2]">
            {day.items.map((item) => {
              const isCurrent = isCurrentItem(item, clock)
              const isNext = item.id === nextItemId
              return (
                <li className={`grid grid-cols-[50px_minmax(0,1fr)] gap-3 px-4 py-3 ${isCurrent ? 'bg-[#fff1df]' : ''}`} key={item.id}>
                  <time className="font-semibold tabular-nums text-[#173b57]">{item.start_time}</time>
                  <div className="min-w-0">
                    <div className="flex flex-wrap items-center gap-2">
                      <p className="break-words font-semibold text-[#10234a]">{item.name}</p>
                      {isCurrent && <span className="rounded-full bg-[#f47c57] px-2 py-0.5 text-xs font-bold text-white">現在</span>}
                      {isNext && <span className="rounded-full bg-[#dff2ef] px-2 py-0.5 text-xs font-bold text-[#117570]">接下來</span>}
                    </div>
                    <div className="mt-1 flex flex-wrap gap-x-3 gap-y-1 text-xs text-[#62778a]">
                      <span>{formatDuration(item.duration_minutes)}</span>
                      <span>{item.indoor ? '室內' : '戶外'}</span>
                      {item.booking ? <span>已預約</span> : !item.movable && <span>行程固定</span>}
                    </div>
                  </div>
                </li>
              )
            })}
          </ol>
        </section>
      ))}
    </div>
  )
}
