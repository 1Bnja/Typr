const RaceTrack = ({ players, userId }) => (
  <ol className="race-track" aria-label="Race progress">
    {players.map((player) => {
      const percent = Math.round(player.progress * 100)
      return (
        <li key={player.userId} className="race-lane" data-current={player.userId === userId} data-finished={player.finished}>
          <span className="race-lane-name">
            <span className="records-username" title={player.username}>{player.username}</span>
            {player.userId === userId && <span className="race-lane-you">(you)</span>}
          </span>
          <span
            className="race-lane-bar"
            role="progressbar"
            aria-label={`${player.username} progress`}
            aria-valuemin={0}
            aria-valuemax={100}
            aria-valuenow={percent}
          >
            <span style={{ width: `${percent}%` }} />
          </span>
          {/* El avance también va en texto: no depende solo del largo de la barra. */}
          <span className="race-lane-value">{player.finished ? 'Done' : `${percent}%`}</span>
        </li>
      )
    })}
  </ol>
)

export default RaceTrack
