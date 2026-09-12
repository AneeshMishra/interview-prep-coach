import { useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { ApiError, createChatSession, listChatMessages, sendChatMessage } from "../api/client";
import type { ChatMessageRecord } from "../api/types";
import { ErrorMessage, Loading } from "../components/StatusStates";

export function ChatPage() {
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [messages, setMessages] = useState<ChatMessageRecord[]>([]);
  const [draft, setDraft] = useState("");
  const [sending, setSending] = useState(false);
  const [initError, setInitError] = useState<string | null>(null);
  const [sendError, setSendError] = useState<string | null>(null);
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    let cancelled = false;
    createChatSession()
      .then(async (session) => {
        if (cancelled) return;
        setSessionId(session.id);
        const history = await listChatMessages(session.id);
        if (!cancelled) setMessages(history);
      })
      .catch((err) => {
        if (!cancelled) {
          setInitError(err instanceof ApiError ? err.message : "Failed to start a chat session.");
        }
      });
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    // Optional chaining on the call itself, not just `.current` — jsdom
    // (used in tests) doesn't implement scrollIntoView at all.
    bottomRef.current?.scrollIntoView?.({ behavior: "smooth" });
  }, [messages]);

  async function handleSubmit(event: React.FormEvent) {
    event.preventDefault();
    const text = draft.trim();
    if (!text || !sessionId || sending) {
      return;
    }

    const userMessage: ChatMessageRecord = {
      id: `pending-${Date.now()}`,
      session_id: sessionId,
      role: "user",
      content: text,
      cited_question_ids: [],
      created_at: new Date().toISOString(),
    };
    setMessages((prev) => [...prev, userMessage]);
    setDraft("");
    setSending(true);
    setSendError(null);

    try {
      const reply = await sendChatMessage(sessionId, text);
      setMessages((prev) => [...prev, reply]);
    } catch (err) {
      setSendError(err instanceof ApiError ? err.message : "Failed to get a response.");
    } finally {
      setSending(false);
    }
  }

  return (
    <section className="chat-page">
      <h1>Ask the Knowledge Base</h1>
      <p className="page-subtitle">
        Ask about your past interview experiences in plain language — answers are grounded only
        in questions you've actually uploaded, with links back to the source.
      </p>

      {initError && <ErrorMessage message={initError} />}

      {!initError && (
        <>
          <div className="chat-log">
            {messages.length === 0 && !sending && (
              <p className="status-message status-message--empty">
                Try asking something like "What system design questions came up at Amazon?"
              </p>
            )}
            {messages.map((message) => (
              <ChatBubble key={message.id} message={message} />
            ))}
            {sending && <Loading label="Thinking…" />}
            <div ref={bottomRef} />
          </div>

          {sendError && <ErrorMessage message={sendError} />}

          <form className="chat-input-form" onSubmit={handleSubmit}>
            <input
              type="text"
              placeholder="Ask a question about your interview history…"
              value={draft}
              onChange={(e) => setDraft(e.target.value)}
              disabled={!sessionId || sending}
              aria-label="Chat message"
            />
            <button type="submit" disabled={!sessionId || sending || !draft.trim()}>
              Send
            </button>
          </form>
        </>
      )}
    </section>
  );
}

function ChatBubble({ message }: { message: ChatMessageRecord }) {
  return (
    <div className={`chat-bubble chat-bubble--${message.role}`}>
      <div className="chat-bubble__content">{message.content}</div>
      {message.cited_question_ids.length > 0 && (
        <div className="chat-bubble__citations">
          Sources:{" "}
          {message.cited_question_ids.map((id, index) => (
            <span key={id}>
              {index > 0 && ", "}
              <Link to={`/questions/${id}`}>#{index + 1}</Link>
            </span>
          ))}
        </div>
      )}
    </div>
  );
}
