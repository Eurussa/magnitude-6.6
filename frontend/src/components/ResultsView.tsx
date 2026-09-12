import type { PlanId, ReplanResponse } from '../api/client'
import { buildPreviewPlans } from '../data/replanPreview'
import { PlanCard } from './PlanCard'

interface ResultsViewProps {
  result: ReplanResponse
  onBack: () => void
  onEditEvent: () => void
  onApply: (planId: PlanId) => void
  applyingPlanId: PlanId | null
  applyError: string
  timezone: string
}

export function ResultsView({ result, onBack, onEditEvent, onApply, applyingPlanId, applyError, timezone }: ResultsViewProps) {
  const isPlaceholder = result.status === 'placeholder'
  const plans = isPlaceholder ? buildPreviewPlans(result) : result.plans
  return (
    <main className="min-h-dvh bg-[#f8fbfd] px-5 pb-[calc(28px+env(safe-area-inset-bottom))] pt-[calc(20px+env(safe-area-inset-top))]">
      <header className="flex min-h-12 items-center gap-3">
        <button
          aria-label="返回今日行程"
          className="grid size-11 shrink-0 place-items-center rounded-full text-2xl text-[#173b57] active:bg-[#eaf2f7] disabled:opacity-40"
          disabled={applyingPlanId !== null}
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

      {isPlaceholder && (
        <section className="mt-5 rounded-2xl bg-[#fff1df] p-4 text-[#67431f]" role="status">
          <p className="font-semibold">示範方案，尚未由後端完成重排</p>
          <p className="mt-1 text-sm leading-6">以下使用固定示範資料呈現比較流程，不會套用或更新偏好。</p>
        </section>
      )}

      {!isPlaceholder && result.preference_insight && (
        <section className="mt-5 rounded-2xl bg-[#eaf6f5] p-4 text-sm leading-6 text-[#235b58]">
          <p className="font-semibold">依照你的旅遊偏好推薦</p>
          <p className="mt-1">{result.preference_insight}</p>
        </section>
      )}

      <p className="mt-5 text-sm leading-6 text-[#5d7187]">
        系統已收到「{result.event.summary}」。{isPlaceholder ? '後端回傳可執行方案後，才能套用並更新偏好。' : '請展開方案，確認接下來幾天的安排。'}
      </p>

      {applyError && <div className="mt-4 rounded-2xl bg-[#fff0ee] p-4 text-sm leading-6 text-[#9c392c]" role="alert">{applyError}</div>}

      <div className="mt-5 grid gap-4">
        {plans.map((plan) => (
          <PlanCard
            canApply={result.status === 'ready' && result.replan_id !== null && plan.feasible && applyingPlanId === null}
            isApplying={applyingPlanId === plan.id}
            isRecommended={result.recommended_plan_id === plan.id}
            key={plan.id}
            onApply={onApply}
            plan={plan}
            timezone={timezone}
          />
        ))}
      </div>

      <button
        className="mt-5 min-h-12 w-full rounded-2xl border border-[#b8c9d6] bg-white px-4 font-semibold text-[#173b57] disabled:opacity-40"
        disabled={applyingPlanId !== null}
        onClick={onEditEvent}
        type="button"
      >
        重新描述狀況
      </button>
    </main>
  )
}
