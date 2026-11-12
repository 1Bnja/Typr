import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { MemoryRouter } from 'react-router-dom'
import App from './app'
import { AuthContext } from './features/auth/context/auth-context'
import TestResults from './features/practice/components/test-results'
import './index.css'
import './features/practice/practice.css'
const params = new URLSearchParams(location.search)
const originalFetch = window.fetch
window.fetch = async (url, options) => {
  if (String(url).startsWith('/api/v1/matches/')) {
    if (options?.method === 'POST') {
      document.documentElement.dataset.payload = options.body
      return Response.json({ id: 1, textId: 1 })
    }
    return Response.json([])
  }
  if (String(url).startsWith('/api/')) throw new Error('Unexpected preview request')
  return originalFetch(url, options)
}
const samples = params.has('short') ? [{timeMs: 750, ppm: 160, errors: 0}] : [60,75,86,81,95,105,99,110,113,104].map((ppm,index) => ({timeMs:(index+1)*1000, ppm, errors:index < 4 ? 0 : index < 7 ? 1 : 2}))
createRoot(document.getElementById('root')).render(<StrictMode>
{params.has('short') || params.has('example') ? <section className="practice practice--results"><header className="practice-header"><h1>Your results</h1><p>English · Easy · 20 words</p></header><TestResults language={params.has('spa')?'spa':'eng'} result={{ppm:samples.at(-1).ppm, precisionPct:98, score:102,timeMs:samples.at(-1).timeMs,speedHistory:samples}} saveStatus="saved" onNewText={()=>{}} onChangeSettings={()=>{}} /></section> : <AuthContext.Provider value={{status:'authenticated', token:'preview', user:{username:'preview',id:1},signOut:()=>{}}}><MemoryRouter initialEntries={['/practice?language=eng']}><App /></MemoryRouter></AuthContext.Provider>}
</StrictMode>)
