const getCharClass = (char, typedChar, isCurrent) => {
  if (typedChar === undefined) {
    return isCurrent ? 'text-charcoal border-b-2 border-charcoal' : 'text-neutral-400'
  }
  if (typedChar === char) return 'text-emerald-600'
  return 'text-red bg-red/15 rounded-sm'
}

const TypingText = ({ text, typed }) => {
  return (
    <p className="whitespace-pre-wrap break-words font-mono text-xl leading-relaxed sm:text-2xl">
      {text.split('').map((char, index) => (
        <span key={index} className={getCharClass(char, typed[index], index === typed.length)}>
          {char}
        </span>
      ))}
    </p>
  )
}

export default TypingText
