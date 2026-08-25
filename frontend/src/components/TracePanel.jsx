export default function TracePanel({ steps, toolPath, loading }) {
  const pathLabel = {
    sql: '⚡ SQL Path',
    vector: '🧠 Vector Path',
    hybrid: '⚡🧠 Hybrid Path',
    none: '—',
  }[toolPath] ?? '—'

  return (
    <section className="trace-panel glass-panel">
      <div className="panel-header">
        <span className="panel-icon">🗺️</span>
        <span className="panel-title">Query Trace</span>
        {toolPath && !loading && (
          <span className={`path-badge path-${toolPath}`}>{pathLabel}</span>
        )}
      </div>

      <div className="trace-log">
        <div className="trace-entry">
          <span className="trace-actor">User:</span>
          <span className="trace-action">Submitted query</span>
        </div>
        
        {loading && (
          <div className="trace-entry pulsing">
            <span className="trace-actor">Router:</span>
            <span className="trace-action">Thinking...</span>
          </div>
        )}

        {steps && steps.map((step, i) => {
          if (step.type === 'classification') {
            return (
              <div key={i} className="trace-entry trace-classification">
                <span className="trace-actor">🔍 Classification:</span>
                <span className="trace-action"><strong>{step.label}</strong></span>
              </div>
            )
          } else if (step.type === 'tool_call') {
            return (
              <div key={i} className="trace-entry">
                <span className="trace-actor">Router:</span>
                <span className="trace-action">
                  Selected tool <strong>{step.tool}</strong> with args: 
                  <code>{JSON.stringify(step.args)}</code>
                </span>
              </div>
            )
          } else {
            return (
              <div key={i} className="trace-entry trace-result">
                <span className="trace-actor">{step.tool}:</span>
                <span className="trace-action">
                  Returned {step.output?.length} characters of output
                </span>
                <div className="trace-output-preview">
                  {step.output?.slice(0, 200)}
                  {step.output?.length > 200 ? '...' : ''}
                </div>
              </div>
            )
          }
        })}

        {!loading && toolPath !== undefined && (
          <div className="trace-entry">
            <span className="trace-actor">Router:</span>
            <span className="trace-action">Generated final response</span>
          </div>
        )}
      </div>
    </section>
  )
}
