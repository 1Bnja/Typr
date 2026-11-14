import { useState } from 'react'
import { Link } from 'react-router-dom'
import Button from '../../../components/button'
import { useAuth } from '../../auth/context/auth-context'
import { generateTexts, saveTexts, verifyText } from '../services/textService'
import './texts.css'

const difficultyLabels = {
  easy: 'Fácil',
  medium: 'Media',
  advanced: 'Avanzada',
  expert: 'Experta',
}

const reasonLabels = {
  difficulty_quota: 'Se alcanzó el límite de 10 frases para esta dificultad.',
  content_too_short: 'La frase debe tener al menos 40 caracteres.',
  content_too_long: 'La frase debe tener como máximo 500 caracteres.',
  too_few_words: 'La frase debe tener al menos cinco palabras.',
  word_count_mismatch: 'La cantidad de palabras no corresponde a su grupo.',
}

const expectedWords = (index) => index < 10 ? 20 : index < 20 ? 30 : 40
const countWords = (content) => content.trim().split(/\s+/).filter((token) => /[\p{L}\p{N}]/u.test(token)).length

const filters = [
  { id: 'all', label: 'Todas' },
  { id: 'pending', label: 'Por revisar' },
  { id: 'approved', label: 'Aprobadas' },
  { id: 'issues', label: 'Observadas' },
  { id: 'stored', label: 'Guardadas' },
]

const makeReviewItem = (phrase, index) => ({
  ...phrase,
  key: index,
  draft: phrase.content,
  editing: false,
  selected: false,
  discarded: false,
  error: '',
})

const getReviewState = (item) => {
  if (item.status === 'stored') return 'stored'
  if (item.discarded || item.status === 'duplicate' || item.status === 'rejected') return 'issues'
  return item.selected ? 'approved' : 'pending'
}

const getStatusLabel = (item) => {
  if (item.status === 'stored') return 'Guardada'
  if (item.discarded) return 'Descartada'
  if (item.status === 'duplicate') return 'Duplicada'
  if (item.status === 'rejected') return 'Rechazada'
  return item.selected ? 'Aprobada' : 'Por revisar'
}

