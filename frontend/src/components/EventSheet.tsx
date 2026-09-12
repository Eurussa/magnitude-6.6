import { useEffect } from 'react'

interface EventSheetProps {
  message: string
  onChange: (message: string) => void
  onClose: () => void
  onSubmit: () => void
}

const examples = ['睡過頭兩小時', '下午開始下大雨', '博物館臨時休館']

export function EventSheet({ message, onChange, onClose, onSubmit }: EventSheetProps) {
  useEffect(() => {
    const previousOverflow = document.body.style.overflow
    document.body.style.overflow = 'hidden'

    function handleKeyDown(event: KeyboardEvent) {
      if (event.key === 'Escape') onClose()
    }

    document.addEventListener('keydown', handleKeyDown)
    return () => {
      document.body.style.overflow = previousOverflow
      document.removeEventListener('keydown', handleKeyDown)
    }
  }, [onClose])

  return (
    <div
      className="fixed inset-0 z-50 flex items-end justify-center bg-[#10234a]/45"
      onMouseDown={(event) => {
        if (event.target === event.currentTarget) onClose()
      }}
    >
      <section
        aria-labelledby="event-sheet-title"
        aria-modal="true"
        className="w-full max-w-[414px] rounded-t-[28px] bg-white px-5 pb-[calc(20px+env(safe-area-inset-bottom))] pt-3 shadow-[0_-20px_50px_rgba(16,35,74,0.18)]"
        role="dialog"
      >
        <div className="mx-auto mb-4 h-1 w-10 rounded-full bg-[#cbd8e5]" />
        <div className="flex items-start justify-between gap-4">
          <div>
            <p className="text-sm font-medium text-[#5d7187]">更新接下來的旅程</p>
            <h2 className="mt-1 text-2xl font-bold text-[#10234a]" id="event-sheet-title">
              發生了什麼事？
            </h2>
          </div>
          <button
            aria-label="關閉事件輸入"
            className="grid size-11 shrink-0 place-items-center rounded-full text-2xl text-[#355169] active:bg-[#edf5fb]"
            onClick={onClose}
            type="button"
          >
            ×
          </button>
        </div>

        <label className="mt-5 block text-sm font-semibold text-[#29445e]" htmlFor="event-message">
          用一句話描述狀況
        </label>
        <textarea
          autoFocus
          className="mt-2 min-h-28 w-full resize-none rounded-2xl border border-[#cbd8e5] bg-[#f8fbfd] p-4 text-base text-[#10234a] outline-none transition focus:border-[#168b86] focus:ring-4 focus:ring-[#168b86]/10"
          id="event-message"
          maxLength={2000}
          onChange={(event) => onChange(event.target.value)}
          placeholder="例如：睡過頭兩小時"
          value={message}
        />
        <p className="mt-2 text-right text-xs text-[#6d8092]">{message.length} / 2000</p>

        <div aria-label="事件範例" className="mt-3 flex flex-wrap gap-2">
          {examples.map((example) => (
            <button
              className="min-h-11 rounded-full border border-[#cbd8e5] bg-white px-3 text-sm font-medium text-[#29445e] active:bg-[#edf5fb]"
              key={example}
              onClick={() => onChange(example)}
              type="button"
            >
              {example}
            </button>
          ))}
        </div>

        <button
          className="mt-5 min-h-12 w-full rounded-2xl bg-[#123d68] px-4 font-semibold text-white shadow-[0_8px_20px_rgba(18,61,104,0.18)] disabled:cursor-not-allowed disabled:opacity-40"
          disabled={!message.trim()}
          onClick={onSubmit}
          type="button"
        >
          比較替代方案
        </button>
      </section>
    </div>
  )
}
