const Stat = ({ label, value, large = false }) => (
  <div className={`practice-stat ${large ? 'practice-stat--large' : ''}`}>
    <span className="practice-stat-label">{label}</span>
    <span className="practice-stat-value">{value}</span>
  </div>
)

export default Stat
