import { render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";
import { InterviewDetailPage } from "../pages/InterviewDetailPage";
import type { InterviewMessageRecord, InterviewSessionRecord, InterviewSummaryRecord } from "../api/types";

const { getInterviewMock, getInterviewTranscriptMock, getInterviewSummaryMock } = vi.hoisted(() => ({
  getInterviewMock: vi.fn(),
  getInterviewTranscriptMock: vi.fn(),
  getInterviewSummaryMock: vi.fn(),
}));

vi.mock("../api/client", async () => {
  const actual = await vi.importActual<typeof import("../api/client")>("../api/client");
  return {
    ...actual,
    getInterview: getInterviewMock,
    getInterviewTranscript: getInterviewTranscriptMock,
    getInterviewSummary: getInterviewSummaryMock,
  };
});

function makeSession(overrides: Partial<InterviewSessionRecord> = {}): InterviewSessionRecord {
  return {
    id: "s1",
    company: "Amazon",
    role: "Backend Engineer",
    round_type: "system_design",
    status: "completed",
    current_state: "COMPLETED",
    rubric_version: "1.0",
    started_at: "2026-01-01T00:00:00Z",
    completed_at: "2026-01-01T01:00:00Z",
    ...overrides,
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

function renderPage(sessionId = "s1") {
  return render(
    <MemoryRouter initialEntries={[`/interviews/${sessionId}`]}>
      <Routes>
        <Route path="/interviews/:sessionId" element={<InterviewDetailPage />} />
      </Routes>
    </MemoryRouter>
  );
}

describe("InterviewDetailPage", () => {
  afterEach(() => {
    getInterviewMock.mockReset();
    getInterviewTranscriptMock.mockReset();
    getInterviewSummaryMock.mockReset();
  });

  it("renders the transcript and summary for a completed interview", async () => {
    getInterviewMock.mockResolvedValue(makeSession());
    getInterviewTranscriptMock.mockResolvedValue([
      makeMessage({ id: "m1", role: "interviewer", content: "Design a URL shortener." }),
      makeMessage({ id: "m2", role: "candidate", content: "I would use consistent hashing." }),
    ]);
    getInterviewSummaryMock.mockResolvedValue(makeSummary());
    renderPage();

    expect(await screen.findByText("Design a URL shortener.")).toBeInTheDocument();
    expect(screen.getByText("I would use consistent hashing.")).toBeInTheDocument();
    expect(await screen.findByText(/overall score: 3\.8 \/ 5/i)).toBeInTheDocument();
  });

  it("shows an in-progress note without a summary for an active interview", async () => {
    getInterviewMock.mockResolvedValue(makeSession({ status: "active" }));
    getInterviewTranscriptMock.mockResolvedValue([makeMessage()]);
    renderPage();

    expect(await screen.findByText(/still in progress/i)).toBeInTheDocument();
    expect(getInterviewSummaryMock).not.toHaveBeenCalled();
  });

  it("shows a not-found error when the interview does not exist", async () => {
    const { ApiError } = await import("../api/client");
    getInterviewMock.mockRejectedValue(new ApiError(404, "Not found"));
    getInterviewTranscriptMock.mockResolvedValue([]);
    renderPage("missing");

    expect(await screen.findByRole("alert")).toHaveTextContent(/could not be found/i);
  });
});
