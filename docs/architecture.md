# Interview Preparation Coach — V1.1 Architecture & Implementation Plan

**Status:** Proposed for V1 OSS  
**Audience:** Senior/Staff Engineers, Solution Architects, OSS contributors  
**Primary goal:** Build a local-first, document-based AI Interview Preparation Coach that converts interview-experience documents into searchable knowledge and runs stateful mock interviews.

---

## 1. Executive Summary

V1.1 keeps the core direction of V1 but makes the architecture implementation-ready.

The application will:

1. Ingest `.docx` interview-experience documents.
2. Extract and normalize interview questions into structured records.
3. Preserve source provenance so users can distinguish real user-provided questions from AI-generated questions.
4. Store structured application data in SQLite by default and PostgreSQL for production deployments.
5. Store embeddings in Qdrant.
6. Provide semantic + metadata-filtered retrieval.
7. Run a deterministic state-machine-driven mock interview.
8. Use an LLM for question generation, follow-ups, answer evaluation, and summaries.
9. Support Ollama locally and provide provider interfaces for OpenAI/Anthropic.
10. Use configurable YAML rubrics with built-in defaults.
11. Package the complete local experience using Docker Compose.

### Core architectural principle

> **The relational database is the system of record, Qdrant is the retrieval index, the LLM performs reasoning/generation, and the deterministic interview state machine owns workflow state.**

---

# 2. V1 Scope

## 2.1 In Scope

- `.docx` upload
- DOCX text/table extraction
- LLM-assisted question structuring
- Pydantic validation
- Question metadata
- Source provenance
- SQLite default persistence
- PostgreSQL compatibility
- Qdrant vector search
- Company/role/round filtering
- System Design mock interview
- Stateful interview sessions
- Answer evaluation
- Configurable System Design rubric
- Final interview summary
- Ollama provider
- Provider abstraction for OpenAI/Anthropic
- React + TypeScript UI
- Docker Compose
- Basic automated tests
- README and OSS setup documentation

## 2.2 Explicitly Out of Scope

- Voice interviews
- Video interviews
- Webcam/proctoring
- Multi-tenant SaaS authentication
- Billing/subscriptions
- Kubernetes production deployment
- Mobile application
- Fine-tuning models
- Complex autonomous multi-agent orchestration
- Recruiter/team features

---

# 3. Architecture

```text
                         ┌─────────────────────────┐
                         │     React / Next.js     │
                         │   Interview Web UI      │
                         └────────────┬────────────┘
                                      │
                              REST + SSE
                                      │
                         ┌────────────▼────────────┐
                         │         FastAPI          │
                         │                          │
                         │ API + Interview         │
                         │ Orchestrator            │
                         └──────┬─────────┬─────────┘
                                │         │
                 ┌──────────────┘         └───────────────┐
                 ▼                                        ▼
        ┌─────────────────┐                      ┌─────────────────┐
        │ SQLite / Postgres│                      │     Qdrant      │
        │                 │                      │                 │
        │ Documents       │                      │ Embeddings      │
        │ Questions       │                      │ Metadata        │
        │ Sessions        │                      │ Retrieval       │
        │ Messages        │                      └─────────────────┘
        │ Evaluations     │
        └────────┬────────┘
                 │
                 ▼
        ┌──────────────────┐
        │    Ingestion     │
        │                  │
        │ DOCX Parser      │
        │ Structurer       │
        │ Validator        │
        │ Embedder         │
        └────────┬─────────┘
                 │
                 ▼
        ┌──────────────────┐
        │   LLM Provider   │
        │                  │
        │ Ollama           │
        │ OpenAI           │
        │ Anthropic        │
        └──────────────────┘
```

---

# 4. Component Responsibilities

## 4.1 Frontend

**Technology:** React + TypeScript. Next.js is acceptable if SSR/routing benefits are needed.

Responsibilities:

- Document upload
- Knowledge-base browsing
- Search/filter questions
- Start mock interview
- Display one question at a time
- Submit answers
- Show evaluation
- Show final report
- Show transcript

The frontend must not contain interview orchestration logic.

---

## 4.2 FastAPI Backend

Responsibilities:

- API endpoints
- Authentication boundary for future versions
- Request validation
- Interview orchestration
- Session lifecycle
- LLM provider selection
- Retrieval coordination
- Evaluation coordination
- Persistence

