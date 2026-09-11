from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routers import documents, questions
from app.config import get_settings
from app.db.migrate import run_migrations

# Schema is Alembic-managed; this brings a fresh or existing database to the
# latest revision before the app starts serving requests.
run_migrations()

app = FastAPI(
    title="Interview Preparation Coach API",
    description="Document-based AI interview preparation coach",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=get_settings().cors_allowed_origins_list,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(documents.router, prefix="/api/v1")
app.include_router(questions.router, prefix="/api/v1")


@app.get("/health")
def health():
    return {"status": "ok"}
