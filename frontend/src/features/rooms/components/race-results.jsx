import { useEffect, useState } from 'react'
import Button from '../../../components/button'
import Crown from '../../../components/icons/crown'
import { getSpeedUnit } from '../../practice/utils/metrics'

const oneDecimal = (value) => Number(value.toFixed(1))

const RaceResults = ({ results, userId, language, onContinue }) => {
  const { round, rounds, nextRoundInS, matchResults, returnToRoomInS } = results
  const final = Array.isArray(matchResults)
  const unit = getSpeedUnit(language)
  const [deadline] = useState(() => (results.receivedAt ?? Date.now()) + (returnToRoomInS ?? 15) * 1000)
  const [secondsLeft, setSecondsLeft] = useState(() => Math.max(0, Math.ceil((deadline - Date.now()) / 1000)))

  useEffect(() => {
    if (!final) return undefined
    const updateCountdown = () => setSecondsLeft(Math.max(0, Math.ceil((deadline - Date.now()) / 1000)))
    const interval = setInterval(updateCountdown, 250)
    const timeout = setTimeout(onContinue, Math.max(0, deadline - Date.now()))
    return () => {
      clearInterval(interval)
      clearTimeout(timeout)
    }
  }, [deadline, final, onContinue])

  return (
    <div className={`race-results${final ? ' race-results--final' : ''}`}>
      {final && (
        <div className="race-final-summary">
          <h2>Final standings</h2>
          <p>Positions are based on average score across the rounds each player played. Unfinished rounds count toward the averages.</p>
        </div>
      )}
      <div className="records-table-scroll styled-scrollbar" role="region" aria-label={final ? 'Final match results' : 'Race results'} tabIndex={0}>
        <table className="records-table records-leaderboard">
          <caption className="sr-only">{final ? 'Final match averages and positions' : `Results of round ${round} of ${rounds}`}</caption>
          <colgroup>
            <col className="records-col-rank" /><col className="records-col-typist" />
            <col /><col /><col /><col />
            {final && <><col /><col /></>}
          </colgroup>
          <thead>
            <tr>
              <th scope="col">Place</th><th scope="col">Typist</th>
              <th scope="col">{final ? 'Avg. score' : 'Score'}</th>
              <th scope="col">{final ? 'Avg. speed' : 'Speed'}</th>
              <th scope="col">{final ? 'Avg. accuracy' : 'Accuracy'}</th>
              <th scope="col">{final ? 'Avg. time' : 'Time'}</th>
              {final && <><th scope="col">Avg. progress</th><th scope="col">Rounds finished</th></>}
            </tr>
          </thead>
          <tbody>
            {(final ? matchResults : results.results).map((result) => (
              <tr key={result.userId} data-current={result.userId === userId}>
                <td>
                  <span className="records-rank">
                    {result.position === 1 ? <><Crown className="records-crown" /><span className="sr-only">1st place</span></> : result.position}
                  </span>
                </td>
                <th scope="row">
                  <span className="records-typist">
                    <span className="records-avatar" aria-hidden="true">{result.username.slice(0, 2).toUpperCase()}</span>
                    <span className="records-identity">
                      <span className="records-username" title={result.username}>{result.username}</span>
                      {result.userId === userId && <span className="records-you">You</span>}
                      {final && result.recordsCount > 0 && <span className="room-badge">{result.recordsCount} new {result.recordsCount === 1 ? 'record' : 'records'}</span>}
                      {!final && result.isRecord && <span className="room-badge">New record</span>}
                    </span>
                  </span>
                </th>
                <td className="records-score">{final ? oneDecimal(result.averageScore) : result.score}</td>
                <td className="records-speed"><strong>{final ? oneDecimal(result.averagePpm) : result.ppm}</strong> <span className="records-unit">{unit}</span></td>
                <td>{oneDecimal(final ? result.averagePrecisionPct : result.precisionPct)}%</td>
                <td>
                  {final
                    ? `${(result.averageTimeMs / 1000).toFixed(1)} s`
                    : result.finished
                      ? `${(result.timeMs / 1000).toFixed(1)} s`
                      : `Did not finish · ${Math.round(result.progress * 100)}%`}
                </td>
                {final && <>
                  <td>{oneDecimal(result.averageProgress * 100)}%</td>
                  <td>{result.finishedRounds} / {result.roundsPlayed}</td>
                </>}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p className="records-scroll-hint">Scroll sideways to see all metrics.</p>

      <div className="room-actions">
        {final ? (
          <>
            <p className="room-hint" role="status">Returning to the room in {secondsLeft} s…</p>
            <Button variant="primary" onClick={onContinue}>Back to the room now</Button>
          </>
        ) : nextRoundInS === null ? (
          <Button variant="primary" onClick={onContinue}>Back to the room</Button>
        ) : (
          <p className="room-hint" role="status">The next round starts in a few seconds…</p>
        )}
      </div>
    </div>
  )
}

export default RaceResults
