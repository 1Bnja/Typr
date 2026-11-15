import { CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { formatMatchDate } from '../../practice/utils/records'
import { MODE_LABELS } from '../utils/stats'

const TrendTooltip = ({ active, payload }) => {
  if (!active || !payload?.length) return null
  const point = payload[0].payload
  return (
    <div className="stats-tooltip">
      <p className="stats-tooltip-title">Match {point.match} · {MODE_LABELS[point.mode]}</p>
      <p className="stats-tooltip-date">{formatMatchDate(point.finishedAt)}</p>
      <p><span className="stats-key stats-key--ppm" aria-hidden="true" /> {point.ppm} WPM</p>
      <p><span className="stats-key stats-key--precision" aria-hidden="true" /> {point.precision}% accuracy</p>
    </div>
  )
}

// Los colores se aplican desde CSS para seguir el tema claro u oscuro.
const TrendChart = ({ data, description }) => (
  <figure className="stats-chart">
    <div className="stats-chart-legend" aria-hidden="true">
      <span><span className="stats-key stats-key--ppm" /> Speed (WPM)</span>
      <span><span className="stats-key stats-key--precision" /> Accuracy (%)</span>
    </div>
    <div role="img" aria-label={description} className="stats-chart-plot">
      <ResponsiveContainer width="100%" height={280}>
        <LineChart data={data} margin={{ top: 12, right: 8, bottom: 4, left: -8 }}>
          <CartesianGrid vertical={false} />
          <XAxis dataKey="match" tickLine={false} axisLine={false} allowDecimals={false} minTickGap={16} />
          <YAxis yAxisId="ppm" tickLine={false} axisLine={false} allowDecimals={false} width={44} />
          <YAxis yAxisId="precision" orientation="right" domain={[0, 100]} tickLine={false} axisLine={false} unit="%" width={44} />
          <Tooltip content={<TrendTooltip />} cursor={{ className: 'stats-chart-cursor' }} />
          <Line yAxisId="ppm" dataKey="ppm" name="Speed (WPM)" className="stats-line stats-line--ppm"
            strokeWidth={2.5} dot={{ r: 3 }} activeDot={{ r: 5 }} isAnimationActive={false} />
          <Line yAxisId="precision" dataKey="precision" name="Accuracy (%)" className="stats-line stats-line--precision"
            strokeWidth={2} strokeDasharray="5 4" dot={false} activeDot={{ r: 4 }} isAnimationActive={false} />
        </LineChart>
      </ResponsiveContainer>
    </div>
    <figcaption className="stats-chart-caption">{description}</figcaption>
  </figure>
)

export default TrendChart
