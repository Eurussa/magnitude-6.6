import { useId, useState, type ReactNode } from 'react'
import type { TripItem } from '../api/client'
import { formatTripDate, getTripClock, groupTripItems, isCurrentItem, isNextItem, isPastItem } from '../utils/tripTime'
import { ChevronDownIcon } from './Icons'
import { TripTimeline } from './TripTimeline'

interface MultiDayScheduleProps {
  items: TripItem[]
  timezone: string
  showMaps?: boolean
}

interface ScheduleAccordionProps {
  children: ReactNode
  countLabel: string
  title: string
  variant?: 'subtle' | 'outlined'
}

function ScheduleAccordion({ children, countLabel, title, variant = 'outlined' }: ScheduleAccordionProps) {
  const [expanded, setExpanded] = useState(false)
  const contentId = useId()
  const isSubtle = variant === 'subtle'

  return (
    <section className={isSubtle ? 'mb-2 rounded-2xl bg-[#f5f8fa]' : 'rounded-2xl border border-[#d7e2ea] bg-white'}>
      <button
        aria-controls={contentId}
        aria-expanded={expanded}
        className={`flex w-full cursor-pointer items-center justify-between gap-3 rounded-2xl text-left focus-visible:outline-none ${isSubtle ? 'min-h-12 px-3 text-sm font-semibold text-[#5d7187]' : 'min-h-14 px-4 font-bold text-[#173b57]'}`}
        onClick={() => setExpanded((value) => !value)}
        type="button"
      >
        <span>{title}</span>
        <span className="flex items-center gap-2 text-xs font-semibold text-[#5d7187]">
          {countLabel}
          <ChevronDownIcon className={`size-5 shrink-0 transition-transform motion-reduce:transition-none ${expanded ? 'rotate-180' : ''}`} />
        </span>
      </button>
      {expanded && <div className="border-t border-[#e2eaf0] px-2 pt-1" id={contentId}>{children}</div>}
    </section>
  )
}

export function MultiDaySchedule({ items, timezone, showMaps = true }: MultiDayScheduleProps) {
  const clock = getTripClock(timezone)
  const days = groupTripItems(items)
  const hasCurrentItem = items.some((item) => isCurrentItem(item, clock))
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
                <ScheduleAccordion countLabel={`${earlierItems.length} 筆`} title="較早行程" variant="subtle">
                  <TripTimeline clock={clock} items={earlierItems} showMaps={showMaps} />
                </ScheduleAccordion>
              )}
              <TripTimeline clock={clock} emphasizeNext={!hasCurrentItem} items={activeAndLaterItems} nextItemId={nextItemId} showMaps={showMaps} />
            </section>
          )
        }

        return (
          <ScheduleAccordion countLabel={`${day.items.length} 個活動`} key={day.date} title={formatTripDate(day.date, clock.date)}>
            <TripTimeline clock={clock} emphasizeNext={!hasCurrentItem} items={day.items} nextItemId={nextItemId} showMaps={showMaps} />
          </ScheduleAccordion>
        )
      })}
    </div>
  )
}
