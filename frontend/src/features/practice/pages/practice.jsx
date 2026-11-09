import { useState } from 'react'
import { Navigate } from 'react-router-dom'
import { useAuth } from '../../auth'
import PracticeSetup from '../components/practice-setup'
import TypingTest from '../components/typing-test'
import TestResults from '../components/test-results'
import TypingReference from '../components/typing-reference'
import { getRandomText, savePracticeMatch } from '../services/practice-service'
import { DIFFICULTIES, LANGUAGES } from '../constants'
import '../practice.css'

const titles = {
  setup: 'Practice test',
  typing: 'Start typing',
  results: 'Your results',
}

const Practice = () => {
  const { status, token } = useAuth()

  const [phase, setPhase] = useState('setup')
  const [language, setLanguage] = useState('spa')
  const [difficulty, setDifficulty] = useState('easy')
  const [text, setText] = useState(null)
  const [isLoading, setIsLoading] = useState(false)
  const [result, setResult] = useState(null)
  const [saveStatus, setSaveStatus] = useState('idle')
  const [attempt, setAttempt] = useState(0)
  const [error, setError] = useState('')

  if (status === 'loading') {
    return <p className="p-8 text-center text-neutral-600">Loading…</p>
  }
  if (status === 'unauthenticated') {
    return <Navigate to="/login" replace />
  }

  const startWithNewText = async () => {
    setIsLoading(true)
    setError('')
    try {
      const newText = await getRandomText({ language, difficulty })
      setText(newText)
      setResult(null)
      setSaveStatus('idle')
      setAttempt((current) => current + 1)
      setPhase('typing')
    } catch {
      setError('Could not prepare the text. Please try again.')
    } finally {
      setIsLoading(false)
    }
  }

  const retrySameText = () => {
    setResult(null)
    setSaveStatus('idle')
    setError('')
    setAttempt((current) => current + 1)
    setPhase('typing')
  }

  const handleFinish = async (testResult) => {
    setResult(testResult)
    setPhase('results')

    setSaveStatus('saving')
    try {
      const textData = text.id == null
        ? { text: { content: text.content, language: text.language } }
        : { textId: text.id }
      const saved = await savePracticeMatch(token, { ...textData, ...testResult })
      if (saved?.score != null) {
        setResult({ ...testResult, score: saved.score })
      }
      setText((current) => ({ ...current, id: saved.textId }))
      setSaveStatus('saved')
    } catch {
      setSaveStatus('error')
    }
  }

  return (
    <section className={`practice practice--${phase}`}>
      <header className="practice-header">
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
        <TypingTest
          key={attempt}
          text={text}
          onFinish={handleFinish}
          onCancel={() => setPhase('setup')}
        />
      )}

      {phase === 'results' && (
        <TestResults
          result={result}
          saveStatus={saveStatus}
          onRetry={retrySameText}
          onNewText={startWithNewText}
          onChangeSettings={() => setPhase('setup')}
          isLoading={isLoading}
          error={error}
        />
      )}

      {phase !== 'typing' && <TypingReference ppm={phase === 'results' ? result.ppm : null} />}
    </section>
  )
}

export default Practice
