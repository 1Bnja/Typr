import { useEffect, useState } from 'react'
import { Link, Navigate } from 'react-router-dom'
import { useAuth } from '../../auth'
import Button from '../../../components/button'
import Select from '../../../components/select/select'
import MonthPicker from '../components/month-picker'
import PracticeNav from '../components/practice-nav'
import { DIFFICULTIES, LANGUAGES } from '../constants'
import { getMonthlyLeaderboard } from '../services/practice-service'
import { formatTime } from '../utils/metrics'
import { formatMonth, getCurrentMonth } from '../utils/records'
import '../practice.css'
import '../records.css'

const Leaderboard = () => {
  const { token, user, status: authStatus } = useAuth()
  const [difficulty, setDifficulty] = useState('easy')
  const [language, setLanguage] = useState('spa')
  const [month, setMonth] = useState(getCurrentMonth)
  const [ranking, setRanking] = useState(null)
  const [status, setStatus] = useState('loading')
  const [retry, setRetry] = useState(0)

  useEffect(() => {
    if (!token || authStatus !== 'authenticated') return
    const controller = new AbortController()
    getMonthlyLeaderboard(token, { difficulty, language, month }, controller.signal)
      .then((data) => {
        if (controller.signal.aborted) return
        setRanking(data)
        setStatus('ready')
      })
      .catch((error) => {
        if (!controller.signal.aborted && error.name !== 'AbortError') setStatus('error')
      })
    return () => controller.abort()
  }, [token, authStatus, difficulty, language, month, retry])

  if (authStatus === 'loading') return <p className="p-8 text-center">Loading…</p>
  if (authStatus === 'unauthenticated') return <Navigate to="/login" replace />

  const changeFilter = (setter, value) => {
    setter(value)
    setStatus('loading')
  }

  return (
    <section className="practice practice-records">
      <PracticeNav />
      <header className="practice-header">
        <h1>Monthly leaderboard</h1>
        <p>A fresh month. A new personal best. Find your place at your level.</p>
      </header>

      <div className="records-toolbar">
        <div className="records-filters">
          <MonthPicker value={month} onChange={(value) => changeFilter(setMonth, value)} />
          <Select label="Language" value={language} options={[{ value: '', label: 'All languages' }, ...LANGUAGES]} onChange={(value) => changeFilter(setLanguage, value)} />
        </div>
        <Link to={`/practice?difficulty=${difficulty}&language=${language || 'spa'}`} className="button button--primary">Take a test</Link>
      </div>

      <div className="records-levels" aria-label="Leaderboard difficulty">
        {DIFFICULTIES.map((option) => (
          <Button key={option.value} variant={difficulty === option.value ? 'primary' : 'ghost'} aria-pressed={difficulty === option.value} onClick={() => { if (difficulty !== option.value) changeFilter(setDifficulty, option.value) }}>
            {option.label}
          </Button>
        ))}
      </div>

      <div className="records-section-heading">
        <h2>{formatMonth(month)}</h2>
        <span>Top 50 · one best test per person</span>
      </div>
      <div className="records-content" aria-busy={status === 'loading'}>
        {status === 'loading' && <p role="status" className="records-feedback">Loading the monthly ranking…</p>}
        {status === 'error' && (
          <div className="records-feedback" role="alert">
            <p>Could not load the leaderboard. Please try again.</p>
            <Button variant="secondary" onClick={() => { setStatus('loading'); setRetry((value) => value + 1) }}>Try again</Button>
          </div>
        )}
        {status === 'ready' && ranking.entries.length === 0 && (
          <div className="records-feedback">
            <h2>The first place is still open.</h2>
            <p>No completed tests for this month and level yet. Finish a test to join.</p>
            <Link to={`/practice?difficulty=${difficulty}&language=${language || 'spa'}`} className="records-text-link">Start a practice test</Link>
          </div>
        )}
        {status === 'ready' && ranking.entries.length > 0 && (
          <div className="records-table-scroll styled-scrollbar" role="region" aria-label="Monthly practice ranking" tabIndex={0}>
            <table className="records-table records-leaderboard">
              <caption className="sr-only">Best completed test for each typist in {formatMonth(month)}</caption>
              <thead><tr><th scope="col">Rank</th><th scope="col">Typist</th><th scope="col">Score</th><th scope="col">Speed</th><th scope="col">Accuracy</th><th scope="col">Time</th></tr></thead>
              <tbody>
                {ranking.entries.map((entry) => (
                  <tr key={entry.userId} data-current={entry.userId === user.id}>
                    <td><span className={`records-rank ${entry.position === 1 ? 'records-rank--first' : ''}`}>{entry.position}</span></td>
                    <td><span className="records-typist"><span className="records-avatar" aria-hidden="true">{entry.username.slice(0, 2).toUpperCase()}</span><span>{entry.username}{entry.userId === user.id && <span className="records-you">You</span>}</span></span></td>
                    <td className="records-score">{entry.score}</td>
                    <td><strong>{entry.ppm}</strong> <span className="records-unit">PPM</span></td>
                    <td>{Number(entry.precisionPct.toFixed(1))}%</td>
                    <td>{formatTime(entry.timeMs)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
      <footer className="records-footer records-ranking-footer">
        <p>Ranked by score, then accuracy, time and earliest finish.</p>
        <p>Months follow Santiago time.</p>
      </footer>
    </section>
  )
}

export default Leaderboard
