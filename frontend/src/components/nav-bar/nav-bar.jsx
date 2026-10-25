import { useEffect, useRef, useState } from 'react'
import { Link, NavLink, useLocation, useNavigate } from 'react-router-dom'
import Button from '../button/button'
import logo from '../../assets/logo.svg'
import { useAuth } from '../../features/auth/context/auth-context'

const links = [
  { to: '/', label: 'Home' },
  { to: '/about', label: 'About' },
  { to: '/contact', label: 'Contact' },
]

const focusRing =
  'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-mint focus-visible:ring-offset-2 focus-visible:ring-offset-canvas'

const desktopLinkClass = ({ isActive }) =>
  [
    'relative rounded-md px-3 py-2 text-sm font-medium transition-colors duration-200',
    'after:absolute after:inset-x-3 after:bottom-0.5 after:h-0.5 after:origin-left after:rounded-full after:bg-mint after:transition-transform after:duration-300',
    focusRing,
    isActive
      ? 'text-charcoal after:scale-x-100'
      : 'text-neutral-600 after:scale-x-0 hover:text-charcoal hover:after:scale-x-100',
  ].join(' ')

const mobileLinkClass = ({ isActive }) =>
  [
    'flex items-center justify-between rounded-lg px-3 py-3 text-base font-medium transition-colors',
    focusRing,
    isActive ? 'bg-mint/10 text-charcoal' : 'text-neutral-700 hover:bg-neutral-100 hover:text-charcoal',
  ].join(' ')

const getInitials = (name = '') => name.trim().slice(0, 2).toUpperCase() || '?'

const Avatar = ({ name, className = '' }) => (
  <span
    aria-hidden="true"
    className={`inline-flex shrink-0 items-center justify-center rounded-full bg-mint/20 font-semibold text-charcoal ring-1 ring-mint/40 ${className}`}
  >
    {getInitials(name)}
  </span>
)

const ChevronDown = ({ className = '' }) => (
  <svg viewBox="0 0 20 20" fill="currentColor" aria-hidden="true" className={className}>
    <path
      fillRule="evenodd"
      d="M5.23 7.21a.75.75 0 0 1 1.06.02L10 11.17l3.71-3.94a.75.75 0 1 1 1.08 1.04l-4.25 4.5a.75.75 0 0 1-1.08 0l-4.25-4.5a.75.75 0 0 1 .02-1.06Z"
      clipRule="evenodd"
    />
  </svg>
)

const MenuIcon = ({ open }) => (
  <span className="relative block h-4 w-5" aria-hidden="true">
    <span
      className={`absolute left-0 top-0 h-0.5 w-5 rounded-full bg-current transition-transform duration-300 ${open ? 'translate-y-[7px] rotate-45' : ''}`}
    />
    <span
      className={`absolute left-0 top-[7px] h-0.5 w-5 rounded-full bg-current transition-opacity duration-200 ${open ? 'opacity-0' : ''}`}
    />
    <span
      className={`absolute left-0 top-[14px] h-0.5 w-5 rounded-full bg-current transition-transform duration-300 ${open ? '-translate-y-[7px] -rotate-45' : ''}`}
    />
  </span>
)

