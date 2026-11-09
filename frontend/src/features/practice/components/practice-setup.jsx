import Button from '../../../components/button'
import { DIFFICULTIES, LANGUAGES } from '../constants'

const optionClass = (isActive) =>
  [
    'rounded-xl border px-4 py-2 text-sm font-semibold transition-colors',
    'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-mint focus-visible:ring-offset-2 focus-visible:ring-offset-canvas',
    isActive
      ? 'border-[#18a98a] bg-mint/20 text-charcoal'
      : 'border-[#e1e2dc] bg-white text-neutral-600 hover:text-charcoal',
  ].join(' ')

const OptionGroup = ({ label, options, value, onChange }) => (
  <fieldset className="flex flex-col gap-3">
    <legend className="mb-3 text-sm font-semibold text-charcoal">{label}</legend>
    <div className="flex flex-wrap gap-2">
      {options.map((option) => (
        <button
          key={option.value}
          type="button"
          aria-pressed={value === option.value}
          className={optionClass(value === option.value)}
          onClick={() => onChange(option.value)}
        >
          {option.label}
        </button>
      ))}
    </div>
  </fieldset>
)

const PracticeSetup = ({ language, difficulty, onLanguageChange, onDifficultyChange, onStart, isLoading }) => {
  return (
    <div className="flex flex-col gap-8">
      <OptionGroup label="Language" options={LANGUAGES} value={language} onChange={onLanguageChange} />
      <OptionGroup label="Difficulty" options={DIFFICULTIES} value={difficulty} onChange={onDifficultyChange} />
      <Button variant="primary" onClick={onStart} isLoading={isLoading} className="self-start">
        Start test
      </Button>
    </div>
  )
}

export default PracticeSetup
