import { useEffect, useRef, useState } from 'react'
import TypingText from '../../practice/components/typing-text'
import { applyRaceInput, raceInputValue } from '../utils/race-input'

// Teclas que moverían el cursor dentro del campo y desordenarían la comparación.
const BLOCKED_KEYS = ['ArrowLeft', 'ArrowRight', 'ArrowUp', 'ArrowDown', 'Home', 'End', 'Enter']

const RaceTyping = ({ content, initial, onInput, inputRef }) => {
  const [isFocused, setIsFocused] = useState(false)
  const textRef = useRef(null)
  const composingRef = useRef(false)
  const stateRef = useRef(initial)

  useEffect(() => {
    // Al montar, el campo parte del avance ya hecho (0, o lo retomado tras recargar).
    const value = raceInputValue(stateRef.current, content)
    inputRef.current.value = value
    textRef.current.updateInput(value)
    inputRef.current.focus()
  }, [content, inputRef])

  const handleChange = (event) => {
    // Las tildes se cuentan al confirmar el carácter, no mientras se componen.
    if (composingRef.current || event.nativeEvent.isComposing) return
    const next = applyRaceInput(stateRef.current, event.target.value.normalize('NFC'), content)
    const value = raceInputValue(next, content)
    // Lo que la regla no acepta se descarta también del campo.
    if (event.target.value !== value) event.target.value = value
    if (next === stateRef.current) return
    stateRef.current = next
    textRef.current.updateInput(value)
    onInput(next)
  }

  const handleKeyDown = (event) => {
    if (event.nativeEvent.isComposing) return
    if (BLOCKED_KEYS.includes(event.key)) event.preventDefault()
  }

  const moveCursorToEnd = (event) => {
    if (composingRef.current) return
    const input = event.target
    const end = input.value.length
    if (input.selectionStart !== end || input.selectionEnd !== end) input.setSelectionRange(end, end)
  }

  return (
    <div className="practice-typing-area">
      <TypingText ref={textRef} text={content} isFocused={isFocused} isActive={isFocused} />
      <textarea
        ref={inputRef}
        className="practice-input"
        aria-label="Type the text"
        aria-describedby="race-instructions practice-text"
        onChange={handleChange}
        onKeyDown={handleKeyDown}
        onPaste={(event) => event.preventDefault()}
        onDrop={(event) => event.preventDefault()}
        onSelect={moveCursorToEnd}
        onCompositionStart={() => { composingRef.current = true }}
        onCompositionEnd={(event) => {
          composingRef.current = false
          handleChange(event)
        }}
        onFocus={() => setIsFocused(true)}
        onBlur={() => setIsFocused(false)}
        autoComplete="off"
        autoCorrect="off"
        autoCapitalize="off"
        spellCheck={false}
      />
    </div>
  )
}

export default RaceTyping
