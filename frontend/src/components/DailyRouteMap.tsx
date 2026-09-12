import { useCallback, useEffect, useRef, useState } from "react";
import type { TripItem } from "../api/client";
import { createDailyMapUrls } from "../utils/googleMaps";
import {
  formatTripDate,
  getTripClock,
  groupTripItems,
} from "../utils/tripTime";
import { MapIcon, XIcon } from "./Icons";

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
  const [isOpen, setIsOpen] = useState(false);
  const openerRef = useRef<HTMLButtonElement>(null);
  const dialogRef = useRef<HTMLDialogElement>(null);
  const closeButtonRef = useRef<HTMLButtonElement>(null);
  const activeDate = dates.includes(selectedDate)
    ? selectedDate
    : preferredDate(dates, clock.date);
  const selectedItems =
    days.find((day) => day.date === activeDate)?.items ?? [];
  const embedApiKey =
    import.meta.env.VITE_GOOGLE_MAPS_EMBED_API_KEY?.trim() ?? "";
  const mapUrls = createDailyMapUrls(selectedItems, embedApiKey);

  const finishClose = useCallback(() => {
    setIsOpen(false);
    window.requestAnimationFrame(() => openerRef.current?.focus());
  }, []);

  const requestClose = finishClose;

  useEffect(() => {
    if (!isOpen) return;
    const dialog = dialogRef.current;
    if (!dialog) return;

    const previousOverflow = document.body.style.overflow;
    if (!dialog.open) dialog.showModal();
    document.body.style.overflow = "hidden";
    closeButtonRef.current?.focus();

    return () => {
      document.body.style.overflow = previousOverflow;
      if (dialog.open) dialog.close();
    };
  }, [isOpen]);

  if (!mapUrls || !activeDate) {
    return (
      <section
        aria-label="本日路線"
        className="mt-6 rounded-3xl bg-[#f1f6f8] p-4"
      >
        <p className="font-bold text-[#10234a]">本日路線</p>
        <p className="mt-2 text-sm leading-6 text-[#5d7187]">
          目前沒有可顯示的當日路線。
        </p>
      </section>
    );
  }

  return (
    <section aria-label="本日路線" className="mt-6">
      <button
        aria-expanded={isOpen}
        aria-haspopup="dialog"
        className="flex size-28 flex-col items-center justify-center gap-2 rounded-3xl border border-[#bcd5dc] bg-[#eaf6f5] font-bold text-[#117570] shadow-[0_8px_20px_rgba(16,35,74,0.06)] transition active:bg-[#dcefed]"
        onClick={() => setIsOpen(true)}
        ref={openerRef}
        type="button"
      >
        <MapIcon className="size-7" />
        <span>本日路線</span>
      </button>

      {isOpen && (
        <dialog
          aria-describedby="daily-route-description"
          aria-labelledby="daily-route-modal-title"
          className="fixed inset-0 m-auto max-h-[calc(100dvh-32px)] w-[calc(100%-32px)] max-w-[382px] overflow-y-auto rounded-[28px] border-0 bg-white p-0 text-[#10234a] shadow-[0_24px_70px_rgba(16,35,74,0.28)] backdrop:bg-[#10234a]/55 backdrop:backdrop-blur-sm"
          onCancel={(event) => {
            event.preventDefault();
            requestClose();
          }}
          onMouseDown={(event) => {
            const bounds = event.currentTarget.getBoundingClientRect();
            const isBackdrop =
              event.clientX < bounds.left ||
              event.clientX > bounds.right ||
              event.clientY < bounds.top ||
              event.clientY > bounds.bottom;
            if (isBackdrop) requestClose();
          }}
          ref={dialogRef}
        >
          <div className="px-5 pb-[calc(20px+env(safe-area-inset-bottom))] pt-5">
            <div className="flex items-start justify-between gap-4">
              <div>
                <h2
                  className="mt-1 text-xl font-bold"
                  id="daily-route-modal-title"
                >
                  本日路線
                </h2>
              </div>
              <button
                aria-label="關閉本日路線"
                className="grid size-11 shrink-0 place-items-center rounded-full text-[#355169] active:bg-[#edf5fb]"
                onClick={requestClose}
                ref={closeButtonRef}
                type="button"
              >
                <XIcon className="size-6" />
              </button>
            </div>

            <div
              aria-label="選擇查看路線的日期"
              className="mt-4 flex flex-wrap gap-2"
            >
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
                className="mt-4 h-56 w-full rounded-2xl border-0 bg-[#f1f6f8]"
                loading="lazy"
                referrerPolicy="strict-origin-when-cross-origin"
                src={mapUrls.embedUrl}
                title={`${formatTripDate(activeDate, clock.date)}的 Google Maps 路線預覽`}
              />
            ) : (
              <div
                className="mt-4 rounded-2xl bg-[#f1f6f8] px-4 py-5 text-sm leading-6 text-[#5d7187]"
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
            <p
              className="mt-2 text-xs leading-5 text-[#62778a]"
              id="daily-route-description"
            >
              路線由 Google Maps 提供，僅供查看大致移動範圍。
            </p>
          </div>
        </dialog>
      )}
    </section>
  );
}
