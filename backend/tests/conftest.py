"""Shared fixtures. The environment is configured *before* the app is imported so the
module-level ``create_app()`` and every ``get_settings()`` call see test settings."""

from __future__ import annotations

import atexit
import os
import shutil
import sys
import tempfile
from collections.abc import Iterator
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # make `app` importable

_BOOT_DIR = Path(tempfile.mkdtemp(prefix="interviewforge-tests-"))
atexit.register(shutil.rmtree, _BOOT_DIR, ignore_errors=True)
os.environ["TEST_MODE"] = "true"
os.environ["LLM_PROVIDER"] = "none"
os.environ["DATABASE_URL"] = f"sqlite:///{_BOOT_DIR / 'boot.db'}"
os.environ["UPLOAD_DIR"] = str(_BOOT_DIR / "uploads")
os.environ["FRONTEND_DIST"] = str(_BOOT_DIR / "no-frontend")
for _var in ("ATS_WEIGHTS", "ANSWER_WEIGHTS", "BEHAVIORAL_ANSWER_WEIGHTS", "INTERVIEW_WEIGHTS", "READINESS_WEIGHTS"):
    os.environ.pop(_var, None)

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app import db as app_db  # noqa: E402
from app.ai import llm  # noqa: E402
from app.config import get_settings  # noqa: E402

get_settings.cache_clear()

from helpers import FIXTURES_DIR  # noqa: E402

from app.main import app  # noqa: E402


@pytest.fixture(autouse=True)
def isolated_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[Path]:
    """Give every test its own SQLite file and upload directory, and reset global LLM state."""
    db_url = f"sqlite:///{tmp_path / 'test.db'}"
    upload_dir = tmp_path / "uploads"
    monkeypatch.setenv("DATABASE_URL", db_url)
    monkeypatch.setenv("UPLOAD_DIR", str(upload_dir))
    get_settings.cache_clear()
    app_db.init_engine(db_url)
    llm.set_provider(None)
    llm._runtime.clear()
    yield tmp_path
    llm.set_provider(None)
    llm._runtime.clear()
    if app_db._engine is not None:
        app_db._engine.dispose()
    get_settings.cache_clear()


@pytest.fixture
def client() -> Iterator[TestClient]:
    with TestClient(app) as c:
        yield c


@pytest.fixture
def fixtures_dir() -> Path:
    return FIXTURES_DIR


@pytest.fixture
def sample_text() -> str:
    return (FIXTURES_DIR / "sample_resume.txt").read_text(encoding="utf-8")


@pytest.fixture
def db_session():
    session = app_db.SessionLocal()
    try:
        yield session
    finally:
        session.close()
