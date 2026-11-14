import { useEffect, useId, useRef, useState } from 'react'
import { NavLink } from 'react-router-dom'
import ChevronDown from '../icons/chevron-down'

const practiceLinks = [
  { to: '/practice', label: 'Start a test' },
  { to: '/practice/history', label: 'History' },
  { to: '/practice/leaderboard', label: 'Monthly leaderboard' },
]

const PracticeMenu = ({ className, mobile = false, onNavigate }) => {
  const id = useId()
  const [open, setOpen] = useState(false)
  const root = useRef(null)
  const trigger = useRef(null)

  useEffect(() => {
    if (!open) return
    root.current.querySelector('a')?.focus()
    const closeOutside = (event) => {
      if (!root.current.contains(event.target)) setOpen(false)
    }
    const closeOnEscape = (event) => {
      if (event.key !== 'Escape') return
      event.stopPropagation()
      setOpen(false)
      trigger.current.focus()
    }
    const closeOnResize = () => setOpen(false)
    const breakpoint = window.matchMedia('(min-width: 768px)')
    document.addEventListener('pointerdown', closeOutside)
    root.current.addEventListener('keydown', closeOnEscape)
    breakpoint.addEventListener('change', closeOnResize)
    const element = root.current
    return () => {
      document.removeEventListener('pointerdown', closeOutside)
      element.removeEventListener('keydown', closeOnEscape)
      breakpoint.removeEventListener('change', closeOnResize)
    }
  }, [open])

  const moveFocus = (event) => {
    const links = [...root.current.querySelectorAll('a')]
    const index = links.indexOf(document.activeElement)
    let next
    if (event.key === 'ArrowDown') next = (index + 1) % links.length
    if (event.key === 'ArrowUp') next = (index - 1 + links.length) % links.length
    if (event.key === 'Home') next = 0
    if (event.key === 'End') next = links.length - 1
    if (next !== undefined) {
      event.preventDefault()
      links[next].focus()
    }
  }

  return (
    <div ref={root} className="relative" onBlur={(event) => { if (!event.currentTarget.contains(event.relatedTarget)) setOpen(false) }}>
      <button ref={trigger} type="button" className={`${className} ${mobile ? 'w-full' : 'inline-flex items-center gap-1'}`} aria-expanded={open} aria-controls={open ? id : undefined}
        onClick={() => setOpen((current) => !current)} onKeyDown={(event) => { if (event.key === 'ArrowDown') { event.preventDefault(); setOpen(true) } }}>
        Practice
        <ChevronDown className={`h-4 w-4 text-muted motion-safe:transition-transform ${open ? 'rotate-180' : ''}`} />
      </button>
      {open && (
        <ul id={id} aria-label="Practice" className={mobile
          ? 'ml-3 mt-1 space-y-1 border-l border-divider pl-3'
          : 'absolute left-0 top-full z-50 mt-2 w-56 rounded-xl border border-divider bg-surface p-1 shadow-[0_3px_0_var(--line)]'} onKeyDown={moveFocus}>
          {practiceLinks.map((link) => (
            <li key={link.to}>
              <NavLink to={link.to} end onClick={() => { setOpen(false); onNavigate?.() }}
                className={({ isActive }) => `block rounded-lg px-3 py-3 text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-[#18a98a] ${isActive ? 'bg-mint/10 font-semibold text-accent' : 'text-charcoal hover:bg-subtle'}`}>
                {link.label}
              </NavLink>
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}

export default PracticeMenu
