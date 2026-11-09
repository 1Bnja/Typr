import { useEffect, useId, useRef, useState } from 'react'
import Button from '../../../components/button'
import ChevronDown from '../../../components/icons/chevron-down'
import { formatMonth, getCurrentMonth } from '../utils/records'

const months = Array.from({ length: 12 }, (_, index) => ({
  value: String(index + 1).padStart(2, '0'),
  label: new Intl.DateTimeFormat('en', { month: 'short', timeZone: 'UTC' }).format(new Date(Date.UTC(2020, index, 1))),
}))

const MonthPicker = ({ value, onChange }) => {
  const id = useId()
  const [open, setOpen] = useState(false)
  const [year, setYear] = useState(Number(value.slice(0, 4)))
  const root = useRef(null)
  const trigger = useRef(null)
  const currentMonth = getCurrentMonth()

  useEffect(() => {
    if (!open) return
    root.current.querySelector('[aria-pressed="true"]')?.focus()
    const closeOutside = (event) => {
      if (!root.current.contains(event.target)) setOpen(false)
    }
    document.addEventListener('pointerdown', closeOutside)
    return () => document.removeEventListener('pointerdown', closeOutside)
  }, [open])

  return (
    <div ref={root} className="select-field month-picker" onBlur={(event) => { if (!event.currentTarget.contains(event.relatedTarget)) setOpen(false) }}
      onKeyDown={(event) => { if (event.key === 'Escape') { setOpen(false); trigger.current.focus() } }}>
      <span id={`${id}-label`} className="select-label">Month</span>
      <Button ref={trigger} variant="secondary" className="select-trigger" aria-labelledby={`${id}-label ${id}-value`} aria-haspopup="dialog" aria-expanded={open} aria-controls={open ? `${id}-months` : undefined}
        onClick={() => { setYear(Number(value.slice(0, 4))); setOpen((current) => !current) }}>
        <span id={`${id}-value`}>{formatMonth(value)}</span>
        <ChevronDown className="select-chevron" />
      </Button>
      {open && (
        <div id={`${id}-months`} role="dialog" aria-label="Choose a month" className="month-picker-menu">
          <div className="month-picker-year">
            <Button variant="ghost" size="sm" aria-label="Previous year" disabled={year <= 1} onClick={() => setYear((current) => current - 1)}><ChevronDown className="month-picker-previous" /></Button>
            <span aria-live="polite">{year}</span>
            <Button variant="ghost" size="sm" aria-label="Next year" disabled={year >= Number(currentMonth.slice(0, 4))} onClick={() => setYear((current) => current + 1)}><ChevronDown className="month-picker-next" /></Button>
          </div>
          <div className="month-picker-grid">
            {months.map((month) => {
              const monthValue = `${String(year).padStart(4, '0')}-${month.value}`
              return <Button key={month.value} size="sm" variant={monthValue === value ? 'primary' : 'ghost'} aria-label={formatMonth(monthValue)} aria-pressed={monthValue === value} disabled={monthValue > currentMonth}
                onClick={() => { if (monthValue !== value) onChange(monthValue); setOpen(false); trigger.current.focus() }}>{month.label}</Button>
            })}
          </div>
        </div>
      )}
    </div>
  )
}

export default MonthPicker
