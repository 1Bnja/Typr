const speedRanges = [
  {
    min: 0,
    max: 19,
    range: '<20',
    label: 'Getting started',
    description: 'Build accuracy and get comfortable with the keys.',
  },
  {
    min: 20,
    max: 40,
    range: '20–40',
    label: 'Casual',
    description: 'An everyday pace for messages and occasional typing.',
  },
  {
    min: 41,
    max: 60,
    range: '41–60',
    label: 'Comfortable',
    description: 'A steady rhythm for writing and daily work.',
  },
  {
    min: 61,
    max: 80,
    range: '61–80',
    label: 'Fast',
    description: 'A quick, confident pace. Keep accuracy in focus.',
  },
  {
    min: 81,
    max: 100,
    range: '81–100',
    label: 'Very fast',
    description: 'A strong rhythm with smooth, consistent keystrokes.',
  },
  {
    min: 101,
    max: 120,
    range: '101–120',
    label: 'Excellent',
    description: 'Speed and control working together. Make every keystroke count.',
  },
  {
    min: 121,
    max: Infinity,
    range: '121+',
    label: 'Exceptional',
    description: 'An impressive pace. Aim to sustain it across longer tests.',
  },
]

const TypingReference = ({ ppm }) => {
  return (
    <section className="practice-reference" aria-labelledby="typing-reference-title">
      <div className="practice-reference-heading">
        <div>
          <h2 id="typing-reference-title">Your speed in perspective</h2>
          <p className="practice-reference-intro">Small improvements add up. Here is a little context for your next test.</p>
        </div>
        <div className="practice-reference-study">
          <p className="practice-reference-average"><strong>52</strong> <span>PPM</span> <span className="practice-reference-average-label">study average</span></p>
          <p className="practice-reference-source">
            168,000 volunteers · <a href="https://www.aalto.fi/en/news/the-traits-of-fast-typists-discovered-by-analysing-136-million-keystrokes" target="_blank" rel="noreferrer">Aalto & Cambridge, 2018</a>
          </p>
        </div>
      </div>

      <div>
        <dl className="practice-speed-ranges">
          {speedRanges.map((level) => {
            const isCurrent = ppm != null && ppm >= level.min && ppm <= level.max
            return (
              <div key={level.label} className="practice-speed-range" data-current={isCurrent}>
                <dt>
                  <span className="practice-speed-range-value">{level.range} <span>PPM</span></span>
                  <span className="practice-speed-range-name">{level.label}</span>
                </dt>
                <dd>
                  <p>{level.description}</p>
                  {isCurrent && <span className="practice-your-pace">Your pace · {ppm} PPM</span>}
                </dd>
              </div>
            )
          })}
        </dl>
        <p className="practice-reference-note">Ranges are a practical guide. Language and test format affect speed; the study used English sentences.</p>
      </div>
    </section>
  )
}

export default TypingReference
