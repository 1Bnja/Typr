import { Link } from 'react-router-dom'
import './nav-bar.css'

const Navbar = () => {
  return (
    <nav className="bg-red-500 flex flex-row justify-between items-center p-4">
      <div>
        <h1>LOGO</h1>
      </div>
      <ul className='flex flex-row gap-2'>
        <li><Link to="/">Home</Link></li>
        <li><Link to="/about">About</Link></li>
        <li><Link to="/contact">Contact</Link></li>
        <li><Link to="/login">Sign in</Link></li>
      </ul>
    </nav>
  )
}

export default Navbar