The backend owns the business state machine.

---

## 4.3 Ingestion Service

Pipeline:

```text
DOCX
  ↓
Raw extraction
  ↓
Normalization
  ↓
LLM structuring
  ↓
Pydantic validation
  ↓
Confidence check
  ↓
Persist structured records
  ↓
Generate embeddings
  ↓
Upsert into Qdrant
```

Use `python-docx` first. Keep `unstructured` as a fallback rather than making it mandatory.

---

# 5. Canonical Question Model

A question should be represented approximately as:

```json
{
  "id": "uuid",
  "company": "Amazon",
  "role": "Backend Engineer",
  "round_type": "system_design",
  "question": "Design an order processing system",
  "answer_notes": "Discuss Kafka, idempotency...",
  "difficulty": "hard",
  "tags": [
    "microservices",
    "kafka",
    "scalability"
  ],
  "source_type": "user_reported",
  "source_document_id": "uuid",
  "source_section": "Round 3 - System Design",
  "extraction_confidence": 0.96
}
```

### Important distinction

`source_type` must distinguish at least:

- `user_reported`
- `ai_generated`
- `ai_followup`

The product must never present an AI-generated question as an actual reported interview question.

---

# 6. Data Architecture

## 6.1 System of Record

Use:

- SQLite for default local OSS deployment.
- PostgreSQL for production/advanced deployment.

The application must use a repository/DAO abstraction so persistence is not tightly coupled to either database.

## 6.2 Vector Store

Use Qdrant as the reference implementation.

Qdrant contains:

- vector
- question ID
- company
- role
- round type
- difficulty
- tags
- source document ID

Qdrant is a retrieval index, not the authoritative source of question/session data.

---

# 7. Initial Database Model

```text
documents
---------
id
filename
content_hash
status
created_at
updated_at

interview_questions
-------------------
id
document_id
company
role
round_type
question
answer_notes
difficulty
source_type
source_section
extraction_confidence
created_at

question_tags
-------------
question_id
tag

interview_sessions
------------------
id
company
role
round_type
status
rubric_version
llm_provider
llm_model
current_state
started_at
completed_at

interview_messages
------------------
id
session_id
sequence_no
role
content
question_id
created_at

evaluations
-----------
id
session_id
message_id
question_id
rubric_version
score
criteria_json
strengths_json
weaknesses_json
feedback
created_at

interview_summaries
-------------------
id
session_id
overall_score
strengths_json
weaknesses_json
recommendations_json
created_at
```

---

# 8. Interview State Machine

The state machine remains deterministic.

```text
SETUP
  ↓
RETRIEVE
  ↓
ASK
  ↓
WAIT_FOR_ANSWER
  ↓
EVALUATE
  ↓
FOLLOW_UP_OR_NEXT
  ↓
ASK
  ↓
...
  ↓
SUMMARY
  ↓
COMPLETED
```

## State ownership

The application owns:

- current state
- question count
- session ID
- question IDs
- answer history
- evaluation status
- termination rules

The LLM does NOT own these.

The LLM can recommend:

- follow-up question
- evaluation
- feedback
- summary

The orchestrator decides whether and when those outputs are accepted.

---

# 9. Session Persistence Decision

## Decision: SQLite/PostgreSQL

Do **not** use an in-memory dictionary as the primary V1 implementation.

### Why?

Interview sessions are product data.

A server restart should not destroy:

- transcript
- scores
- answers
- evaluation
- final report

### V1 deployment

```text
SQLite
  ↓
single-user local application
```

### Production profile

```text
PostgreSQL
  ↓
persistent hosted deployment
```

### Redis

Redis is intentionally deferred.

Potential future uses:

- distributed sessions
- caching
- rate limiting
- background job coordination
- temporary agent state

Redis should be introduced only when there is a measured requirement.

---

# 10. Rubric Decision

## Decision: Configuration-driven rubrics

Rubrics will NOT be permanently hardcoded in Python.

Use YAML configuration with Pydantic validation.

Example:

```yaml
name: system_design
version: "1.0"

criteria:
  requirements_clarity:
    weight: 10

  architecture:
    weight: 25

  scalability:
    weight: 20

  reliability:
    weight: 15

  data_design:
    weight: 15

  security:
    weight: 5

  observability:
    weight: 5

  communication:
    weight: 5

score:
  min: 1
  max: 5
```

