import { NavLink } from 'react-router-dom'

const PracticeNav = () => (
  <nav className="practice-nav" aria-label="Practice navigation">
    <NavLink to="/practice" end>Practice</NavLink>
    <NavLink to="/practice/history">History</NavLink>
    <NavLink to="/practice/leaderboard">Monthly leaderboard</NavLink>
  </nav>
)

export default PracticeNav
