import { useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { ApiError, startInterview, submitInterviewAnswer } from "../api/client";
import type {
  InterviewMessageRecord,
  InterviewSessionRecord,
  InterviewSummaryRecord,
} from "../api/types";
import { InterviewBubble, SummaryCard } from "../components/InterviewDisplay";
import { ErrorMessage, Loading } from "../components/StatusStates";

type Phase = "setup" | "in-progress" | "completed";

export function InterviewPage() {
  const [phase, setPhase] = useState<Phase>("setup");
  const [company, setCompany] = useState("");
  const [role, setRole] = useState("");
  const [session, setSession] = useState<InterviewSessionRecord | null>(null);
  const [messages, setMessages] = useState<InterviewMessageRecord[]>([]);
  const [summary, setSummary] = useState<InterviewSummaryRecord | null>(null);
  const [draft, setDraft] = useState("");
  const [starting, setStarting] = useState(false);
  const [sending, setSending] = useState(false);
  const [startError, setStartError] = useState<string | null>(null);
  const [sendError, setSendError] = useState<string | null>(null);
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView?.({ behavior: "smooth" });
  }, [messages]);

  async function handleStart(event: React.FormEvent) {
    event.preventDefault();
    setStarting(true);
    setStartError(null);
    try {
      const result = await startInterview(company.trim(), role.trim());
      setSession(result.session);
      if (result.type === "message" && result.message) {
        setMessages([result.message]);
        setPhase("in-progress");
      } else if (result.type === "summary" && result.summary) {
        setSummary(result.summary);
        setPhase("completed");
      }
    } catch (err) {
      setStartError(err instanceof ApiError ? err.message : "Failed to start the interview.");
    } finally {
      setStarting(false);
    }
  }

  async function handleSubmitAnswer(event: React.FormEvent) {
    event.preventDefault();
    const text = draft.trim();
    if (!text || !session || sending) return;

    const candidateMessage: InterviewMessageRecord = {
      id: `pending-${Date.now()}`,
      session_id: session.id,
      sequence_no: messages.length,
      role: "candidate",
      content: text,
      question_id: null,
      created_at: new Date().toISOString(),
    };
    setMessages((prev) => [...prev, candidateMessage]);
    setDraft("");
    setSending(true);
    setSendError(null);

    try {
      const result = await submitInterviewAnswer(session.id, text);
      if (result.type === "message") {
        setMessages((prev) => [...prev, result.message]);
      } else {
        setSummary(result.summary);
        setPhase("completed");
      }
    } catch (err) {
      setSendError(err instanceof ApiError ? err.message : "Failed to submit the answer.");
    } finally {
      setSending(false);
    }
  }

  function handleRestart() {
    setPhase("setup");
    setSession(null);
    setMessages([]);
    setSummary(null);
    setDraft("");
    setStartError(null);
    setSendError(null);
  }

  return (
    <section className="chat-page">
      <div className="page-header-row">
        <div>
          <h1>Mock Interview</h1>
          <p className="page-subtitle">
            A System Design mock interview: one question at a time, evaluated against a rubric, with
            a scored summary at the end. Questions are pulled from your uploaded knowledge base when
            available.
          </p>
        </div>
        <Link to="/interviews" className="page-header-row__link">
          Past Interviews →
        </Link>
      </div>

      {phase === "setup" && (
        <form className="interview-setup-form" onSubmit={handleStart}>
          <input
            type="text"
            placeholder="Company (optional)"
            value={company}
            onChange={(e) => setCompany(e.target.value)}
          />
          <input
            type="text"
            placeholder="Role (optional)"
            value={role}
            onChange={(e) => setRole(e.target.value)}
          />
          <button type="submit" disabled={starting}>
            {starting ? "Starting…" : "Start Mock Interview"}
          </button>
          {startError && <ErrorMessage message={startError} />}
        </form>
      )}

      {phase !== "setup" && (
        <>
          <div className="chat-log">
            {messages.map((message) => (
              <InterviewBubble key={message.id} message={message} />
            ))}
            {sending && <Loading label="Evaluating…" />}

            {phase === "completed" && summary && <SummaryCard summary={summary} />}

            <div ref={bottomRef} />
          </div>

          {sendError && <ErrorMessage message={sendError} />}

          {phase === "in-progress" && (
            <form className="chat-input-form" onSubmit={handleSubmitAnswer}>
              <input
                type="text"
                placeholder="Type your answer…"
                value={draft}
                onChange={(e) => setDraft(e.target.value)}
                disabled={sending}
                aria-label="Interview answer"
              />
              <button type="submit" disabled={sending || !draft.trim()}>
                Send
              </button>
            </form>
          )}

          {phase === "completed" && (
            <button type="button" onClick={handleRestart}>
              Start a New Interview
            </button>
          )}
        </>
      )}
    </section>
  );
}
