import { useEffect, useState } from 'react'

const ThemeToggle = ({ className }) => {
  const [dark, setDark] = useState(() => (
    document.documentElement.dataset.theme
      ? document.documentElement.dataset.theme === 'dark'
      : window.matchMedia('(prefers-color-scheme: dark)').matches
  ))

  useEffect(() => {
    const preference = window.matchMedia('(prefers-color-scheme: dark)')
    const sync = () => {
      if (!document.documentElement.dataset.theme) setDark(preference.matches)
    }
    preference.addEventListener('change', sync)
    return () => preference.removeEventListener('change', sync)
  }, [])

  const toggle = () => {
    const theme = dark ? 'light' : 'dark'
    document.documentElement.dataset.theme = theme
    setDark(!dark)
    try {
      localStorage.setItem('typr-theme', theme)
    } catch {
      // The selected theme still applies to this page.
    }
  }

  return (
    <button type="button" aria-label="Dark mode" aria-pressed={dark} title={dark ? 'Switch to light mode' : 'Switch to dark mode'}
      className={className} onClick={toggle}>
      <svg viewBox="0 0 24 24" className="h-5 w-5" fill="none" stroke="currentColor" strokeWidth="1.65" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
        {dark ? (
          <>
            <circle cx="12" cy="12" r="4" />
            <path d="M12 2v2m0 16v2M2 12h2m16 0h2M5 5l1.5 1.5m11 11L19 19M5 19l1.5-1.5m11-11L19 5" />
          </>
        ) : <path d="M20.8 14a9 9 0 0 1-10.8-10.8A9 9 0 1 0 20.8 14Z" />}
      </svg>
    </button>
  )
}

export default ThemeToggle
