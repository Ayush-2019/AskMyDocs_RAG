import { FileText, Loader2, Check, AlertCircle, X } from "lucide-react";

function StatusIcon({ status }) {
  if (status === "processing")
    return <Loader2 size={16} className="spinner" />;
  if (status === "done") return <Check size={16} />;
  if (status === "error") return <AlertCircle size={16} />;
  return <FileText size={16} />;
}

function formatSize(bytes) {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

export default function FileCard({ file, onRemove }) {
  const status = file.status || "pending";

  return (
    <div className="file-card">
      <div className={`file-icon ${status}`}>
        <StatusIcon status={status} />
      </div>

      <div className="file-info">
        <div className="file-name">{file.name}</div>
        <div className="file-meta">
          <span>{formatSize(file.size)}</span>
          {status === "done" && file.chunks > 0 && (
            <span className="chunks-badge">{file.chunks} chunks</span>
          )}
          {status === "processing" && <span>Processing...</span>}
          {status === "error" && (
            <span style={{ color: "var(--red-500)" }}>
              {file.error || "Failed"}
            </span>
          )}
        </div>
      </div>

      {(status === "pending" || status === "done") && (
        <button
          className="file-remove"
          onClick={() => onRemove(file.id)}
          title="Remove file"
        >
          <X size={14} />
        </button>
      )}
    </div>
  );
}
