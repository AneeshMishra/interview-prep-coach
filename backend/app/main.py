from fastapi import FastAPI

from app.api.routers import documents, questions
from app.db.base import Base, engine

# v1: create tables directly. Swap for Alembic migrations once schema stabilizes.
Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="Interview Preparation Coach API",
    description="Document-based AI interview preparation coach",
    version="0.1.0",
)

app.include_router(documents.router, prefix="/api/v1")
app.include_router(questions.router, prefix="/api/v1")


@app.get("/health")
def health():
    return {"status": "ok"}
