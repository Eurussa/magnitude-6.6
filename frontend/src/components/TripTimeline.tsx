import type { TripItem } from '../api/client'
import { formatDuration, isCurrentItem, isPastItem, type TripClock } from '../utils/tripTime'
import { MapIcon } from './Icons'

interface TripTimelineProps { items: TripItem[]; clock: TripClock; emphasizeNext?: boolean; nextItemId?: string; showMaps?: boolean }

export function TripTimeline({ items, clock, emphasizeNext = false, nextItemId, showMaps = true }: TripTimelineProps) {
  return (
    <ol>
      {items.map((item, index) => {
        const isCurrent = isCurrentItem(item, clock)
        const isNext = item.id === nextItemId
        const isEmphasizedNext = isNext && emphasizeNext
        const isPast = isPastItem(item, clock)
        return (
          <li className={`grid grid-cols-[54px_18px_minmax(0,1fr)] gap-2 rounded-2xl px-2 pt-3 ${isCurrent ? 'bg-[#fff1df]' : ''}`} key={item.id}>
            <time className={`pt-0.5 font-semibold tabular-nums ${isPast ? 'text-[#93a1ae]' : 'text-[#173b57]'}`}>{item.start_time}</time>
            <span className="relative flex justify-center" aria-hidden="true">
              {(isCurrent || isEmphasizedNext) && (
                <span className="absolute top-0.5 size-5 rounded-full border border-[#f47c57]/60 motion-safe:[animation:timeline-ring-pulse_1.6s_ease-in-out_infinite]" />
              )}
              <span className={`relative z-10 mt-1.5 size-3 rounded-full border-2 ${isCurrent ? 'border-[#f47c57] bg-[#f47c57]' : isEmphasizedNext ? 'border-[#f47c57] bg-white' : 'border-[#168b86] bg-white'}`} />
              {index < items.length - 1 && <span className="absolute bottom-0 top-4 w-px bg-[#cbd8e5]" />}
            </span>
            <div className="min-w-0 pb-6">
              <div className="flex flex-wrap items-center gap-2">
                <p className={`break-words font-semibold ${isPast ? 'text-[#8695a2]' : 'text-[#10234a]'}`}>{item.name}</p>
                {isCurrent && <span className="rounded-full bg-[#f47c57] px-2 py-0.5 text-xs font-bold text-white">現在</span>}
                {isNext && <span className="rounded-full bg-[#eaf6f5] px-2 py-0.5 text-xs font-bold text-[#117570]">接下來</span>}
              </div>
              <div className="mt-1.5 flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-[#62778a]">
                <span>{formatDuration(item.duration_minutes)}</span><span>{item.indoor ? '室內' : '戶外'}</span>
                {item.booking ? <span>已預約</span> : !item.movable && <span>行程固定</span>}
              </div>
              {showMaps && (
                <a
                  aria-label={`在 Google Maps 查看「${item.name}」`}
                  className="mt-1 grid size-11 place-items-center rounded-full text-[#117570] transition active:bg-[#eaf6f5]"
                  href={`https://www.google.com/maps/search/?api=1&query=${item.latitude},${item.longitude}`}
                  rel="noopener noreferrer"
                  target="_blank"
                >
                  <MapIcon className="size-5" />
                </a>
              )}
            </div>
          </li>
        )
      })}
    </ol>
  )
}
