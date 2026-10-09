"""Question generation: local LLM when available, curated bank otherwise. Never repeats a question."""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field

from app.ai.llm import get_provider
from app.ai.prompts import question_generation
from app.data import question_bank as bank
from app.data.skills import skill_category
from app.interview.textutil import concept_label, is_duplicate
from app.schemas import CandidateProfile, LLMQuestion, QuestionSchema

logger = logging.getLogger(__name__)

DIFFICULTIES = ["Easy", "Medium", "Hard", "Very Hard"]
LEAK_RE = re.compile(r"system prompt|my instructions|as an ai|language model|untrusted_", re.I)


@dataclass
class InterviewContext:
    role: str
    level: str
    personality: str
    profile: CandidateProfile
    resume_text: str
    jd_summary: str = ""
    answer_history: list[str] = field(default_factory=list)
    seed: int = 0

    def as_prompt_dict(self) -> dict:
        p = self.profile
        edu = p.education[0] if p.education else None
        return {
            "role": self.role,
            "level": self.level,
            "personality": self.personality,
            "skills": p.skills,
            "projects": [pr.name for pr in p.projects],
            "experience": [f"{e.title} at {e.company}".strip(" at") for e in p.experience],
            "education": f"{edu.degree}, {edu.institution}" if edu else "",
            "resume_excerpt": self.resume_text[:2500],
            "jd_summary": self.jd_summary,
            "answer_history": "\n".join(self.answer_history[-4:]),
        }


@dataclass
class GeneratedQuestion:
    schema: QuestionSchema
    generated_by: str  # "llm" | "bank"
    probe: str = ""


def difficulty_distance(a: str, b: str) -> int:
    ia = DIFFICULTIES.index(a) if a in DIFFICULTIES else 1
    ib = DIFFICULTIES.index(b) if b in DIFFICULTIES else 1
    return abs(ia - ib)


def _pick(
    candidates: list[bank.BankQuestion],
    difficulty: str,
    asked_hashes: list[str],
    asked_texts: list[str],
    seed: int,
    fmt: dict[str, str],
) -> tuple[bank.BankQuestion, str] | None:
    if not candidates:
        return None
    n = len(candidates)
    rotated = [candidates[(i + seed) % n] for i in range(n)]
    ordered = sorted(rotated, key=lambda q: difficulty_distance(q.difficulty, difficulty))
    for q in ordered:
        text = _fmt(q.q, fmt)
        if not is_duplicate(text, asked_hashes, asked_texts):
            return q, text
    return None


def _fmt(template: str, values: dict[str, str]) -> str:
    out = template
    for k, v in values.items():
        out = out.replace("{" + k + "}", v)
    return out


def _schema_from_bank(
    q: bank.BankQuestion,
    text: str,
    slot: dict,
    fmt: dict[str, str],
    source: str,
    skill: str = "",
    claim: str | None = None,
) -> GeneratedQuestion:
    rubric = list(q.rubric) or [
        f"Covers: {', '.join(concept_label(c) for c in q.concepts[:4])}",
        "Gives concrete, specific examples rather than generalities",
        "Explains reasoning and trade-offs clearly",
    ]
    return GeneratedQuestion(
        QuestionSchema(
            question=text,
            category=slot["category"],
            difficulty=q.difficulty,
            skill=skill,
            source=source,
            expected_concepts=list(q.concepts),
            evaluation_rubric=rubric,
            ideal_answer=_fmt(q.ideal, fmt),
            claim=claim,
        ),
        "bank",
        _fmt(q.probe, fmt),
    )


