import Button from '../../../components/button'
import Crown from '../../../components/icons/crown'
import { getSpeedUnit } from '../../practice/utils/metrics'

const RaceResults = ({ results, userId, language, onContinue }) => {
  const { round, rounds, nextRoundInS } = results
  const unit = getSpeedUnit(language)

  return (
    <div className="race-results">
      <div className="records-table-scroll styled-scrollbar" role="region" aria-label="Race results" tabIndex={0}>
        <table className="records-table records-leaderboard">
          <caption className="sr-only">Results of round {round} of {rounds}</caption>
          <colgroup><col className="records-col-rank" /><col className="records-col-typist" /><col /><col /><col /><col /></colgroup>
          <thead>
            <tr>
              <th scope="col">Place</th><th scope="col">Typist</th><th scope="col">Score</th>
              <th scope="col">Speed</th><th scope="col">Accuracy</th><th scope="col">Time</th>
            </tr>
          </thead>
          <tbody>
            {results.results.map((result) => (
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
                      {result.isRecord && <span className="room-badge">New record</span>}
                    </span>
                  </span>
                </th>
                <td className="records-score">{result.score}</td>
                <td className="records-speed"><strong>{result.ppm}</strong> <span className="records-unit">{unit}</span></td>
                <td>{Number(result.precisionPct.toFixed(1))}%</td>
                <td>
                  {result.finished
                    ? `${(result.timeMs / 1000).toFixed(1)} s`
                    : `Did not finish · ${Math.round(result.progress * 100)}%`}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p className="records-scroll-hint">Scroll sideways to see all metrics.</p>

      <div className="room-actions">
        {nextRoundInS === null ? (
          <Button variant="primary" onClick={onContinue}>Back to the room</Button>
        ) : (
          <p className="room-hint" role="status">The next round starts in a few seconds…</p>
        )}
      </div>
    </div>
  )
}

export default RaceResults
