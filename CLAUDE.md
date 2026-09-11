# CLAUDE.md — Interview Preparation Coach

## Mission

Implement the **Interview Preparation Coach**, an open-source, local-first AI application that converts user-provided interview-experience `.docx` files into a searchable knowledge base and later conducts stateful mock interviews.

Core flow:

```text
DOCX → Parse → LLM Structuring → Pydantic Validation
     → SQLite/PostgreSQL → Embeddings → Qdrant
     → Retrieval → Mock Interview → Evaluation → Summary
```

## V1.1 Architecture Rules

- **FastAPI + Python** backend.
- **React + TypeScript** frontend.
- **LlamaIndex** for document/RAG workflows.
- **Qdrant** is the reference vector store.
- **SQLite** is the default local database; **PostgreSQL** for production.
- **Redis is deferred**. Do not add it in Phase 1.
- Relational DB is the **system of record**.
- Qdrant is only a **retrieval index** and must be rebuildable from relational data.
- **Ollama** is the initial local LLM provider.
- Keep provider interfaces for **OpenAI and Anthropic**.
- Embeddings must have a provider abstraction.
- Rubrics are **YAML + Pydantic**, not hardcoded Python constants.
- V1 ships **System Design** rubric first.
- Use **SSE** for LLM streaming; WebSockets are deferred.
- Use a deterministic application state machine for interview workflow.
- The LLM generates questions, follow-ups, evaluations and summaries; it does **not** own workflow state.

## Phase 1 — Current Development Target

Do not start mock interviews yet. First deliver:

1. Repository/project foundation
2. Docker Compose
3. Configuration
4. DOCX upload
5. DOCX parsing
6. LLM-assisted question extraction
7. Pydantic validation
8. SQLite persistence
9. Embeddings
10. Qdrant indexing
11. Metadata + semantic search
12. React question explorer
13. Tests
14. OSS documentation

Phase 1 excludes voice, video, auth, multi-tenancy, billing, Kubernetes, fine-tuning, Redis and complex autonomous agents.

## Repository Structure

```text
interview-prep-coach/
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
│   ├── tests/
│   ├── pyproject.toml
│   └── Dockerfile
├── frontend/
│   ├── src/
│   ├── tests/
│   ├── package.json
│   └── Dockerfile
├── rubrics/
│   └── system_design.yaml
├── docker/
│   ├── docker-compose.yml
│   └── docker-compose.postgres.yml
├── sample-data/
├── docs/
│   ├── architecture.md
│   └── adr/
├── .env.example
├── README.md
├── CONTRIBUTING.md
└── LICENSE
```

Keep domain/business logic independent from FastAPI route handlers.

## Persistence

Use SQLAlchemy or SQLModel + Alembic.

Core Phase 1 entities:

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
```

Future Phase 2 entities:

```text
interview_sessions
interview_messages
evaluations
interview_summaries
```

Never use an in-memory dictionary as the primary session store.

## Provenance

Every question must retain:

```text
source_document_id
source_section
source_type
extraction_confidence
```

`source_type` must distinguish:

```text
user_reported
ai_generated
ai_followup
```

Never present an AI-generated question as a historical/user-reported interview question.

## DOCX Ingestion

Primary parser: `python-docx`.

Extract:

- paragraphs
- headings
- tables

Preserve section information. Normalize whitespace and empty/duplicate lines.

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
Persist
 ↓
Embed
 ↓
Qdrant
```

Use structured LLM output wherever possible. Invalid LLM output must be validated, retried when appropriate, and safely marked failed if it cannot be repaired.

## Question Model

Target structure:

```json
{
  "company": "Amazon",
  "role": "Backend Engineer",
  "round_type": "system_design",
  "question": "Design an order processing system",
  "answer_notes": "Discuss Kafka, idempotency...",
  "difficulty": "hard",
  "tags": ["microservices", "kafka", "scalability"],
  "source_type": "user_reported",
  "source_section": "Round 3 - System Design",
  "extraction_confidence": 0.96
}
```

Use enums for finite fields such as `round_type`, `difficulty`, `source_type` and document status.

## Retrieval

Use:

```text
metadata filtering + semantic similarity
```

Example filters:

```text
company
role
round_type
difficulty
tag
source_type
```

Qdrant payload should include:

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

Retrieval flow:

```text
query
 ↓
embedding
 ↓
Qdrant search + metadata filters
 ↓
question IDs
 ↓
relational DB lookup
 ↓
API response
```

The relational DB remains authoritative.

## Provider Interfaces

Define interfaces before provider-specific business logic.

```python
class LLMProvider:
    async def generate(self, messages, response_schema=None):
        ...
```

Initial implementations:

```text
OllamaProvider
OpenAIProvider
AnthropicProvider
```

