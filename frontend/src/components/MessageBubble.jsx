import { useState } from "react";
import { BookOpen, ChevronDown, ChevronUp, Bot, User } from "lucide-react";
import SourcesPanel from "./SourcesPanel";

/**
 * Render the answer text, converting [Source N] references
 * into styled citation badges and `backtick` spans into code.
 */
function renderAnswerText(text) {
  if (!text) return null;

  // Split on [Source N] patterns and inline code
  const parts = text.split(/(\[Source \d+\]|`[^`]+`)/g);

  return parts.map((part, i) => {
    // Citation reference
    const citationMatch = part.match(/^\[Source (\d+)\]$/);
    if (citationMatch) {
      return (
        <span key={i} className="citation-ref">
          {citationMatch[1]}
        </span>
      );
    }

    // Inline code
    if (part.startsWith("`") && part.endsWith("`")) {
      return <code key={i}>{part.slice(1, -1)}</code>;
    }

    return <span key={i}>{part}</span>;
  });
}

export default function MessageBubble({ message }) {
  const [showSources, setShowSources] = useState(false);
  const isUser = message.role === "user";
  const hasSources = message.sources && message.sources.length > 0;

  return (
    <div className={`message-row ${message.role}`}>
      <div className={`message-avatar ${isUser ? "human" : "ai"}`}>
        {isUser ? <User size={16} /> : <Bot size={16} />}
      </div>

      <div className="message-content">
        <div className="message-bubble">
          {isUser ? message.content : renderAnswerText(message.content)}
        </div>

        {/* Source toggle + latency — only for assistant messages with sources */}
        {!isUser && hasSources && (
          <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
            <button
              className="sources-toggle"
              onClick={() => setShowSources((v) => !v)}
            >
              <BookOpen size={13} />
              <span>
                {message.sources.length} source
                {message.sources.length !== 1 ? "s" : ""}
              </span>
              <span
                className={`toggle-dot ${message.citationReport?.passed ? "pass" : "fail"}`}
              />
              {showSources ? (
                <ChevronUp size={13} />
              ) : (
                <ChevronDown size={13} />
              )}
            </button>

            {message.latencyMs && (
              <span className="latency-badge">{message.latencyMs.toFixed(0)} ms</span>
            )}
          </div>
        )}

        {/* Expanded sources panel */}
        {showSources && hasSources && (
          <SourcesPanel
            sources={message.sources}
            citationReport={message.citationReport}
          />
        )}
      </div>
    </div>
  );
}
