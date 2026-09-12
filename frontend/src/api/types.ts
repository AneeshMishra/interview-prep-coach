// Mirrors backend/app/db/models.py and app/api/routers/*.py response shapes.
// Keep in sync by hand for now — Phase 1 has no shared schema generation.

export type DocumentStatus = "pending" | "processing" | "done" | "failed";

export interface DocumentRecord {
  id: string;
  filename: string;
  content_hash: string;
  status: DocumentStatus;
  error_message: string | null;
  created_at: string;
  updated_at: string;
}

export type RoundType =
  | "system_design"
  | "dsa"
  | "behavioral"
  | "technical"
  | "hr"
  | "other";

export type Difficulty = "easy" | "medium" | "hard";

export type SourceType = "user_reported" | "ai_generated" | "ai_followup";

export interface Question {
  id: string;
  document_id: string;
  company: string | null;
  role: string | null;
  round_type: RoundType | string | null;
  question: string;
  answer_notes: string | null;
  difficulty: Difficulty | string | null;
  source_type: SourceType | string;
  source_section: string | null;
  extraction_confidence: number | null;
  needs_review: boolean;
  tags: string[];
  created_at: string;
}

export interface QuestionFilters {
  company?: string;
  role?: string;
  round_type?: string;
  difficulty?: string;
  needs_review?: boolean;
  query?: string;
}

export interface UploadResponse {
  document_id: string;
  status: DocumentStatus | "duplicate";
  detail?: string;
}

export interface ChatSessionRecord {
  id: string;
  created_at: string;
}

export type ChatRole = "user" | "assistant";

export interface ChatMessageRecord {
  id: string;
  session_id: string;
  role: ChatRole;
  content: string;
  cited_question_ids: string[];
  created_at: string;
}

export interface ChatHistoryEntry {
  id: string;
  created_at: string;
  updated_at: string;
  message_count: number;
  preview: string | null;
}

export type InterviewStatus = "active" | "completed" | "abandoned";

export interface InterviewSessionRecord {
  id: string;
  company: string | null;
  role: string | null;
  round_type: string;
  status: InterviewStatus;
  current_state: string;
  rubric_version: string | null;
  started_at: string;
  completed_at: string | null;
}

export interface InterviewHistoryEntry extends InterviewSessionRecord {
  overall_score: number | null;
}

export type InterviewMessageRole = "interviewer" | "candidate";

export interface InterviewMessageRecord {
  id: string;
  session_id: string;
  sequence_no: number;
  role: InterviewMessageRole;
  content: string;
  question_id: string | null;
  created_at: string;
}

export interface InterviewSummaryRecord {
  session_id: string;
  overall_score: number;
  // Average score per rubric criterion (e.g. "architecture", "scalability")
  // across the session's answers. A criterion never scored on any answer
  // is simply absent here, not defaulted to a fabricated value.
  criteria_breakdown: Record<string, number>;
  strengths: string[];
  weaknesses: string[];
  recommendations: string[];
  created_at: string;
}

export type InterviewTurnResult =
  | { type: "message"; message: InterviewMessageRecord }
  | { type: "summary"; summary: InterviewSummaryRecord };

export interface UserProfile {
  id: string;
  email: string;
  display_name: string | null;
  avatar_url: string | null;
}

// Only "google" is wired up on the backend so far — see
// backend/app/auth/oauth/factory.py. The others are listed so the login
// page can show them as "coming soon" rather than omitting them silently.
export type OAuthProviderName = "google" | "facebook" | "linkedin" | "azure";

export interface StartInterviewResponse {
  session: InterviewSessionRecord;
  type: "message" | "summary";
  message?: InterviewMessageRecord;
  summary?: InterviewSummaryRecord;
}
