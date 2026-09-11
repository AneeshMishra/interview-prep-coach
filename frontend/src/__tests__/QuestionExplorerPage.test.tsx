import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";
import { QuestionExplorerPage } from "../pages/QuestionExplorerPage";
import type { Question } from "../api/types";

const { listQuestionsMock } = vi.hoisted(() => ({ listQuestionsMock: vi.fn() }));

vi.mock("../api/client", async () => {
  const actual = await vi.importActual<typeof import("../api/client")>("../api/client");
  return { ...actual, listQuestions: listQuestionsMock };
});

function makeQuestion(overrides: Partial<Question> = {}): Question {
  return {
    id: "q1",
    document_id: "doc1",
    company: "Amazon",
    role: "Backend Engineer",
    round_type: "system_design",
    question: "Design a URL shortener.",
    answer_notes: null,
    difficulty: "medium",
    source_type: "user_reported",
    source_section: null,
    extraction_confidence: 0.9,
    needs_review: false,
    tags: ["scaling"],
    created_at: "2026-01-01T00:00:00Z",
    ...overrides,
  };
}

function renderPage() {
  return render(
    <MemoryRouter>
      <QuestionExplorerPage />
    </MemoryRouter>
  );
}

describe("QuestionExplorerPage", () => {
  afterEach(() => {
    listQuestionsMock.mockReset();
  });

  it("shows a prompt before any search has been run", () => {
    renderPage();
    expect(screen.getByText(/set filters above and search/i)).toBeInTheDocument();
  });

  it("renders matching questions with provenance and review badges after a search", async () => {
    listQuestionsMock.mockResolvedValue([
      makeQuestion(),
      makeQuestion({ id: "q2", question: "Unreliable extraction.", needs_review: true, source_type: "ai_generated" }),
    ]);
    const user = userEvent.setup();
    renderPage();

    await user.click(screen.getByRole("button", { name: /search/i }));

    expect(await screen.findByText("Design a URL shortener.")).toBeInTheDocument();
    expect(screen.getByText("Unreliable extraction.")).toBeInTheDocument();
    expect(screen.getByText("User Reported")).toBeInTheDocument();
    expect(screen.getByText("AI Generated")).toBeInTheDocument();
    expect(screen.getByText("Needs review")).toBeInTheDocument();
  });

  it("shows an empty state when nothing matches", async () => {
    listQuestionsMock.mockResolvedValue([]);
    const user = userEvent.setup();
    renderPage();

    await user.click(screen.getByRole("button", { name: /search/i }));

    expect(await screen.findByText(/no questions match those filters/i)).toBeInTheDocument();
  });

  it("shows an error message when the search fails", async () => {
    listQuestionsMock.mockRejectedValue(new Error("boom"));
    const user = userEvent.setup();
    renderPage();

    await user.click(screen.getByRole("button", { name: /search/i }));

    await waitFor(() => expect(screen.getByRole("alert")).toBeInTheDocument());
  });
});
