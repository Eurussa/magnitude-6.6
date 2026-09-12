import { TOKYO_WAITING_TIP } from "../data/travelTips";

interface LoadingViewProps {
  message: string;
}

export function LoadingView({ message }: LoadingViewProps) {
  return (
    <main className="flex min-h-dvh flex-col bg-white px-5 pb-[calc(24px+env(safe-area-inset-bottom))] pt-[calc(28px+env(safe-area-inset-top))]">
      <p className="text-sm font-semibold text-[#168b86]">SmartTrip</p>
      <section
        aria-live="polite"
        className="flex flex-1 flex-col justify-center py-8 text-center"
      >
        <div className="mx-auto size-16 rounded-full border-[5px] border-[#dbeaf1] border-t-[#f47c57] motion-safe:animate-spin" />
        <h1 className="mt-6 text-2xl font-bold text-[#10234a]">
          正在比較替代方案
        </h1>
        <p className="mt-2 break-words text-[#5d7187]">「{message}」</p>

        <ol className="mx-auto mt-8 w-full max-w-72 space-y-4 text-left text-sm text-[#5d7187]">
          <li className="flex gap-3 text-[#173b57]">
            <span aria-hidden="true">●</span>理解事件與影響時間
          </li>
          <li className="flex gap-3">
            <span aria-hidden="true">○</span>檢查預約與不可移動行程
          </li>
          <li className="flex gap-3">
            <span aria-hidden="true">○</span>確認後續行程是否受影響
          </li>
        </ol>
      </section>

      <aside className="overflow-hidden rounded-3xl bg-[#eaf6f5]">
        <img
          alt=""
          className="h-24 w-full object-cover"
          src="/assets/tokyo-journey-banner.png"
        />
        <div className="p-4">
          <h2 className="mt-2 text-base font-bold text-[#173b57]">
            {TOKYO_WAITING_TIP.title}
          </h2>
          <p className="mt-1 text-sm leading-6 text-[#29445e]">
            {TOKYO_WAITING_TIP.body}
          </p>
        </div>
      </aside>
    </main>
  );
}