const Navbar = () => {
  const navigate = useNavigate()
  const { pathname } = useLocation()
  const { user, signOut } = useAuth()

  const [open, setOpen] = useState(false)
  const [userMenuOpen, setUserMenuOpen] = useState(false)
  const [scrolled, setScrolled] = useState(false)
  const [lastPathname, setLastPathname] = useState(pathname)

  const toggleRef = useRef(null)
  const userMenuRef = useRef(null)

  const close = () => setOpen(false)

  // Sombra / blur al hacer scroll
  useEffect(() => {
    const onScroll = () => setScrolled(window.scrollY > 8)
    onScroll()
    window.addEventListener('scroll', onScroll, { passive: true })
    return () => window.removeEventListener('scroll', onScroll)
  }, [])

  // Cierra los menús al cambiar de ruta (incluye atrás/adelante del navegador)
  if (pathname !== lastPathname) {
    setLastPathname(pathname)
    setOpen(false)
    setUserMenuOpen(false)
  }

  // Cierra el menú móvil al pasar a escritorio
  useEffect(() => {
    const mq = window.matchMedia('(min-width: 768px)')
    const onChange = (event) => {
      if (event.matches) setOpen(false)
    }
    mq.addEventListener('change', onChange)
    return () => mq.removeEventListener('change', onChange)
  }, [])

  // Bloquea el scroll del body con el menú móvil abierto
  useEffect(() => {
    if (!open) return
    const { overflow } = document.body.style
    document.body.style.overflow = 'hidden'
    return () => {
      document.body.style.overflow = overflow
    }
  }, [open])

  // Escape cierra cualquier menú abierto
  useEffect(() => {
    if (!open && !userMenuOpen) return
    const onKey = (event) => {
      if (event.key !== 'Escape') return
      if (open) {
        setOpen(false)
        toggleRef.current?.focus()
      }
      setUserMenuOpen(false)
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [open, userMenuOpen])

  // Click fuera cierra el menú de usuario
  useEffect(() => {
    if (!userMenuOpen) return
    const onPointerDown = (event) => {
      if (!userMenuRef.current?.contains(event.target)) setUserMenuOpen(false)
    }
    document.addEventListener('pointerdown', onPointerDown)
    return () => document.removeEventListener('pointerdown', onPointerDown)
  }, [userMenuOpen])

  const handleSignOut = () => {
    setUserMenuOpen(false)
    setOpen(false)
    signOut()
  }

  const elevated = scrolled || open

  return (
    <>
      <header
        className={[
          'sticky top-0 z-40 border-b transition-[background-color,border-color,box-shadow] duration-300',
          elevated
            ? 'border-neutral-200/80 bg-canvas/80 shadow-sm backdrop-blur-md'
            : 'border-transparent bg-canvas',
        ].join(' ')}
      >
        <nav
          aria-label="Principal"
          className="mx-auto flex h-16 max-w-6xl items-center justify-between gap-4 px-4 sm:px-6 md:grid md:grid-cols-[1fr_auto_1fr]"
        >
          {/* Logo */}
          <Link
            to="/"
            onClick={close}
            className={`flex items-center gap-2 justify-self-start rounded-lg ${focusRing}`}
          >
            <img src={logo} alt="" className="h-9 w-9" />
            <span className="text-xl font-extrabold tracking-tight text-charcoal">Typr</span>
          </Link>

          {/* Links escritorio (centrados) */}
          <ul className="hidden items-center gap-1 md:flex">
            {links.map((link) => (
              <li key={link.to}>
                <NavLink to={link.to} className={desktopLinkClass} end={link.to === '/'}>
                  {link.label}
                </NavLink>
              </li>
            ))}
          </ul>

          {/* Acciones escritorio */}
          <div className="hidden items-center gap-2 justify-self-end md:flex">
            {user ? (
              <div className="relative" ref={userMenuRef}>
                <button
                  type="button"
                  aria-expanded={userMenuOpen}
                  aria-controls="user-menu"
                  onClick={() => setUserMenuOpen((value) => !value)}
                  className={`flex items-center gap-2 rounded-full border border-neutral-200 py-1 pl-1 pr-3 text-sm font-medium text-charcoal transition-colors hover:bg-neutral-100 ${focusRing}`}
                >
                  <Avatar name={user.username} className="h-7 w-7 text-xs" />
                  <span className="max-w-32 truncate">{user.username}</span>
                  <ChevronDown
                    className={`h-4 w-4 text-neutral-500 transition-transform duration-200 ${userMenuOpen ? 'rotate-180' : ''}`}
                  />
                </button>

                <div
                  id="user-menu"
                  className={[
                    'absolute right-0 mt-2 w-56 origin-top-right rounded-xl border border-neutral-200 bg-canvas p-1.5 shadow-lg transition-all duration-200',
                    userMenuOpen ? 'visible scale-100 opacity-100' : 'invisible scale-95 opacity-0',
                  ].join(' ')}
                >
                  <div className="px-3 py-2">
                    <p className="text-xs text-neutral-500">Sesión iniciada como</p>
                    <p className="truncate text-sm font-semibold text-charcoal">{user.username}</p>
                  </div>
                  <div className="my-1 h-px bg-neutral-200" />
                  <button
                    type="button"
                    onClick={handleSignOut}
                    className={`w-full rounded-lg px-3 py-2 text-left text-sm font-medium text-neutral-700 transition-colors hover:bg-neutral-100 hover:text-charcoal ${focusRing}`}
                  >
                    Sign out
                  </button>
                </div>
              </div>
            ) : (
              <>
                <Button variant="secondary" size="sm" onClick={() => navigate('/login')}>
                  Sign in
                </Button>
                <Button variant="streak" size="sm">Try</Button>
              </>
            )}
          </div>

          {/* Toggle móvil */}
          <button
            ref={toggleRef}
            type="button"
            className={`inline-flex h-10 w-10 items-center justify-center rounded-lg text-charcoal transition-colors hover:bg-neutral-100 md:hidden ${focusRing}`}
            aria-expanded={open}
            aria-controls="mobile-menu"
            aria-label={open ? 'Cerrar menú' : 'Abrir menú'}
            onClick={() => setOpen((value) => !value)}
          >
            <MenuIcon open={open} />
          </button>
        </nav>
      </header>

      {/* Fondo oscurecido (móvil) */}
      <div
        aria-hidden="true"
        onClick={close}
        className={`fixed inset-0 top-16 z-30 bg-charcoal/20 backdrop-blur-sm transition-opacity duration-300 md:hidden ${open ? 'opacity-100' : 'pointer-events-none opacity-0'}`}
      />

      {/* Panel móvil */}
      <div
        id="mobile-menu"
        className={[
          'fixed inset-x-0 top-16 z-30 max-h-[calc(100dvh-4rem)] overflow-y-auto border-b border-neutral-200 bg-canvas px-4 pb-6 pt-4 shadow-lg transition-all duration-300 ease-out sm:px-6 md:hidden',
          open ? 'visible translate-y-0 opacity-100' : 'invisible -translate-y-2 opacity-0',
        ].join(' ')}
      >
        {user && (
          <div className="mb-4 flex items-center gap-3 rounded-xl border border-neutral-200 p-3">
            <Avatar name={user.username} className="h-10 w-10 text-sm" />
            <div className="min-w-0">
              <p className="text-xs text-neutral-500">Sesión iniciada como</p>
              <p className="truncate text-sm font-semibold text-charcoal">{user.username}</p>
            </div>
          </div>
        )}

        <ul className="flex flex-col gap-1">
          {links.map((link) => (
            <li key={link.to}>
              <NavLink to={link.to} className={mobileLinkClass} end={link.to === '/'} onClick={close}>
                {link.label}
              </NavLink>
            </li>
          ))}
        </ul>

        <div className="mt-6 border-t border-neutral-200 pt-4">
          {user ? (
            <div className="flex flex-col">
              <Button variant="ghost" onClick={handleSignOut}>Sign out</Button>
            </div>
          ) : (
            <div className="grid grid-cols-2 gap-2">
              <Button variant="secondary" onClick={() => { navigate('/login'); close() }}>
                Sign in
              </Button>
              <Button variant="streak" onClick={close}>Try</Button>
            </div>
          )}
        </div>
      </div>
    </>
  )
}

export default Navbar