def bank_question(
    slot: dict,
    ctx: InterviewContext,
    difficulty: str,
    asked_hashes: list[str],
    asked_texts: list[str],
) -> GeneratedQuestion:
    cat = slot["category"]
    p = ctx.profile
    seed = ctx.seed + len(asked_texts)
    fmt = {"role": ctx.role, "skill": slot.get("focus") or "this technology"}

    if cat == "intro":
        n = len(bank.INTRO)
        for i in range(n):
            text = _fmt(bank.INTRO[(ctx.seed + i) % n], fmt)
            if not is_duplicate(text, asked_hashes, asked_texts):
                break
        q = bank.BankQuestion(text, "Easy", tuple(bank.INTRO_CONCEPTS), bank.INTRO_IDEAL)
        return _schema_from_bank(q, text, slot, fmt, "role_template")

    if cat == "claim_verification" and slot.get("focus"):
        claim = slot["focus"]
        fmt["claim"] = claim.rstrip(".")
        kind = slot.get("claim_kind", "metric")
        picked = _pick(
            bank.CLAIM_TEMPLATES.get(kind, bank.CLAIM_TEMPLATES["metric"]),
            difficulty,
            asked_hashes,
            asked_texts,
            seed,
            fmt,
        )
        if picked:
            return _schema_from_bank(picked[0], picked[1], slot, fmt, "resume", claim=claim)
        cat = "resume"

    if cat == "resume":
        if slot.get("focus_kind") == "experience":
            exp = next((e for e in p.experience if slot["focus"] in (e.company, e.title)), None)
            if exp:
                fmt.update(title=exp.title or "your role", company=exp.company or "that company")
                picked = _pick(bank.EXPERIENCE_TEMPLATES, difficulty, asked_hashes, asked_texts, seed, fmt)
                if picked:
                    return _schema_from_bank(picked[0], picked[1], slot, fmt, "resume")
        degree = p.education[0].degree if p.education else "studies"
        fmt["degree"] = degree
        picked = _pick(bank.EDUCATION_TEMPLATES, difficulty, asked_hashes, asked_texts, seed, fmt)
        if picked:
            return _schema_from_bank(picked[0], picked[1], slot, fmt, "resume")
        cat = "behavioral"

    if cat == "project" and slot.get("focus"):
        proj = next((x for x in p.projects if x.name == slot["focus"]), None)
        stack_categories = ("programming_languages", "frameworks", "databases", "tools")
        techs = [t for t in (proj.technologies if proj else []) if skill_category(t) in stack_categories][:3]
        fmt.update(project=slot["focus"], techs=" and ".join(techs) if techs else "your technology stack")
        start = int(slot.get("template", 0))
        templates = bank.PROJECT_TEMPLATES
        if not techs:
            templates = [t for t in templates if "{techs}" not in t.q]
        ordered = [templates[(start + i) % len(templates)] for i in range(len(templates))]
        for q in ordered:
            text = _fmt(q.q, fmt)
            if not is_duplicate(text, asked_hashes, asked_texts):
                return _schema_from_bank(q, text, slot, fmt, "resume")
        cat = "technical"

    if cat in ("technical", "skills", "role_specific", "jd_specific"):
        skill = slot.get("focus") or ""
        source = slot.get("source", "resume")
        if cat == "jd_specific" and skill:
            text = _fmt(bank.JD_GAP_TEMPLATE.q, fmt)
            if not is_duplicate(text, asked_hashes, asked_texts):
                return _schema_from_bank(bank.JD_GAP_TEMPLATE, text, slot, fmt, "job_description", skill=skill)
        candidates = bank.bank_for_skill(skill) if skill else []
        picked = _pick(candidates, difficulty, asked_hashes, asked_texts, seed, fmt)
        if picked is None and skill:
            picked = _pick(bank.GENERIC_SKILL, difficulty, asked_hashes, asked_texts, seed, fmt)
        if picked:
            src = "job_description" if source == "job_description" else ("resume" if skill else "question_bank")
            return _schema_from_bank(picked[0], picked[1], {**slot, "category": "technical"}, fmt, src, skill=skill)
        cat = "problem_solving"

    pools = {
        "coding": bank.CODING,
        "system_design": bank.SYSTEM_DESIGN,
        "problem_solving": bank.PROBLEM_SOLVING,
        "situational": bank.SITUATIONAL,
        "behavioral": bank.BEHAVIORAL,
        "hr": bank.HR,
    }
    order = [cat] + [c for c in pools if c != cat]
    for c in order:
        if c not in pools:
            continue
        picked = _pick(pools[c], difficulty, asked_hashes, asked_texts, seed, fmt)
        if picked:
            return _schema_from_bank(picked[0], picked[1], {**slot, "category": c}, fmt, "question_bank")
    # Every pool exhausted (extremely long interview): ask a generic reflective question.
    q = bank.BankQuestion(
        "Is there anything about your experience we haven't covered that you think is relevant for this role?",
        "Easy",
        ("relevant experience", "example", "impact"),
        "Highlight one relevant, concrete accomplishment not yet discussed.",
    )
    return _schema_from_bank(q, q.q, {**slot, "category": "hr"}, fmt, "question_bank")


def llm_question(
    slot: dict, ctx: InterviewContext, difficulty: str, asked_hashes: list[str], asked_texts: list[str]
) -> GeneratedQuestion | None:
    provider = get_provider()
    if not provider.is_available():
        return None
    excerpt = ""
    if slot.get("focus_kind") == "project":
        proj = next((x for x in ctx.profile.projects if x.name == slot["focus"]), None)
        if proj:
            excerpt = "\n".join([proj.name, proj.description, *proj.bullets])
    elif slot.get("focus_kind") == "claim":
        excerpt = slot["focus"]
    system, user = question_generation.build(
        ctx=ctx.as_prompt_dict(), slot={**slot, "context_text": excerpt}, asked=asked_texts, difficulty=difficulty
    )

    def validate(q: LLMQuestion) -> str | None:
        if LEAK_RE.search(q.question):
            return "The question must not mention prompts, instructions or AI."
        if is_duplicate(q.question, asked_hashes, asked_texts):
            return "That question repeats one already asked. Ask about a different aspect."
        if q.question.count("?") > 3:
            return "Ask one question at a time."
        return None

    result = provider.complete_structured(system, user, LLMQuestion, validator=validate)
    if result is None:
        return None
    cat = slot["category"]
    source = {
        "intro": "role_template",
        "claim_verification": "resume",
        "resume": "resume",
        "project": "resume",
        "jd_specific": "job_description",
    }.get(cat, "resume" if slot.get("focus") else "question_bank")
    if cat == "technical" and slot.get("source") == "job_description":
        source = "job_description"
    try:
        schema = QuestionSchema(
            question=result.question.strip(),
            category=cat,
            difficulty=difficulty,
            skill=slot.get("focus", "") if slot.get("focus_kind") == "skill" else "",
            source=source,
            expected_concepts=[c.strip() for c in result.expected_concepts if c.strip()][:8],
            evaluation_rubric=[r.strip() for r in result.evaluation_rubric if r.strip()][:6],
            ideal_answer=result.ideal_answer.strip(),
            claim=slot["focus"] if cat == "claim_verification" else None,
        )
    except Exception as exc:
        logger.info("llm question failed schema: %s", type(exc).__name__)
        return None
    return GeneratedQuestion(schema, "llm")


def generate_question(
    slot: dict, ctx: InterviewContext, difficulty: str, asked_hashes: list[str], asked_texts: list[str]
) -> GeneratedQuestion:
    # The intro is always templated: it needs no reasoning, and saves an LLM round-trip.
    if slot["category"] != "intro":
        llm = llm_question(slot, ctx, difficulty, asked_hashes, asked_texts)
        if llm is not None:
            return llm
    return bank_question(slot, ctx, difficulty, asked_hashes, asked_texts)
