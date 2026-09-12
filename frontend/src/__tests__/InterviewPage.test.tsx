import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";
import { InterviewPage } from "../pages/InterviewPage";
import type { InterviewMessageRecord, InterviewSummaryRecord, StartInterviewResponse } from "../api/types";

const { startInterviewMock, submitInterviewAnswerMock } = vi.hoisted(() => ({
  startInterviewMock: vi.fn(),
  submitInterviewAnswerMock: vi.fn(),
}));

vi.mock("../api/client", async () => {
  const actual = await vi.importActual<typeof import("../api/client")>("../api/client");
  return { ...actual, startInterview: startInterviewMock, submitInterviewAnswer: submitInterviewAnswerMock };
});

function makeSession() {
  return {
    id: "s1",
    company: "Amazon",
    role: "Backend Engineer",
    round_type: "system_design",
    status: "active" as const,
    current_state: "WAIT_FOR_ANSWER",
    rubric_version: "1.0",
    started_at: "2026-01-01T00:00:00Z",
    completed_at: null,
  };
}

function makeMessage(overrides: Partial<InterviewMessageRecord> = {}): InterviewMessageRecord {
  return {
    id: "m1",
    session_id: "s1",
    sequence_no: 0,
    role: "interviewer",
    content: "Design a URL shortener.",
    question_id: "q1",
    created_at: "2026-01-01T00:00:00Z",
    ...overrides,
  };
}

function makeSummary(overrides: Partial<InterviewSummaryRecord> = {}): InterviewSummaryRecord {
  return {
    session_id: "s1",
    overall_score: 3.8,
    strengths: ["Clear communication."],
    weaknesses: ["Missed failure modes."],
    recommendations: ["Practice capacity estimation."],
    created_at: "2026-01-01T00:00:00Z",
    ...overrides,
  };
}

function renderPage() {
  return render(
    <MemoryRouter>
      <InterviewPage />
    </MemoryRouter>
  );
}

describe("InterviewPage", () => {
  afterEach(() => {
    startInterviewMock.mockReset();
    submitInterviewAnswerMock.mockReset();
  });

  it("shows the setup form first, with no session started", () => {
    renderPage();
    expect(screen.getByRole("button", { name: /start mock interview/i })).toBeInTheDocument();
    expect(screen.queryByLabelText(/interview answer/i)).not.toBeInTheDocument();
  });

  it("starts an interview and shows the first question", async () => {
    const response: StartInterviewResponse = {
      session: makeSession(),
      type: "message",
      message: makeMessage(),
    };
    startInterviewMock.mockResolvedValue(response);
    const user = userEvent.setup();
    renderPage();

    await user.type(screen.getByPlaceholderText(/company/i), "Amazon");
    await user.click(screen.getByRole("button", { name: /start mock interview/i }));

    expect(await screen.findByText("Design a URL shortener.")).toBeInTheDocument();
    expect(startInterviewMock).toHaveBeenCalledWith("Amazon", "");
    expect(screen.getByLabelText(/interview answer/i)).toBeInTheDocument();
  });

  it("submits an answer and renders the next question", async () => {
    startInterviewMock.mockResolvedValue({
      session: makeSession(),
      type: "message",
      message: makeMessage({ content: "Design a URL shortener." }),
    });
    submitInterviewAnswerMock.mockResolvedValue({
      type: "message",
      message: makeMessage({ id: "m2", content: "How would you handle hot keys?" }),
    });
    const user = userEvent.setup();
    renderPage();

    await user.click(screen.getByRole("button", { name: /start mock interview/i }));
    await screen.findByText("Design a URL shortener.");

    const answerInput = screen.getByLabelText(/interview answer/i);
    await user.type(answerInput, "I would use consistent hashing.");
    await user.click(screen.getByRole("button", { name: /send/i }));

    expect(screen.getByText("I would use consistent hashing.")).toBeInTheDocument();
    expect(await screen.findByText("How would you handle hot keys?")).toBeInTheDocument();
  });

  it("shows the summary card and allows restarting once the interview completes", async () => {
    startInterviewMock.mockResolvedValue({
      session: makeSession(),
      type: "message",
      message: makeMessage(),
    });
    submitInterviewAnswerMock.mockResolvedValue({ type: "summary", summary: makeSummary() });
    const user = userEvent.setup();
    renderPage();

    await user.click(screen.getByRole("button", { name: /start mock interview/i }));
    await screen.findByText("Design a URL shortener.");

    await user.type(screen.getByLabelText(/interview answer/i), "My final answer.");
    await user.click(screen.getByRole("button", { name: /send/i }));

    expect(await screen.findByText(/overall score: 3\.8 \/ 5/i)).toBeInTheDocument();
    expect(screen.getByText("Clear communication.")).toBeInTheDocument();
    expect(screen.getByText("Missed failure modes.")).toBeInTheDocument();
    expect(screen.getByText("Practice capacity estimation.")).toBeInTheDocument();
    expect(screen.queryByLabelText(/interview answer/i)).not.toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: /start a new interview/i }));
    expect(screen.getByRole("button", { name: /start mock interview/i })).toBeInTheDocument();
  });

  it("shows an error when starting fails", async () => {
    startInterviewMock.mockRejectedValue(new Error("Could not start the interview right now."));
    const user = userEvent.setup();
    renderPage();

    await user.click(screen.getByRole("button", { name: /start mock interview/i }));

    expect(await screen.findByRole("alert")).toBeInTheDocument();
  });

  it("shows an error when submitting an answer fails, without losing the typed answer", async () => {
    startInterviewMock.mockResolvedValue({
      session: makeSession(),
      type: "message",
      message: makeMessage(),
    });
    submitInterviewAnswerMock.mockRejectedValue(new Error("Could not evaluate the answer right now."));
    const user = userEvent.setup();
    renderPage();

    await user.click(screen.getByRole("button", { name: /start mock interview/i }));
    await screen.findByText("Design a URL shortener.");

    await user.type(screen.getByLabelText(/interview answer/i), "My answer.");
    await user.click(screen.getByRole("button", { name: /send/i }));

    expect(screen.getByText("My answer.")).toBeInTheDocument();
    expect(await screen.findByRole("alert")).toBeInTheDocument();
  });
});
