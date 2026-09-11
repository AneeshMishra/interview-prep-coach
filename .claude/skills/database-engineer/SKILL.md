# database engineer Skill

## Mission
Provide specialized implementation guidance for Interview Preparation Coach V1/V1.1.

## Project Rules
- Follow the repository root CLAUDE.md and V1.1 architecture.
- Keep the relational database as the system of record and Qdrant as the retrieval index.
- Keep interview workflow deterministic; the LLM must not own application state.
- Preserve source provenance and distinguish user-reported from AI-generated questions.
- Do not introduce Redis, Kubernetes, auth, multi-tenancy, voice, video or billing in Phase 1.

## Role Focus
- SQLite is the default local database; PostgreSQL is the production database.
- Use migrations, constraints, indexes and timestamps.
- Phase 1 entities: documents, interview_questions and question_tags.
- Future entities: sessions, messages, evaluations and summaries.
