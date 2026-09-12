import { BrowserRouter, Link, Navigate, Route, Routes } from 'react-router-dom'
import { TripPage } from './pages/TripPage'

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<Navigate to="/trip" replace />} />
        <Route path="/trip" element={<TripPage />} />
        <Route
          path="*"
          element={
            <main className="mx-auto flex min-h-dvh w-full max-w-[414px] flex-col items-center justify-center bg-white px-6 text-center">
              <h1 className="text-2xl font-bold text-[#10234a]">找不到這個頁面</h1>
              <Link className="mt-5 min-h-11 rounded-xl bg-[#123d68] px-5 py-3 font-semibold text-white" to="/trip">
                返回行程
              </Link>
            </main>
          }
        />
      </Routes>
    </BrowserRouter>
  )
}
