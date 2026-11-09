import { memo, useCallback, useLayoutEffect, useMemo, useRef } from 'react'
import { createAnimatable } from 'animejs/animatable'

const TypingWord = memo(({ word, start, input }) => (
  <span className="practice-word">
    {word.split('').map((char, index) => {
      const typedChar = input[index]
      const state = typedChar === undefined ? 'pending' : typedChar === char ? 'correct' : 'incorrect'
      return <span key={index} data-index={start + index} className={`practice-character practice-character--${state}`}>{typedChar ?? char}</span>
    })}
  </span>
))

const TypingText = ({ text, typed, isFocused, isActive }) => {
  const windowRef = useRef(null)
  const textRef = useRef(null)
  const caretRef = useRef(null)
  const caretTrackRef = useRef(null)
  const indexRef = useRef(0)
  const frameRef = useRef(null)
  const layoutRef = useRef(null)
  const animationsRef = useRef(null)
  const motionRef = useRef(null)
  const targetRef = useRef({ y: null, scroll: null })
  const words = useMemo(() => Array.from(text.matchAll(/\S+ */g), (match) => ({
    word: match[0], start: match.index,
  })), [text])

  const moveCaret = useCallback((smooth = true) => {
    const layout = layoutRef.current
    const animations = animationsRef.current
    const position = layout?.positions[indexRef.current]
    if (!position || !animations) return

    const animate = smooth && !motionRef.current.matches
    const duration = animate ? 100 : 0
    const y = position.y + layout.caretInset
    const scroll = Math.min(Math.max(0, position.y - layout.lineHeight), layout.maxScroll)

    animations.caret.x(position.x, duration)
    if (!animate || y !== targetRef.current.y) animations.caret.y(y, duration)
    // El texto y el soporte del cursor comparten el desplazamiento de línea.
    if (!animate || scroll !== targetRef.current.scroll) {
      animations.text.y(-scroll, animate ? 125 : 0)
      animations.track.y(-scroll, animate ? 125 : 0)
    }
    targetRef.current = { y, scroll }
    windowRef.current.dataset.ready = 'true'
  }, [])

  const measureLayout = useCallback(() => {
    const paragraph = textRef.current
    const bounds = paragraph.getBoundingClientRect()
    const style = getComputedStyle(paragraph)
    const lineHeight = parseFloat(style.lineHeight)
    // Las medidas se calculan al montar o redimensionar, fuera de cada pulsación.
    layoutRef.current = {
      lineHeight,
      caretInset: (lineHeight - parseFloat(style.fontSize) * 1.2) / 2,
      maxScroll: Math.max(0, bounds.height - windowRef.current.getBoundingClientRect().height),
      positions: Array.from(paragraph.querySelectorAll('[data-index]'), (letter) => {
        const rect = letter.getBoundingClientRect()
        return { x: Math.max(0, rect.left - bounds.left - 1), y: rect.top - bounds.top }
      }),
    }
    moveCaret(false)
  }, [moveCaret])

  useLayoutEffect(() => {
    let active = true
    const animations = {
      caret: createAnimatable(caretRef.current, { x: 100, y: 100, ease: 'inOut(1.25)' }),
      text: createAnimatable(textRef.current, { y: 125, ease: 'out(2)' }),
      track: createAnimatable(caretTrackRef.current, { y: 125, ease: 'out(2)' }),
    }
    animationsRef.current = animations
    const motion = window.matchMedia('(prefers-reduced-motion: reduce)')
    motionRef.current = motion
    const resizeObserver = new ResizeObserver(measureLayout)
    resizeObserver.observe(windowRef.current)
    motion.addEventListener('change', measureLayout)
    measureLayout()
    document.fonts.ready.then(() => { if (active) measureLayout() })
    return () => {
      active = false
      cancelAnimationFrame(frameRef.current)
      frameRef.current = null
      resizeObserver.disconnect()
      motion.removeEventListener('change', measureLayout)
      Object.values(animations).forEach((animation) => animation.revert())
      animationsRef.current = null
    }
  }, [text, measureLayout])

  useLayoutEffect(() => {
    indexRef.current = Math.min(typed.length, text.length - 1)
    if (frameRef.current !== null) return
    frameRef.current = requestAnimationFrame(() => {
      frameRef.current = null
      moveCaret()
    })
  }, [typed.length, text, moveCaret])

  return (
    <div ref={windowRef} className="practice-text-window" data-focused={isFocused} data-active={isActive}>
      <p ref={textRef} id="practice-text" className="practice-text">
        {words.map(({ word, start }) => <TypingWord key={start} word={word} start={start} input={typed.slice(start, start + word.length)} />)}
      </p>
      <span ref={caretTrackRef} className="practice-caret-track" aria-hidden="true">
        <span ref={caretRef} className="practice-caret" />
      </span>
    </div>
  )
}

export default memo(TypingText)
