import { useEffect, useRef } from 'react'

const getCharClass = (char, typedChar, isCurrent) => {
  if (typedChar === undefined) {
    return isCurrent ? 'practice-character--current' : 'practice-character--pending'
  }
  return typedChar === char ? 'practice-character--correct' : 'practice-character--incorrect'
}

const TypingText = ({ text, typed }) => {
  const currentRef = useRef(null)

  useEffect(() => {
    if (typed.length > 0) currentRef.current?.scrollIntoView({ block: 'nearest' })
  }, [typed.length])

  return (
    <p id="practice-text" className="practice-text">
      {text.split('').map((char, index) => (
        <span
          key={index}
          ref={index === typed.length ? currentRef : null}
          className={getCharClass(char, typed[index], index === typed.length)}
        >
          {typed[index] ?? char}
        </span>
      ))}
    </p>
  )
}

export default TypingText
