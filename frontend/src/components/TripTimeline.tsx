import type { TripItem } from '../api/client'
import { isCurrentItem, isPastItem, type TripClock } from '../utils/tripTime'

interface TripTimelineProps { items: TripItem[]; clock: TripClock; nextItemId?: string; showMaps?: boolean }

export function TripTimeline({ items, clock, nextItemId, showMaps = true }: TripTimelineProps) {
  return (
    <ol>
      {items.map((item, index) => {
        const isCurrent = isCurrentItem(item, clock)
        const isNext = item.id === nextItemId
        const isPast = isPastItem(item, clock)
        return (
          <li className={`grid grid-cols-[54px_18px_minmax(0,1fr)] gap-2 rounded-2xl px-2 pt-3 ${isCurrent ? 'bg-[#fff1df]' : ''}`} key={item.id}>
            <time className={`pt-0.5 font-semibold tabular-nums ${isPast ? 'text-[#93a1ae]' : 'text-[#173b57]'}`}>{item.start_time}</time>
            <span className="relative flex justify-center" aria-hidden="true">
              <span className={`relative z-10 mt-1.5 size-3 rounded-full border-2 ${isCurrent ? 'border-[#f47c57] bg-[#f47c57]' : 'border-[#168b86] bg-white'}`} />
              {index < items.length - 1 && <span className="absolute bottom-0 top-4 w-px bg-[#cbd8e5]" />}
            </span>
            <div className="min-w-0 pb-6">
              <div className="flex flex-wrap items-center gap-2">
                <p className={`break-words font-semibold ${isPast ? 'text-[#8695a2]' : 'text-[#10234a]'}`}>{item.name}</p>
                {isCurrent && <span className="rounded-full bg-[#f47c57] px-2 py-0.5 text-xs font-bold text-white">現在</span>}
                {isNext && <span className="rounded-full bg-[#eaf6f5] px-2 py-0.5 text-xs font-bold text-[#117570]">接下來</span>}
              </div>
              <div className="mt-1.5 flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-[#62778a]">
                <span>{item.duration_minutes} 分鐘</span><span>{item.indoor ? '室內' : '戶外'}</span>
                {item.booking && <span>已預約 · 不可隨意移動</span>}
              </div>
              {showMaps && <a className="mt-2 inline-flex min-h-11 items-center text-sm font-semibold text-[#117570] underline decoration-[#9bc9c6] underline-offset-4" href={`https://www.google.com/maps/search/?api=1&query=${item.latitude},${item.longitude}`} rel="noopener noreferrer" target="_blank">在 Google Maps 查看</a>}
            </div>
          </li>
        )
      })}
    </ol>
  )
}
