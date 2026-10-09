"""Deterministic job-description analysis and resume <-> JD matching."""

from __future__ import annotations

import re
from collections import Counter

from app.data.lexicon import GENERIC_JD_WORDS, STOPWORDS
from app.data.skills import SKILLS, _compiled, find_line_evidence, find_skills, skill_family
from app.schemas import CandidateProfile, JDAnalysis, JDMatch, RequirementMatch

REQ_HEADINGS = re.compile(
    r"^(requirements?|qualifications?|minimum qualifications|basic qualifications|what you('| wi)ll need|"
    r"must[- ]haves?|who you are|what we('re| are) looking for|skills( required)?|you have|about you|"
    r"required skills)\s*:?$",
    re.I,
)
PREF_HEADINGS = re.compile(
    r"^(nice[- ]to[- ]haves?|preferred( qualifications| skills)?|bonus( points)?|good to have|pluses|"
    r"preferred|additional qualifications|it'?s a plus if)\s*:?$",
    re.I,
)
RESP_HEADINGS = re.compile(
    r"^(responsibilities|key responsibilities|what you('| wi)ll do|the role|duties|your role|"
    r"day[- ]to[- ]day|role overview|in this role)\s*:?$",
    re.I,
)
OTHER_HEADINGS = re.compile(r"^(about (us|the company|the role)|benefits|perks|why join us|compensation)\s*:?$", re.I)
PREF_CUE = re.compile(r"\b(nice to have|preferred|is a plus|a plus|bonus|ideally|good to have|exposure to)\b", re.I)
YEARS_RE = re.compile(r"(\d+(?:\.\d+)?)\s*(?:\+|\s*(?:-|–|to)\s*\d+)?\s*(?:years?|yrs)", re.I)
DEGREE_REQ_RE = re.compile(r"\b(bachelor|master|degree|b\.?tech|b\.?e\b|b\.?s\b|m\.?s\b|ph\.?d|diploma)", re.I)
SENIORITY_RE = re.compile(r"\b(intern|junior|entry[- ]level|graduate|mid[- ]level|senior|staff|lead|principal)\b", re.I)
DOMAIN_TERMS = [
    "fintech",
    "payments",
    "banking",
    "healthcare",
    "e-commerce",
    "ecommerce",
    "retail",
    "logistics",
    "saas",
    "b2b",
    "b2c",
    "edtech",
    "gaming",
    "insurance",
    "telecom",
    "marketplace",
    "supply chain",
    "advertising",
    "media",
    "security",
    "cybersecurity",
    "analytics",
    "automotive",
    "travel",
    "real estate",
    "crm",
]


class InvalidJobDescription(ValueError):
    pass


def _tokens(text: str) -> list[str]:
    return re.findall(r"[a-z][a-z+#.\-/]*[a-z+#]|[a-z]", text.lower())


def stem(word: str) -> str:
    for suf in ("ization", "isation", "ations", "ation", "ments", "ment", "ings", "ing", "ies", "ers", "ed", "es", "s"):
        if word.endswith(suf) and len(word) - len(suf) >= 4:
            return word[: -len(suf)]
    return word


def text_contains_term(text_lower: str, term: str, text_stems: set[str] | None = None) -> bool:
    term_l = term.lower().strip()
    if not term_l:
        return False
    if re.search(rf"(?<![a-z0-9]){re.escape(term_l)}(?![a-z0-9])", text_lower):
        return True
    words = _tokens(term_l)
    if not words:
        return False
    stems = text_stems if text_stems is not None else {stem(w) for w in _tokens(text_lower)}
    return all(stem(w) in stems for w in words)


