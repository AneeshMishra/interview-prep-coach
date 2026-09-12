import type {
  ChatMessageRecord,
  ChatSessionRecord,
  DocumentRecord,
  InterviewHistoryEntry,
  InterviewMessageRecord,
  InterviewSessionRecord,
  InterviewSummaryRecord,
  InterviewTurnResult,
  Question,
  QuestionFilters,
  StartInterviewResponse,
  UploadResponse,
} from "./types";

// Browser-context default: the backend container/process publishes its API
// on localhost:8000 regardless of whether this app itself runs via `vite
// dev` or the Docker Compose frontend service (Vite env vars are baked in
// at build time, not read at container-runtime).
const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000/api/v1";

export class ApiError extends Error {
  status: number;

  constructor(status: number, message: string) {
    super(message);
    this.status = status;
    this.name = "ApiError";
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`${API_BASE_URL}${path}`, init);
  } catch {
    throw new ApiError(0, "Could not reach the API. Is the backend running?");
  }

  if (!response.ok) {
    let detail = response.statusText;
    try {
      const body = await response.json();
      if (typeof body?.detail === "string") {
        detail = body.detail;
      }
    } catch {
      // Response body wasn't JSON — fall back to statusText.
    }
    throw new ApiError(response.status, detail);
  }

  return (await response.json()) as T;
}

export function uploadDocument(file: File): Promise<UploadResponse> {
  const formData = new FormData();
  formData.append("file", file);
  return request<UploadResponse>("/documents/upload", { method: "POST", body: formData });
}

export function listDocuments(): Promise<DocumentRecord[]> {
  return request<DocumentRecord[]>("/documents");
}

export function listQuestions(filters: QuestionFilters = {}): Promise<Question[]> {
  const params = new URLSearchParams();
  for (const [key, value] of Object.entries(filters)) {
    if (value !== undefined && value !== "") {
      params.set(key, String(value));
    }
  }
  const search = params.toString();
  return request<Question[]>(`/questions${search ? `?${search}` : ""}`);
}

export function getQuestion(questionId: string): Promise<Question> {
  return request<Question>(`/questions/${questionId}`);
}

export function createChatSession(): Promise<ChatSessionRecord> {
  return request<ChatSessionRecord>("/chat/sessions", { method: "POST" });
}

export function listChatMessages(sessionId: string): Promise<ChatMessageRecord[]> {
  return request<ChatMessageRecord[]>(`/chat/sessions/${sessionId}/messages`);
}

export function sendChatMessage(sessionId: string, message: string): Promise<ChatMessageRecord> {
  return request<ChatMessageRecord>(`/chat/sessions/${sessionId}/messages`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ message }),
  });
}

export function startInterview(company: string, role: string): Promise<StartInterviewResponse> {
  return request<StartInterviewResponse>("/interviews", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ company: company || undefined, role: role || undefined }),
  });
}

export function submitInterviewAnswer(sessionId: string, answer: string): Promise<InterviewTurnResult> {
  return request<InterviewTurnResult>(`/interviews/${sessionId}/answers`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ answer }),
  });
}

export function getInterview(sessionId: string): Promise<InterviewSessionRecord> {
  return request<InterviewSessionRecord>(`/interviews/${sessionId}`);
}

export function listInterviews(): Promise<InterviewHistoryEntry[]> {
  return request<InterviewHistoryEntry[]>("/interviews");
}

export function getInterviewTranscript(sessionId: string): Promise<InterviewMessageRecord[]> {
  return request<InterviewMessageRecord[]>(`/interviews/${sessionId}/transcript`);
}

export function getInterviewSummary(sessionId: string): Promise<InterviewSummaryRecord> {
  return request<InterviewSummaryRecord>(`/interviews/${sessionId}/summary`);
}
