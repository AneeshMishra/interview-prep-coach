import { render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";
import { QuestionDetailPage } from "../pages/QuestionDetailPage";
import { ApiError } from "../api/client";
import type { Question } from "../api/types";

const { getQuestionMock } = vi.hoisted(() => ({ getQuestionMock: vi.fn() }));

vi.mock("../api/client", async () => {
  const actual = await vi.importActual<typeof import("../api/client")>("../api/client");
  return { ...actual, getQuestion: getQuestionMock };
});

const question: Question = {
  id: "q1",
  document_id: "doc1",
  company: "Amazon",
  role: "Backend Engineer",
  round_type: "system_design",
  question: "Design a URL shortener.",
  answer_notes: "Discuss hashing and sharding.",
  difficulty: "medium",
  source_type: "ai_generated",
  source_section: "Round 3",
  extraction_confidence: 0.42,
  needs_review: true,
  tags: ["scaling", "hashing"],
  created_at: "2026-01-01T00:00:00Z",
};

function renderAt(questionId: string) {
  return render(
    <MemoryRouter initialEntries={[`/questions/${questionId}`]}>
      <Routes>
        <Route path="/questions/:questionId" element={<QuestionDetailPage />} />
      </Routes>
    </MemoryRouter>
  );
}

describe("QuestionDetailPage", () => {
  afterEach(() => {
    getQuestionMock.mockReset();
  });

  it("shows the question, provenance, tags and review flag", async () => {
    getQuestionMock.mockResolvedValue(question);
    renderAt("q1");

    expect(await screen.findByText("Design a URL shortener.")).toBeInTheDocument();
    expect(screen.getByText("AI Generated")).toBeInTheDocument();
    expect(screen.getByText("Needs review")).toBeInTheDocument();
    expect(screen.getByText("Discuss hashing and sharding.")).toBeInTheDocument();
    expect(screen.getByText("scaling")).toBeInTheDocument();
    expect(screen.getByText("hashing")).toBeInTheDocument();
    expect(screen.getByText(/42%/)).toBeInTheDocument();
  });

  it("shows a not-found message for a missing question", async () => {
    getQuestionMock.mockRejectedValue(new ApiError(404, "Question not found."));
    renderAt("missing");

    expect(await screen.findByText(/could not be found/i)).toBeInTheDocument();
  });
});
