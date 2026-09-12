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
              {isCurrent && <span className="absolute top-0 size-6 rounded-full border border-[#f47c57]/70 motion-safe:animate-ping motion-reduce:hidden" />}
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
                  <svg aria-hidden="true" className="size-5" fill="none" stroke="currentColor" strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" viewBox="0 0 24 24">
                    <path d="M14.106 5.553a2 2 0 0 0 1.788 0l3.659-1.83A1 1 0 0 1 21 4.619v12.764a1 1 0 0 1-.553.894l-4.553 2.277a2 2 0 0 1-1.788 0l-4.212-2.106a2 2 0 0 0-1.788 0l-3.659 1.83A1 1 0 0 1 3 19.381V6.618a1 1 0 0 1 .553-.894l4.553-2.277a2 2 0 0 1 1.788 0z" />
                    <path d="M15 5.764v15" />
                    <path d="M9 3.236v15" />
                  </svg>
                </a>
              )}
            </div>
          </li>
        )
      })}
    </ol>
  )
}
