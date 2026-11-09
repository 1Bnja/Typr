import { memo, useCallback, useImperativeHandle, useLayoutEffect, useMemo, useRef } from 'react'
import { gsap } from 'gsap'

const TypingText = ({ ref, text, isFocused, isActive }) => {
  const windowRef = useRef(null)
  const textRef = useRef(null)
  const layerRef = useRef(null)
  const caretRef = useRef(null)
  const lettersRef = useRef([])
  const inputRef = useRef('')
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
    const position = layout?.positions[Math.min(inputRef.current.length, text.length - 1)]
    if (!position || !animations) return

    const animate = smooth && !motionRef.current.matches
    const move = (animation, value) => {
      if (animate) animation(value)
      else animation(value, value).progress(1).pause()
    }
    const y = position.y + layout.caretInset
    const scroll = Math.min(Math.max(0, position.y - layout.lineHeight), layout.maxScroll)

    move(animations.x, position.x)
    if (!animate || y !== targetRef.current.y) move(animations.y, y)
    if (!animate || scroll !== targetRef.current.scroll) move(animations.scroll, -scroll)
    targetRef.current = { y, scroll }
    windowRef.current.dataset.ready = 'true'
  }, [text.length])

  const updateInput = useCallback((value) => {
    const previous = inputRef.current
    if (value === previous) return
    let start = 0
    while (start < previous.length && start < value.length && previous[start] === value[start]) start++
    // React conserva la estructura; solo cambiamos las letras afectadas por la tecla.
    for (let i = start; i < Math.max(previous.length, value.length); i++) {
      const letter = lettersRef.current[i]
      if (!letter) break
      const char = value[i]
      const state = char === undefined ? 'pending' : char === text[i] ? 'correct' : 'incorrect'
      letter.textContent = char ?? text[i]
      letter.className = `practice-character practice-character--${state}`
    }
    inputRef.current = value
    moveCaret()
  }, [text, moveCaret])

  useImperativeHandle(ref, () => ({ updateInput }), [updateInput])

  const measureLayout = useCallback(() => {
    const paragraph = textRef.current
    const bounds = paragraph.getBoundingClientRect()
    const style = getComputedStyle(paragraph)
    const lineHeight = parseFloat(style.lineHeight)
    // Las medidas se guardan al montar o redimensionar, nunca al escribir.
    layoutRef.current = {
      lineHeight,
      caretInset: (lineHeight - parseFloat(style.fontSize) * 1.2) / 2,
      maxScroll: Math.max(0, bounds.height - windowRef.current.getBoundingClientRect().height),
      positions: lettersRef.current.map((letter) => {
        const rect = letter.getBoundingClientRect()
        return { x: Math.max(0, rect.left - bounds.left - 1), y: rect.top - bounds.top }
      }),
    }
    moveCaret(false)
  }, [moveCaret])

  useLayoutEffect(() => {
    let active = true
    lettersRef.current = Array.from(textRef.current.querySelectorAll('[data-index]'))
    inputRef.current = ''
    lettersRef.current.forEach((letter, index) => {
      letter.textContent = text[index]
      letter.className = 'practice-character practice-character--pending'
    })
    const animations = {
      x: gsap.quickTo(caretRef.current, 'x', { duration: 0.1, ease: 'power2.out' }),
      y: gsap.quickTo(caretRef.current, 'y', { duration: 0.1, ease: 'power2.out' }),
      scroll: gsap.quickTo(layerRef.current, 'y', { duration: 0.125, ease: 'power2.out' }),
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
      resizeObserver.disconnect()
      motion.removeEventListener('change', measureLayout)
      Object.values(animations).forEach((animation) => animation.tween.kill())
      animationsRef.current = null
    }
  }, [text, measureLayout])

  return (
    <div ref={windowRef} className="practice-text-window" data-focused={isFocused} data-active={isActive}>
      <div ref={layerRef} className="practice-text-layer">
        <p ref={textRef} id="practice-text" className="practice-text">
          {words.map(({ word, start }) => (
            <span key={start} className="practice-word">
              {word.split('').map((_, index) => (
                <span key={index} data-index={start + index} className="practice-character" />
              ))}
            </span>
          ))}
        </p>
        <span ref={caretRef} className="practice-caret" aria-hidden="true" />
      </div>
    </div>
  )
}

export default memo(TypingText)
