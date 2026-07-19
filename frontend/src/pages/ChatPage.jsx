import { useState, useRef, useEffect, useCallback } from "react";
import { Send, MessageSquare } from "lucide-react";
import MessageBubble from "../components/MessageBubble";
import { askQuestion } from "../api";

const STARTER_QUESTIONS = [
  "How do I configure OAuth2?",
  "What environment variables are required?",
  "What are the system requirements?",
  "How do I fix 'Connection refused on port 5432'?",
];

export default function ChatPage() {
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const messagesEndRef = useRef(null);
  const textareaRef = useRef(null);

  // Auto-scroll to the latest message
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, isLoading]);

  // Auto-resize textarea
  useEffect(() => {
    if (textareaRef.current) {
      textareaRef.current.style.height = "auto";
      textareaRef.current.style.height =
        Math.min(textareaRef.current.scrollHeight, 120) + "px";
    }
  }, [input]);

  const sendMessage = useCallback(
    async (text) => {
      const question = text.trim();
      if (!question || isLoading) return;

      // Add user message
      const userMsg = {
        id: Date.now(),
        role: "user",
        content: question,
      };
      setMessages((prev) => [...prev, userMsg]);
      setInput("");
      setIsLoading(true);

      try {
        const response = await askQuestion(question);

        const assistantMsg = {
          id: Date.now() + 1,
          role: "assistant",
          content: response.answer,
          sources: response.sources,
          citationReport: response.citation_report,
          latencyMs: response.latency_ms,
          retrievalCount: response.retrieval_count,
        };
        setMessages((prev) => [...prev, assistantMsg]);
      } catch (err) {
        const errorMsg = {
          id: Date.now() + 1,
          role: "assistant",
          content: `Sorry, something went wrong: ${err.message}. Make sure the backend is running on port 8000.`,
          sources: [],
          citationReport: null,
        };
        setMessages((prev) => [...prev, errorMsg]);
      } finally {
        setIsLoading(false);
        textareaRef.current?.focus();
      }
    },
    [isLoading]
  );

  function handleKeyDown(e) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      sendMessage(input);
    }
  }

  const isEmpty = messages.length === 0;

  return (
    <div className="chat-page">
      <div className="chat-messages">
        {/* Welcome state */}
        {isEmpty && !isLoading && (
          <div className="chat-welcome">
            <div className="chat-welcome-icon">
              <MessageSquare size={24} />
            </div>
            <h2>Ask your documents</h2>
            <p>
              Your documents have been indexed. Ask any question and get an
              answer with source citations.
            </p>
            <div className="starter-chips">
              {STARTER_QUESTIONS.map((q) => (
                <button
                  key={q}
                  className="starter-chip"
                  onClick={() => sendMessage(q)}
                >
                  {q}
                </button>
              ))}
            </div>
          </div>
        )}

        {/* Messages */}
        {messages.map((msg) => (
          <MessageBubble key={msg.id} message={msg} />
        ))}

        {/* Typing indicator */}
        {isLoading && (
          <div className="message-row assistant">
            <div className="message-avatar ai">
              <MessageSquare size={14} />
            </div>
            <div className="message-content">
              <div className="message-bubble" style={{ padding: "4px 8px" }}>
                <div className="typing-dots">
                  <span />
                  <span />
                  <span />
                </div>
              </div>
            </div>
          </div>
        )}

        <div ref={messagesEndRef} />
      </div>

      {/* Input bar */}
      <div className="chat-input-bar">
        <div className="chat-input-row">
          <textarea
            ref={textareaRef}
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Ask a question about your documents..."
            rows={1}
            disabled={isLoading}
          />
          <button
            className="send-btn"
            onClick={() => sendMessage(input)}
            disabled={!input.trim() || isLoading}
          >
            <Send size={18} />
          </button>
        </div>
      </div>
    </div>
  );
}
