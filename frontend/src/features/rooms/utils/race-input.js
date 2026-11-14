// Regla de la carrera: ante un error el cursor se bloquea. No se avanza ni se
// cuenta progreso hasta borrar el carácter equivocado.

export const initialRaceInput = (typed = 0, errors = 0) => ({ typed, errors, wrong: null })

// Lo que muestra el campo: lo correcto hasta ahora más, si lo hay, el error pendiente.
export const raceInputValue = (state, content) => content.slice(0, state.typed) + (state.wrong ?? '')

export function applyRaceInput(state, value, content) {
  if (state.typed >= content.length) return state
  const prefix = content.slice(0, state.typed)
  if (state.wrong !== null) {
    // Bloqueado: lo único que se acepta es borrar el carácter equivocado.
    return value === prefix ? { ...state, wrong: null } : state
  }
  // Lo ya escrito bien es definitivo: no se puede borrar ni reemplazar.
  if (!value.startsWith(prefix) || value.length <= prefix.length) return state

  let { typed, errors } = state
  for (let index = prefix.length; index < value.length && typed < content.length; index++) {
    if (value[index] !== content[typed]) {
      return { typed, errors: errors + 1, wrong: value[index] }
    }
    typed += 1
  }
  return { typed, errors, wrong: null }
}