Only Ollama needs to be fully implemented for the first local milestone if time is limited.

Embedding:

```python
class EmbeddingProvider:
    async def embed(self, texts):
        ...
```

Vector store:

```python
class VectorStore:
    async def upsert(self, records):
        ...

    async def search(self, query_vector, filters, limit):
        ...

    async def delete(self, ids):
        ...
```

Do not import provider-specific SDKs into core domain logic.

## Rubrics

Rubrics live in `/rubrics/*.yaml`.

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

Persist `rubric_version` with every evaluation.

## Future Interview State Machine

Phase 2 must use:

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
SUMMARY
 ↓
COMPLETED
```

The backend owns state, question count, session lifecycle, persistence and termination rules.

## API

Version all APIs:

```text
/api/v1/...
```

Phase 1:

```http
POST /api/v1/documents
POST /api/v1/documents/{document_id}/ingest
GET  /api/v1/documents

GET  /api/v1/questions
GET  /api/v1/questions/{question_id}
```

Future Phase 2:

```http
POST /api/v1/interviews
GET  /api/v1/interviews/{session_id}
POST /api/v1/interviews/{session_id}/answers
GET  /api/v1/interviews/{session_id}/summary
GET  /api/v1/interviews/{session_id}/transcript
```

Use Pydantic validation and consistent error responses.

## Testing

Every feature must include tests.

Unit tests:

- DOCX parsing
- normalization
- schema validation
- extraction
- repositories
- filtering
- rubric loading
- provider adapters

Integration tests:

```text
DOCX → ingestion → DB → embedding → Qdrant → search
```

Do not depend on a real external LLM for normal unit tests. Use deterministic mocks/fixtures.

## Security

Interview documents may contain sensitive information.

- Never log full documents by default.
- Never log complete user answers by default.
- Keep API keys in environment variables.
- Never commit `.env`.
- Validate uploaded file type.
- Limit upload size.
- Sanitize filenames.
- Do not execute uploaded document content.
- Clearly document when cloud LLM providers receive user data.
- Ollama mode should support local/private processing.

## Docker

V1 reference deployment:

```text
frontend
backend
qdrant
ollama
```

Persist volumes for SQLite, Qdrant and Ollama.

Target:

```bash
docker compose up
```

A standard user should not need to manually install Python, Node or Qdrant for the Docker workflow.

## Phase 1 Implementation Order

Implement in this order:

1. Repository scaffolding
2. Configuration
3. SQLite + SQLAlchemy/SQLModel + Alembic
4. Document model + upload API
5. DOCX parser
6. InterviewQuestion schema
7. Ollama provider
8. LLM structuring service
9. Persist extracted questions
10. Embedding provider
11. Qdrant adapter
12. Index questions
13. Retrieval API
14. React upload page
15. React question explorer
16. Integration tests
17. Docker Compose
18. README/developer docs

## Phase 1 Definition of Done

Phase 1 is complete when:

- A user can upload a DOCX.
- DOCX paragraphs/headings/tables are parsed.
- LLM extracts structured interview questions.
- Pydantic validates the extraction.
- Questions are persisted.
- Provenance is preserved.
- Embeddings are generated.
- Questions are indexed in Qdrant.
- Semantic search works.
- Company/role/round/difficulty filtering works.
- Results show source information.
- User-reported and AI-generated questions are distinguishable.
- Data survives application restart.
- Docker Compose starts the stack.
- Core ingestion/retrieval tests pass.

## Development Rules

1. Read this file before implementing.
2. Inspect existing code before creating or replacing files.
3. Implement one backlog item at a time.
4. Keep commits small and logically scoped.
5. Add tests with backend features.
6. Run tests after meaningful changes.
7. Update documentation when setup or architecture changes.
8. Do not introduce Redis, Kubernetes or future-phase features prematurely.
9. Do not let the LLM control workflow state.
10. Do not make Qdrant the source of truth.
11. Do not hardcode rubrics into Python business logic.
12. Do not hardcode one LLM provider into core logic.
13. Preserve provenance throughout ingestion and retrieval.
14. Never expose secrets.
15. Prefer a simple working implementation over speculative abstractions.
16. If a requested change conflicts with an ADR/architecture rule, explain the conflict and propose the architecture change instead of silently violating it.

## Current Claude Code Task

Unless explicitly asked to work on another phase, start with:

```text
P1-001 Repository setup
P1-002 Docker Compose
P1-003 Configuration module
```

Then:

```text
P1-004 DOCX upload API
P1-005 DOCX parser
```

After each milestone:

```text
- run tests
- verify application startup
- list files changed
- list commands executed
- report completed backlog items
- report remaining Phase 1 items
```

Do not jump directly to the mock interview agent.
