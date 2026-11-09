import { memo, useCallback, useEffect, useLayoutEffect, useMemo, useRef } from 'react'

const getCharClass = (char, typedChar) => {
  if (typedChar === undefined) return 'practice-character--pending'
  return typedChar === char ? 'practice-character--correct' : 'practice-character--incorrect'
}

const TypingText = ({ text, typed, isFocused }) => {
  const windowRef = useRef(null)
  const textRef = useRef(null)
  const caretRef = useRef(null)
  const caretTrackRef = useRef(null)
  const indexRef = useRef(0)
  const previousRowRef = useRef(null)
  const idleTimerRef = useRef(null)
  const words = useMemo(() => Array.from(text.matchAll(/\S+/g), (match) => ({
    word: match[0], start: match.index,
  })), [text])

  const moveCaret = useCallback((smooth = true) => {
    const viewport = windowRef.current
    const paragraph = textRef.current
    const character = paragraph?.querySelector(`[data-index="${indexRef.current}"]`)
    if (!viewport || !character) return

    const textBounds = paragraph.getBoundingClientRect()
    const characterBounds = character.getBoundingClientRect()
    const style = getComputedStyle(paragraph)
    const lineHeight = parseFloat(style.lineHeight)
    const caretHeight = parseFloat(style.fontSize) * 1.2
    const x = characterBounds.left - textBounds.left
    const y = characterBounds.top - textBounds.top
    const maxScroll = Math.max(0, textBounds.height - viewport.getBoundingClientRect().height)
    // La línea activa se mantiene en el centro, dejando ver la siguiente.
    const scroll = Math.min(Math.max(0, y - lineHeight), maxScroll)
    const sameRow = previousRowRef.current !== null && Math.abs(previousRowRef.current - y) < 1

    viewport.style.setProperty('--caret-step-duration', smooth && sameRow ? '80ms' : '0ms')
    viewport.style.setProperty('--line-scroll-duration', smooth ? '160ms' : '0ms')
    paragraph.style.transform = `translate3d(0, ${-scroll}px, 0)`
    caretTrackRef.current.style.transform = `translate3d(0, ${y - scroll + (lineHeight - caretHeight) / 2}px, 0)`
    caretRef.current.style.transform = `translate3d(${Math.max(0, x - 1)}px, 0, 0)`
    viewport.dataset.ready = 'true'
    previousRowRef.current = y
  }, [])

  useLayoutEffect(() => {
    indexRef.current = Math.min(typed.length, text.length - 1)
    moveCaret()
    windowRef.current.dataset.moving = 'true'
    clearTimeout(idleTimerRef.current)
    idleTimerRef.current = setTimeout(() => {
      if (windowRef.current) windowRef.current.dataset.moving = 'false'
    }, 600)
  }, [typed.length, text, moveCaret])

  useEffect(() => {
    let active = true
    const observer = new ResizeObserver(() => moveCaret(false))
    observer.observe(windowRef.current)
    document.fonts.ready.then(() => { if (active) moveCaret(false) })
    return () => {
      active = false
      observer.disconnect()
      clearTimeout(idleTimerRef.current)
    }
  }, [moveCaret])

  const character = (char, index) => (
    <span key={index} data-index={index} className={`practice-character ${getCharClass(char, typed[index])}`}>
      {typed[index] ?? char}
    </span>
  )

  return (
    <div ref={windowRef} className="practice-text-window" data-focused={isFocused}>
      <p ref={textRef} id="practice-text" className="practice-text">
        {words.map(({ word, start }, wordIndex) => (
          <span key={start} className="practice-word">
            {word.split('').map((char, index) => character(char, start + index))}
            {wordIndex < words.length - 1 && character(' ', start + word.length)}
          </span>
        ))}
      </p>
      <span ref={caretTrackRef} className="practice-caret-track" aria-hidden="true">
        <span ref={caretRef} className="practice-caret" />
      </span>
    </div>
  )
}

export default memo(TypingText)
