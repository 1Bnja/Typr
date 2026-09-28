import { Routes, Route } from 'react-router-dom'
import Navbar from '../components/nav-bar'
import Login from '../features/auth/pages/login'
import { Home } from '../features/home'
import './app.css'

const App = () => {
  return (
    <>
    <div className="flex min-h-dvh flex-col">
      <Navbar />
      <main className="flex flex-1 flex-col">
      <Routes>
        <Route path="/" element={<Home />} />
        <Route path="/about" element={<div>About</div>} />
        <Route path="/contact" element={<div>Contact</div>} />
        <Route path="/login" element={<Login />} />
        <Route path="/register" element={<div>Register</div>} />
      </Routes>
      </main>
    </div>
    </>
  )
}

export default App
