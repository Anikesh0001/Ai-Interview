"""Small text utilities: question de-duplication and concept coverage."""

from __future__ import annotations

import hashlib
import re

from app.data.lexicon import STOPWORDS
from app.services.jd import stem

_WORD = re.compile(r"[a-z0-9+#]+")


def normalize(text: str) -> str:
    return " ".join(_WORD.findall((text or "").lower()))


def question_hash(text: str) -> str:
    return hashlib.sha256(normalize(text).encode()).hexdigest()[:16]


def content_stems(text: str) -> set[str]:
    return {stem(w) for w in _WORD.findall((text or "").lower()) if w not in STOPWORDS and len(w) > 2}


def similarity(a: str, b: str) -> float:
    sa, sb = content_stems(a), content_stems(b)
    if not sa or not sb:
        return 0.0
    return len(sa & sb) / len(sa | sb)


def is_duplicate(text: str, asked_hashes: list[str], asked_texts: list[str], threshold: float = 0.6) -> bool:
    if question_hash(text) in asked_hashes:
        return True
    return any(similarity(text, prev) >= threshold for prev in asked_texts)


def concept_label(concept: str) -> str:
    return concept.split("|", 1)[0].strip()


def concept_covered(answer_lower: str, answer_stems: set[str], concept: str) -> bool:
    """A concept ("a|b|c") is covered if any alternative appears literally, or all its content words do."""
    for alt in concept.split("|"):
        alt = alt.strip().lower()
        if not alt:
            continue
        if re.search(rf"(?<![a-z0-9]){re.escape(alt)}", answer_lower):
            return True
        words = [w for w in _WORD.findall(alt) if w not in STOPWORDS]
        if words and all(stem(w) in answer_stems for w in words):
            return True
    return False