def _skill_groups(line: str) -> list[list[str]]:
    """Find skills in a line and group alternatives such as "Python or Java" or "PostgreSQL/MySQL"."""
    hits: list[tuple[int, int, str]] = []
    for name, strong, _weak in _compiled():
        for p in strong:
            for m in p.finditer(line):
                hits.append((m.start(), m.end(), name))
    # keep the longest non-overlapping matches ("Tailwind CSS" beats "CSS")
    hits.sort(key=lambda h: (h[0], -(h[1] - h[0])))
    kept: list[tuple[int, int, str]] = []
    for h in hits:
        if any(h[0] < k[1] and k[0] < h[1] for k in kept):
            continue
        kept.append(h)
    kept.sort()
    dedup: list[tuple[int, int, str]] = []
    for h in kept:
        if any(d[2] == h[2] for d in dedup):
            continue
        dedup.append(h)
    groups: list[list[str]] = []
    chain: list[str] = []
    chain_has_or = False
    prev_end = None
    for start, end, name in dedup:
        connector = line[prev_end:start] if prev_end is not None else None
        if (
            connector is not None
            and len(connector) <= 14
            and re.fullmatch(r"[\s,/()]*(?:or|and|and/or|/)?[\s,/()]*(?:\w+\s)?", connector, re.I)
            and re.search(r"\bor\b|/", connector, re.I)
        ):
            chain.append(name)
            chain_has_or = True
        elif connector is not None and re.fullmatch(r"[\s,]*(?:or\s+)?", connector, re.I) and chain:
            chain.append(name)
        else:
            if chain:
                groups.extend([chain] if chain_has_or else [[c] for c in chain])
            chain, chain_has_or = [name], False
        prev_end = end
    if chain:
        groups.extend([chain] if chain_has_or else [[c] for c in chain])
    return groups


def analyze_job_description(text: str, title: str = "") -> JDAnalysis:
    clean = (text or "").strip()
    words = re.findall(r"\w+", clean)
    if len(clean) < 60 or len(words) < 12:
        raise InvalidJobDescription(
            "The job description is too short to analyze. Paste the full posting, including requirements."
        )
    if not find_skills(clean) and len(words) < 40:
        raise InvalidJobDescription(
            "This doesn't look like a job description. Please paste the role's responsibilities and requirements."
        )

    lines = [ln.strip() for ln in clean.splitlines()]
    analysis = JDAnalysis()
    first = next((ln for ln in lines if ln), "")
    analysis.title = title.strip() or (first if len(first.split()) <= 8 else "")
    sen = SENIORITY_RE.search(analysis.title or "") or SENIORITY_RE.search(clean[:400])
    analysis.seniority = sen.group(1).title() if sen else ""

    section = "other"
    required: list[str] = []
    preferred: list[str] = []
    responsibilities: list[str] = []
    focus_text: list[str] = []
    for line in lines:
        bare = line.strip("•-*: ").strip()
        if not bare:
            continue
        if REQ_HEADINGS.match(bare):
            section = "req"
            continue
        if PREF_HEADINGS.match(bare):
            section = "pref"
            continue
        if RESP_HEADINGS.match(bare):
            section = "resp"
            continue
        if OTHER_HEADINGS.match(bare):
            section = "other"
            continue
        is_pref = section == "pref" or bool(PREF_CUE.search(bare))
        groups = _skill_groups(bare)
        for g in groups:
            item = " or ".join(dict.fromkeys(g))
            target = preferred if is_pref else required
            if item not in target:
                target.append(item)
        if section == "resp" and len(bare.split()) >= 4:
            responsibilities.append(bare[:200])
        if section in ("req", "resp", "pref"):
            focus_text.append(bare)
        if section in ("req", "other") or "experience" in bare.lower():
            ym = YEARS_RE.search(bare)
            if ym and re.search(r"experience|years", bare, re.I):
                yrs = float(ym.group(1))
                if analysis.experience_years_min is None or yrs < analysis.experience_years_min:
                    analysis.experience_years_min = yrs
        if DEGREE_REQ_RE.search(bare) and len(bare.split()) <= 30:
            analysis.education_requirements.append(bare[:200])

    # a skill listed as both required and preferred stays required
    req_names = {s for item in required for s in item.split(" or ")}
    preferred = [p for p in preferred if not all(s in req_names for s in p.split(" or "))]
    analysis.required_skills = required[:25]
    analysis.preferred_skills = preferred[:15]
    analysis.responsibilities = responsibilities[:12]
    analysis.technologies = sorted(find_skills(clean).keys())

    # keyword extraction: frequent non-stopword unigrams/bigrams that are not already skills
    skill_words = {w for s in SKILLS.values() for a in (s.name, *s.aliases) for w in _tokens(a)}
    body = "\n".join(focus_text) or clean
    noise = STOPWORDS | GENERIC_JD_WORDS
    toks = [t for t in _tokens(body) if t not in noise and len(t) >= 3 and not t.isdigit()]
    uni = Counter(stem(t) for t in toks if t not in skill_words)
    surface: dict[str, str] = {}
    for t in toks:
        surface.setdefault(stem(t), t)
    bigrams = Counter()
    raw_toks = _tokens(body)
    for a, b in zip(raw_toks, raw_toks[1:], strict=False):
        if a in noise or b in noise or len(a) < 3 or len(b) < 3:
            continue
        if a in skill_words and b in skill_words:
            continue
        bigrams[f"{a} {b}"] += 1
    keywords: list[str] = [bg for bg, c in bigrams.most_common(30) if c >= 2][:6]
    for st, _c in uni.most_common(40):
        word = surface[st]
        if any(word in k for k in keywords):
            continue
        keywords.append(word)
        if len(keywords) >= 15:
            break
    analysis.keywords = keywords
    low = clean.lower()
    analysis.domain_terms = [d for d in DOMAIN_TERMS if re.search(rf"\b{re.escape(d)}\b", low)][:8]
    if not analysis.required_skills and not analysis.preferred_skills:
        analysis.warnings.append("No recognizable technical skills were found; matching will rely on keywords only.")
    return analysis


