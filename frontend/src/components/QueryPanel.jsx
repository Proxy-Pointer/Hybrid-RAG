import { useState, useEffect } from 'react'

const STRATEGY_COLORS = {
  aggregation: '#f6c23e',
  sql: '#4e9af1',
  semantic: '#6bcf7f',
  hybrid: '#c084fc',
}

const STRATEGY_LABELS = {
  aggregation: 'Aggregation',
  sql: 'SQL Listing',
  semantic: 'Semantic',
  hybrid: 'Hybrid',
}

export default function QueryPanel({ onQuery, loading, activeQuery }) {
  const [customQuery, setCustomQuery] = useState('')
  const [presets, setPresets] = useState([])

  useEffect(() => {
    let attempts = 0
    const maxAttempts = 10

    function fetchPresets() {
      fetch('http://localhost:5000/api/queries')
        .then((r) => r.json())
        .then((data) => setPresets(data.queries ?? []))
        .catch(() => {
          attempts++
          if (attempts < maxAttempts) {
            setTimeout(fetchPresets, 2000) // retry every 2s while backend is starting
          }
        })
    }

    fetchPresets()
  }, [])

  function handleCustomSubmit(e) {
    e.preventDefault()
    if (customQuery.trim()) {
      onQuery(customQuery.trim())
    }
  }

  return (
    <aside className="query-panel">
      <div className="panel-title">Preset Queries</div>

      <div className="strategy-legend">
        {Object.entries(STRATEGY_COLORS).map(([k, color]) => (
          <span key={k} className="legend-item">
            <span className="legend-dot" style={{ background: color }} />
            {STRATEGY_LABELS[k]}
          </span>
        ))}
      </div>

      <div className="query-buttons">
        {presets.map((q) => (
          <button
            key={q.id}
            className={`query-btn ${activeQuery === q.query ? 'active' : ''}`}
            style={{ '--accent': STRATEGY_COLORS[q.strategy] ?? '#888' }}
            onClick={() => !loading && onQuery(q.query)}
            disabled={loading}
            title={q.query}
          >
            <span className="btn-dot" style={{ background: STRATEGY_COLORS[q.strategy] ?? '#888' }} />
            <span className="btn-label">{q.label}</span>
          </button>
        ))}
      </div>

      <div className="custom-query-section">
        <div className="panel-title" style={{ marginBottom: '0.75rem' }}>Custom Query</div>
        <form onSubmit={handleCustomSubmit} className="custom-form">
          <textarea
            className="custom-input"
            value={customQuery}
            onChange={(e) => setCustomQuery(e.target.value)}
            placeholder="Ask anything about the articles..."
            rows={3}
            disabled={loading}
            onKeyDown={(e) => {
              if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault()
                handleCustomSubmit(e)
              }
            }}
          />
          <button type="submit" className="send-btn" disabled={loading || !customQuery.trim()}>
            {loading ? <span className="spinner" /> : '↵ Send'}
          </button>
        </form>
      </div>
    </aside>
  )
}
