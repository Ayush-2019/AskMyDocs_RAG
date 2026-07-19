import { useState, useEffect } from "react";
import { BookOpen, ChevronLeft, Wifi, WifiOff } from "lucide-react";
import UploadPage from "./pages/UploadPage";
import ChatPage from "./pages/ChatPage";
import { checkHealth } from "./api";

export default function App() {
  const [page, setPage] = useState("upload"); // "upload" | "chat"
  const [health, setHealth] = useState(null); // { status, chunk_count }

  // Poll health on mount and when returning to upload page
  useEffect(() => {
    let cancelled = false;

    async function poll() {
      try {
        const data = await checkHealth();
        if (!cancelled) setHealth(data);
      } catch {
        if (!cancelled) setHealth({ status: "unreachable", chunk_count: 0 });
      }
    }

    poll();
    const interval = setInterval(poll, 15000);
    return () => {
      cancelled = true;
      clearInterval(interval);
    };
  }, [page]);

  const isHealthy = health?.status === "healthy";

  return (
    <div className="app-shell">
      {/* Header */}
      <header className="header">
        {page === "chat" && (
          <button className="back-btn" onClick={() => setPage("upload")}>
            <ChevronLeft size={15} />
            Documents
          </button>
        )}

        <div className="header-logo">
          <BookOpen size={20} />
          <span>Ask My Docs</span>
        </div>

        <div className="header-spacer" />

        {health && (
          <span className={`header-pill ${isHealthy ? "healthy" : "unhealthy"}`}>
            {isHealthy ? <Wifi size={12} /> : <WifiOff size={12} />}
            {isHealthy
              ? `${health.chunk_count} chunks`
              : "Backend offline"}
          </span>
        )}
      </header>

      {/* Pages */}
      {page === "upload" && (
        <UploadPage onStartChat={() => setPage("chat")} />
      )}
      {page === "chat" && <ChatPage />}
    </div>
  );
}
