# backend developer Skill

## Mission
Provide specialized implementation guidance for Interview Preparation Coach V1/V1.1.

## Project Rules
- Follow the repository root CLAUDE.md and V1.1 architecture.
- Keep the relational database as the system of record and Qdrant as the retrieval index.
- Keep interview workflow deterministic; the LLM must not own application state.
- Preserve source provenance and distinguish user-reported from AI-generated questions.
- Do not introduce Redis, Kubernetes, auth, multi-tenancy, voice, video or billing in Phase 1.

## Role Focus
- Use FastAPI, Pydantic, SQLAlchemy/SQLModel and Alembic.
- Keep routes thin: API → service → domain → repository/provider.
- Version APIs under /api/v1.
- Add unit and integration tests for every meaningful feature.
