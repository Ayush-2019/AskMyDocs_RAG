import { Check, X, ExternalLink } from "lucide-react";

function DensityBar({ density }) {
  const pct = Math.round(density * 100);
  const cls = pct >= 80 ? "good" : pct >= 50 ? "warn" : "bad";

  return (
    <div>
      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          marginBottom: 2,
        }}
      >
        <span className="report-label">Citation density</span>
        <span className="report-value">{pct}%</span>
      </div>
      <div className="density-bar-track">
        <div
          className={`density-bar-fill ${cls}`}
          style={{ width: `${pct}%` }}
        />
      </div>
    </div>
  );
}

export default function SourcesPanel({ sources, citationReport }) {
  if (!sources || sources.length === 0) return null;

  return (
    <div className="sources-panel">
      {/* Source list */}
      <div className="sources-panel-header">
        <h4>Sources ({sources.length})</h4>
      </div>

      {sources.map((src) => (
        <div key={src.source_index} className="source-item">
          <div className="source-index">{src.source_index}</div>
          <div className="source-details">
            <div className="source-heading">{src.heading}</div>
            <div className="source-path">{src.section_path}</div>
          </div>
          <div className="source-score">
            {(src.relevance_score * 100).toFixed(1)}%
          </div>
        </div>
      ))}

      {/* Citation report */}
      {citationReport && (
        <div className="citation-report">
          <h5>Citation report</h5>

          <div className="report-grid">
            <div className="report-item">
              <span className="report-label">Status</span>
              <span
                className={`pass-badge ${citationReport.passed ? "pass" : "fail"}`}
              >
                {citationReport.passed ? (
                  <>
                    <Check size={12} /> Passed
                  </>
                ) : (
                  <>
                    <X size={12} /> Failed
                  </>
                )}
              </span>
            </div>

            <div className="report-item">
              <span className="report-label">Valid citations</span>
              <span className="report-value">
                {citationReport.valid_citations?.length || 0}
              </span>
            </div>

            {citationReport.invalid_citations?.length > 0 && (
              <div className="report-item">
                <span className="report-label">Invalid citations</span>
                <span className="report-value" style={{ color: "var(--red-500)" }}>
                  {citationReport.invalid_citations.join(", ")}
                </span>
              </div>
            )}

            {citationReport.uncited_sentences?.length > 0 && (
              <div className="report-item" style={{ gridColumn: "1 / -1" }}>
                <span className="report-label">
                  Uncited sentences ({citationReport.uncited_sentences.length})
                </span>
                <div style={{ marginTop: 4 }}>
                  {citationReport.uncited_sentences.map((s, i) => (
                    <div
                      key={i}
                      style={{
                        fontSize: 12,
                        color: "var(--gray-600)",
                        padding: "2px 0",
                        borderLeft: "2px solid var(--amber-100)",
                        paddingLeft: 8,
                        marginBottom: 4,
                      }}
                    >
                      {s}
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>

          <div style={{ marginTop: 12 }}>
            <DensityBar density={citationReport.citation_density || 0} />
          </div>
        </div>
      )}
    </div>
  );
}
