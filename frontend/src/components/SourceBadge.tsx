import type { SourceType } from "../api/types";

const LABELS: Record<string, string> = {
  user_reported: "User Reported",
  ai_generated: "AI Generated",
  ai_followup: "AI Follow-up",
};

/**
 * Always render this next to a question's text. Per CLAUDE.md provenance
 * rules, an AI-generated question must never be visually indistinguishable
 * from a real, user-reported one.
 */
export function SourceBadge({ sourceType }: { sourceType: SourceType | string }) {
  const label = LABELS[sourceType] ?? sourceType;
  const variant = sourceType === "user_reported" ? "source-badge--reported" : "source-badge--generated";
  return <span className={`source-badge ${variant}`}>{label}</span>;
}
