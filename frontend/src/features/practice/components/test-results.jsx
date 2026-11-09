import Button from '../../../components/button'
import Stat from './stat'
import { formatTime } from '../utils/metrics'

const saveMessages = {
  saving: 'Saving your match…',
  saved: 'Match saved in your history.',
  error: 'We could not save this match.',
  skipped: 'Results for this sample text are not saved.',
}

const TestResults = ({ result, saveStatus, onRetry, onNewText, onChangeSettings }) => {
  return (
    <div className="flex flex-col gap-8">
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        <Stat label="PPM" value={result.ppm} large />
        <Stat label="Precision" value={`${result.precisionPct}%`} large />
        <Stat label="Score" value={result.score} large />
        <Stat label="Time" value={formatTime(result.timeMs)} large />
      </div>

      {saveMessages[saveStatus] && (
        <p role="status" className={saveStatus === 'error' ? 'text-red' : 'text-neutral-600'}>
          {saveMessages[saveStatus]}
        </p>
      )}

      <div className="flex flex-wrap gap-3">
        <Button variant="primary" onClick={onNewText}>
          New text
        </Button>
        <Button variant="secondary" onClick={onRetry}>
          Retry same text
        </Button>
        <Button variant="ghost" onClick={onChangeSettings}>
          Change settings
        </Button>
      </div>
    </div>
  )
}

export default TestResults
