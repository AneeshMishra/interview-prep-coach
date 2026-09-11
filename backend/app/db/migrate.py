"""
Programmatic Alembic entrypoint so `uvicorn app.main:app` always starts
against an up-to-date schema without a manual `alembic upgrade head` step.
"""
from pathlib import Path

from alembic import command
from alembic.config import Config

BACKEND_ROOT = Path(__file__).resolve().parent.parent.parent


def run_migrations() -> None:
    config = Config(str(BACKEND_ROOT / "alembic.ini"))
    config.set_main_option("script_location", str(BACKEND_ROOT / "alembic"))
    command.upgrade(config, "head")