export default function Texts() {
  const { token, status } = useAuth()
  const [language, setLanguage] = useState('spa')
  const [generation, setGeneration] = useState(null)
  const [items, setItems] = useState([])
  const [filter, setFilter] = useState('all')
  const [generating, setGenerating] = useState(false)
  const [saving, setSaving] = useState(false)
  const [verifyingId, setVerifyingId] = useState(null)
  const [message, setMessage] = useState(null)

  const busy = generating || saving || verifyingId !== null
  const counts = items.reduce((current, item) => {
    current[getReviewState(item)] += 1
    return current
  }, { pending: 0, approved: 0, issues: 0, stored: 0 })
  const visibleItems = filter === 'all' ? items : items.filter((item) => getReviewState(item) === filter)

  const updateItem = (key, changes) => {
    setItems((current) => current.map((item) => item.key === key ? { ...item, ...changes } : item))
  }

  const generate = async () => {
    setGenerating(true)
    setMessage(null)
    try {
      const result = await generateTexts(language, token)
      setGeneration(result)
      setItems(result.phrases.map(makeReviewItem))
      setFilter('all')
      setMessage({ tone: 'success', text: `${result.generated} frases generadas. Revisa las aptas antes de guardarlas.` })
    } catch (error) {
      setMessage({ tone: 'error', text: error.message })
    } finally {
      setGenerating(false)
    }
  }

  const verify = async (item) => {
    const draft = item.draft.trim()
    if (!draft) {
      updateItem(item.key, { error: 'Escribe una frase para verificarla.' })
      return
    }
    setVerifyingId(item.key)
    updateItem(item.key, { error: '' })
    try {
      const verified = await verifyText(draft, generation.language, token)
      const expected = expectedWords(item.key)
      if (countWords(verified.content) !== expected) {
        updateItem(item.key, { error: `Esta frase debe tener exactamente ${expected} palabras.` })
        return
      }
      if (items.some((other) => other.key !== item.key && other.content === verified.content && other.status !== 'rejected')) {
        updateItem(item.key, { error: 'Esta frase ya aparece en el lote. Cámbiala antes de aprobarla.' })
        return
      }
      updateItem(item.key, {
        content: verified.content,
        draft: verified.content,
        difficulty: verified.difficulty,
        status: 'valid',
        reasonCode: null,
        editing: false,
        selected: false,
        discarded: false,
        error: '',
      })
      setMessage({ tone: 'success', text: 'Frase verificada. Puedes aprobarla para guardarla.' })
    } catch (error) {
      updateItem(item.key, { error: error.message })
    } finally {
      setVerifyingId(null)
    }
  }

  const saveApproved = async () => {
    const approved = items.filter((item) => item.selected && item.status === 'valid')
    if (approved.length === 0) return
    setSaving(true)
    setMessage(null)
    try {
      const result = await saveTexts(approved.map((item) => item.content), generation.language, token)
      if (result.phrases.length !== approved.length) throw new Error('La respuesta del servidor está incompleta. Revisa las frases antes de repetir el guardado.')
      const savedByKey = new Map(approved.map((item, index) => [item.key, result.phrases[index]]))
      setItems((current) => current.map((item) => {
        const saved = savedByKey.get(item.key)
        return saved ? { ...item, ...saved, selected: false, discarded: false, draft: saved.content } : item
      }))
      setMessage({
        tone: 'success',
        text: `${result.stored} guardadas, ${result.duplicates} duplicadas y ${result.rejected} rechazadas al guardar.`,
      })
    } catch (error) {
      setMessage({ tone: 'error', text: error.message })
    } finally {
      setSaving(false)
    }
  }

  if (status === 'loading') return <p className="texts-session">Comprobando sesión...</p>
  if (!token) return (
    <section className="texts-page texts-auth">
      <h1>Revisa frases para practicar</h1>
      <p>Inicia sesión para generar, revisar y guardar frases.</p>
      <Link to="/login" className="button button--primary">Iniciar sesión</Link>
    </section>
  )

  return (
    <section className="texts-page">
      <header className="texts-header">
        <h1>Revisión de frases</h1>
        <p className="texts-intro">Genera un lote, revisa cada frase y guarda solo las que apruebes.</p>
        <div className="texts-language-control">
          <label htmlFor="texts-language">Idioma de las nuevas frases</label>
          <select id="texts-language" value={language} onChange={(event) => setLanguage(event.target.value)} disabled={busy}>
            <option value="spa">Español</option>
            <option value="eng">Inglés</option>
          </select>
        </div>
        {generation && <Button onClick={generate} disabled={busy} isLoading={generating}>Generar otro lote</Button>}
      </header>

      {message && <p role={message.tone === 'error' ? 'alert' : 'status'} className={`texts-message texts-message--${message.tone}`}>{message.text}</p>}

      {!generation && (
        <div className="texts-empty">
          <span className="texts-empty-icon" aria-hidden="true">“ ”</span>
          <h2>Tu mesa de revisión está lista</h2>
          <p>Genera frases para ver su dificultad y estado. Podrás corregir las observadas y aprobar las que quieras guardar.</p>
          <Button onClick={generate} disabled={busy} isLoading={generating}>Generar primer lote</Button>
        </div>
      )}

      {generation && (
        <>
          <div className="texts-overview">
            <div className="texts-overview-heading">
              <div>
                <p className="texts-overview-label">Lote actual · {generation.language === 'spa' ? 'Español' : 'Inglés'}</p>
                <h2>{generation.generated} frases generadas</h2>
              </div>
              <p>Aprueba las frases aptas. Las duplicadas o rechazadas pueden editarse y verificarse de nuevo.</p>
            </div>
            <div className="texts-metrics">
              <div><strong>{counts.pending}</strong><span>Por revisar</span></div>
              <div><strong>{counts.approved}</strong><span>Aprobadas</span></div>
              <div><strong>{counts.issues}</strong><span>Observadas</span></div>
              <div><strong>{counts.stored}</strong><span>Guardadas</span></div>
            </div>
          </div>

          <div className="texts-list-header">
            <div>
              <h2>Frases del lote</h2>
              <p>Selecciona una frase para aprobarla o edítala antes de verificarla.</p>
            </div>
            <span>{visibleItems.length} de {items.length}</span>
          </div>

          <div className="texts-filters" aria-label="Filtrar frases">
            {filters.map((option) => (
              <button
                key={option.id}
                type="button"
                className="texts-filter"
                aria-pressed={filter === option.id}
                onClick={() => setFilter(option.id)}
              >
                {option.label}
                <span>{option.id === 'all' ? items.length : counts[option.id]}</span>
              </button>
            ))}
          </div>

          {visibleItems.length === 0 ? (
            <div className="texts-filter-empty">No hay frases en este estado.</div>
          ) : (
            <ol className="texts-list">
              {visibleItems.map((item) => {
                const reviewState = getReviewState(item)
                const expected = expectedWords(item.key)
                const wordCount = countWords(item.editing ? item.draft : item.content)
                const wordCountValid = wordCount === expected
                return (
                  <li key={item.key} className={`texts-card texts-card--${reviewState}`}>
                    <div className="texts-card-top">
                      <span className="texts-number">Frase {String(item.key + 1).padStart(2, '0')}</span>
                      <div className="texts-tags">
                        {item.difficulty && <span className="texts-difficulty">{difficultyLabels[item.difficulty] || item.difficulty}</span>}
                        <span className={`texts-status texts-status--${reviewState}`}>{getStatusLabel(item)}</span>
                      </div>
                    </div>
                    <p className={`texts-word-count ${wordCountValid ? 'texts-word-count--valid' : 'texts-word-count--invalid'}`} aria-live={item.editing ? 'polite' : undefined}>
                      {wordCount} palabras <span>· objetivo {expected}</span>
                    </p>

                    {item.editing ? (
                      <div className="texts-editor">
                        <label htmlFor={`phrase-${item.key}`}>Editar frase</label>
                        <textarea
                          id={`phrase-${item.key}`}
                          value={item.draft}
                          onChange={(event) => updateItem(item.key, { draft: event.target.value, error: '' })}
                          rows={3}
                          maxLength={5000}
                          disabled={busy}
                        />
                        <p className="texts-editor-hint">La verificación comprueba el texto y vuelve a calcular su dificultad.</p>
                        {item.error && <p className="texts-item-error" role="alert">{item.error}</p>}
                        <div className="texts-actions">
                          <Button size="sm" onClick={() => verify(item)} disabled={busy} isLoading={verifyingId === item.key}>Verificar cambios</Button>
                          <Button size="sm" variant="ghost" disabled={busy} onClick={() => updateItem(item.key, { editing: false, draft: item.content, error: '' })}>Cancelar</Button>
                        </div>
                      </div>
                    ) : (
                      <>
                        <p className="texts-content">{item.content}</p>
                        {item.reasonCode && <p className="texts-reason">{item.reasonCode === 'word_count_mismatch' ? `Esta frase debe tener exactamente ${expected} palabras.` : reasonLabels[item.reasonCode] || `Motivo: ${item.reasonCode}`}</p>}
                        {item.id != null && <p className="texts-saved-id">Guardada como frase #{item.id}</p>}
                        {item.status !== 'stored' && (
                          <div className="texts-actions">
                            {item.status === 'valid' && !item.discarded && (
                              <Button size="sm" variant={item.selected ? 'secondary' : 'primary'} disabled={busy} onClick={() => updateItem(item.key, { selected: !item.selected })}>
                                {item.selected ? 'Quitar aprobación' : 'Aprobar frase'}
                              </Button>
                            )}
                            <Button size="sm" variant="ghost" disabled={busy} onClick={() => updateItem(item.key, { editing: true, selected: false, discarded: false, draft: item.content, error: '' })}>Editar y verificar</Button>
                            <Button size="sm" variant="ghost" disabled={busy} onClick={() => updateItem(item.key, { discarded: !item.discarded, selected: false })}>
                              {item.discarded ? 'Restaurar' : 'Descartar'}
                            </Button>
                          </div>
                        )}
                      </>
                    )}
                  </li>
                )
              })}
            </ol>
          )}

          <div className="texts-save-bar">
            <div><strong>{counts.approved} {counts.approved === 1 ? 'frase aprobada' : 'frases aprobadas'}</strong><span>Solo estas frases se enviarán a la base de datos.</span></div>
            <Button onClick={saveApproved} disabled={busy || counts.approved === 0} isLoading={saving}>
              Guardar aprobadas
            </Button>
          </div>
        </>
      )}
    </section>
  )
}
