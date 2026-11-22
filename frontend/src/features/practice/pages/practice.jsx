import { useRef, useState } from 'react'
import { Navigate, useSearchParams } from 'react-router-dom'
import { useAuth } from '../../auth'
import PlayExpiryWarning from '../../auth/components/play-expiry-warning'
import { getAbsoluteDeadline } from '../../auth/utils/session'
import { rejectSession } from '../../auth/utils/session-fetch'
import PracticeSetup from '../components/practice-setup'
import TypingTest from '../components/typing-test'
import TestResults from '../components/test-results'
import TypingReference from '../components/typing-reference'
import { createPracticeAttemptId, getRandomText, reportPracticeActivity, savePracticeMatch } from '../services/practice-service'
import { DIFFICULTIES, LANGUAGES } from '../constants'
import '../practice.css'

const titles = {
  setup: 'Practice test',
  typing: 'Start typing',
  results: 'Your results',
}

const expiryNotice = 'Tu sesión ya no es válida. Inicia sesión de nuevo. Tu prueba de práctica no se guardó.'

const Practice = ({ focusMode = false, onFocusChange }) => {
  const { status, token } = useAuth()
  const [searchParams] = useSearchParams()

  const [phase, setPhase] = useState('setup')
  const [language, setLanguage] = useState(() => LANGUAGES.some((option) => option.value === searchParams.get('language')) ? searchParams.get('language') : 'spa')
  const [difficulty, setDifficulty] = useState(() => DIFFICULTIES.some((option) => option.value === searchParams.get('difficulty')) ? searchParams.get('difficulty') : 'easy')
  const [text, setText] = useState(null)
  const [isLoading, setIsLoading] = useState(false)
  const [result, setResult] = useState(null)
  const [saveStatus, setSaveStatus] = useState('idle')
  const submission = useRef(null)
  const saving = useRef(false)
  const [attempt, setAttempt] = useState(0)
  const [error, setError] = useState('')

  if (status === 'loading') {
    return <p className="p-8 text-center text-muted">Loading…</p>
  }
  if (status === 'unauthenticated') {
    return <Navigate to="/login" replace />
  }

  const startWithNewText = async () => {
    setIsLoading(true)
    setError('')
    try {
      const newText = await getRandomText(token, { language, difficulty, previousId: text?.id })
      setText(newText)
      setResult(null)
      submission.current = null
      setSaveStatus('idle')
      setAttempt((current) => current + 1)
      setPhase('typing')
    } catch (loadError) {
      setError(loadError.message)
    } finally {
      setIsLoading(false)
    }
  }

  const saveResult = async () => {
    if (saving.current || !submission.current) return
    if (Date.now() >= getAbsoluteDeadline(token)) {
      rejectSession(token, expiryNotice)
      return
    }
    saving.current = true
    setSaveStatus('saving')
    try {
      const saved = await savePracticeMatch(token, submission.current)
      if (saved?.ppm != null) {
        setResult((current) => ({ ...current, ppm: saved.ppm, precisionPct: saved.precisionPct, score: saved.score, progress: saved.progress }))
      }
      setSaveStatus('saved')
    } catch {
      setSaveStatus('error')
    } finally {
      saving.current = false
    }
  }

  const handleFinish = (testResult) => {
    if (submission.current) return
    submission.current = { ...testResult, textId: text.id, difficulty: text.difficulty, attemptId: createPracticeAttemptId() }
    setResult(testResult)
    setPhase('results')
    void saveResult()
  }

  return (
    <section className={`practice practice--${phase} ${focusMode ? 'practice--focus' : ''}`}>
      <header className="practice-header practice-focus-fade" aria-hidden={focusMode || undefined}>
        <h1 className={phase === 'typing' ? 'sr-only' : ''}>{titles[phase]}</h1>
        <p>
          {phase === 'setup'
            ? 'Choose a language and a difficulty to practice at your own pace.'
            : `${LANGUAGES.find((option) => option.value === text.language)?.label} · ${DIFFICULTIES.find((option) => option.value === text.difficulty)?.label} · ${text.content.split(' ').length} words`}
        </p>
      </header>

      {phase === 'setup' && (
        <PracticeSetup
          language={language}
          difficulty={difficulty}
          onLanguageChange={setLanguage}
          onDifficultyChange={setDifficulty}
          onStart={startWithNewText}
          isLoading={isLoading}
          error={error}
        />
      )}

      {phase === 'typing' && (
        <>
          <PlayExpiryWarning token={token} expiryNotice={expiryNotice} />
          <TypingTest
            key={attempt}
            text={text}
            onActivity={() => reportPracticeActivity(token)}
            onFinish={handleFinish}
            onFocusChange={onFocusChange}
            onCancel={() => setPhase('setup')}
          />
        </>
      )}

      {phase === 'results' && (
        <TestResults
          result={result}
          language={text.language}
          saveStatus={saveStatus}
          onRetrySave={saveResult}
          onNewText={startWithNewText}
          onChangeSettings={() => setPhase('setup')}
          isLoading={isLoading}
          error={error}
        />
      )}

      {phase !== 'typing' && <TypingReference language={phase === 'results' ? text.language : language} ppm={phase === 'results' ? result.ppm : null} />}
    </section>
  )
}

export default Practice
