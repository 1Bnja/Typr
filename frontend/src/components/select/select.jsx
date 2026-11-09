import { useEffect, useId, useRef, useState } from 'react'
import Button from '../button'
import ChevronDown from '../icons/chevron-down'
import './select.css'

const Select = ({ label, value, options, onChange }) => {
  const id = useId()
  const [open, setOpen] = useState(false)
  const root = useRef(null)
  const trigger = useRef(null)
  const items = useRef([])
  const selected = options.findIndex((option) => option.value === value)

  useEffect(() => {
    if (!open) return
    items.current[Math.max(0, selected)]?.focus()
    const closeOutside = (event) => {
      if (!root.current.contains(event.target)) setOpen(false)
    }
    document.addEventListener('pointerdown', closeOutside)
    return () => document.removeEventListener('pointerdown', closeOutside)
  }, [open, selected])

  const handleKeys = (event) => {
    if (event.key === 'Escape') {
      event.preventDefault()
      setOpen(false)
      trigger.current.focus()
      return
    }
    const index = items.current.indexOf(document.activeElement)
    let next
    if (event.key === 'ArrowDown') next = (index + 1) % options.length
    if (event.key === 'ArrowUp') next = (index - 1 + options.length) % options.length
    if (event.key === 'Home') next = 0
    if (event.key === 'End') next = options.length - 1
    if (event.key.length === 1 && event.key !== ' ') {
      next = options.findIndex((option, position) => position > index && option.label.toLowerCase().startsWith(event.key.toLowerCase()))
      if (next === -1) next = options.findIndex((option) => option.label.toLowerCase().startsWith(event.key.toLowerCase()))
    }
    if (next !== undefined && next >= 0) {
      event.preventDefault()
      items.current[next]?.focus()
    }
  }

  return (
    <div ref={root} className="select-field" onBlur={(event) => { if (!event.currentTarget.contains(event.relatedTarget)) setOpen(false) }}>
      <span id={`${id}-label`} className="select-label">{label}</span>
      <Button ref={trigger} variant="secondary" className="select-trigger" aria-labelledby={`${id}-label ${id}-value`} aria-haspopup="listbox" aria-expanded={open} aria-controls={open ? `${id}-options` : undefined}
        onClick={() => setOpen((current) => !current)} onKeyDown={(event) => { if (event.key === 'ArrowDown' || event.key === 'ArrowUp') { event.preventDefault(); setOpen(true) } }}>
        <span id={`${id}-value`}>{options[selected]?.label}</span>
        <ChevronDown className="select-chevron" />
      </Button>
      {open && (
        <div id={`${id}-options`} role="listbox" aria-labelledby={`${id}-label`} className="select-options styled-scrollbar" onKeyDown={handleKeys}>
          {options.map((option, index) => (
            <button key={option.value} ref={(element) => { items.current[index] = element }} type="button" role="option" aria-selected={option.value === value} tabIndex={-1}
              onClick={() => { if (option.value !== value) onChange(option.value); setOpen(false); trigger.current.focus() }}>
              <span>{option.label}</span>
              <span className="select-indicator" aria-hidden="true" />
            </button>
          ))}
        </div>
      )}
    </div>
  )
}

export default Select
