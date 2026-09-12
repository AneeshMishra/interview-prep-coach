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
