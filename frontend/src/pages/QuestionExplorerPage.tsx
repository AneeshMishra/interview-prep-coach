import { useState } from "react";
import { Link } from "react-router-dom";
import { ApiError, listQuestions } from "../api/client";
import type { Question, QuestionFilters } from "../api/types";
import { ReviewBadge } from "../components/ReviewBadge";
import { SourceBadge } from "../components/SourceBadge";
import { EmptyState, ErrorMessage, Loading } from "../components/StatusStates";

const EMPTY_FILTERS: QuestionFilters = {};

export function QuestionExplorerPage() {
  const [filters, setFilters] = useState<QuestionFilters>(EMPTY_FILTERS);
  const [questions, setQuestions] = useState<Question[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [hasSearched, setHasSearched] = useState(false);

  async function runSearch(nextFilters: QuestionFilters) {
    setLoading(true);
    setError(null);
    try {
      const results = await listQuestions(nextFilters);
      setQuestions(results);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Search failed.");
      setQuestions(null);
    } finally {
      setLoading(false);
      setHasSearched(true);
    }
  }

  function handleSubmit(event: React.FormEvent) {
    event.preventDefault();
    void runSearch(filters);
  }

  function handleClear() {
    setFilters(EMPTY_FILTERS);
    setQuestions(null);
    setHasSearched(false);
  }

  return (
    <section>
      <h1>Question Explorer</h1>
      <form className="filter-form" onSubmit={handleSubmit}>
        <input
          type="search"
          placeholder="Search previous interview questions…"
          value={filters.query ?? ""}
          onChange={(e) => setFilters({ ...filters, query: e.target.value })}
        />
        <input
          type="text"
          placeholder="Company"
          value={filters.company ?? ""}
          onChange={(e) => setFilters({ ...filters, company: e.target.value })}
        />
        <input
          type="text"
          placeholder="Role"
          value={filters.role ?? ""}
          onChange={(e) => setFilters({ ...filters, role: e.target.value })}
        />
        <select
          value={filters.round_type ?? ""}
          onChange={(e) => setFilters({ ...filters, round_type: e.target.value || undefined })}
        >
          <option value="">Any round</option>
          <option value="system_design">System Design</option>
          <option value="dsa">DSA</option>
          <option value="behavioral">Behavioral</option>
          <option value="technical">Technical</option>
          <option value="hr">HR</option>
          <option value="other">Other</option>
        </select>
        <select
          value={filters.difficulty ?? ""}
          onChange={(e) => setFilters({ ...filters, difficulty: e.target.value || undefined })}
        >
          <option value="">Any difficulty</option>
          <option value="easy">Easy</option>
          <option value="medium">Medium</option>
          <option value="hard">Hard</option>
        </select>
        <label className="checkbox-label">
          <input
            type="checkbox"
            checked={filters.needs_review === true}
            onChange={(e) => setFilters({ ...filters, needs_review: e.target.checked ? true : undefined })}
          />
          Needs review only
        </label>
        <button type="submit">Search</button>
        <button type="button" onClick={handleClear}>
          Clear
        </button>
      </form>

      {loading && <Loading label="Searching…" />}
      {error && <ErrorMessage message={error} />}
      {!loading && hasSearched && questions !== null && questions.length === 0 && (
        <EmptyState message="No questions match those filters." />
      )}
      {!hasSearched && !loading && <EmptyState message="Set filters above and search to explore the knowledge base." />}

      {questions !== null && questions.length > 0 && (
        <ul className="question-list">
          {questions.map((q) => (
            <li key={q.id} className="question-card">
              <Link to={`/questions/${q.id}`} className="question-card__link">
                <div className="question-card__meta">
                  {q.company && <span className="tag">{q.company}</span>}
                  {q.role && <span className="tag">{q.role}</span>}
                  {q.round_type && <span className="tag">{q.round_type}</span>}
                  {q.difficulty && <span className="tag">{q.difficulty}</span>}
                </div>
                <p className="question-card__text">{q.question}</p>
                <div className="question-card__badges">
                  <SourceBadge sourceType={q.source_type} />
                  <ReviewBadge needsReview={q.needs_review} />
                </div>
              </Link>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
