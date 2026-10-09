"""FastAPI application factory."""

from __future__ import annotations

import logging
import time
import uuid
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from sqlalchemy.exc import SQLAlchemyError

from app.ai.llm import set_runtime_options
from app.api.routes import router
from app.config import get_settings
from app.db import SessionLocal, init_engine
from app.interview.engine import InterviewError
from app.interview.state import InvalidTransition
from app.models import SettingRow
from app.services.extract import ResumeParseError
from app.services.jd import InvalidJobDescription

logger = logging.getLogger("interviewforge")


def configure_logging() -> None:
    if not logging.getLogger().handlers:
        logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")


def _load_runtime_settings() -> None:
    db = SessionLocal()
    try:
        values = {row.key: row.value for row in db.query(SettingRow).all()}
        set_runtime_options(model=values.get("ollama_model"), base_url=values.get("ollama_base_url"))
    except SQLAlchemyError:
        logger.warning("could not load saved settings")
    finally:
        db.close()


@asynccontextmanager
async def lifespan(_app: FastAPI):
    settings = get_settings()
    init_engine(settings.database_url)
    Path(settings.upload_dir).mkdir(parents=True, exist_ok=True)
    _load_runtime_settings()
    logger.info("InterviewForge started env=%s test_mode=%s", settings.app_env, settings.test_mode)
    yield


def _error(status: int, message: str, request: Request, code: str = "error") -> JSONResponse:
    rid = getattr(request.state, "request_id", "")
    return JSONResponse(status_code=status, content={"detail": message, "code": code, "request_id": rid})


def create_app() -> FastAPI:
    configure_logging()
    settings = get_settings()
    app = FastAPI(title="InterviewForge API", version="1.0.0", lifespan=lifespan)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=False,
        allow_methods=["GET", "POST", "PUT", "DELETE"],
        allow_headers=["Content-Type"],
    )

    @app.middleware("http")
    async def request_logging(request: Request, call_next):
        rid = uuid.uuid4().hex[:12]
        request.state.request_id = rid
        started = time.perf_counter()
        error_type = "-"
        try:
            response = await call_next(request)
        except Exception as exc:  # pragma: no cover - handled by exception handlers
            error_type = type(exc).__name__
            raise
        finally:
            duration_ms = (time.perf_counter() - started) * 1000
            # Never log request bodies: they contain resumes and answers.
            if request.url.path.startswith("/api"):
                logger.info(
                    "request_id=%s method=%s path=%s duration_ms=%.0f error=%s",
                    rid,
                    request.method,
                    request.url.path,
                    duration_ms,
                    error_type,
                )
        response.headers["X-Request-ID"] = rid
        response.headers["X-Content-Type-Options"] = "nosniff"
        return response

    @app.exception_handler(ResumeParseError)
    async def _parse_error(request: Request, exc: ResumeParseError):
        return _error(exc.status_code, exc.user_message, request, "resume_parse_error")

    @app.exception_handler(InvalidJobDescription)
    async def _jd_error(request: Request, exc: InvalidJobDescription):
        return _error(422, str(exc), request, "invalid_job_description")

    @app.exception_handler(InterviewError)
    async def _interview_error(request: Request, exc: InterviewError):
        return _error(exc.status_code, exc.user_message, request, "interview_error")

    @app.exception_handler(InvalidTransition)
    async def _transition_error(request: Request, exc: InvalidTransition):
        logger.warning("invalid transition: %s", exc)
        return _error(409, "That action isn't possible at this stage of the interview.", request, "invalid_state")

    @app.exception_handler(HTTPException)
    async def _http_error(request: Request, exc: HTTPException):
        return _error(exc.status_code, str(exc.detail), request, "http_error")

    @app.exception_handler(RequestValidationError)
    async def _validation_error(request: Request, exc: RequestValidationError):
        first = exc.errors()[0] if exc.errors() else {}
        field = ".".join(str(p) for p in first.get("loc", []) if p not in ("body", "query"))
        msg = first.get("msg", "Invalid request")
        if "at most" in msg and "character" in msg:
            msg = "That text is too long."
        return _error(422, f"Invalid input{(' for ' + field) if field else ''}: {msg}", request, "validation_error")

    @app.exception_handler(SQLAlchemyError)
    async def _db_error(request: Request, exc: SQLAlchemyError):
        logger.error("database error: %s", type(exc).__name__)
        return _error(503, "A local database error occurred. Please try again.", request, "database_error")

    @app.exception_handler(Exception)
    async def _unhandled(request: Request, exc: Exception):
        logger.exception("unhandled error request_id=%s", getattr(request.state, "request_id", ""))
        return _error(500, "Something went wrong on our side. Please try again.", request, "internal_error")

    app.include_router(router)

    # Serve the built frontend (single-process mode, e.g. Docker) when it exists.
    dist = Path(settings.frontend_dist)
    if dist.is_dir() and (dist / "index.html").exists():
        dist_resolved = dist.resolve()

        @app.get("/{full_path:path}", include_in_schema=False)
        async def spa(full_path: str):
            if full_path.startswith("api/"):
                raise HTTPException(404, "Not found.")
            candidate = (dist_resolved / full_path).resolve()
            if full_path and candidate.is_file() and dist_resolved in candidate.parents:
                return FileResponse(candidate)
            return FileResponse(dist_resolved / "index.html")

    return app


app = create_app()