## Built-in V1 rubrics

Only ship:

1. `system_design.yaml`

Future releases can add:

- DSA
- Java
- Spring Boot
- Kafka
- Behavioral
- Cloud Architecture

Every evaluation stores `rubric_version`.

This guarantees reproducibility when a rubric changes later.

---

# 11. Retrieval Architecture

Retrieval must combine:

```text
Metadata filtering
       +
Semantic similarity
       +
Optional reranking
```

Example:

```text
company = Amazon
role = Backend Engineer
round_type = system_design
```

Then semantic search over question text.

### Retrieval result

Each result should return:

```json
{
  "question_id": "...",
  "question": "...",
  "score": 0.91,
  "source_type": "user_reported",
  "company": "Amazon",
  "role": "Backend Engineer",
  "round_type": "system_design"
}
```

---

# 12. LLM Architecture

Use an explicit provider interface:

```python
class LLMProvider:

    async def generate(
        self,
        messages,
        response_schema=None
    ):
        ...
```

Initial implementations:

```text
OllamaProvider
OpenAIProvider
AnthropicProvider
```

Configuration:

```yaml
llm:
  provider: ollama
  model: <configured-model>
```

Do not scatter provider-specific logic throughout the application.

---

# 13. Local LLM Strategy

Default OSS experience:

```text
Ollama
   ↓
Qwen-family model
```

Alternative supported local model:

```text
Ollama
   ↓
Gemma 3
```

Model choice should remain configuration-driven.

Do not hardcode a model name into business logic.

---

# 14. Embedding Architecture

Use:

```text
EmbeddingProvider
       │
       ├── local embedding model
       └── future API embedding provider
```

Store embedding model information with the collection/configuration.

This allows migration later without changing retrieval APIs.

---

# 15. API Contract

## Documents

```http
POST /api/v1/documents
POST /api/v1/documents/{document_id}/ingest
GET  /api/v1/documents
```

## Questions

```http
GET /api/v1/questions
GET /api/v1/questions/{question_id}
```

Filters:

```text
company
role
round_type
difficulty
tag
source_type
```

## Interviews

```http
POST /api/v1/interviews
GET  /api/v1/interviews/{session_id}
POST /api/v1/interviews/{session_id}/answers
GET  /api/v1/interviews/{session_id}/summary
GET  /api/v1/interviews/{session_id}/transcript
```

## Rubrics

```http
GET /api/v1/rubrics
```

---

# 16. Streaming

Use Server-Sent Events (SSE) for LLM response streaming in V1.

```text
React
  │
  │ SSE
  ▼
FastAPI
  │
  ▼
LLM Provider
```

WebSockets are deferred until real-time voice/live interview functionality is required.

---

# 17. ADRs

## ADR-001 — Relational Database for Persistent State

**Status:** Accepted

**Decision:** Use SQLite by default and PostgreSQL for production.

**Reason:** Interview sessions, transcripts, questions and evaluations are durable application data.

**Rejected:** In-memory dictionary as primary persistence.

**Redis:** Deferred.

---

## ADR-002 — Qdrant as Reference Vector Store

**Status:** Accepted

**Decision:** Qdrant is the reference vector database.

**Reason:** Strong metadata filtering and a clear migration path from local to larger deployments.

**Rejected:** Making the vector database the system of record.

---

## ADR-003 — Configuration-Driven Rubrics

**Status:** Accepted

**Decision:** YAML rubrics validated using Pydantic.

**Reason:** Extensible without requiring code changes.

**V1:** Ship System Design rubric only.

---

## ADR-004 — Deterministic Interview Orchestration

**Status:** Accepted

**Decision:** A backend state machine owns interview flow.

**Reason:** Predictability, testing, recovery and provider independence.

**Rejected:** Fully autonomous LLM-controlled workflow.

---

## ADR-005 — LlamaIndex for Retrieval/Document Workflows

**Status:** Accepted

**Decision:** Use LlamaIndex where it reduces document/RAG implementation complexity.

**Constraint:** LlamaIndex does not own business workflow state.

---

## ADR-006 — Provider-Agnostic LLM Layer

**Status:** Accepted

**Decision:** Define `LLMProvider` before implementing the first provider.

