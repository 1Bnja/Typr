import { useEffect, useId, useRef, useState } from 'react'
import { getSpeedUnit } from '../utils/metrics'

const formatSeconds = (timeMs) => `${Number((timeMs / 1000).toFixed(1))}s`

const SpeedChart = ({ samples, average, language }) => {
  const id = useId()
  const plotRef = useRef(null)
  const [width, setWidth] = useState(600)
  const [activeIndex, setActiveIndex] = useState(null)
  const unit = getSpeedUnit(language)
  const duration = samples.at(-1).timeMs
  const height = width < 480 ? 200 : 220
  const left = 40
  const right = width - 12
  const top = 20
  const bottom = height - 32
  const maxSpeed = Math.max(20, Math.ceil(Math.max(average, ...samples.map((sample) => sample.ppm)) * 1.1 / 20) * 20)
  const x = (timeMs) => left + timeMs / duration * (right - left)
  const y = (ppm) => bottom - ppm / maxSpeed * (bottom - top)
  const speedTicks = [0, 0.25, 0.5, 0.75, 1].map((part) => part * maxSpeed)
  const timeTicks = duration < 4000 ? [0, duration] : [0, 0.25, 0.5, 0.75, 1].map((part) => part * duration)
  const mistakes = samples.map((sample, index) => sample.errors - (samples[index - 1]?.errors ?? 0))
  const selected = activeIndex === null ? null : samples[activeIndex]
  const newErrors = activeIndex === null ? 0 : mistakes[activeIndex]

  useEffect(() => {
    const observer = new ResizeObserver(([entry]) => setWidth(entry.contentRect.width))
    observer.observe(plotRef.current)
    return () => observer.disconnect()
  }, [])

  const inspectPoint = (e) => {
    const bounds = e.currentTarget.getBoundingClientRect()
    const time = Math.max(0, Math.min(1, (e.clientX - bounds.left - left) / (right - left))) * duration
    let nearest = 0
    for (let i = 1; i < samples.length; i++) {
      if (Math.abs(samples[i].timeMs - time) < Math.abs(samples[nearest].timeMs - time)) nearest = i
    }
    setActiveIndex(nearest)
  }

  const handleKeyDown = (e) => {
    const index = activeIndex ?? samples.length - 1
    if (e.key === 'ArrowLeft') setActiveIndex(Math.max(0, index - 1))
    else if (e.key === 'ArrowRight') setActiveIndex(Math.min(samples.length - 1, index + 1))
    else if (e.key === 'Home') setActiveIndex(0)
    else if (e.key === 'End') setActiveIndex(samples.length - 1)
    else if (e.key === 'Escape') setActiveIndex(null)
    else return
    e.preventDefault()
  }

  return (
    <section className="practice-speed-chart" aria-labelledby={`${id}-title`}>
      <div className="practice-chart-header">
        <h2 id={`${id}-title`}>Speed over time</h2>
        <p className="practice-chart-reading" aria-live="polite" aria-atomic="true">
          {selected ? <><span>{formatSeconds(selected.timeMs)}</span><strong>{selected.ppm} {unit}</strong><span>{newErrors} {newErrors === 1 ? 'new mistake' : 'new mistakes'}</span></> : 'Select a moment to see your pace.'}
        </p>
      </div>
      <div className="practice-chart-legend" aria-hidden="true">
        <span><i className="practice-chart-key practice-chart-key--speed" />Speed ({unit})</span>
        <span><i className="practice-chart-key practice-chart-key--average" />Final average · {average} {unit}</span>
        {mistakes.some((count) => count > 0) && <span><i className="practice-chart-key practice-chart-key--mistake" />Mistakes</span>}
      </div>
      <div
        ref={plotRef}
        className="practice-chart-plot"
        role="group"
        tabIndex={0}
        aria-label="Inspect typing speed"
        aria-describedby={`${id}-help`}
        onPointerMove={inspectPoint}
        onPointerDown={inspectPoint}
        onPointerLeave={() => setActiveIndex(null)}
        onFocus={() => setActiveIndex(samples.length - 1)}
        onBlur={() => setActiveIndex(null)}
        onKeyDown={handleKeyDown}
      >
        <svg viewBox={`0 0 ${width} ${height}`} role="img" aria-labelledby={`${id}-svg-title ${id}-description`}>
          <title id={`${id}-svg-title`}>Typing speed in {unit} over {formatSeconds(duration)}</title>
          <desc id={`${id}-description`}>Average speed from the start of this test, ending at {average} {unit}. The dashed line marks the final average. Crosses mark mistakes made between samples.</desc>
          {speedTicks.map((tick) => (
            <g key={tick}>
              <line className="practice-chart-grid" x1={left} x2={right} y1={y(tick)} y2={y(tick)} />
              <text className="practice-chart-label" x={left - 12} y={y(tick)} textAnchor="end" dominantBaseline="middle">{tick}</text>
            </g>
          ))}
          {timeTicks.map((tick, index) => (
            <text key={tick} className="practice-chart-label" x={x(tick)} y={height - 8} textAnchor={index === 0 ? 'start' : index === timeTicks.length - 1 ? 'end' : 'middle'}>{formatSeconds(tick)}</text>
          ))}
          <line className="practice-chart-average" x1={left} x2={right} y1={y(average)} y2={y(average)} />
          <polyline className="practice-chart-line" points={samples.map((sample) => `${x(sample.timeMs)},${y(sample.ppm)}`).join(' ')} />
          {samples.map((sample, index) => mistakes[index] > 0 && (
            <path key={sample.timeMs} className="practice-chart-mistake" d={`M${x(sample.timeMs) - 3},${y(sample.ppm) - 3}l6,6m0,-6l-6,6`} />
          ))}
          {selected && <line className="practice-chart-guide" x1={x(selected.timeMs)} x2={x(selected.timeMs)} y1={top} y2={bottom} />}
          <circle className="practice-chart-point" cx={x((selected ?? samples.at(-1)).timeMs)} cy={y((selected ?? samples.at(-1)).ppm)} r={selected ? 4 : 3} />
        </svg>
      </div>
      <p id={`${id}-help`} className="practice-chart-caption">
        {samples.length === 1 ? 'Short test: only the final speed was recorded.' : 'Speed is averaged from your first keystroke. Crosses include corrected mistakes.'}
        <span className="sr-only"> Focus the chart and use the Left and Right arrow keys to inspect samples. Home and End jump to the first and last sample.</span>
      </p>
    </section>
  )
}

export default SpeedChart
