# Contributing

Thanks for considering a contribution.

## Development setup

```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

```bash
cd frontend
npm install
npm run dev
```

The frontend calls the backend at `http://localhost:8000/api/v1` by
default (see `frontend/.env.example`); the backend's CORS allow-list
(`IPC_CORS_ALLOWED_ORIGINS`) must include the origin you're serving the
frontend from, or the browser will silently block the requests.

## Adding an LLM provider

Implement the `LLMProvider` interface in `app/llm_providers/base.py`, register
it in `app/llm_providers/factory.py`, and add any provider-specific settings
(e.g. an API key) to `app/config.py`. See `openai_provider.py` for the
pattern: plain `httpx` calls to the provider's REST API, no vendor SDK.

## Adding an embedding provider

Implement the `EmbeddingProvider` interface in `app/embeddings/base.py`
(`embed(texts) -> list[list[float]]` plus a `dimension` property, used to
size the Qdrant collection) and register it in `app/embeddings/factory.py`.
`VectorStore` only depends on this interface, never on sentence-transformers
directly, so a new provider needs no changes there.

## Adding a rubric

Add a new YAML file under `app/rubrics/` following the schema in
`app/rubrics/system_design.yaml`.

## Database migrations

Schema changes are managed with Alembic; the app applies the latest
migration automatically on startup (`app/db/migrate.py`), so a fresh
`uvicorn app.main:app` always runs against an up-to-date database.

After changing a model in `app/db/models.py`, generate a migration:

```bash
cd backend
alembic revision --autogenerate -m "describe the change"
```

Review the generated file under `alembic/versions/` — autogenerate doesn't
always get renames, index changes, or SQLite-specific ALTERs right — then
apply it:

```bash
alembic upgrade head
```

To roll back one revision: `alembic downgrade -1`.

## Rebuilding the Qdrant index

Qdrant is a retrieval index, not the source of truth (ADR-002) — it must
always be reconstructable from the relational database alone. If it's
wiped, moved, or you change the embedding model:

```bash
cd backend
python -m app.ingestion.reindex
```

This re-upserts every persisted question. It does not touch the
relational DB.

## Running tests

```bash
cd backend
pytest
```

```bash
cd frontend
npm test
```

## Pull requests

- Keep PRs scoped to one concern.
- Add/update tests for any behavior change.
- Update docs when you change public behavior.
