"""Builds a deterministic interview plan: an ordered list of question slots grounded in the resume/JD."""

from __future__ import annotations

from app.data.lexicon import role_template
from app.data.question_bank import bank_for_skill
from app.data.skills import find_skills, skill_category
from app.schemas import CandidateProfile, InterviewConfig, JDAnalysis, JDMatch

PHASE_ORDER = ["INTRO", "RESUME", "PROJECT", "TECHNICAL", "PROBLEM_SOLVING", "BEHAVIORAL"]

CATEGORY_PHASE = {
    "intro": "INTRO",
    "resume": "RESUME",
    "claim_verification": "RESUME",
    "project": "PROJECT",
    "technical": "TECHNICAL",
    "skills": "TECHNICAL",
    "coding": "TECHNICAL",
    "system_design": "TECHNICAL",
    "jd_specific": "TECHNICAL",
    "role_specific": "TECHNICAL",
    "problem_solving": "PROBLEM_SOLVING",
    "situational": "PROBLEM_SOLVING",
    "behavioral": "BEHAVIORAL",
    "hr": "BEHAVIORAL",
}

# Share of the (non-intro) questions per category for each interview type.
MIXES: dict[str, dict[str, float]] = {
    "Mixed": {
        "resume": 0.12,
        "project": 0.2,
        "technical": 0.3,
        "coding": 0.08,
        "system_design": 0.04,
        "problem_solving": 0.1,
        "behavioral": 0.12,
        "hr": 0.04,
    },
    "Technical": {
        "resume": 0.05,
        "project": 0.15,
        "technical": 0.45,
        "coding": 0.12,
        "system_design": 0.1,
        "problem_solving": 0.13,
    },
    "Behavioral": {"resume": 0.1, "behavioral": 0.6, "situational": 0.2, "hr": 0.1},
    "HR": {"resume": 0.15, "hr": 0.55, "behavioral": 0.3},
    "Project Deep Dive": {"resume": 0.25, "project": 0.75},
    "Coding": {"coding": 0.7, "technical": 0.2, "problem_solving": 0.1},
    "System Design": {"system_design": 0.55, "project": 0.15, "technical": 0.2, "problem_solving": 0.1},
}
MINIMUMS: dict[str, dict[str, int]] = {
    "Mixed": {"resume": 1, "project": 1, "technical": 1, "behavioral": 1},
    "Technical": {"technical": 1, "project": 1},
    "Behavioral": {"behavioral": 1},
    "HR": {"hr": 1},
    "Project Deep Dive": {"project": 1},
    "Coding": {"coding": 1},
    "System Design": {"system_design": 1},
}
# Skills that make poor standalone technical questions; asked only when nothing better exists.
LOW_SIGNAL_SKILLS = {"Git", "Agile", "Postman", "Jira", "Linux", "HTML", "CSS", "Bootstrap", "Excel", "Figma"}
NON_CODING_ROLES = ("product manager", "data analyst", "hr", "designer", "project manager", "business analyst")


def _allocate(n: int, mix: dict[str, float], minimums: dict[str, int]) -> dict[str, int]:
    """Largest-remainder allocation of n slots, honouring minimums when n allows."""
    counts = dict.fromkeys(mix, 0)
    budget = n
    for cat, m in minimums.items():
        if budget <= 0:
            break
        if cat in counts:
            take = min(m, budget)
            counts[cat] += take
            budget -= take
    if budget > 0:
        raw = {c: mix[c] * n - counts[c] for c in mix}
        for c in mix:
            add = max(0, int(raw[c]))
            add = min(add, budget)
            counts[c] += add
            budget -= add
        order = sorted(mix, key=lambda c: (-(raw[c] - int(raw[c])), -mix[c]))
        i = 0
        while budget > 0:
            counts[order[i % len(order)]] += 1
            budget -= 1
            i += 1
    return {c: v for c, v in counts.items() if v > 0}


def _skill_priority(
    profile: CandidateProfile, jd: JDAnalysis | None, config: InterviewConfig
) -> tuple[list[tuple[str, str]], list[str]]:
    """Return ([(skill, source)], jd_gaps). Skills the candidate actually has come first."""
    has = set(profile.skill_mentions)
    ordered: list[tuple[str, str]] = []
    seen: set[str] = set()

    def add(skill: str, source: str) -> None:
        if skill not in seen and skill_category(skill) != "soft":
            seen.add(skill)
            ordered.append((skill, source))

    if config.interview_type == "Custom" and config.custom_focus:
        for s in find_skills(config.custom_focus, include_weak=True):
            add(s, "role_template")

    def rank(skill: str) -> tuple:
        return (skill in LOW_SIGNAL_SKILLS, 0 if bank_for_skill(skill) else 1, -profile.skill_mentions.get(skill, 0))

    gaps: list[str] = []
    if jd:
        jd_owned: list[str] = []
        for req in jd.required_skills:
            alts = req.split(" or ")
            owned = sorted((a for a in alts if a in has), key=rank)
            if owned:
                jd_owned.append(owned[0])
            elif not (set(alts) & LOW_SIGNAL_SKILLS):
                gaps.append(alts[0])
        for s in sorted(jd_owned, key=rank):
            if s not in LOW_SIGNAL_SKILLS:
                add(s, "job_description")
    tpl = role_template(config.target_role)
    core = [s for s in tpl["core_skills"] if s in has]
    # resume skills, preferring those with curated questions and more mentions
    resume_skills = sorted(
        (s for s in profile.skill_mentions if skill_category(s) != "soft"),
        key=lambda s: (
            s in LOW_SIGNAL_SKILLS,
            0 if bank_for_skill(s) else 1,
            -profile.skill_mentions[s],
            0 if s in tpl["core_skills"] + tpl["nice_skills"] else 1,
        ),
    )
    for s in sorted(core, key=rank):
        if s not in LOW_SIGNAL_SKILLS:
            add(s, "resume")
    for s in resume_skills:
        add(s, "resume")
    if not ordered:
        for s in tpl["core_skills"]:
            add(s, "role_template")
    return ordered, gaps


