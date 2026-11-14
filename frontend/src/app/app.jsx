import { useState } from 'react'
import { Routes, Route } from 'react-router-dom'
import Navbar from '../components/nav-bar'
import Login from '../features/auth/pages/login'
import { Home } from '../features/home'
import Texts from '../features/texts/pages/texts'
import { History, Leaderboard, Practice } from '../features/practice'
import { Room, Rooms } from '../features/rooms'
import './app.css'

const App = () => {
  const [focusMode, setFocusMode] = useState(false)
  return (
    <>
    <div className="flex min-h-dvh flex-col">
      <Navbar focusMode={focusMode} />
      <main className="flex flex-1 flex-col">
      <Routes>
        <Route path="/" element={<Home />} />
        <Route path="/about" element={<div>About</div>} />
        <Route path="/contact" element={<div>Contact</div>} />
        <Route path="/login" element={<Login />} />
        <Route path="/practice" element={<Practice focusMode={focusMode} onFocusChange={setFocusMode} />} />
        <Route path="/practice/history" element={<History />} />
        <Route path="/practice/leaderboard" element={<Leaderboard />} />
        <Route path="/register" element={<div>Register</div>} />
        <Route path="/rooms" element={<Rooms />} />
        <Route path="/rooms/:code" element={<Room onFocusChange={setFocusMode} />} />
        <Route path="/texts" element={<Texts />} />
      </Routes>
      </main>
    </div>
    </>
  )
}

export default App
