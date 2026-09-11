import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { ApiError, getQuestion } from "../api/client";
import type { Question } from "../api/types";
import { ReviewBadge } from "../components/ReviewBadge";
import { SourceBadge } from "../components/SourceBadge";
import { ErrorMessage, Loading } from "../components/StatusStates";

export function QuestionDetailPage() {
  const { questionId } = useParams<{ questionId: string }>();
  const [question, setQuestion] = useState<Question | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!questionId) {
      return;
    }
    setLoading(true);
    setError(null);
    getQuestion(questionId)
      .then(setQuestion)
      .catch((err) => {
        setError(
          err instanceof ApiError
            ? err.status === 404
              ? "This question could not be found."
              : err.message
            : "Failed to load the question."
        );
      })
      .finally(() => setLoading(false));
  }, [questionId]);

  return (
    <section>
      <Link to="/questions" className="back-link">
        ← Back to Question Explorer
      </Link>

      {loading && <Loading label="Loading question…" />}
      {error && <ErrorMessage message={error} />}

      {question && (
        <article className="question-detail">
          <div className="question-detail__badges">
            <SourceBadge sourceType={question.source_type} />
            <ReviewBadge needsReview={question.needs_review} />
          </div>

          <h1>{question.question}</h1>

          <dl className="question-detail__meta">
            <div>
              <dt>Company</dt>
              <dd>{question.company ?? "Unknown"}</dd>
            </div>
            <div>
              <dt>Role</dt>
              <dd>{question.role ?? "Unknown"}</dd>
            </div>
            <div>
              <dt>Round</dt>
              <dd>{question.round_type ?? "Unknown"}</dd>
            </div>
            <div>
              <dt>Difficulty</dt>
              <dd>{question.difficulty ?? "Unspecified"}</dd>
            </div>
          </dl>

          {question.tags.length > 0 && (
            <div className="question-detail__tags">
              {question.tags.map((tag) => (
                <span key={tag} className="tag">
                  {tag}
                </span>
              ))}
            </div>
          )}

          {question.answer_notes && (
            <>
              <h2>Answer notes</h2>
              <p>{question.answer_notes}</p>
            </>
          )}

          <h2>Source</h2>
          <p className="question-detail__provenance">
            {question.source_section ? `${question.source_section} — ` : ""}
            extraction confidence:{" "}
            {question.extraction_confidence !== null
              ? `${Math.round(question.extraction_confidence * 100)}%`
              : "unknown"}
          </p>
        </article>
      )}
    </section>
  );
}
