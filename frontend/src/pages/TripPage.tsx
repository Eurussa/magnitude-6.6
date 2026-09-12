import { useCallback, useEffect, useRef, useState } from 'react'
import { getTrip, replan, selectPlan, type PlanId, type ReplanResponse, type Trip } from '../api/client'
import { EventSheet } from '../components/EventSheet'
import { DailyRouteMap } from '../components/DailyRouteMap'
import { LoadingView } from '../components/LoadingView'
import { MultiDaySchedule } from '../components/MultiDaySchedule'
import { ResultsView } from '../components/ResultsView'
import { getTripClock, isPastItem } from '../utils/tripTime'

const minimumLoadingTime = 900

function wait(milliseconds: number) {
  return new Promise((resolve) => window.setTimeout(resolve, milliseconds))
}

function errorMessage(error: unknown) {
  return error instanceof Error ? error.message : '發生未預期的錯誤，請再試一次。'
}

export function TripPage() {
  const [trip, setTrip] = useState<Trip | null>(null)
  const [message, setMessage] = useState('睡過頭兩小時')
  const [result, setResult] = useState<ReplanResponse | null>(null)
  const [tripError, setTripError] = useState('')
  const [replanError, setReplanError] = useState('')
  const [loadingTrip, setLoadingTrip] = useState(true)
  const [replanning, setReplanning] = useState(false)
  const [applyingPlanId, setApplyingPlanId] = useState<PlanId | null>(null)
  const [applyError, setApplyError] = useState('')
  const [hidePastItems, setHidePastItems] = useState(false)
  const [appliedNotice, setAppliedNotice] = useState('')
  const [eventSheetOpen, setEventSheetOpen] = useState(false)
  const loadAttempt = useRef(0)

  const loadTrip = useCallback(async () => {
    const attempt = ++loadAttempt.current
    setLoadingTrip(true)
    setTripError('')

    try {
      const response = await getTrip()
      if (attempt === loadAttempt.current) {
        setTrip(response)
        setHidePastItems(response.version > 1)
      }
    } catch (error) {
      if (attempt === loadAttempt.current) setTripError(errorMessage(error))
    } finally {
      if (attempt === loadAttempt.current) setLoadingTrip(false)
    }
  }, [])

  useEffect(() => {
    // Initial server state belongs in an effect; the request id prevents stale responses.
    // oxlint-disable-next-line react/set-state-in-effect
    void loadTrip()
    return () => {
      loadAttempt.current += 1
    }
  }, [loadTrip])

  async function submitEvent() {
    if (!message.trim() || !trip || replanning) return
    setEventSheetOpen(false)
    setReplanning(true)
    setReplanError('')
    setApplyError('')
    setResult(null)
    const startedAt = Date.now()

    try {
      const response = await replan(message.trim())
      await wait(Math.max(0, minimumLoadingTime - (Date.now() - startedAt)))
      setResult(response)
    } catch (error) {
      await wait(Math.max(0, minimumLoadingTime - (Date.now() - startedAt)))
      setReplanError(errorMessage(error))
    } finally {
      setReplanning(false)
    }
  }

  async function applyPlan(planId: PlanId) {
    if (!result?.replan_id || result.status !== 'ready' || applyingPlanId) return
    setApplyingPlanId(planId)
    setApplyError('')
    try {
      const response = await selectPlan(result.replan_id, planId)
      setTrip(response.trip)
      setHidePastItems(true)
      setAppliedNotice(`已套用方案 ${response.selection.plan_id}，以下只顯示目前時間之後的行程。`)
      setResult(null)
    } catch (error) {
      setApplyError(errorMessage(error))
    } finally {
      setApplyingPlanId(null)
    }
  }

  if (replanning) {
    return <div className="app-shell"><LoadingView message={message} /></div>
  }

  if (result) {
    return (
      <div className="app-shell">
        <ResultsView
          onBack={() => {
            setApplyError('')
            setResult(null)
          }}
          onEditEvent={() => {
            setApplyError('')
            setResult(null)
            setEventSheetOpen(true)
          }}
          result={result}
          applyingPlanId={applyingPlanId}
          applyError={applyError}
          onApply={(planId) => void applyPlan(planId)}
          timezone={trip?.timezone ?? result.weather.timezone}
        />
        {eventSheetOpen && (
          <EventSheet
            message={message}
            onChange={setMessage}
            onClose={() => setEventSheetOpen(false)}
            onSubmit={() => void submitEvent()}
          />
        )}
      </div>
    )
  }

  const visibleItems = trip
    ? hidePastItems
      ? trip.items.filter((item) => !isPastItem(item, getTripClock(trip.timezone)))
      : trip.items
    : []

  return (
    <div className="app-shell">
      <main className="min-h-dvh bg-white pb-[calc(96px+env(safe-area-inset-bottom))]">
        <header className="px-5 pb-4 pt-[calc(18px+env(safe-area-inset-top))]">
          <div className="flex items-center justify-between gap-4">
            <p className="text-lg font-bold text-[#10234a]">SmartTrip</p>
            <span className="rounded-full bg-[#eaf6f5] px-3 py-1.5 text-xs font-bold text-[#117570]">Asia/Tokyo</span>
          </div>
        </header>

        <section className="relative mx-4 h-40 overflow-hidden rounded-[28px] bg-[#ccecff]">
          <img alt="" className="h-full w-full object-cover" src="/assets/tokyo-journey-banner.png" />
          <div className="absolute inset-0 bg-gradient-to-t from-[#10234a]/70 via-transparent to-transparent" />
          <div className="absolute inset-x-0 bottom-0 p-5 text-white">
            <p className="text-sm font-semibold text-white/85">東京旅程</p>
            <h1 className="mt-0.5 text-2xl font-bold">今天要去哪裡？</h1>
          </div>
        </section>

        <section aria-labelledby="today-title" className="px-4 pt-6">
          <div className="flex items-end justify-between gap-4 px-2">
            <div>
              <p className="text-sm font-medium text-[#5d7187]">目前行程</p>
              <h2 className="mt-1 text-2xl font-bold text-[#10234a]" id="today-title">{trip?.city ?? 'Tokyo'}</h2>
            </div>
            {trip && <p className="text-sm font-semibold text-[#168b86]">共 {visibleItems.length} 個活動</p>}
          </div>

          {appliedNotice && <p className="mt-4 rounded-2xl bg-[#eaf6f5] p-4 text-sm leading-6 text-[#235b58]" role="status">{appliedNotice}</p>}

          {loadingTrip && <p className="px-2 py-10 text-center text-[#5d7187]" role="status">正在載入行程⋯</p>}

          {tripError && (
            <div className="mt-5 rounded-2xl bg-[#fff0ee] p-4" role="alert">
              <p className="font-semibold text-[#9c392c]">無法載入目前行程</p>
              <p className="mt-1 break-words text-sm leading-6 text-[#7b4a44]">{tripError}</p>
              <button
                className="mt-3 min-h-11 rounded-xl bg-[#9c392c] px-4 text-sm font-semibold text-white"
                onClick={() => void loadTrip()}
                type="button"
              >
                重新載入行程
              </button>
            </div>
          )}

          {trip && <DailyRouteMap items={visibleItems} timezone={trip.timezone} />}

          {trip && <MultiDaySchedule items={visibleItems} timezone={trip.timezone} />}

          {replanError && (
            <div className="mb-5 rounded-2xl bg-[#fff0ee] p-4" role="alert">
              <p className="font-semibold text-[#9c392c]">無法產生替代方案</p>
              <p className="mt-1 break-words text-sm leading-6 text-[#7b4a44]">{replanError}</p>
              <button
                className="mt-3 min-h-11 rounded-xl border border-[#c77c72] px-4 text-sm font-semibold text-[#9c392c]"
                onClick={() => setEventSheetOpen(true)}
                type="button"
              >
                修改事件後再試一次
              </button>
            </div>
          )}
        </section>

        <div className="fixed bottom-0 left-1/2 z-20 w-full max-w-[414px] -translate-x-1/2 border-t border-[#dbe4eb] bg-white/95 px-4 pb-[calc(14px+env(safe-area-inset-bottom))] pt-3 backdrop-blur">
          <button
            className="min-h-14 w-full rounded-2xl bg-[#123d68] px-5 text-base font-bold text-white shadow-[0_10px_24px_rgba(18,61,104,0.2)] disabled:cursor-not-allowed disabled:opacity-40"
            disabled={!trip}
            onClick={() => setEventSheetOpen(true)}
            type="button"
          >
            發生了什麼事？
          </button>
        </div>
      </main>

      {eventSheetOpen && (
        <EventSheet
          message={message}
          onChange={setMessage}
          onClose={() => setEventSheetOpen(false)}
          onSubmit={() => void submitEvent()}
        />
      )}
    </div>
  )
}
