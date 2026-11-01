import { useState } from 'react'
import { Link } from 'react-router-dom'
import { useAuth } from '../../auth/context/auth-context'
import { generateTexts, saveTexts } from '../services/textService'

const statusLabel = {
  valid: 'Lista para subir',
  stored: 'Guardada',
  duplicate: 'Duplicada',
  rejected: 'Rechazada',
}

const reasonLabel = {
  difficulty_quota: 'Ya se guardaron 10 frases de esta dificultad.',
}

export default function Texts() {
  const { token, status } = useAuth()
  const [result, setResult] = useState(null)
  const [generating, setGenerating] = useState(false)
  const [saving, setSaving] = useState(false)
  const [uploaded, setUploaded] = useState(false)
  const [message, setMessage] = useState('')

  const generate = async () => {
    setGenerating(true)
    setResult(null)
    setUploaded(false)
    setMessage('')
    try {
      const generated = await generateTexts(token)
      setResult(generated)
      setMessage(
        `${generated.generated} generadas, ${generated.valid} listas para subir, ` +
        `${generated.duplicates} duplicadas y ${generated.rejected} rechazadas.`,
      )
    } catch (error) {
      setMessage(error.message)
    } finally {
      setGenerating(false)
    }
  }

  const saveAll = async () => {
    const phrases = result.phrases
      .filter((phrase) => phrase.status === 'valid')
      .map((phrase) => phrase.content)
    setSaving(true)
    setMessage('')
    try {
      const saved = await saveTexts(phrases, token)
      const byContent = new Map(saved.phrases.map((phrase) => [phrase.content, phrase]))
      setResult((previous) => ({
        ...previous,
        phrases: previous.phrases.map((phrase) =>
          phrase.status === 'valid' ? byContent.get(phrase.content) || phrase : phrase,
        ),
      }))
      setUploaded(true)
      setMessage(
        `${saved.stored} guardadas, ${saved.duplicates} duplicadas y ` +
        `${saved.rejected} rechazadas al subir.`,
      )
    } catch (error) {
      setMessage(error.message)
    } finally {
      setSaving(false)
    }
  }

  if (status === 'loading') return <p>Comprobando sesión...</p>
  if (!token) return <p>Inicia sesión para gestionar frases. <Link to="/login">Iniciar sesión</Link></p>

  return (
    <section>
      <h1>Frases</h1>
      <button type="button" disabled={generating || saving} onClick={generate}>
        {generating ? 'Generando...' : 'Generar frases'}
      </button>
      {result?.valid > 0 && !uploaded && (
        <button type="button" disabled={generating || saving} onClick={saveAll}>
          {saving ? 'Subiendo...' : 'Subir todas'}
        </button>
      )}
      {message && <p role="status">{message}</p>}
      {result && (
        <ol>
          {result.phrases.map((phrase, index) => (
            <li key={index}>
              <hr />
              <p>Frase {index + 1}: {phrase.content}</p>
              <p>{statusLabel[phrase.status]}</p>
              {phrase.difficulty && <p>Dificultad: {phrase.difficulty}</p>}
              {phrase.id != null && <p>ID: {phrase.id}</p>}
              {phrase.reasonCode && (
                <p>Motivo: {reasonLabel[phrase.reasonCode] || phrase.reasonCode}</p>
              )}
            </li>
          ))}
        </ol>
      )}
    </section>
  )
}
