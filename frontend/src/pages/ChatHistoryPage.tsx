import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { ApiError, listChatSessions } from "../api/client";
import type { ChatHistoryEntry } from "../api/types";
import { EmptyState, ErrorMessage, Loading } from "../components/StatusStates";

export function ChatHistoryPage() {
  const [chats, setChats] = useState<ChatHistoryEntry[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    listChatSessions()
      .then((result) => {
        if (!cancelled) setChats(result);
      })
      .catch((err) => {
        if (!cancelled) {
          setError(err instanceof ApiError ? err.message : "Failed to load past chats.");
        }
      });
    return () => {
      cancelled = true;
    };
  }, []);

  return (
    <section>
      <div className="page-header-row">
        <div>
          <h1>Past Chats</h1>
          <p className="page-subtitle">Your conversations with the knowledge base, most recent first.</p>
        </div>
        <Link to="/chat" className="page-header-row__link">
          + New Chat
        </Link>
      </div>

      {chats === null && error === null && <Loading label="Loading past chats…" />}
      {error && <ErrorMessage message={error} />}
      {chats !== null && chats.length === 0 && (
        <EmptyState message="No chats yet — ask something to see it here." />
      )}

      {chats !== null && chats.length > 0 && (
        <ul className="chat-history-list">
          {chats.map((chat) => (
            <li key={chat.id} className="chat-history-card">
              <Link to={`/chats/${chat.id}`} className="chat-history-card__link">
                <div className="chat-history-card__meta">
                  <span>{new Date(chat.updated_at).toLocaleString()}</span>
                  <span>
                    · {chat.message_count} message{chat.message_count === 1 ? "" : "s"}
                  </span>
                </div>
                <p className="chat-history-card__preview">
                  {chat.preview || "No messages yet."}
                </p>
              </Link>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