# ---------------------------------------------------------------- matching


def _resume_has(profile: CandidateProfile, resume_text: str, skill: str) -> str:
    """Return 'matched', 'partial' or 'missing' for a single canonical skill."""
    if skill in profile.skill_mentions:
        return "matched"
    if find_skills(resume_text, include_weak=True).get(skill):
        return "matched"
    fam = skill_family(skill)
    if fam and any(skill_family(s) == fam for s in profile.skill_mentions):
        return "partial"
    return "missing"


def match_skill_requirement(
    profile: CandidateProfile, resume_text: str, requirement: str
) -> tuple[str, list[str], str]:
    alts = [a.strip() for a in requirement.split(" or ") if a.strip()]
    statuses = {a: _resume_has(profile, resume_text, a) for a in alts}
    for a, st in statuses.items():
        if st == "matched":
            return "matched", find_line_evidence(resume_text, a), a
    for a, st in statuses.items():
        if st == "partial":
            fam = skill_family(a)
            similar = [s for s in profile.skill_mentions if skill_family(s) == fam]
            ev = find_line_evidence(resume_text, similar[0]) if similar else []
            return "partial", ev, f"Related experience with {', '.join(similar[:3])}"
    return "missing", [], ""


def classify_score(score: float) -> str:
    if score >= 90:
        return "Excellent"
    if score >= 80:
        return "Strong"
    if score >= 70:
        return "Good"
    if score >= 60:
        return "Needs Improvement"
    return "Weak"


