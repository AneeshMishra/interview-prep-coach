# Interview Preparation Coach

A local-first, open-source AI interview preparation coach. Upload past interview-experience
documents (`.docx`), turn them into a searchable knowledge base, and run stateful mock
interviews graded against configurable rubrics.

> **Status:** Phase 1 in progress — document ingestion, retrieval, and the
> question explorer UI are working end to end. Mock interviews are Phase 2.
> See [docs/architecture.md](docs/architecture.md) for the full V1.1 design.

## Core idea

```
Interview Experiences → Knowledge Base → Personalized Mock Interview
→ Answer Evaluation → Weak Area Detection → Targeted Preparation
```

## Architecture principle

The relational database is the system of record, Qdrant is the retrieval index,
the LLM performs reasoning/generation, and a deterministic state machine owns
interview workflow state. The LLM never becomes the database or the workflow engine.

## Tech stack

| Layer | Choice |
|---|---|
| Backend | FastAPI (Python) |
| Relational DB | SQLite (default) / PostgreSQL (production) |
| Vector DB | Qdrant |
| Embeddings | sentence-transformers (local default) |
| LLM | Ollama (local) / OpenAI / Anthropic (pluggable) |
| Frontend | React + TypeScript |
| Deployment | Docker Compose |

## Quick start (target developer experience)

```bash
git clone <repo-url>
cd interview-prep-coach
docker compose up
```

## Development order (Phase 1 first)

1. Repository & config
2. Database models
3. DOCX parser
4. Structured question schema + validation
5. LLM structuring pass
6. Qdrant embeddings + upsert
7. Retrieval API
8. React question explorer
9. Integration tests
10. Mock interview state machine (Phase 2)
11. Evaluation engine (Phase 3)

**Phase 1 milestone:** upload one `.docx` and reliably retrieve the right interview
questions by company/role/round, with provenance.

## Local backend setup

```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

## Local frontend setup

```bash
cd frontend
npm install
npm run dev
```

Runs on http://localhost:5173 and talks to the backend on
http://localhost:8000 by default — see [frontend/README.md](frontend/README.md).

## License

See [LICENSE](LICENSE).

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md).
