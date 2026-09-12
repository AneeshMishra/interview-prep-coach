import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { ApiError, getInterview, getInterviewSummary, getInterviewTranscript } from "../api/client";
import type {
  InterviewMessageRecord,
  InterviewSessionRecord,
  InterviewSummaryRecord,
} from "../api/types";
import { InterviewBubble, SummaryCard } from "../components/InterviewDisplay";
import { EmptyState, ErrorMessage, Loading } from "../components/StatusStates";

export function InterviewDetailPage() {
  const { sessionId } = useParams<{ sessionId: string }>();
  const [session, setSession] = useState<InterviewSessionRecord | null>(null);
  const [messages, setMessages] = useState<InterviewMessageRecord[] | null>(null);
  const [summary, setSummary] = useState<InterviewSummaryRecord | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!sessionId) return;
    let cancelled = false;
    setLoading(true);
    setError(null);

    Promise.all([getInterview(sessionId), getInterviewTranscript(sessionId)])
      .then(async ([sessionResult, transcriptResult]) => {
        if (cancelled) return;
        setSession(sessionResult);
        setMessages(transcriptResult);

        if (sessionResult.status === "completed") {
          try {
            const summaryResult = await getInterviewSummary(sessionId);
            if (!cancelled) setSummary(summaryResult);
          } catch {
            // Summary genuinely may not exist yet even for a completed
            // session in an edge case (e.g. it failed to generate) —
            // the transcript is still useful on its own.
          }
        }
      })
      .catch((err) => {
        if (!cancelled) {
          setError(
            err instanceof ApiError && err.status === 404
              ? "This interview could not be found."
              : "Failed to load this interview."
          );
        }
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });

    return () => {
      cancelled = true;
    };
  }, [sessionId]);

  return (
    <section>
      <Link to="/interviews" className="back-link">
        ← Back to Past Interviews
      </Link>

      {loading && <Loading label="Loading interview…" />}
      {error && <ErrorMessage message={error} />}

      {session && messages && (
        <>
          <h1>
            {session.company || "Unspecified company"}
            {session.role ? ` — ${session.role}` : ""}
          </h1>
          <p className="page-subtitle">
            <span className={`interview-status interview-status--${session.status}`}>
              {session.status}
            </span>{" "}
            · Started {new Date(session.started_at).toLocaleString()}
          </p>

          <div className="chat-log">
            {messages.length === 0 && <EmptyState message="No messages recorded for this interview." />}
            {messages.map((message) => (
              <InterviewBubble key={message.id} message={message} />
            ))}
            {summary && <SummaryCard summary={summary} />}
            {session.status === "active" && (
              <EmptyState message="This interview is still in progress — resuming isn't supported yet." />
            )}
          </div>
        </>
      )}
    </section>
  );
}
