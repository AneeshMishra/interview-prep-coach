import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { SummaryCard } from "../components/InterviewDisplay";
import type { InterviewSummaryRecord } from "../api/types";

function makeSummary(overrides: Partial<InterviewSummaryRecord> = {}): InterviewSummaryRecord {
  return {
    session_id: "s1",
    overall_score: 3.8,
    criteria_breakdown: {},
    strengths: [],
    weaknesses: [],
    recommendations: [],
    created_at: "2026-01-01T00:00:00Z",
    ...overrides,
  };
}

describe("SummaryCard criteria breakdown", () => {
  it("renders each criterion with a prettified name and score out of 5", () => {
    render(
      <SummaryCard
        summary={makeSummary({
          criteria_breakdown: { architecture: 4.2, requirements_clarity: 3.0 },
        })}
      />
    );

    expect(screen.getByText("Architecture")).toBeInTheDocument();
    expect(screen.getByText("4.2 / 5")).toBeInTheDocument();
    expect(screen.getByText("Requirements Clarity")).toBeInTheDocument();
    expect(screen.getByText("3.0 / 5")).toBeInTheDocument();
  });

  it("renders no breakdown section when criteria_breakdown is empty", () => {
    render(<SummaryCard summary={makeSummary({ criteria_breakdown: {} })} />);

    expect(screen.queryByText("Score by Criterion")).not.toBeInTheDocument();
  });

  it("sizes the bar fill proportionally to the score", () => {
    render(<SummaryCard summary={makeSummary({ criteria_breakdown: { scalability: 2.5 } })} />);

    const bar = document.querySelector(".interview-criteria-breakdown__bar-fill") as HTMLElement;
    expect(bar.style.width).toBe("50%");
  });
});
