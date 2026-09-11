# ai agent developer Skill

## Mission
Provide specialized implementation guidance for Interview Preparation Coach V1/V1.1.

## Project Rules
- Follow the repository root CLAUDE.md and V1.1 architecture.
- Keep the relational database as the system of record and Qdrant as the retrieval index.
- Keep interview workflow deterministic; the LLM must not own application state.
- Preserve source provenance and distinguish user-reported from AI-generated questions.
- Do not introduce Redis, Kubernetes, auth, multi-tenancy, voice, video or billing in Phase 1.

## Role Focus
- Build LLM-powered question generation, follow-ups, evaluation and summaries.
- Use structured Pydantic outputs and validate every LLM response.
- State machine: SETUP → RETRIEVE → ASK → WAIT_FOR_ANSWER → EVALUATE → FOLLOW_UP_OR_NEXT → SUMMARY → COMPLETED.
- LLM generates content; application controls transitions and persistence.
