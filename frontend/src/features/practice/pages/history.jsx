import { useEffect, useState } from 'react'
import { Link, Navigate } from 'react-router-dom'
import { useAuth } from '../../auth'
import Button from '../../../components/button'
import PracticeNav from '../components/practice-nav'
import { LANGUAGES } from '../constants'
import { getPracticeHistory } from '../services/practice-service'
import { formatTime } from '../utils/metrics'
import { formatMatchDate, getDifficultyLabel, RECORD_DIFFICULTIES } from '../utils/records'
import '../practice.css'
import '../records.css'

const PAGE_SIZE = 10

const History = () => {
  const { token, status: authStatus } = useAuth()
  const [matches, setMatches] = useState([])
  const [difficulty, setDifficulty] = useState('')
  const [language, setLanguage] = useState('')
  const [page, setPage] = useState(0)
  const [status, setStatus] = useState('loading')
  const [retry, setRetry] = useState(0)

  useEffect(() => {
    if (!token || authStatus !== 'authenticated') return
    const controller = new AbortController()
    getPracticeHistory(token, { difficulty, language, offset: page * PAGE_SIZE, limit: PAGE_SIZE + 1 }, controller.signal)
      .then((data) => {
        if (controller.signal.aborted) return
        setMatches(data)
        setStatus('ready')
      })
      .catch((error) => {
        if (!controller.signal.aborted && error.name !== 'AbortError') setStatus('error')
      })
    return () => controller.abort()
  }, [token, authStatus, difficulty, language, page, retry])

  if (authStatus === 'loading') return <p className="p-8 text-center">Loading…</p>
  if (authStatus === 'unauthenticated') return <Navigate to="/login" replace />

  const changeFilter = (setter, value) => {
    setter(value)
    setPage(0)
    setStatus('loading')
  }
  const changePage = (value) => {
    setPage(value)
    setStatus('loading')
  }
  const rows = matches.slice(0, PAGE_SIZE)

  return (
    <section className="practice practice-records">
      <PracticeNav />
      <header className="practice-header">
        <h1>Your typing history</h1>
        <p>Every saved test, with your speed, accuracy and score.</p>
      </header>

      <div className="records-toolbar">
        <div className="records-filters">
          <label>Difficulty
            <select value={difficulty} onChange={(event) => changeFilter(setDifficulty, event.target.value)}>
              <option value="">All difficulties</option>
              {RECORD_DIFFICULTIES.map((option) => <option key={option.value} value={option.value}>{option.label}</option>)}
            </select>
          </label>
          <label>Language
            <select value={language} onChange={(event) => changeFilter(setLanguage, event.target.value)}>
              <option value="">All languages</option>
              {LANGUAGES.map((option) => <option key={option.value} value={option.value}>{option.label}</option>)}
            </select>
          </label>
        </div>
        <Link to="/practice" className="button button--primary">New test</Link>
      </div>

      <div className="records-content" aria-busy={status === 'loading'}>
        {status === 'loading' && <p role="status" className="records-feedback">Loading your tests…</p>}
        {status === 'error' && (
          <div className="records-feedback" role="alert">
            <p>Could not load your history. Please try again.</p>
            <Button variant="secondary" onClick={() => { setStatus('loading'); setRetry((value) => value + 1) }}>Try again</Button>
          </div>
        )}
        {status === 'ready' && rows.length === 0 && (
          <div className="records-feedback">
            <h2>{difficulty || language ? 'No tests match these filters.' : 'Your first result starts here.'}</h2>
            <p>{difficulty || language ? 'Choose another difficulty or language to see more tests.' : 'Finish a practice test and your result will appear here.'}</p>
            <Link to="/practice" className="records-text-link">Start a practice test</Link>
          </div>
        )}
        {status === 'ready' && rows.length > 0 && (
          <div className="records-table-scroll" role="region" aria-label="Saved practice tests" tabIndex={0}>
            <table className="records-table">
              <caption className="sr-only">Your saved tests, newest first</caption>
              <thead><tr><th scope="col">Played</th><th scope="col">Difficulty</th><th scope="col">Speed</th><th scope="col">Accuracy</th><th scope="col">Time</th><th scope="col">Score</th></tr></thead>
              <tbody>
                {rows.map((match) => (
                  <tr key={match.id}>
                    <td><time dateTime={match.finishedAt}>{formatMatchDate(match.finishedAt)}</time><span className="records-secondary">{LANGUAGES.find((option) => option.value === match.language)?.label}</span></td>
                    <td><span className={`records-difficulty records-difficulty--${match.difficulty}`}>{getDifficultyLabel(match.difficulty)}</span></td>
                    <td><strong>{match.ppm}</strong> <span className="records-unit">PPM</span></td>
                    <td>{Number(match.precisionPct.toFixed(1))}%</td>
                    <td>{formatTime(match.timeMs)}</td>
                    <td className="records-score">{match.score}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      <footer className="records-footer">
        <p>Times shown in Santiago.</p>
        <div className="records-pagination">
          <Button variant="ghost" size="sm" disabled={page === 0 || status !== 'ready'} onClick={() => changePage(page - 1)}>Previous</Button>
          <span aria-live="polite">Page {page + 1}</span>
          <Button variant="ghost" size="sm" disabled={matches.length <= PAGE_SIZE || status !== 'ready'} onClick={() => changePage(page + 1)}>Next</Button>
        </div>
      </footer>
    </section>
  )
}

export default History
