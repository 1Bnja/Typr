import { lazy, Suspense, useState } from 'react'
import { Navigate, Outlet, Routes, Route } from 'react-router-dom'
import Navbar from '../components/nav-bar'
import Login from '../features/auth/pages/login'
import { useAuth } from '../features/auth/context/auth-context'
import { Dashboard } from '../features/dashboard'
import { Home } from '../features/home'
import Texts from '../features/texts/pages/texts'
import { History, Leaderboard, Practice } from '../features/practice'
import { Room, Rooms } from '../features/rooms'
import './app.css'

// Recharts solo se descarga al abrir la analítica.
const Stats = lazy(() => import('../features/stats/pages/stats'))

function SessionBoundary() {
  const { status, retryValidation, signOut } = useAuth()
  if (status === 'loading') return <p role="status" className="p-8 text-center">Loading…</p>
  if (status === 'unavailable') return (
    <section className="space-y-4 p-8 text-center">
      <p role="alert">Could not verify your session. Please try again.</p>
      <button type="button" className="button button--primary" onClick={retryValidation}>Retry</button>{' '}
      <button type="button" className="button button--secondary" onClick={signOut}>Sign out</button>
    </section>
  )
  return <Outlet />
}

function Index() {
  const { status } = useAuth()
  return status === 'authenticated' ? <Navigate to="/profile" replace /> : <Home />
}

function ProfileBoundary() {
  const { status } = useAuth()
  return status === 'authenticated' ? <Outlet /> : <Navigate to="/login" replace />
}

const App = () => {
  const [focusMode, setFocusMode] = useState(false)
  return (
    <>
    <div className="flex min-h-dvh flex-col">
      <Navbar focusMode={focusMode} />
      <main className="flex flex-1 flex-col">
      <Routes>
        <Route path="/about" element={<div>About</div>} />
        <Route path="/contact" element={<div>Contact</div>} />
        <Route path="/login" element={<Login />} />
        <Route path="/register" element={<div>Register</div>} />
        <Route element={<SessionBoundary />}>
          <Route index element={<Index />} />
          <Route element={<ProfileBoundary />}>
            <Route path="/profile" element={<Dashboard />} />
            <Route path="/dashboard" element={<Navigate to="/profile" replace />} />
          </Route>
          <Route path="/practice" element={<Practice focusMode={focusMode} onFocusChange={setFocusMode} />} />
          <Route path="/practice/history" element={<History />} />
          <Route path="/practice/leaderboard" element={<Leaderboard />} />
          <Route path="/practice/stats" element={<Suspense fallback={<p className="p-8 text-center">Loading…</p>}><Stats /></Suspense>} />
          <Route path="/rooms" element={<Rooms />} />
          <Route path="/rooms/:code" element={<Room onFocusChange={setFocusMode} />} />
          <Route path="/texts" element={<Texts />} />
        </Route>
      </Routes>
      </main>
    </div>
    </>
  )
}

export default App
