import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { ApiError, listInterviews } from "../api/client";
import type { InterviewHistoryEntry } from "../api/types";
import { EmptyState, ErrorMessage, Loading } from "../components/StatusStates";

export function InterviewHistoryPage() {
  const [interviews, setInterviews] = useState<InterviewHistoryEntry[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    listInterviews()
      .then((result) => {
        if (!cancelled) setInterviews(result);
      })
      .catch((err) => {
        if (!cancelled) {
          setError(err instanceof ApiError ? err.message : "Failed to load past interviews.");
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
          <h1>Past Interviews</h1>
          <p className="page-subtitle">Your mock interview history, most recent first.</p>
        </div>
        <Link to="/interview" className="page-header-row__link">
          + New Mock Interview
        </Link>
      </div>

      {interviews === null && error === null && <Loading label="Loading past interviews…" />}
      {error && <ErrorMessage message={error} />}
      {interviews !== null && interviews.length === 0 && (
        <EmptyState message="No mock interviews yet — start one to see it here." />
      )}

      {interviews !== null && interviews.length > 0 && (
        <ul className="interview-history-list">
          {interviews.map((interview) => (
            <li key={interview.id} className="interview-history-card">
              <Link to={`/interviews/${interview.id}`} className="interview-history-card__link">
                <div className="interview-history-card__meta">
                  <span className={`interview-status interview-status--${interview.status}`}>
                    {interview.status}
                  </span>
                  <span>{interview.company || "Unspecified company"}</span>
                  {interview.role && <span>· {interview.role}</span>}
                  <span>· {new Date(interview.started_at).toLocaleString()}</span>
                </div>
                {interview.overall_score !== null && (
                  <span className="interview-history-card__score">
                    {interview.overall_score.toFixed(1)} / 5
                  </span>
                )}
              </Link>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
