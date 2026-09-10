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

## Running tests

```bash
cd backend
pytest
```

## Pull requests

- Keep PRs scoped to one concern.
- Add/update tests for any behavior change.
- Update docs when you change public behavior.