**Initial:** Ollama.

**Future:** OpenAI and Anthropic.

---

## ADR-007 — System Design as First Mock Interview Type

**Status:** Accepted

**Decision:** System Design is the first supported interview type.

**Reason:** It demonstrates the value of contextual retrieval, follow-up questions, architecture reasoning and rubric-based evaluation.

---

## ADR-008 — Docker Compose as V1 Deployment

**Status:** Accepted

**Decision:** Docker Compose is the reference deployment.

**Services:**

```text
frontend
backend
qdrant
ollama
```

SQLite can be mounted as a persistent volume.

PostgreSQL can be enabled as an alternative deployment profile.

---

## ADR-009 — Source Provenance

**Status:** Accepted

**Decision:** Every extracted question must retain source document and section information.

**Reason:** Trust and traceability.

---

## ADR-010 — AI-Generated vs User-Reported Questions

**Status:** Accepted

**Decision:** Explicitly label question origin.

**Reason:** Prevent hallucinated/generated questions from being presented as historical interview facts.

---

# 18. Repository Structure

```text
interview-prep-coach/
│
├── backend/
│   ├── app/
│   │   ├── api/
│   │   ├── agent/
│   │   ├── ingestion/
│   │   ├── retrieval/
│   │   ├── evaluation/
│   │   ├── llm_providers/
│   │   ├── persistence/
│   │   ├── models/
│   │   ├── services/
│   │   ├── config/
│   │   └── main.py
│   │
│   ├── tests/
│   ├── pyproject.toml
│   └── Dockerfile
│
├── frontend/
│   ├── src/
│   ├── tests/
│   ├── package.json
│   └── Dockerfile
│
├── rubrics/
│   └── system_design.yaml
│
├── docker/
│   ├── docker-compose.yml
│   └── docker-compose.postgres.yml
│
├── sample-data/
│   └── README.md
│
├── docs/
│   ├── architecture.md
│   ├── adr/
│   └── development.md
│
├── .env.example
├── README.md
└── LICENSE
```

---

# 19. Phase 1 — Implementation Backlog

## Phase 1 Goal

> Upload a DOCX containing interview experiences, convert it into structured questions, persist the records, embed them into Qdrant, and allow users to search/filter the questions.

No mock interview is required for Phase 1.

---

## Epic 1 — Project Foundation

### P1-001 Repository setup

**Priority:** P0

Tasks:

- Initialize Git repository.
- Create backend/frontend directories.
- Add Python project configuration.
- Add React/TypeScript project.
- Add `.gitignore`.
- Add `.env.example`.

**Acceptance:**

```text
backend starts
frontend starts
configuration loads
```

---

### P1-002 Docker Compose

**Priority:** P0

Services:

```text
backend
frontend
qdrant
ollama
```

Tasks:

- Health checks.
- Persistent Qdrant volume.
- Ollama volume.
- Backend environment configuration.

**Acceptance:**

```bash
docker compose up
```

starts the application stack.

---

### P1-003 Configuration module

**Priority:** P0

Create typed configuration:

```text
AppConfig
DatabaseConfig
QdrantConfig
LLMConfig
EmbeddingConfig
```

Use environment variables.

---

# Epic 2 — Document Ingestion

## P1-004 DOCX upload API

**Priority:** P0

Endpoint:

```http
POST /api/v1/documents
```

Requirements:

- Accept `.docx`.
- Validate extension/content type.
- Generate document UUID.
- Calculate content hash.
- Persist document metadata.

---

## P1-005 DOCX parser

**Priority:** P0

Use `python-docx`.

Extract:

- paragraphs
- headings
- tables

Normalize:

- whitespace
- empty paragraphs
- duplicated lines

Output an internal document representation.

---

## P1-006 Interview structure extraction

**Priority:** P0

Send normalized text to the LLM.

Extract:

```text
company
role
round_type
question
answer_notes
difficulty
tags
```

Use structured output/Pydantic validation.

---

## P1-007 Extraction confidence

**Priority:** P1

Generate/derive a confidence value.

Flag low-confidence records for review.

Example:

```text
confidence < 0.75
```

---

## P1-008 Ingestion status

**Priority:** P1

Document lifecycle:

```text
UPLOADED
PROCESSING
COMPLETED
FAILED
```

Persist error information.

---

