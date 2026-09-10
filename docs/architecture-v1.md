# Interview Preparation Coach Agent — Design Document

## 1. Overview

An open-source, document-based AI agent that ingests Word documents containing
past interview experiences (questions, companies, roles) and:

1. Lets users query/browse past interview questions by company or role.
2. Runs **mock interviews** — an LLM-driven interviewer persona that asks
   questions one at a time, evaluates answers, and gives a final report.

**Tech constraints:** Python, FastAPI backend, LLM-based agent (provider
pluggable — local via Ollama or API-based).

---

## 2. Goals & Non-Goals

**Goals**
- Parse unstructured `.docx` interview-experience documents into structured data.
- Company/role/round-based filtering and retrieval.
- Stateful mock interview sessions (multi-turn, not single-shot Q&A).
- Answer evaluation with a scoring rubric.
- Fully open-source, self-hostable, pluggable LLM backend.

**Non-Goals (v1)**
- Voice-based interviews (text-only for v1).
- Video/webcam proctoring.
- Multi-tenant SaaS auth (single-user/local-first for v1).

---

## 3. High-Level Architecture

```
                        ┌─────────────────────┐
                        │   Word Documents      │
                        │   (.docx uploads)     │
                        └──────────┬───────────┘
                                   │
                        ┌──────────▼───────────┐
                        │  Ingestion Service     │
                        │  (parse + structure)  │
                        └──────────┬───────────┘
                                   │
                        ┌──────────▼───────────┐
                        │  Chunker + Metadata    │
                        │  Tagger                │
                        └──────────┬───────────┘
                                   │
                        ┌──────────▼───────────┐
                        │  Vector Store          │
                        │  (Chroma / Qdrant)     │
                        └──────────┬───────────┘
                                   │
              ┌────────────────────┼────────────────────┐
              │                                          │
   ┌──────────▼───────────┐                  ┌───────────▼──────────┐
   │  Retrieval API         │                  │  Mock Interview Agent │
   │  (company/role filter) │                  │  (stateful loop)      │
   └──────────┬───────────┘                  └───────────┬──────────┘
              │                                          │
              └────────────────────┬─────────────────────┘
                                   │
                        ┌──────────▼───────────┐
                        │   FastAPI Backend      │
                        └──────────┬───────────┘
                                   │
                        ┌──────────▼───────────┐
                        │   Frontend (chat UI)   │
                        └──────────────────────┘
```

---

## 4. Components

### 4.1 Ingestion Service
- **Input:** `.docx` files.
- **Library:** `python-docx` for raw text/table extraction; fallback to
  `unstructured` for messier formats.
- **Process:**
  1. Extract raw text/tables from the document.
  2. Pass raw text through an LLM "structuring" prompt to normalize into:
     ```json
     {
       "company": "Amazon",
       "role": "Backend Engineer",
       "round_type": "system_design",
       "question": "...",
       "answer_notes": "...",
       "difficulty": "medium",
       "tags": ["microservices", "scaling"]
     }
     ```
  3. Validate output against a Pydantic schema; retry/flag on failure.

### 4.2 Chunker + Metadata Tagger
- One chunk = one Q&A pair (atomic; no arbitrary token-based splitting).
- Metadata stored alongside each chunk's embedding for hybrid filtering.

### 4.3 Vector Store
- **Choice:** Chroma (default, embedded, zero-ops) with an adapter interface
  so Qdrant can be swapped in for scale.
- **Embeddings:** `sentence-transformers` (e.g., `bge-small-en` or
  `all-MiniLM-L6-v2`) — local, free, no API cost.

### 4.4 Retrieval API
- Hybrid search: metadata filter (company + role + round_type) combined with
  semantic similarity on the question text.
- Exposed as a FastAPI endpoint: `GET /questions?company=Amazon&role=Backend`

### 4.5 Mock Interview Agent (core feature)
A **stateful state machine**, not a single RAG call:

| State | Description |
|---|---|
| `SETUP` | User selects company + role + round type |
| `RETRIEVE` | Agent pulls relevant past questions for that context |
| `ASK` | LLM (interviewer persona) asks one question at a time |
| `EVALUATE` | User's answer scored against a rubric; follow-up decided |
| `NEXT_OR_END` | Loop to `ASK` or move to `SUMMARY` |
| `SUMMARY` | Final report: strengths, gaps, per-round scores |

- Session state held server-side (in-memory dict or Redis for v1; DB-backed
  later) keyed by `session_id`.
- System prompt fixes the interviewer persona per company culture (e.g.,
  "You are a senior interviewer at Amazon focused on leadership principles").

### 4.6 Evaluation Engine
- Round-type-specific rubric templates (DSA, system design, behavioral each
  need different scoring criteria).
- Output: structured score (e.g., 1-5 per criterion) + qualitative feedback.
- Transcripts persisted for later analytics (e.g., "system design is your
  weak area across sessions").

### 4.7 LLM Provider Layer
- **Pluggable interface** — critical for open-source adoption:
  - Local: Ollama (Llama 3, Mistral) — free, no API key needed.
  - Remote: Claude / OpenAI via API key, same interface.
- Implemented as an abstract `LLMProvider` class; config-driven selection.

---

## 5. Tech Stack

| Layer | Tool |
|---|---|
| Backend framework | FastAPI (Python) |
| Doc parsing | python-docx, unstructured |
| Orchestration | LlamaIndex or LangChain (RAG + agent loop) |
| Vector DB | Chroma (default), Qdrant (scale option) |
| Embeddings | sentence-transformers (local) |
| LLM | Ollama (local) or pluggable API (Claude/OpenAI) |
| Session state | In-memory / Redis |
| Frontend | React/Next.js chat UI (separate repo or `/frontend`) |
| Deployment | Docker Compose |

---

## 6. API Surface (FastAPI)

```
POST   /documents/upload        # upload .docx, triggers ingestion
GET    /questions                # filter by company/role/round_type
POST   /interview/start          # {company, role, round_type} -> session_id
POST   /interview/{session_id}/answer   # submit answer, get next question/feedback
GET    /interview/{session_id}/summary  # final report
```

---

## 7. Repository Structure

```
/ingestion      - doc parser, LLM structuring pass, Pydantic schemas
/retrieval      - vector store adapter, hybrid search
/agent          - mock interview state machine, prompts, session store
/evaluation     - rubric templates, scoring logic
/llm_providers  - pluggable LLM interface (Ollama, Claude, OpenAI)
/api            - FastAPI routers
/frontend       - chat UI
/docker         - Docker Compose setup
```

---

## 8. Open Design Questions

- Session persistence: in-memory (simplest, v1) vs Redis vs DB — affects
  restart durability.
- How much of the LLM "structuring" pass needs human review before trusting
  ingested data for mock interviews.
- Whether round-type rubrics are hardcoded or user-configurable/extensible.

---

## 9. Roadmap (Suggested Phases)

1. **Phase 1:** Ingestion + retrieval (upload doc → query by company/role).
2. **Phase 2:** Mock interview state machine (single round type first).
3. **Phase 3:** Evaluation engine + summary reports.
4. **Phase 4:** Multi-round-type rubrics + analytics across sessions.
5. **Phase 5:** Pluggable LLM providers + Docker Compose packaging for OSS release.
