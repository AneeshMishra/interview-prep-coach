import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";
import { InterviewHistoryPage } from "../pages/InterviewHistoryPage";
import type { InterviewHistoryEntry } from "../api/types";

const { listInterviewsMock } = vi.hoisted(() => ({
  listInterviewsMock: vi.fn(),
}));

vi.mock("../api/client", async () => {
  const actual = await vi.importActual<typeof import("../api/client")>("../api/client");
  return { ...actual, listInterviews: listInterviewsMock };
});

function makeEntry(overrides: Partial<InterviewHistoryEntry> = {}): InterviewHistoryEntry {
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
    overall_score: 3.8,
    ...overrides,
  };
}

function renderPage() {
  return render(
    <MemoryRouter>
      <InterviewHistoryPage />
    </MemoryRouter>
  );
}

describe("InterviewHistoryPage", () => {
  afterEach(() => {
    listInterviewsMock.mockReset();
  });

  it("shows an empty state when there are no past interviews", async () => {
    listInterviewsMock.mockResolvedValue([]);
    renderPage();

    expect(await screen.findByText(/no mock interviews yet/i)).toBeInTheDocument();
  });

  it("lists past interviews with status, company, role and score", async () => {
    listInterviewsMock.mockResolvedValue([
      makeEntry(),
      makeEntry({ id: "s2", company: "Google", role: null, status: "active", overall_score: null }),
    ]);
    renderPage();

    expect(await screen.findByText("Amazon")).toBeInTheDocument();
    expect(screen.getByText("Backend Engineer", { exact: false })).toBeInTheDocument();
    expect(screen.getByText("3.8 / 5")).toBeInTheDocument();
    expect(screen.getByText("Google")).toBeInTheDocument();

    const link = screen.getByRole("link", { name: /amazon/i });
    expect(link).toHaveAttribute("href", "/interviews/s1");
  });

  it("shows an error message when loading fails", async () => {
    listInterviewsMock.mockRejectedValue(new Error("Could not reach the API."));
    renderPage();

    expect(await screen.findByRole("alert")).toBeInTheDocument();
  });

  it("links to the new-interview page", async () => {
    listInterviewsMock.mockResolvedValue([]);
    renderPage();

    await screen.findByText(/no mock interviews yet/i);
    expect(screen.getByRole("link", { name: /new mock interview/i })).toHaveAttribute("href", "/interview");
  });
});
