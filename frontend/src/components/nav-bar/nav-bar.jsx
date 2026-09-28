import Button from '../button/button'
import logo from '../../assets/logo.svg'
import { Link, useNavigate } from 'react-router-dom'
import './nav-bar.css'

const Navbar = () => {

  const navigate = useNavigate()

  const handleSignIn = () => {
    navigate('/login')
  }

  return (
    <nav className="grid grid-cols-3 items-center p-4 border-b border-gray-200">
      <div className="flex justify-start flex-row items-center gap-2">
        <img src={logo} alt="logo" className="w-10 h-10" />
        <p className="text-2xl font-extrabold">Typr</p>
      </div>

      <div>
      <ul className='flex flex-row gap-8 justify-center'>
        <li><Link to="/">Home</Link></li>
        <li><Link to="/about">About</Link></li>
        <li><Link to="/contact">Contact</Link></li>
      </ul>
      </div>
      
      <div className="flex flex-row gap-4 justify-end">
        <Button variant="streak">Try</Button>
        <Button variant="destructive" onClick={handleSignIn}>Sign in</Button>
      </div>
    </nav>
  )
}

export default Navbar
