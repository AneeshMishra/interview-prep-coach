# Interview Preparation Coach

A local-first, open-source AI interview preparation coach. Upload past interview-experience
documents (`.docx`), turn them into a searchable knowledge base, and run stateful mock
interviews graded against configurable rubrics.

> **Status:** Phase 1 (ingestion, retrieval, question explorer) and the
> Phase 2 core (Q&A chat, mock interviews, multi-user auth, chat/interview
> history) are working end to end. See
> [docs/architecture.md](docs/architecture.md) for the full V1.1 design.

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
cp .env.example .env    # then fill in the Google OAuth values — see below
docker compose up
```

Every route in the app requires signing in, so `docker compose up` will start but the
app itself won't be usable until Google sign-in is configured (next section). Compose
fails fast with a clear error if `.env` doesn't exist at all, rather than starting with
an unconfigured, silently-broken login.

## Authentication setup

Sign-in is always via an external OAuth provider — there's no local password. Google is
the only provider implemented so far (Facebook, LinkedIn and Azure AD SSO are planned;
see `backend/app/auth/oauth/factory.py`).

1. Go to the [Google Cloud Console credentials page](https://console.cloud.google.com/apis/credentials)
   and create an **OAuth client ID** of type **Web application** (create a project first
   if you don't have one).
2. Under **Authorized redirect URIs**, add exactly:
   `http://localhost:8000/api/v1/auth/google/callback`
   (this must match `IPC_GOOGLE_OAUTH_REDIRECT_URI` in your `.env` — the default already
   matches the Docker Compose and local-dev backend port).
3. Copy the generated **Client ID** and **Client secret** into your `.env`:
   ```
   IPC_GOOGLE_CLIENT_ID=...
   IPC_GOOGLE_CLIENT_SECRET=...
   ```
4. Also set a real `IPC_JWT_SECRET_KEY` outside local dev — the checked-in default is
   intentionally insecure. Generate one with:
   ```bash
   python -c "import secrets; print(secrets.token_urlsafe(48))"
   ```

See `.env.example` for every other setting (LLM provider, embeddings, CORS, upload
limits) with inline comments.

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
cp ../.env.example .env    # pydantic-settings reads .env relative to this directory
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

For local (non-Docker) dev, also change `IPC_QDRANT_URL`/`IPC_OLLAMA_BASE_URL` in
`backend/.env` back to `http://localhost:...` (the `qdrant`/`ollama` hostnames in
`.env.example` only resolve inside the Docker Compose network) and set
`IPC_FRONTEND_BASE_URL=http://localhost:5173` to match the Vite dev server.

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
