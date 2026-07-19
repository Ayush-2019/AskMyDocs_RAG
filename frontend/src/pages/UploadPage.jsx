import { useState, useCallback } from "react";
import { ArrowRight, Loader2 } from "lucide-react";
import DropZone from "../components/DropZone";
import FileCard from "../components/FileCard";
import { uploadFiles } from "../api";

let fileIdCounter = 0;

export default function UploadPage({ onStartChat }) {
  const [files, setFiles] = useState([]);
  const [isUploading, setIsUploading] = useState(false);
  const [totalChunks, setTotalChunks] = useState(0);

  const handleAddFiles = useCallback((newFiles) => {
    const entries = newFiles.map((f) => ({
      id: ++fileIdCounter,
      name: f.name,
      size: f.size,
      raw: f,
      status: "pending",
      chunks: 0,
      error: null,
    }));
    setFiles((prev) => [...prev, ...entries]);
  }, []);

  const handleRemoveFile = useCallback((id) => {
    setFiles((prev) => prev.filter((f) => f.id !== id));
  }, []);

  const handleProcess = useCallback(async () => {
    const pending = files.filter((f) => f.status === "pending");
    if (pending.length === 0) return;

    setIsUploading(true);

    // Mark all pending files as processing
    setFiles((prev) =>
      prev.map((f) =>
        f.status === "pending" ? { ...f, status: "processing" } : f
      )
    );

    try {
      const rawFiles = pending.map((f) => f.raw);
      const response = await uploadFiles(rawFiles);

      // Match results back to our file objects by filename
      setFiles((prev) =>
        prev.map((f) => {
          if (f.status !== "processing") return f;
          const result = response.results.find(
            (r) => r.filename === f.name
          );
          if (!result) return { ...f, status: "error", error: "No response" };
          if (result.error)
            return { ...f, status: "error", error: result.error };
          return { ...f, status: "done", chunks: result.chunks || 0 };
        })
      );

      setTotalChunks((prev) => prev + (response.total_chunks || 0));
    } catch (err) {
      // Mark all processing files as errored
      setFiles((prev) =>
        prev.map((f) =>
          f.status === "processing"
            ? { ...f, status: "error", error: err.message }
            : f
        )
      );
    } finally {
      setIsUploading(false);
    }
  }, [files]);

  const hasPending = files.some((f) => f.status === "pending");
  const hasDone = files.some((f) => f.status === "done");

  return (
    <div className="upload-page">
      <h1 className="upload-title">Upload your documents</h1>
      <p className="upload-subtitle">
        Add Markdown, HTML, or text files. They'll be chunked, embedded, and
        indexed for hybrid retrieval.
      </p>

      <DropZone onFiles={handleAddFiles} disabled={isUploading} />

      {files.length > 0 && (
        <div className="file-list">
          {files.map((f) => (
            <FileCard key={f.id} file={f} onRemove={handleRemoveFile} />
          ))}
        </div>
      )}

      {files.length > 0 && (
        <div className="action-bar">
          <div className="stats-text">
            {totalChunks > 0 && <span>{totalChunks} chunks indexed</span>}
          </div>

          <div style={{ display: "flex", gap: 10 }}>
            {hasPending && (
              <button
                className="btn-secondary"
                onClick={handleProcess}
                disabled={isUploading}
              >
                {isUploading && <Loader2 size={15} className="spinner" />}
                {isUploading ? "Processing..." : "Process files"}
              </button>
            )}

            {hasDone && (
              <button className="btn-primary" onClick={onStartChat}>
                Start chatting
                <ArrowRight size={16} />
              </button>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
