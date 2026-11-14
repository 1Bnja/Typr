import Button from '../../../components/button'
import { DIFFICULTIES, LANGUAGES } from '../constants'

const PracticeSetup = ({ language, difficulty, onLanguageChange, onDifficultyChange, onStart, isLoading, error }) => {
  const selectedDifficulty = DIFFICULTIES.find((option) => option.value === difficulty)
  const selectedLanguage = LANGUAGES.find((option) => option.value === language)

  return (
    <div className="practice-setup">
      <div className="practice-configuration">
        <fieldset disabled={isLoading}>
          <legend className="practice-field-label">Text language</legend>
          <div className="practice-languages">
            {LANGUAGES.map((option) => (
              <button
                key={option.value}
                type="button"
                className="practice-language"
                aria-pressed={language === option.value}
                onClick={() => onLanguageChange(option.value)}
              >
                {option.label}
              </button>
            ))}
          </div>
        </fieldset>

        <fieldset disabled={isLoading}>
          <legend className="practice-field-label">Difficulty</legend>
          <div className="practice-levels">
            {DIFFICULTIES.map((option, index) => (
              <button
                key={option.value}
                type="button"
                className="practice-level"
                aria-label={`${option.label} ${option.wordCount} words`}
                aria-pressed={difficulty === option.value}
                onClick={() => onDifficultyChange(option.value)}
              >
                <span className="practice-level-bars" aria-hidden="true">
                  {[0, 1, 2].map((bar) => <span key={bar} data-filled={bar <= index} />)}
                </span>
                <span className="practice-level-name">{option.label}</span>
                <span className="practice-level-count">{option.wordCount} words</span>
                <span className="practice-level-check" aria-hidden="true">
                  {difficulty === option.value && (
                    <svg viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="2">
                      <path d="m5 10 3 3 7-7" strokeLinecap="round" strokeLinejoin="round" />
                    </svg>
                  )}
                </span>
              </button>
            ))}
          </div>
        </fieldset>
      </div>

      <aside className="practice-preview" aria-labelledby="preview-title">
        <div className="practice-preview-heading">
          <h2 id="preview-title">Your practice text</h2>
          <span className="practice-word-count">{selectedDifficulty.wordCount} words</span>
        </div>
        <p className="practice-preview-bank">A phrase from the text bank will appear when you start.</p>
        <p className="practice-preview-description">{selectedDifficulty.description} The selection will match your chosen language and difficulty.</p>
        <div className="practice-preview-notes">
          <p>Your first character starts the timer.</p>
          <p>Use <kbd>Backspace</kbd> to correct a mistake.</p>
        </div>
      </aside>

      <div className="practice-setup-footer">
        <div>
          <p className="practice-selection">{selectedLanguage.label} <span>·</span> {selectedDifficulty.label}</p>
          <p className="practice-footer-note">Your pace. No time limit.</p>
        </div>
        <Button variant="primary" onClick={onStart} isLoading={isLoading} className="practice-start">
          {isLoading ? 'Preparing text…' : 'Start test'}
          {!isLoading && (
            <svg viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="1.75" aria-hidden="true">
              <path d="M4 10h12m-5-5 5 5-5 5" strokeLinecap="round" strokeLinejoin="round" />
            </svg>
          )}
        </Button>
        {error && <p role="alert" className="practice-error">{error}</p>}
      </div>
    </div>
  )
}

export default PracticeSetup
