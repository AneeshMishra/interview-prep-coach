# Frontend

React + TypeScript UI for the Phase 1 backend milestone: upload a `.docx`,
watch ingestion status, and search/filter the resulting question knowledge
base.

## Screens

- **Upload** — pick a `.docx`, see it and any previously uploaded documents
  with live ingestion status (polls while a document is pending/processing).
- **Question Explorer** — filter by company/role/round/difficulty, free-text
  semantic search, and a "needs review only" toggle for low-confidence
  extractions (see `docs/architecture.md` P1-007).
- **Question Detail** — full question with provenance: source document
  section, extraction confidence, tags, and a clear **User Reported** vs
  **AI Generated** badge — the product must never blur that distinction.

Mock interview screens are Phase 2 and not built yet.

## Local development

```bash
cd frontend
npm install
npm run dev
```

Runs on http://localhost:5173 and expects the backend at
http://localhost:8000 (see `.env.example` to override).

## Tests

```bash
npm test
```

## Build

```bash
npm run build
```

Type-checks then produces a static `dist/` bundle. The Docker image
(`Dockerfile`) builds this and serves it via nginx on port 3000, matching
the root `docker-compose.yml`.
