import { useState } from 'react'
import QueryPanel from './components/QueryPanel'
import ResponsePanel from './components/ResponsePanel'
import TracePanel from './components/TracePanel'
import './App.css'

const API_BASE = 'http://localhost:5000'

export default function App() {
  const [query, setQuery] = useState('')
  const [result, setResult] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)

  async function runQuery(q) {
    setQuery(q)
    setLoading(true)
    setError(null)
    setResult(null)
    try {
      const res = await fetch(`${API_BASE}/api/query`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ query: q }),
      })
      const data = await res.json()
      if (data.error) setError(data.error)
      else setResult(data)
    } catch (e) {
      setError('Could not reach the API server. Make sure it is running on port 5000.')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="app">
      <header className="app-header">
        <div className="header-inner">
          <span className="logo">⚡ TableRAG</span>
          <span className="subtitle">Hybrid SQL + Semantic Article Search</span>
        </div>
      </header>

      <main className="app-main">
        <QueryPanel onQuery={runQuery} loading={loading} activeQuery={query} />

        <div className="results-area">
          <ResponsePanel response={result?.response} loading={loading} error={error} query={query} />
          <TracePanel steps={result?.steps} toolPath={result?.tool_path} loading={loading} />
        </div>
      </main>
    </div>
  )
}
