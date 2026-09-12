import { useEffect, useRef, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { ApiError, createChatSession, listChatMessages, sendChatMessageStream } from "../api/client";
import type { ChatMessageRecord } from "../api/types";
import { ErrorMessage, Loading } from "../components/StatusStates";

export function ChatPage() {
  // /chat starts a brand-new conversation; /chats/:sessionId resumes one
  // from history — same page, just a different way to obtain a session id.
  const { sessionId: resumeSessionId } = useParams<{ sessionId?: string }>();
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [messages, setMessages] = useState<ChatMessageRecord[]>([]);
  const [draft, setDraft] = useState("");
  const [sending, setSending] = useState(false);
  const [initError, setInitError] = useState<string | null>(null);
  const [sendError, setSendError] = useState<string | null>(null);
  // null while waiting for the first chunk (shows "Thinking…"); becomes a
  // growing string as the assistant's answer streams in via SSE.
  const [streamingText, setStreamingText] = useState<string | null>(null);
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    let cancelled = false;
    setSessionId(null);
    setMessages([]);
    setInitError(null);

    const ready = resumeSessionId
      ? Promise.resolve({ id: resumeSessionId })
      : createChatSession();

    ready
      .then(async (session) => {
        if (cancelled) return;
        setSessionId(session.id);
        const history = await listChatMessages(session.id);
        if (!cancelled) setMessages(history);
      })
      .catch((err) => {
        if (!cancelled) {
          setInitError(
            err instanceof ApiError
              ? err.message
              : resumeSessionId
                ? "Failed to load this chat."
                : "Failed to start a chat session."
          );
        }
      });
    return () => {
      cancelled = true;
    };
  }, [resumeSessionId]);

  useEffect(() => {
    // Optional chaining on the call itself, not just `.current` — jsdom
    // (used in tests) doesn't implement scrollIntoView at all.
    bottomRef.current?.scrollIntoView?.({ behavior: "smooth" });
  }, [messages, streamingText]);

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
    setStreamingText(null);

    try {
      const reply = await sendChatMessageStream(sessionId, text, (chunk) => {
        setStreamingText((prev) => (prev ?? "") + chunk);
      });
      setMessages((prev) => [...prev, reply]);
    } catch (err) {
      setSendError(err instanceof ApiError ? err.message : "Failed to get a response.");
    } finally {
      setSending(false);
      setStreamingText(null);
    }
  }

  return (
    <section className="chat-page">
      <div className="page-header-row">
        <div>
          <h1>Ask the Knowledge Base</h1>
          <p className="page-subtitle">
            Ask about your past interview experiences in plain language — answers are grounded
            only in questions you've actually uploaded, with links back to the source.
          </p>
        </div>
        <Link to="/chats" className="page-header-row__link">
          Past Chats →
        </Link>
      </div>

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
            {sending && streamingText === null && <Loading label="Thinking…" />}
            {sending && streamingText !== null && (
              <ChatBubble
                message={{
                  id: "streaming",
                  session_id: sessionId ?? "",
                  role: "assistant",
                  content: streamingText,
                  cited_question_ids: [],
                  created_at: new Date().toISOString(),
                }}
              />
            )}
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
