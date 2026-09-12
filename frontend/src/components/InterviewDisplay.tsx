import type { InterviewMessageRecord, InterviewSummaryRecord } from "../api/types";

export function InterviewBubble({ message }: { message: InterviewMessageRecord }) {
  const variant = message.role === "candidate" ? "user" : "assistant";
  return (
    <div className={`chat-bubble chat-bubble--${variant}`}>
      <div className="chat-bubble__content">{message.content}</div>
    </div>
  );
}

export function SummaryCard({ summary }: { summary: InterviewSummaryRecord }) {
  return (
    <div className="interview-summary-card">
      <h2>Interview Summary</h2>
      <p className="interview-summary-card__score">Overall score: {summary.overall_score.toFixed(1)} / 5</p>

      {summary.strengths.length > 0 && (
        <>
          <h3>Strengths</h3>
          <ul>
            {summary.strengths.map((s, i) => (
              <li key={i}>{s}</li>
            ))}
          </ul>
        </>
      )}

      {summary.weaknesses.length > 0 && (
        <>
          <h3>Weaknesses</h3>
          <ul>
            {summary.weaknesses.map((w, i) => (
              <li key={i}>{w}</li>
            ))}
          </ul>
        </>
      )}

      {summary.recommendations.length > 0 && (
        <>
          <h3>Recommendations</h3>
          <ul>
            {summary.recommendations.map((r, i) => (
              <li key={i}>{r}</li>
            ))}
          </ul>
        </>
      )}
    </div>
  );
}
