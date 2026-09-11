# devops engineer Skill

## Mission
Provide specialized implementation guidance for Interview Preparation Coach V1/V1.1.

## Project Rules
- Follow the repository root CLAUDE.md and V1.1 architecture.
- Keep the relational database as the system of record and Qdrant as the retrieval index.
- Keep interview workflow deterministic; the LLM must not own application state.
- Preserve source provenance and distinguish user-reported from AI-generated questions.
- Do not introduce Redis, Kubernetes, auth, multi-tenancy, voice, video or billing in Phase 1.

## Role Focus
- Use Docker Compose for V1 with frontend, backend, Qdrant and Ollama.
- Provide health checks, persistent volumes, .env.example and reproducible builds.
- Keep secrets out of source control.
- CI should run backend tests and frontend build/tests.