def _rank_projects(profile: CandidateProfile, target_skills: set[str]) -> list[str]:
    def score(p) -> tuple:
        return (-len(set(p.technologies) & target_skills), -len(p.bullets), -len(p.technologies))

    return [p.name for p in sorted(profile.projects, key=score) if p.name]


def build_plan(
    config: InterviewConfig,
    profile: CandidateProfile,
    jd: JDAnalysis | None = None,
    jd_match: JDMatch | None = None,
) -> list[dict]:
    n = config.num_questions
    itype = config.interview_type if config.interview_type in MIXES else "Mixed"
    mix = dict(MIXES[itype])
    role_l = config.target_role.lower()
    if any(r in role_l for r in NON_CODING_ROLES):
        for c in ("coding", "system_design"):
            if c in mix:
                mix["technical"] = mix.get("technical", 0) + mix.pop(c)
    elif itype == "Mixed" and (
        config.experience_level in ("Mid-Level", "Senior") or config.difficulty in ("Hard", "Very Hard")
    ):
        mix["system_design"] += 0.06
        mix["technical"] -= 0.06
    if not profile.projects and "project" in mix:
        share = mix.pop("project")
        mix["technical" if "technical" in mix else next(iter(mix))] = mix.get("technical", 0) + share
    counts = _allocate(n - 1, mix, {k: v for k, v in MINIMUMS.get(itype, {}).items() if k in mix})

    skills, gaps = _skill_priority(profile, jd, config)
    target = {s for s, _ in skills[:10]}
    projects = _rank_projects(profile, target)
    claims = list(profile.claims)

    slots: list[dict] = [
        {"phase": "INTRO", "category": "intro", "focus": "", "focus_kind": "", "source": "role_template"}
    ]

    # resume / claim verification
    exp_entries = [e for e in profile.experience if e.title or e.company]
    for i in range(counts.get("resume", 0)):
        if i < len(claims) and (i == 0 or itype == "Project Deep Dive" or i % 2 == 0):
            c = claims[i]
            slots.append(
                {
                    "phase": "RESUME",
                    "category": "claim_verification",
                    "focus": c.text,
                    "focus_kind": "claim",
                    "claim_kind": c.kind,
                    "subject": c.subject,
                    "source": "resume",
                }
            )
        elif exp_entries:
            e = exp_entries[i % len(exp_entries)]
            slots.append(
                {
                    "phase": "RESUME",
                    "category": "resume",
                    "focus": e.company or e.title,
                    "focus_kind": "experience",
                    "source": "resume",
                }
            )
        elif claims:
            c = claims[i % len(claims)]
            slots.append(
                {
                    "phase": "RESUME",
                    "category": "claim_verification",
                    "focus": c.text,
                    "focus_kind": "claim",
                    "claim_kind": c.kind,
                    "subject": c.subject,
                    "source": "resume",
                }
            )
        else:
            slots.append(
                {"phase": "RESUME", "category": "resume", "focus": "", "focus_kind": "education", "source": "resume"}
            )

    # project deep dive: several angles on the most relevant project, then the next one
    k = counts.get("project", 0)
    for i in range(k):
        if not projects:
            break
        primary_share = max(2, k - 1) if len(projects) > 1 else k
        if i < primary_share:
            name, template = projects[0], i
        else:
            idx = 1 + (i - primary_share) % (len(projects) - 1)
            name, template = projects[idx], (i - primary_share) // (len(projects) - 1)
        slots.append(
            {
                "phase": "PROJECT",
                "category": "project",
                "focus": name,
                "focus_kind": "project",
                "template": template,
                "source": "resume",
            }
        )

    # technical: one skill per slot; reserve one slot for a JD gap when the JD exposes one
    t = counts.get("technical", 0)
    use_gap = bool(gaps) and t >= 3
    skill_slots = t - (1 if use_gap else 0)
    for i in range(skill_slots):
        if skills:
            skill, source = skills[i % len(skills)]
        else:
            skill, source = "", "role_template"
        slots.append(
            {"phase": "TECHNICAL", "category": "technical", "focus": skill, "focus_kind": "skill", "source": source}
        )
    if use_gap:
        slots.append(
            {
                "phase": "TECHNICAL",
                "category": "jd_specific",
                "focus": gaps[0],
                "focus_kind": "skill",
                "source": "job_description",
            }
        )
    for cat in ("coding", "system_design"):
        for _ in range(counts.get(cat, 0)):
            slots.append(
                {"phase": "TECHNICAL", "category": cat, "focus": "", "focus_kind": "", "source": "question_bank"}
            )
    for cat in ("problem_solving", "situational"):
        for _ in range(counts.get(cat, 0)):
            slots.append(
                {"phase": "PROBLEM_SOLVING", "category": cat, "focus": "", "focus_kind": "", "source": "question_bank"}
            )
    for cat in ("behavioral", "hr"):
        for _ in range(counts.get(cat, 0)):
            slots.append(
                {"phase": "BEHAVIORAL", "category": cat, "focus": "", "focus_kind": "", "source": "question_bank"}
            )

    # top up (e.g. no projects / no skills) with behavioral questions so the length is honoured
    while len(slots) < n:
        slots.append(
            {"phase": "BEHAVIORAL", "category": "behavioral", "focus": "", "focus_kind": "", "source": "question_bank"}
        )
    slots = slots[:n]
    slots.sort(key=lambda s: PHASE_ORDER.index(s["phase"]))
    return slots
