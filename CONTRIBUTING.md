# Contributing

Thanks for considering a contribution.

## Development setup

```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

## Adding an LLM provider

Implement the `LLMProvider` interface in `app/llm_providers/base.py` and register
it in `app/config.py`.

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

## Running tests

```bash
cd backend
pytest
```

## Pull requests

- Keep PRs scoped to one concern.
- Add/update tests for any behavior change.
- Update docs when you change public behavior.