# Epic 3 — Persistence

## P1-009 Database schema

**Priority:** P0

Implement:

- documents
- interview_questions
- question_tags

Use SQLAlchemy or SQLModel.

---

## P1-010 Database migrations

**Priority:** P0

Use Alembic.

Requirements:

- initial migration
- migration documentation
- clean database startup

---

# Epic 4 — Embeddings + Qdrant

## P1-011 Embedding provider

**Priority:** P0

Implement:

```python
class EmbeddingProvider:
    async def embed(self, texts):
        ...
```

Start with a local embedding implementation.

---

## P1-012 Qdrant adapter

**Priority:** P0

Implement:

```text
create_collection()
upsert()
search()
delete()
```

Hide Qdrant-specific implementation behind an interface.

---

## P1-013 Metadata payload

**Priority:** P0

Store:

```text
question_id
company
role
round_type
difficulty
tags
source_document_id
source_type
```

---

# Epic 5 — Retrieval API

## P1-014 Question search

**Priority:** P0

Endpoint:

```http
GET /api/v1/questions
```

Support:

```text
company
role
round_type
difficulty
tag
source_type
```

---

## P1-015 Semantic search

**Priority:** P0

Endpoint:

```http
GET /api/v1/questions?query=design scalable order system
```

Flow:

```text
query
 ↓
embedding
 ↓
Qdrant
 ↓
metadata filtering
 ↓
results
```

---

## P1-016 Source display

**Priority:** P1

Every result should display:

```text
Question
Company
Role
Round
Source document
Source type
```

---

# Epic 6 — Frontend

## P1-017 Upload screen

**Priority:** P0

UI:

```text
Upload Interview Experience

[ Select DOCX ]

Upload
```

Show ingestion status.

---

## P1-018 Question explorer

**Priority:** P0

Filters:

```text
Company
Role
Round
Difficulty
```

Search box:

```text
Search previous interview questions...
```

---

## P1-019 Question detail

**Priority:** P1

Display:

- question
- metadata
- tags
- source
- answer notes if available

Clearly show:

```text
User Reported
```

or:

```text
AI Generated
```

---

# Epic 7 — Testing

## P1-020 Parser tests

Test:

- normal DOCX
- headings
- tables
- empty paragraphs
- malformed content

---

## P1-021 Schema validation tests

Test:

- valid extraction
- missing company
- missing question
- invalid round type
- malformed LLM output

---

## P1-022 Retrieval tests

Test:

- semantic relevance
- company filtering
- role filtering
- round filtering
- combined filters

---

## P1-023 API tests

Test:

```text
upload
list documents
search questions
question detail
```

---

# Epic 8 — OSS Documentation

## P1-024 README

Include:

- product overview
- architecture
- prerequisites
- Docker setup
- Ollama setup
- configuration
- document upload
- screenshots
- troubleshooting

---

## P1-025 Developer documentation

Document:

```text
local development
database migration
adding an LLM provider
adding an embedding provider
adding a rubric
running tests
```

---

# 20. Phase 1 Definition of Done

Phase 1 is complete only when this flow works:

```text
User
 │
 ▼
Upload interview.docx
 │
 ▼
Backend
 │
 ├── Parse
 ├── Structure
 ├── Validate
 └── Persist
 │
 ▼
Embedding
 │
 ▼
Qdrant
 │
 ▼
React
 │
 ▼
Search
 │
 ▼
Filtered Questions
```

Example:

```text
Search:
"Kafka performance"

Company:
UHG

Role:
Kafka Solution Architect

Round:
Technical
```

returns relevant historical questions with provenance.

---

# 21. Phase 2 Preview

Only after Phase 1 is stable:

```text
POST /interviews
        ↓
SETUP
        ↓
RETRIEVE
        ↓
ASK
        ↓
WAIT_FOR_ANSWER
        ↓
EVALUATE
        ↓
FOLLOW-UP
        ↓
NEXT
        ↓
SUMMARY
```

Phase 2 should initially support only:

> **System Design mock interviews**

---

# 22. Phase 3 Preview

Evaluation engine:

```text
Answer
  ↓
System Design Rubric
  ↓
Criteria Scores
  ↓
Qualitative Feedback
  ↓
Strengths
  ↓
Weaknesses
```

Final report:

