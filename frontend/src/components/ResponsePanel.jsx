import ReactMarkdown from 'react-markdown'

export default function ResponsePanel({ response, loading, error, query }) {
  return (
    <section className="response-panel glass-panel">
      <div className="panel-header">
        <span className="panel-icon">📄</span>
        <span className="panel-title">Response</span>
      </div>

      {query && (
        <div className="active-query-badge">
          <span className="aq-label">Query:</span>
          <span className="aq-text">{query}</span>
        </div>
      )}

      <div className="response-body">
        {loading && (
          <div className="loading-state">
            <div className="pulse-ring" />
            <span>Thinking...</span>
          </div>
        )}

        {error && !loading && (
          <div className="error-box">
            <span className="error-icon">⚠️</span>
            <span>{error}</span>
          </div>
        )}

        {!loading && !error && !response && (
          <div className="empty-state">
            <div className="empty-icon">🔍</div>
            <p>Select a preset query or type your own to get started.</p>
          </div>
        )}

        {!loading && !error && response && (
          <div className="response-text markdown-body">
            <ReactMarkdown>{response}</ReactMarkdown>
          </div>
        )}
      </div>
    </section>
  )
}
