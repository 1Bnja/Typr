import { useState } from 'react'
import { Navigate } from 'react-router-dom'
import { useAuth } from '../../auth'
import PracticeSetup from '../components/practice-setup'
import TypingTest from '../components/typing-test'
import TestResults from '../components/test-results'
import { getRandomText, savePracticeMatch } from '../services/practice-service'

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

  if (status === 'loading') {
    return <p className="p-8 text-center text-neutral-600">Loading…</p>
  }
  if (status === 'unauthenticated') {
    return <Navigate to="/login" replace />
  }

  const startWithNewText = async () => {
    setIsLoading(true)
    const newText = await getRandomText({ language, difficulty })
    setText(newText)
    setIsLoading(false)
    setAttempt((current) => current + 1)
    setPhase('typing')
  }

  const retrySameText = () => {
    setAttempt((current) => current + 1)
    setPhase('typing')
  }

  const handleFinish = async (testResult) => {
    setResult(testResult)
    setPhase('results')

    if (text.id === null) {
      setSaveStatus('skipped')
      return
    }

    setSaveStatus('saving')
    try {
      const saved = await savePracticeMatch(token, { textId: text.id, ...testResult })
      if (saved?.score != null) {
        setResult({ ...testResult, score: saved.score })
      }
      setSaveStatus('saved')
    } catch {
      setSaveStatus('error')
    }
  }

  return (
    <section className="mx-auto flex w-full max-w-3xl flex-col gap-8 px-6 py-10">
      <h1 className="text-4xl font-extrabold tracking-tight text-charcoal">{titles[phase]}</h1>

      {phase === 'setup' && (
        <PracticeSetup
          language={language}
          difficulty={difficulty}
          onLanguageChange={setLanguage}
          onDifficultyChange={setDifficulty}
          onStart={startWithNewText}
          isLoading={isLoading}
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
        />
      )}
    </section>
  )
}

export default Practice
