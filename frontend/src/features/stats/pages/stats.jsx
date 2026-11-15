import { useEffect, useState } from 'react'
import { Link, Navigate } from 'react-router-dom'
import { useAuth } from '../../auth'
import Button from '../../../components/button'
import Stat from '../../practice/components/stat'
import { LANGUAGES } from '../../practice/constants'
import { formatTime, getSpeedUnit } from '../../practice/utils/metrics'
import { formatMatchDate, getDifficultyLabel } from '../../practice/utils/records'
import TrendChart from '../components/trend-chart'
import { MODE_LABELS, describeTrend, getMyStats, ordinal, toTrendData } from '../utils/stats'
import '../../practice/practice.css'
import '../../practice/records.css'
import '../stats.css'

const PAGE_SIZE = 10

const Stats = () => {
  const { token, status: authStatus } = useAuth()
  const [stats, setStats] = useState(null)
  const [page, setPage] = useState(0)
  const [status, setStatus] = useState('loading')
  const [retry, setRetry] = useState(0)

  useEffect(() => {
    if (!token || authStatus !== 'authenticated') return
    const controller = new AbortController()
    getMyStats(token, { offset: page * PAGE_SIZE, limit: PAGE_SIZE }, controller.signal)
      .then((data) => {
        if (controller.signal.aborted) return
        setStats(data)
        setStatus('ready')
      })
      .catch((error) => {
        if (!controller.signal.aborted && error.name !== 'AbortError') setStatus('error')
      })
    return () => controller.abort()
  }, [token, authStatus, page, retry])

  if (authStatus === 'loading') return <p className="p-8 text-center">Loading…</p>
  if (authStatus === 'unauthenticated') return <Navigate to="/login" replace />

  const changePage = (value) => {
    setPage(value)
    setStatus('loading')
  }

  const summary = stats?.summary
  const empty = status === 'ready' && summary.totalMatches === 0

  return (
    <section className="practice practice-records stats">
      <header className="practice-header">
        <h1>Your progress</h1>
        <p>Your speed and accuracy over time, across practice tests and multiplayer races.</p>
      </header>

      {status === 'loading' && !stats && <p role="status" className="records-feedback">Loading your stats…</p>}
      {status === 'error' && (
        <div className="records-feedback" role="alert">
          <p>Could not load your stats. Please try again.</p>
          <Button variant="secondary" onClick={() => { setStatus('loading'); setRetry((value) => value + 1) }}>Try again</Button>
        </div>
      )}

      {empty && (
        <div className="records-feedback stats-empty">
          <h2>Play your first match to see your progress.</h2>
          <p>Your charts and history appear here once you finish a practice test or a multiplayer race.</p>
          <div className="stats-empty-actions">
            <Link to="/practice" className="button button--primary">Start a practice test</Link>
            <Link to="/rooms" className="button button--secondary">Race other typists</Link>
          </div>
        </div>
      )}

      {stats && !empty && (
        <>
          <div className="stats-summary">
            <Stat label="Average speed" value={`${summary.averagePpm} WPM`} large />
            <Stat label="Average accuracy" value={`${summary.averagePrecisionPct}%`} large />
            <Stat label="Best speed" value={`${summary.bestPpm} WPM`} large />
            <Stat label="Matches" value={summary.totalMatches} large />
          </div>
          <p className="stats-modes">
            {summary.practiceMatches} practice {summary.practiceMatches === 1 ? 'test' : 'tests'}
            {' · '}
            {summary.multiplayerMatches} multiplayer {summary.multiplayerMatches === 1 ? 'race' : 'races'}
          </p>

          <section aria-labelledby="stats-trend">
            <div className="records-section-heading">
              <h2 id="stats-trend">Recent trend</h2>
              <span>Last {stats.trend.length} {stats.trend.length === 1 ? 'match' : 'matches'}</span>
            </div>
            <TrendChart data={toTrendData(stats.trend, summary.totalMatches)} description={describeTrend(stats.trend)} />
          </section>

          <section aria-labelledby="stats-history" className="stats-history">
            <div className="records-section-heading">
              <h2 id="stats-history">Match history</h2>
              <span>Newest first</span>
            </div>
            <div className="records-content" aria-busy={status === 'loading'}>
              <div className="records-table-scroll styled-scrollbar" role="region" aria-label="Match history" tabIndex={0}>
                <table className="records-table">
                  <caption className="sr-only">Your finished matches, newest first</caption>
                  <colgroup><col className="records-col-date" /><col className="stats-col-mode" /><col /><col /><col /><col /></colgroup>
                  <thead>
                    <tr>
                      <th scope="col">Played</th><th scope="col">Mode</th><th scope="col">Speed</th>
                      <th scope="col">Accuracy</th><th scope="col">Time</th><th scope="col">Score</th>
                    </tr>
                  </thead>
                  <tbody>
                    {stats.history.map((match) => (
                      <tr key={match.gameId}>
                        <th scope="row">
                          <time dateTime={match.finishedAt}>{formatMatchDate(match.finishedAt)}</time>
                          <span className="records-secondary">
                            {LANGUAGES.find((option) => option.value === match.language)?.label} · {getDifficultyLabel(match.difficulty)}
                          </span>
                        </th>
                        <td>
                          <span className="stats-mode" data-mode={match.mode}>{MODE_LABELS[match.mode]}</span>
                          {match.position !== null && <span className="records-secondary">{ordinal(match.position)} place</span>}
                        </td>
                        <td className="records-speed"><strong>{match.ppm}</strong> <span className="records-unit">{getSpeedUnit(match.language)}</span></td>
                        <td>{Number(match.precisionPct.toFixed(1))}%</td>
                        <td>{match.progress < 1 ? `Unfinished · ${Math.round(match.progress * 100)}%` : formatTime(match.timeMs)}</td>
                        <td className="records-score">{match.score}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
            <p className="records-scroll-hint">Scroll sideways to see all metrics.</p>
            <footer className="records-footer">
              <p>Times shown in Santiago.</p>
              <div className="records-pagination">
                <Button variant="ghost" size="sm" disabled={page === 0 || status !== 'ready'} onClick={() => changePage(page - 1)}>Previous</Button>
                <span aria-live="polite">Page {page + 1}</span>
                <Button variant="ghost" size="sm" disabled={!stats.hasMore || status !== 'ready'} onClick={() => changePage(page + 1)}>Next</Button>
              </div>
            </footer>
          </section>
        </>
      )}
    </section>
  )
}

export default Stats
