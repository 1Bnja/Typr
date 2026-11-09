import Button from '../../../components/button'
import Stat from './stat'
import { formatTime } from '../utils/metrics'

const saveMessages = {
  saving: 'Saving your match…',
  saved: 'Match saved in your history.',
  error: 'We could not save this match.',
  skipped: 'Test complete. You can retry these words or generate a new set.',
}

const TestResults = ({ result, saveStatus, onRetry, onNewText, onChangeSettings, isLoading, error }) => {
  const isSaving = saveStatus === 'saving'
  return (
    <div className="practice-results">
      <div className="practice-results-stats">
        <Stat label="PPM" value={result.ppm} large />
        <Stat label="Accuracy" value={`${result.precisionPct}%`} large />
        <Stat label="Score" value={result.score} large />
        <Stat label="Time" value={formatTime(result.timeMs)} large />
      </div>
      <p className="practice-results-explanation">
        Speed uses five characters per word. Accuracy includes corrected mistakes.
      </p>
      {saveMessages[saveStatus] && (
        <p role="status" className={`practice-result-status ${saveStatus === 'error' ? 'practice-error' : ''}`}>
          {saveMessages[saveStatus]}
        </p>
      )}

      {error && <p role="alert" className="practice-error">{error}</p>}

      <div className="practice-result-actions">
        <Button variant="primary" onClick={onNewText} isLoading={isLoading} disabled={isSaving}>
          {isLoading ? 'Preparing text…' : 'New text'}
        </Button>
        <Button variant="secondary" onClick={onRetry} disabled={isLoading || isSaving}>
          Retry same text
        </Button>
        <Button variant="ghost" onClick={onChangeSettings} disabled={isLoading || isSaving}>
          Change settings
        </Button>
      </div>
    </div>
  )
}

export default TestResults
