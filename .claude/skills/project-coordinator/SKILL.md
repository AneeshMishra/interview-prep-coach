# project coordinator Skill

## Mission
Provide specialized implementation guidance for Interview Preparation Coach V1/V1.1.

## Project Rules
- Follow the repository root CLAUDE.md and V1.1 architecture.
- Keep the relational database as the system of record and Qdrant as the retrieval index.
- Keep interview workflow deterministic; the LLM must not own application state.
- Preserve source provenance and distinguish user-reported from AI-generated questions.
- Do not introduce Redis, Kubernetes, auth, multi-tenancy, voice, video or billing in Phase 1.

## Role Focus
- Enforce phase order: Phase 1 ingestion/retrieval; Phase 2 System Design interview; Phase 3 evaluation; Phase 4 analytics/multiple rubrics; Phase 5 OSS polish.
- Work one backlog item at a time.
- After milestones report files changed, tests, commands, completed items, remaining items and blockers.
