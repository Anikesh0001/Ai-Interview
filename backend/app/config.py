"""Application configuration, loaded from environment variables and an optional .env file."""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Annotated

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parent.parent
PROJECT_DIR = BACKEND_DIR.parent

# Scoring weights. Every group must sum to 1.0; they can be overridden through the
# *_WEIGHTS environment variables (JSON objects) or the settings page.
DEFAULT_ATS_WEIGHTS: dict[str, float] = {
    "keyword_match": 0.15,
    "skills_match": 0.15,
    "experience_relevance": 0.10,
    "project_relevance": 0.10,
    "achievements": 0.10,
    "structure": 0.10,
    "completeness": 0.10,
    "education": 0.05,
    "formatting": 0.05,
    "action_verbs": 0.05,
    "contact": 0.05,
}

DEFAULT_ANSWER_WEIGHTS: dict[str, float] = {
    "technical_correctness": 0.25,
    "relevance": 0.15,
    "depth": 0.15,
    "completeness": 0.15,
    "problem_solving": 0.15,
    "communication": 0.10,
    "confidence_indicators": 0.05,
}

# Behavioral / HR answers are judged on structure and relevance, not technical accuracy.
DEFAULT_BEHAVIORAL_ANSWER_WEIGHTS: dict[str, float] = {
    "technical_correctness": 0.05,
    "relevance": 0.25,
    "depth": 0.15,
    "completeness": 0.20,
    "problem_solving": 0.10,
    "communication": 0.20,
    "confidence_indicators": 0.05,
}

DEFAULT_INTERVIEW_WEIGHTS: dict[str, float] = {
    "technical": 0.30,
    "problem_solving": 0.20,
    "project_knowledge": 0.15,
    "communication": 0.15,
    "behavioral": 0.10,
    "role_fit": 0.10,
}

DEFAULT_READINESS_WEIGHTS: dict[str, float] = {
    "interview": 0.40,
    "jd_match": 0.30,
    "ats": 0.20,
    "evidence": 0.10,
}


def _normalise(weights: dict[str, float], defaults: dict[str, float]) -> dict[str, float]:
    merged = {k: float(weights.get(k, v)) for k, v in defaults.items()}
    if any(v < 0 for v in merged.values()):
        raise ValueError("weights must be non-negative")
    total = sum(merged.values())
    if total <= 0:
        raise ValueError("weights must not all be zero")
    return {k: v / total for k, v in merged.items()}


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(str(PROJECT_DIR / ".env"), str(BACKEND_DIR / ".env")),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_env: str = "development"
    database_url: str = f"sqlite:///{PROJECT_DIR / 'data' / 'interviewforge.db'}"
    upload_dir: Path = PROJECT_DIR / "uploads"
    frontend_dist: Path = PROJECT_DIR / "frontend" / "dist"

    llm_provider: str = "ollama"  # "ollama" or "none"
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "qwen2.5:3b"
    llm_timeout_seconds: float = 90.0
    llm_temperature: float = 0.4
    llm_max_retries: int = 1

    max_resume_size_mb: float = 10.0
    max_jd_chars: int = 20000
    max_answer_chars: int = 6000
    interview_default_questions: int = 10
    voice_enabled: bool = True
    test_mode: bool = False

    cors_origins: Annotated[list[str], NoDecode] = Field(
        default_factory=lambda: [
            "http://localhost:5173",
            "http://127.0.0.1:5173",
            "http://localhost:4173",
            "http://127.0.0.1:4173",
        ]
    )

    ats_weights: dict[str, float] = Field(default_factory=dict)
    answer_weights: dict[str, float] = Field(default_factory=dict)
    behavioral_answer_weights: dict[str, float] = Field(default_factory=dict)
    interview_weights: dict[str, float] = Field(default_factory=dict)
    readiness_weights: dict[str, float] = Field(default_factory=dict)

    @field_validator("cors_origins", mode="before")
    @classmethod
    def _split_origins(cls, v: object) -> object:
        if isinstance(v, str):
            if v.strip().startswith("["):
                return json.loads(v)
            return [o.strip() for o in v.split(",") if o.strip()]
        return v

    @field_validator(
        "ats_weights",
        "answer_weights",
        "behavioral_answer_weights",
        "interview_weights",
        "readiness_weights",
        mode="before",
    )
    @classmethod
    def _parse_weights(cls, v: object) -> object:
        if isinstance(v, str):
            return json.loads(v) if v.strip() else {}
        return v

    @property
    def max_resume_bytes(self) -> int:
        return int(self.max_resume_size_mb * 1024 * 1024)

    @property
    def llm_enabled(self) -> bool:
        return not self.test_mode and self.llm_provider.lower() != "none"

    def weights(self, group: str) -> dict[str, float]:
        defaults = {
            "ats": DEFAULT_ATS_WEIGHTS,
            "answer": DEFAULT_ANSWER_WEIGHTS,
            "behavioral_answer": DEFAULT_BEHAVIORAL_ANSWER_WEIGHTS,
            "interview": DEFAULT_INTERVIEW_WEIGHTS,
            "readiness": DEFAULT_READINESS_WEIGHTS,
        }[group]
        overrides = getattr(self, f"{group}_weights")
        return _normalise(overrides, defaults)


@lru_cache
def get_settings() -> Settings:
    return Settings()
