import { useState } from "react";
import type { TripItem } from "../api/client";
import { createDailyMapUrls } from "../utils/googleMaps";
import {
  formatTripDate,
  getTripClock,
  groupTripItems,
} from "../utils/tripTime";

interface DailyRouteMapProps {
  items: TripItem[];
  timezone: string;
}

function preferredDate(dates: string[], today: string) {
  if (dates.includes(today)) return today;
  return dates.find((date) => date > today) ?? dates[0] ?? "";
}

export function DailyRouteMap({ items, timezone }: DailyRouteMapProps) {
  const clock = getTripClock(timezone);
  const days = groupTripItems(items);
  const dates = days.map((day) => day.date);
  const [selectedDate, setSelectedDate] = useState("");
  const activeDate = dates.includes(selectedDate)
    ? selectedDate
    : preferredDate(dates, clock.date);
  const selectedItems =
    days.find((day) => day.date === activeDate)?.items ?? [];
  const embedApiKey =
    import.meta.env.VITE_GOOGLE_MAPS_EMBED_API_KEY?.trim() ?? "";
  const mapUrls = createDailyMapUrls(selectedItems, embedApiKey);

  if (!mapUrls || !activeDate) {
    return (
      <section
        aria-label="當日路線"
        className="mt-6 rounded-3xl bg-[#f1f6f8] p-4"
      >
        <p className="font-bold text-[#10234a]">當日路線</p>
        <p className="mt-2 text-sm leading-6 text-[#5d7187]">
          目前沒有可顯示的當日路線。
        </p>
      </section>
    );
  }

  return (
    <section aria-label="當日路線" className="mt-6">
      <details className="group overflow-hidden rounded-3xl border border-[#d7e2ea] bg-white">
        <summary className="flex min-h-14 cursor-pointer list-none items-center justify-between gap-3 px-4 [&::-webkit-details-marker]:hidden">
          <span>
            <span className="block text-sm font-medium text-[#5d7187]">
              大致移動範圍
            </span>
            <span className="mt-0.5 block font-bold text-[#10234a]">
              當日路線
            </span>
          </span>
          <span className="flex items-center gap-2 text-xs font-semibold text-[#5d7187]">
            {selectedItems.length} 個活動
            <span
              aria-hidden="true"
              className="text-lg transition group-open:rotate-180"
            >
              ⌄
            </span>
          </span>
        </summary>

        <div className="border-t border-[#e2eaf0] bg-[#f1f6f8] p-4">
          <div aria-label="選擇查看路線的日期" className="flex flex-wrap gap-2">
            {days.map((day) => {
              const selected = day.date === activeDate;
              return (
                <button
                  aria-pressed={selected}
                  className={`min-h-11 rounded-xl border px-3 text-sm font-semibold transition ${selected ? "border-[#117570] bg-[#117570] text-white" : "border-[#cbd8e5] bg-white text-[#29445e] active:bg-[#eaf2f7]"}`}
                  key={day.date}
                  onClick={() => setSelectedDate(day.date)}
                  type="button"
                >
                  {formatTripDate(day.date, clock.date)}
                </button>
              );
            })}
          </div>

          {embedApiKey ? (
            <iframe
              allowFullScreen
              className="mt-4 h-56 w-full rounded-2xl border-0 bg-white"
              loading="lazy"
              referrerPolicy="strict-origin-when-cross-origin"
              src={mapUrls.embedUrl}
              title={`${formatTripDate(activeDate, clock.date)}的 Google Maps 路線預覽`}
            />
          ) : (
            <div
              className="mt-4 rounded-2xl bg-white px-4 py-5 text-sm leading-6 text-[#5d7187]"
              role="status"
            >
              地圖預覽目前無法載入。
            </div>
          )}

          <a
            className="mt-3 inline-flex min-h-11 items-center rounded-xl px-3 text-sm font-semibold text-[#117570] underline decoration-[#9bc9c6] underline-offset-4 active:bg-[#e4f3f1]"
            href={mapUrls.externalUrl}
            rel="noopener noreferrer"
            target="_blank"
          >
            {mapUrls.isSinglePlace
              ? "在 Google Maps 查看地點"
              : "在 Google Maps 查看當日路線"}
          </a>
          <p className="mt-2 text-xs leading-5 text-[#62778a]">
            路線由 Google Maps 提供，僅供查看大致移動範圍。
          </p>
        </div>
      </details>
    </section>
  );
}
