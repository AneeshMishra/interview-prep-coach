import type { InterviewMessageRecord, InterviewSummaryRecord } from "../api/types";

export function InterviewBubble({ message }: { message: InterviewMessageRecord }) {
  const variant = message.role === "candidate" ? "user" : "assistant";
  return (
    <div className={`chat-bubble chat-bubble--${variant}`}>
      <div className="chat-bubble__content">{message.content}</div>
    </div>
  );
}

function prettifyCriterionName(name: string): string {
  return name
    .split("_")
    .map((word) => word.charAt(0).toUpperCase() + word.slice(1))
    .join(" ");
}

export function SummaryCard({ summary }: { summary: InterviewSummaryRecord }) {
  const criteriaBreakdown = Object.entries(summary.criteria_breakdown);

  return (
    <div className="interview-summary-card">
      <h2>Interview Summary</h2>
      <p className="interview-summary-card__score">Overall score: {summary.overall_score.toFixed(1)} / 5</p>

      {criteriaBreakdown.length > 0 && (
        <>
          <h3>Score by Criterion</h3>
          <ul className="interview-criteria-breakdown">
            {criteriaBreakdown.map(([criterion, score]) => (
              <li key={criterion} className="interview-criteria-breakdown__row">
                <span className="interview-criteria-breakdown__name">{prettifyCriterionName(criterion)}</span>
                <span className="interview-criteria-breakdown__bar-track">
                  <span
                    className="interview-criteria-breakdown__bar-fill"
                    style={{ width: `${(score / 5) * 100}%` }}
                  />
                </span>
                <span className="interview-criteria-breakdown__score">{score.toFixed(1)} / 5</span>
              </li>
            ))}
          </ul>
        </>
      )}

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
