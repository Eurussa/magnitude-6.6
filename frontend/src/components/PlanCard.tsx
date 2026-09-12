import { useId, useState } from 'react'
import type { Plan, PlanId } from '../api/client'
import { PlanSchedulePreview } from './PlanSchedulePreview'

interface PlanCardProps {
  plan: Plan
  canApply: boolean
  isApplying: boolean
  isRecommended: boolean
  onApply: (planId: PlanId) => void
  timezone: string
}

export function PlanCard({ plan, canApply, isApplying, isRecommended, onApply, timezone }: PlanCardProps) {
  const [expanded, setExpanded] = useState(false)
  const scheduleId = useId()

  return (
    <article className={`rounded-3xl border bg-white p-4 shadow-[0_10px_24px_rgba(16,35,74,0.06)] transition-colors ${expanded ? 'border-[#82b9b5] ring-2 ring-[#168b86]/10' : 'border-[#d7e2ea]'}`}>
      <div className="flex items-start gap-3">
        <span className="grid size-10 shrink-0 place-items-center rounded-2xl bg-[#eaf6f5] font-bold text-[#117570]">
          {plan.id}
        </span>
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2">
            <h2 className="break-words text-lg font-bold text-[#10234a]">{plan.title}</h2>
            {isRecommended && <span className="rounded-full bg-[#fff1df] px-2 py-1 text-xs font-bold text-[#9a562e]">推薦</span>}
          </div>
          <p className="mt-0.5 text-sm text-[#5d7187]">{canApply ? '可以套用' : '目前不可套用'}</p>
        </div>
      </div>

      <p className="mt-4 break-words leading-7 text-[#29445e]">{plan.explanation}</p>

      {expanded && (
        <div className="mt-4 rounded-2xl border border-[#bcd5dc] bg-[#e8f2f5] p-3" id={scheduleId}>
          <p className="px-1 text-sm font-bold text-[#173b57]">方案中的行程</p>
          <PlanSchedulePreview items={plan.items} timezone={timezone} />
        </div>
      )}

      {plan.booking_warnings.length > 0 && (
        <ul className="mt-4 space-y-1 rounded-2xl bg-[#fff1df] p-3 text-sm leading-6 text-[#67431f]">
          {plan.booking_warnings.map((warning) => <li key={warning}>{warning}</li>)}
        </ul>
      )}

      <div className="mt-4 flex gap-2">
        <button
          aria-controls={scheduleId}
          aria-expanded={expanded}
          className={`min-h-11 rounded-xl border px-4 text-sm font-semibold transition-colors ${expanded ? 'border-[#117570] bg-[#e1f2f0] text-[#0c625e]' : 'border-[#cbd8e5] text-[#29445e] active:bg-[#edf5fb]'}`}
          onClick={() => setExpanded((value) => !value)}
          type="button"
        >
          {expanded ? '收起行程' : '查看行程'}
        </button>
        <button
          className="min-h-11 flex-1 rounded-xl bg-[#123d68] px-4 text-sm font-semibold text-white disabled:cursor-not-allowed disabled:bg-[#d8e0e7] disabled:text-[#718191]"
          disabled={!canApply || isApplying}
          onClick={() => onApply(plan.id)}
          type="button"
        >
          {isApplying ? '正在套用⋯' : `套用方案 ${plan.id}`}
        </button>
      </div>
    </article>
  )
}
