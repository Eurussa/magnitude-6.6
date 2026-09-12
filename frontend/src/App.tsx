import { useEffect, useState } from 'react'
import { BrowserRouter, Navigate, Route, Routes, Link } from 'react-router-dom'
import { getTrip, replan, type Trip, type ReplanResponse } from './api/client'

function TripPage() {
  const [trip, setTrip] = useState<Trip | null>(null)
  const [message, setMessage] = useState('下午開始下大雨')
  const [result, setResult] = useState<ReplanResponse | null>(null)
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)
  useEffect(() => { getTrip().then(setTrip).catch(e => setError(String(e))) }, [])
  async function submit(event: React.FormEvent) {
    event.preventDefault()
    setLoading(true); setError(''); setResult(null)
    try { setResult(await replan(message)) }
    catch (e) { setError(String(e)) }
    finally { setLoading(false) }
  }
  return <main className="mx-auto max-w-5xl p-6 md:p-12">
    <header className="mb-10"><p className="text-teal-700 font-semibold">MAGNITUDE 6.6 / HACKATHON</p>
      <h1 className="text-4xl font-bold my-3">旅行有變，下一步不慌。</h1>
      <p className="text-slate-600">SmartTrip · 即時行程重排助手 / 初始化預覽</p></header>
    <section className="bg-white rounded-2xl p-6 shadow-sm"><h2 className="text-xl font-bold mb-4">Tokyo · 今日行程</h2>
      {!trip && !error && <p>正在載入行程…</p>}
      <ul className="space-y-4">{trip?.items.map(item => <li key={item.id} className="flex flex-wrap gap-4 border-b border-slate-100 pb-3">
        <time className="font-mono">{item.start_time}</time><span className="flex-1">{item.name} {item.booking && '🔒'} · {item.indoor ? '室內' : '戶外'}</span>
        <a className="text-teal-700 underline" href={`https://www.google.com/maps/search/?api=1&query=${item.latitude},${item.longitude}`} target="_blank" rel="noreferrer">Google Maps ↗</a>
      </li>)}</ul></section>
    <form onSubmit={submit} className="my-6 space-y-3"><label htmlFor="event" className="block font-semibold">發生了什麼事？</label>
      <textarea id="event" className="w-full rounded-xl border border-slate-300 bg-white p-4" value={message} onChange={e => setMessage(e.target.value)} maxLength={2000} required />
      <button className="rounded-xl bg-teal-800 px-6 py-3 text-white disabled:opacity-50" disabled={loading || !trip || !message.trim()}>{loading ? '處理中…' : '取得重排佔位方案'}</button>
    </form>
    {error && <p role="alert" className="text-red-700">{error}</p>}
    <div aria-live="polite">{result && <><p className="bg-amber-100 p-4 rounded-xl mb-4">{result.warnings.join(' ')}</p>
      <div className="grid gap-4 md:grid-cols-3">{result.plans.map(plan => <article key={plan.id} className="bg-white p-5 rounded-xl"><h2 className="font-bold">Plan {plan.id} · {plan.title}</h2><p className="mt-3 text-slate-600">{plan.explanation}</p></article>)}</div></>}</div>
  </main>
}
export default function App() {
  return <BrowserRouter><Routes><Route path="/" element={<Navigate to="/trip" replace />} /><Route path="/trip" element={<TripPage />} /><Route path="*" element={<main className="p-8">找不到頁面。<Link to="/trip">返回行程</Link></main>} /></Routes></BrowserRouter>
}
