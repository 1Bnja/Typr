import { useRef } from 'react'
import Button from '../../../components/button'
import Stat from './stat'
import SpeedChart from './speed-chart'
import { formatTime, getSpeedUnit } from '../utils/metrics'

const saveMessages = {
  saving: 'Saving your match…',
  saved: 'Match saved in your history.',
  error: 'We could not confirm that this match was saved. You can retry without taking the test again.',
}

const TestResults = ({ result, language, saveStatus, onRetrySave, onNewText, onChangeSettings, isLoading, error }) => {
  const saveFeedback = useRef(null)
  const isSaving = saveStatus === 'saving'
  return (
    <div className="practice-results">
      <div className="practice-results-stats">
        <Stat label={getSpeedUnit(language)} value={result.ppm} large />
        <Stat label="Accuracy" value={`${result.precisionPct}%`} large />
        <Stat label="Score" value={result.score} large />
        <Stat label="Time" value={formatTime(result.timeMs)} large />
      </div>
      <p className="practice-results-explanation">
        Speed uses five characters per word. Accuracy includes corrected mistakes.
      </p>
      {result.speedHistory?.length > 0 && (
        <SpeedChart samples={result.speedHistory} average={result.ppm} language={language} />
      )}
      {saveMessages[saveStatus] && (
        <p ref={saveFeedback} tabIndex={-1} role="status" className={`practice-result-status ${saveStatus === 'error' ? 'practice-error' : ''}`}>
          {saveMessages[saveStatus]}
        </p>
      )}

      {error && <p role="alert" className="practice-error">{error}</p>}

      <div className="practice-result-actions">
        {saveStatus === 'error' && (
          <Button variant="secondary" onClick={() => {
            saveFeedback.current?.focus()
            onRetrySave()
          }} disabled={isLoading}>Retry save</Button>
        )}
        <Button variant="primary" onClick={onNewText} isLoading={isLoading} disabled={isSaving}>
          {isLoading ? 'Preparing text…' : 'New text'}
        </Button>
        <Button variant="ghost" onClick={onChangeSettings} disabled={isLoading || isSaving}>
          Change settings
        </Button>
      </div>
    </div>
  )
}

export default TestResults
