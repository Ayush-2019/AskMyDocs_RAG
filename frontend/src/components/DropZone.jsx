import { useState, useRef } from "react";
import { Upload } from "lucide-react";

const ALLOWED_TYPES = [".md", ".html", ".htm", ".txt"];

export default function DropZone({ onFiles, disabled }) {
  const [dragOver, setDragOver] = useState(false);
  const inputRef = useRef(null);

  function handleDrop(e) {
    e.preventDefault();
    setDragOver(false);
    if (disabled) return;

    const dropped = Array.from(e.dataTransfer.files).filter((f) =>
      ALLOWED_TYPES.some((ext) => f.name.toLowerCase().endsWith(ext))
    );
    if (dropped.length) onFiles(dropped);
  }

  function handleFileSelect(e) {
    const selected = Array.from(e.target.files);
    if (selected.length) onFiles(selected);
    e.target.value = "";
  }

  return (
    <div
      className={`dropzone ${dragOver ? "drag-over" : ""}`}
      onDragOver={(e) => {
        e.preventDefault();
        if (!disabled) setDragOver(true);
      }}
      onDragLeave={() => setDragOver(false)}
      onDrop={handleDrop}
      onClick={() => !disabled && inputRef.current?.click()}
      style={disabled ? { opacity: 0.5, cursor: "not-allowed" } : {}}
    >
      <div className="dropzone-icon">
        <Upload size={22} />
      </div>
      <div className="dropzone-text">
        Drop files here, or <strong>browse</strong>
      </div>
      <div className="dropzone-hint">
        Supports {ALLOWED_TYPES.join(", ")} files
      </div>
      <input
        ref={inputRef}
        type="file"
        multiple
        accept={ALLOWED_TYPES.join(",")}
        style={{ display: "none" }}
        onChange={handleFileSelect}
      />
    </div>
  );
}