def match_resume_to_jd(profile: CandidateProfile, resume_text: str, jd: JDAnalysis) -> JDMatch:
    reqs: list[RequirementMatch] = []
    low = resume_text.lower()
    stems = {stem(w) for w in _tokens(low)}

    def frac(items: list[RequirementMatch]) -> float | None:
        if not items:
            return None
        pts = sum(1.0 if r.status == "matched" else 0.5 if r.status == "partial" else 0.0 for r in items)
        return pts / len(items)

    req_items = []
    for r in jd.required_skills:
        status, ev, note = match_skill_requirement(profile, resume_text, r)
        req_items.append(RequirementMatch(requirement=r, kind="required_skill", status=status, evidence=ev, note=note))
    pref_items = []
    for r in jd.preferred_skills:
        status, ev, note = match_skill_requirement(profile, resume_text, r)
        pref_items.append(
            RequirementMatch(requirement=r, kind="preferred_skill", status=status, evidence=ev, note=note)
        )
    kw_items = []
    for k in jd.keywords:
        ok = text_contains_term(low, k, stems)
        ev = [ln.strip("• ")[:200] for ln in resume_text.splitlines() if k.lower() in ln.lower()][:1]
        kw_items.append(
            RequirementMatch(requirement=k, kind="keyword", status="matched" if ok else "missing", evidence=ev)
        )

    exp_items = []
    if jd.experience_years_min is not None:
        need = jd.experience_years_min
        have = profile.years_of_experience or 0.0
        has_internship = any("intern" in (e.title + e.company).lower() for e in profile.experience)
        if have >= need or need == 0:
            status, note = "matched", f"Resume shows about {have:g} years; role asks for {need:g}+."
        elif have >= need * 0.5 or (need <= 2 and (has_internship or profile.projects)):
            status, note = (
                "partial",
                f"Resume shows about {have:g} years (incl. internships/projects); role asks for {need:g}+.",
            )
        else:
            status, note = "missing", f"Resume shows about {have:g} years; role asks for {need:g}+."
        exp_items.append(
            RequirementMatch(requirement=f"{need:g}+ years of experience", kind="experience", status=status, note=note)
        )
    edu_items = []
    for e in jd.education_requirements[:2]:
        if profile.education:
            fields = " ".join(f"{ed.degree} {ed.field}" for ed in profile.education).lower()
            req_low = e.lower()
            field_ok = (
                any(
                    term in fields and term in req_low
                    for term in (
                        "computer",
                        "engineering",
                        "statistics",
                        "mathematics",
                        "economics",
                        "science",
                        "information",
                        "business",
                        "data",
                    )
                )
                or "related field" in req_low
            )
            status = "matched" if field_ok else "partial"
            ev = [f"{ed.degree} — {ed.institution}".strip(" —") for ed in profile.education[:1]]
        else:
            status, ev = "missing", []
        edu_items.append(RequirementMatch(requirement=e, kind="education", status=status, evidence=ev))

    reqs = req_items + pref_items + exp_items + edu_items + kw_items
    weights = {"required": 0.50, "preferred": 0.15, "keywords": 0.15, "experience": 0.10, "education": 0.10}
    parts = {
        "required": frac(req_items),
        "preferred": frac(pref_items),
        "keywords": frac(kw_items),
        "experience": frac(exp_items),
        "education": frac(edu_items),
    }
    active = {k: v for k, v in parts.items() if v is not None}
    total_w = sum(weights[k] for k in active) or 1.0
    score = round(sum(weights[k] * v for k, v in active.items()) / total_w * 100, 1) if active else 0.0
    breakdown = {k: round(v * 100, 1) for k, v in active.items()}

    matched = [r.requirement for r in reqs if r.status == "matched" and r.kind != "keyword"]
    partial = [r.requirement for r in reqs if r.status == "partial"]
    missing = [r.requirement for r in reqs if r.status == "missing" and r.kind != "keyword"]
    req_missing = [r.requirement for r in req_items if r.status == "missing"]
    if score >= 80:
        summary = "Your resume covers most of what this role asks for."
    elif score >= 60:
        summary = "Your resume matches the core of this role, with some gaps worth addressing."
    else:
        summary = "Your resume is missing several requirements this role emphasizes."
    if req_missing:
        summary += f" Biggest gaps: {', '.join(req_missing[:4])}."
    return JDMatch(
        score=score,
        classification=classify_score(score),
        requirements=reqs,
        matched=matched,
        partial=partial,
        missing=missing,
        summary=summary,
        breakdown=breakdown,
    )
