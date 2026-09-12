import type { ReplanResponse } from '../api/client'
import { PlanCard } from './PlanCard'

interface ResultsViewProps {
  result: ReplanResponse
  onBack: () => void
  onEditEvent: () => void
}

export function ResultsView({ result, onBack, onEditEvent }: ResultsViewProps) {
  return (
    <main className="min-h-dvh bg-[#f8fbfd] px-5 pb-[calc(28px+env(safe-area-inset-bottom))] pt-[calc(20px+env(safe-area-inset-top))]">
      <header className="flex min-h-12 items-center gap-3">
        <button
          aria-label="返回今日行程"
          className="grid size-11 shrink-0 place-items-center rounded-full text-2xl text-[#173b57] active:bg-[#eaf2f7]"
          onClick={onBack}
          type="button"
        >
          ‹
        </button>
        <div>
          <p className="text-xs font-bold tracking-wide text-[#168b86]">替代行程</p>
          <h1 className="text-2xl font-bold text-[#10234a]">比較 {result.plans.length} 個方案</h1>
        </div>
      </header>

      <section className="mt-5 rounded-2xl bg-[#fff1df] p-4 text-[#67431f]" role="status">
        <p className="font-semibold">目前是預覽結果，尚未完成重排</p>
        <p className="mt-1 text-sm leading-6">{result.warnings.join(' ')}</p>
      </section>

      <p className="mt-5 text-sm leading-6 text-[#5d7187]">
        系統已收到「{result.event.summary}」。後端回傳可執行方案後，才能套用並更新偏好。
      </p>

      <div className="mt-5 grid gap-4">
        {result.plans.map((plan) => <PlanCard canApply={false} key={plan.id} plan={plan} />)}
      </div>

      <button
        className="mt-5 min-h-12 w-full rounded-2xl border border-[#b8c9d6] bg-white px-4 font-semibold text-[#173b57]"
        onClick={onEditEvent}
        type="button"
      >
        重新描述狀況
      </button>
    </main>
  )
}
