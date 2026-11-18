import { useEffect, useState } from 'react'
import { Link, Navigate } from 'react-router-dom'
import { useAuth } from '../../auth'
import Button from '../../../components/button'
import Stat from '../../practice/components/stat'
import { LANGUAGES } from '../../practice/constants'
import { formatTime, getSpeedUnit } from '../../practice/utils/metrics'
import { formatMatchDate, getDifficultyLabel } from '../../practice/utils/records'
import { getMyStats } from '../../stats/utils/stats'
import '../../practice/practice.css'
import '../../practice/records.css'
import '../../stats/stats.css'
import '../dashboard.css'

const RECENT_LIMIT = 5

const Dashboard = () => {
    const { user, token, status: authStatus } = useAuth()
    const [stats, setStats] = useState(null)
    const [status, setStatus] = useState('loading')
    const [retry, setRetry] = useState(0)

    useEffect(() => {
        if (!token || authStatus !== 'authenticated') return
        const controller = new AbortController()
        getMyStats(token, { offset: 0, limit: RECENT_LIMIT }, controller.signal)
            .then((data) => {
                if (controller.signal.aborted) return
                setStats(data)
                setStatus('ready')
            })
            .catch((error) => {
                if (!controller.signal.aborted && error.name !== 'AbortError') setStatus('error')
            })
        return () => controller.abort()
    }, [token, authStatus, retry])

    if (authStatus === 'loading') return <p className="p-8 text-center">Loading…</p>
    if (authStatus === 'unauthenticated') return <Navigate to="/login" replace />

    const summary = stats?.summary
    const recent = stats?.history.slice(0, RECENT_LIMIT) ?? []
    const empty = status === 'ready' && summary.totalMatches === 0

    return (
        <section className="practice practice-records stats">
            <header className="practice-header">
                <h1>{user?.username ? `Welcome back, ${user.username}` : 'Welcome back'}</h1>
                <p>Your speed, accuracy and latest matches at a glance.</p>
            </header>

            {status === 'loading' && !stats && <p role="status" className="records-feedback">Loading your dashboard…</p>}
            {status === 'error' && (
                <div className="records-feedback" role="alert">
                    <p>Could not load your dashboard. Please try again.</p>
                    <Button variant="secondary" onClick={() => { setStatus('loading'); setRetry((value) => value + 1) }}>Try again</Button>
                </div>
            )}

            {empty && (
                <div className="records-feedback stats-empty">
                    <h2>Play your first match to see your progress.</h2>
                    <p>Your summary and recent matches appear here once you finish a practice test or a multiplayer race.</p>
                    <div className="stats-empty-actions">
                        <Link to="/practice" className="button button--primary">Start a practice test</Link>
                    </div>
                </div>
            )}

            {stats && !empty && (
                <>
                    <div className="stats-summary dashboard-summary">
                        <Stat label="Best speed" value={`${summary.bestPpm} WPM`} large />
                        <Stat label="Average accuracy" value={`${summary.averagePrecisionPct}%`} large />
                        <Stat label="Matches" value={summary.totalMatches} large />
                    </div>
                    <p className="stats-modes">
                        {summary.practiceMatches} practice {summary.practiceMatches === 1 ? 'test' : 'tests'}
                        {' · '}
                        {summary.multiplayerMatches} multiplayer {summary.multiplayerMatches === 1 ? 'race' : 'races'}
                    </p>

                    <section aria-labelledby="dashboard-recent" className="dashboard-recent">
                        <div className="records-section-heading">
                            <h2 id="dashboard-recent">Recent matches</h2>
                            <span>Newest first</span>
                        </div>
                        <div className="records-table-scroll styled-scrollbar" role="region" aria-label="Recent matches" tabIndex={0}>
                            <table className="records-table">
                                <caption className="sr-only">Your latest finished matches, newest first</caption>
                                <colgroup><col className="records-col-date" /><col className="records-col-difficulty" /><col /><col /><col /><col /></colgroup>
                                <thead><tr><th scope="col">Played</th><th scope="col">Difficulty</th><th scope="col">Speed</th><th scope="col">Accuracy</th><th scope="col">Time</th><th scope="col">Score</th></tr></thead>
                                <tbody>
                                    {recent.map((match) => (
                                        <tr key={match.gameId}>
                                            <th scope="row"><time dateTime={match.finishedAt}>{formatMatchDate(match.finishedAt)}</time><span className="records-secondary">{LANGUAGES.find((option) => option.value === match.language)?.label}</span></th>
                                            <td><span className={`records-difficulty records-difficulty--${match.difficulty}`}>{getDifficultyLabel(match.difficulty)}</span></td>
                                            <td className="records-speed"><strong>{match.ppm}</strong> <span className="records-unit">{getSpeedUnit(match.language)}</span></td>
                                            <td>{Number(match.precisionPct.toFixed(1))}%</td>
                                            <td>{formatTime(match.timeMs)}</td>
                                            <td className="records-score">{match.score}</td>
                                        </tr>
                                    ))}
                                </tbody>
                            </table>
                        </div>
                        <p className="records-scroll-hint">Scroll sideways to see all metrics.</p>
                    </section>

                    <div className="stats-empty-actions dashboard-actions">
                        <Link to="/practice" className="button button--primary">Start a practice test</Link>
                        <Link to="/practice/stats" className="button button--secondary">Full stats</Link>
                        <Link to="/practice/history" className="button button--secondary">Full history</Link>
                    </div>

                    <footer className="records-footer">
                        <p>Times shown in Santiago.</p>
                    </footer>
                </>
            )}
        </section>
    )
}

export default Dashboard