```text
Overall Score
Architecture
Scalability
Reliability
Data Design
Security
Observability
Communication

Strengths
Weaknesses
Recommendations
```

---

# 23. Phase 4 Preview

Add:

- DSA rubric
- Behavioral rubric
- Java rubric
- Spring Boot rubric
- Kafka rubric
- Azure/Cloud rubric
- cross-session analytics
- weak-area detection
- personalized preparation plan

---

# 24. Phase 5 — OSS Release

Before public v1.0:

```text
README
LICENSE
CONTRIBUTING.md
CODE_OF_CONDUCT.md
SECURITY.md
CHANGELOG.md
Docker Compose
Example dataset
Architecture documentation
API documentation
Unit tests
Integration tests
CI/CD
Release tags
```

---

# 25. Business/Product Direction

The product should not be positioned merely as:

> "Chat with your interview documents."

The stronger positioning is:

> **Turn real interview experiences into a personalized AI interview coach.**

Core product loop:

```text
Interview Experiences
        ↓
Knowledge Base
        ↓
Personalized Mock Interview
        ↓
Answer Evaluation
        ↓
Weak Area Detection
        ↓
Targeted Preparation
        ↓
Next Mock Interview
```

## OSS model

Free/open:

- local deployment
- document ingestion
- RAG
- mock interview
- Ollama
- basic evaluation

Future hosted product:

- managed hosting
- premium models
- advanced analytics
- personalized preparation plans
- company/role preparation packs
- team/recruiter features

---

# 26. Recommended Development Order

Do not start by building the AI interviewer.

Start here:

```text
1. Repository
        ↓
2. Configuration
        ↓
3. Database
        ↓
4. DOCX parser
        ↓
5. Structured question schema
        ↓
6. LLM structuring
        ↓
7. Qdrant
        ↓
8. Retrieval API
        ↓
9. React question explorer
        ↓
10. Integration tests
        ↓
11. Mock Interview
        ↓
12. Evaluation
```

The first milestone should be:

> **"Upload one DOCX and reliably retrieve the right interview questions."**

Once retrieval quality is trustworthy, build the interviewer on top of it.

---

# 27. Architecture Quality Gates

Before moving from Phase 1 to Phase 2:

### Reliability

- Failed ingestion does not corrupt existing data.
- Duplicate document uploads are detected using content hash.
- Qdrant can be rebuilt from relational data.
- API errors are structured.

### Quality

- Extracted question has provenance.
- AI-generated content is explicitly labeled.
- Retrieval tests exist.
- LLM output is schema validated.

### Maintainability

- LLM provider abstraction exists.
- Embedding provider abstraction exists.
- Vector store abstraction exists.
- Repository layer exists.
- Rubrics are external configuration.

### OSS usability

```bash
git clone ...
docker compose up
```

should be the target developer experience.

---

# 28. Final V1.1 Architecture Decisions

| Area | V1.1 Decision |
|---|---|
| Backend | FastAPI |
| Frontend | React + TypeScript |
| Agent orchestration | Deterministic state machine |
| RAG framework | LlamaIndex |
| Relational DB | SQLite default / PostgreSQL production |
| Session persistence | Relational DB |
| Redis | Deferred |
| Vector DB | Qdrant |
| Embeddings | Provider abstraction + local default |
| Local LLM | Ollama |
| Cloud LLM | OpenAI / Anthropic adapters |
| Rubric | YAML + Pydantic |
| First rubric | System Design |
| Streaming | SSE |
| Deployment | Docker Compose |
| Auth | Deferred |
| Multi-tenancy | Deferred |
| Voice | Deferred |
| First mock interview | System Design |
| First development milestone | Document ingestion + retrieval |

---

## 29. Architecture Principle to Preserve

The most important boundary in this project is:

```text
                 ┌──────────────────────┐
                 │   Interview Agent    │
                 │                      │
                 │ LLM = intelligence   │
                 │ State machine = flow │
                 └──────────┬───────────┘
                            │
              ┌─────────────┼──────────────┐
              ▼             ▼              ▼
           Postgres       Qdrant          LLM
        source of truth   retrieval      reasoning
```

Do not let the LLM become the database, workflow engine, or source of truth.

That decision will make the Interview Preparation Coach easier to test, cheaper to operate, safer to evolve, and significantly easier for other developers to contribute to.
