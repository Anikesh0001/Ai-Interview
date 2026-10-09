"""Deterministic, explainable ATS-style compatibility scoring.

Every dimension is a 0-100 sub-score computed from observable resume features; the
overall score is their weighted sum using ``Settings.weights("ats")``. Identical input
always yields identical output.
"""

from __future__ import annotations

import re

from app.config import get_settings
from app.data.lexicon import ACTION_VERBS, WEAK_PHRASES, role_template
from app.data.skills import find_line_evidence, find_skills, skill_family
from app.schemas import ATSDimension, ATSReport, CandidateProfile, JDAnalysis
from app.services.jd import _tokens, classify_score, stem, text_contains_term
from app.services.profile import METRIC_RE, is_bullet, split_sections, strip_bullet

DISCLAIMER = (
    "This is an ATS-style compatibility score computed by InterviewForge's transparent rules. "
    "Real applicant tracking systems differ between employers and vendors, so treat it as guidance, "
    "not as the score any particular company will see."
)

LABELS = {
    "keyword_match": "Keyword Match",
    "skills_match": "Skills Match",
    "experience_relevance": "Experience Match",
    "project_relevance": "Project Match",
    "achievements": "Achievement Strength",
    "structure": "Resume Structure",
    "completeness": "Section Completeness",
    "education": "Education",
    "formatting": "Formatting & Parsing",
    "action_verbs": "Action Verbs",
    "contact": "Contact & Links",
}

LEVEL_EXPECTED_MONTHS = {"Student": 0, "Fresher": 3, "Junior": 12, "Mid-Level": 36, "Senior": 72}


def _clamp(v: float) -> float:
    return round(max(0.0, min(100.0, v)), 1)


def _all_bullets(profile: CandidateProfile) -> list[str]:
    out = [b for e in profile.experience for b in e.bullets]
    out += [b for p in profile.projects for b in p.bullets]
    return out


def _skill_status(profile: CandidateProfile, text: str, skill: str) -> float:
    alts = [a.strip() for a in skill.split(" or ")]
    best = 0.0
    for a in alts:
        if a in profile.skill_mentions or find_skills(text, include_weak=True).get(a):
            return 1.0
        fam = skill_family(a)
        if fam and any(skill_family(s) == fam for s in profile.skill_mentions):
            best = max(best, 0.5)
    return best


def compute_ats(
    text: str,
    profile: CandidateProfile,
    *,
    target_role: str = "Software Engineer",
    experience_level: str = "Junior",
    jd: JDAnalysis | None = None,
    parse_warnings: list[str] | None = None,
    page_count: int | None = None,
) -> ATSReport:
    weights = get_settings().weights("ats")
    tpl = role_template(target_role)
    low = text.lower()
    stems = {stem(w) for w in _tokens(low)}
    words = re.findall(r"\b\w+\b", text)
    word_count = len(words)
    bullets = _all_bullets(profile)
    _, sections = split_sections(text)
    raw_bullet_lines = [ln for ln in text.splitlines() if is_bullet(ln.strip())]
    problems: list[str] = list(parse_warnings or [])
    recs: list[str] = []
    dims: dict[str, tuple[float, str]] = {}

    # --- target skills / keywords: from the JD if provided, otherwise from the role template
    if jd is not None and (jd.required_skills or jd.keywords):
        important = list(jd.required_skills)
        secondary = list(jd.preferred_skills)
        keywords = list(dict.fromkeys(jd.keywords + [s for s in jd.technologies if s not in " ".join(important)]))
        source = "job_description"
    else:
        important = list(tpl["core_skills"])
        secondary = list(tpl["nice_skills"])
        keywords = list(tpl["keywords"])
        source = "role_template"

    # 1. keyword match
    matched_kw = [k for k in keywords if text_contains_term(low, k, stems)]
    missing_kw = [k for k in keywords if k not in matched_kw]
    kw_score = 100 * len(matched_kw) / len(keywords) if keywords else 50
    dims["keyword_match"] = (kw_score, f"{len(matched_kw)} of {len(keywords)} target keywords found.")

    # 2. skills match (important skills weigh 2x secondary; related-family skills earn half credit)
    imp_scores = {s: _skill_status(profile, text, s) for s in important}
    sec_scores = {s: _skill_status(profile, text, s) for s in secondary}
    denom = 2 * len(imp_scores) + len(sec_scores)
    skill_score = 100 * (2 * sum(imp_scores.values()) + sum(sec_scores.values())) / denom if denom else 50
    missing_important = [s for s, v in imp_scores.items() if v == 0]
    dims["skills_match"] = (
        skill_score,
        f"{sum(1 for v in imp_scores.values() if v == 1)} of {len(imp_scores)} key skills found"
        + (
            f" ({sum(1 for v in imp_scores.values() if v == 0.5)} via related skills)"
            if any(v == 0.5 for v in imp_scores.values())
            else ""
        )
        + (
            f"; {sum(1 for v in sec_scores.values() if v == 1)} of {len(sec_scores)} nice-to-have."
            if sec_scores
            else "."
        ),
    )

    # weak keywords: skills listed only in a skills section with no supporting evidence elsewhere
    skills_section_text = "\n".join(sections.get("skills", []))
    evidence_text = "\n".join(
        [*bullets, *(p.description for p in profile.projects), *(e.title for e in profile.experience)]
    )
    evidence_skills = find_skills(evidence_text, include_weak=True)
    weak = [
        s
        for s in find_skills(skills_section_text, include_weak=True)
        if s not in evidence_skills and s in (set(important) | set(secondary) | set(profile.skill_mentions))
    ]

    # 3. experience relevance
    target_skill_names = {a for s in important + secondary for a in s.split(" or ")}
    relevant_bullets = [
        b
        for b in [x for e in profile.experience for x in e.bullets]
        if set(find_skills(b, include_weak=True)) & target_skill_names
    ]
    total_months = sum(e.duration_months or 0 for e in profile.experience)
    expected_months = (
        int(jd.experience_years_min * 12)
        if jd and jd.experience_years_min is not None
        else LEVEL_EXPECTED_MONTHS.get(experience_level, 12)
    )
    if profile.experience:
        exp_score = 40 + 30 * min(1.0, len(relevant_bullets) / 3)
        exp_score += 30 * (1.0 if expected_months == 0 else min(1.0, total_months / expected_months))
        exp_detail = (
            f"{len(profile.experience)} role(s), ~{total_months} months, {len(relevant_bullets)} relevant bullet(s)."
        )
    elif experience_level in ("Student", "Fresher") and profile.projects:
        exp_score = 45
        exp_detail = "No work experience section; projects are used as evidence for an entry-level profile."
    else:
        exp_score = 10 if profile.projects else 0
        exp_detail = "No work experience detected."
    dims["experience_relevance"] = (exp_score, exp_detail)

    # 4. project relevance
    projects = profile.projects
    if projects:
        overlap = {t for p in projects for t in p.technologies} & target_skill_names
        detailed = sum(1 for p in projects if len(p.bullets) >= 2)
        evidenced = sum(1 for p in projects if p.links or any(METRIC_RE.search(b) for b in p.bullets))
        proj_score = (
            35 * min(1.0, len(projects) / 3)
            + 35 * min(1.0, len(overlap) / 4)
            + 15 * min(1.0, detailed / max(1, min(3, len(projects))))
            + 15 * min(1.0, evidenced / 2)
        )
        proj_detail = f"{len(projects)} project(s) using {len(overlap)} target technologies."
    else:
        proj_score, proj_detail = 0.0, "No projects section detected."
    dims["project_relevance"] = (proj_score, proj_detail)

    # 5. measurable achievements
    quantified = [b for b in bullets + profile.achievements if METRIC_RE.search(b) or re.search(r"\d", b)]
    strong_q = [b for b in bullets + profile.achievements if METRIC_RE.search(b)]
    total_b = max(1, len(bullets))
    ach_score = 0.0
    if bullets:
        ach_score = 60 * min(1.0, (len(quantified) / total_b) / 0.4) + 40 * min(1.0, len(strong_q) / 4)
    dims["achievements"] = (ach_score, f"{len(quantified)} of {len(bullets)} bullet(s) contain numbers.")

    # 6. structure
    struct = 0.0
    if "experience" in sections or "projects" in sections:
        struct += 25
    if "education" in sections:
        struct += 15
    if "skills" in sections:
        struct += 20
    if raw_bullet_lines:
        struct += 20 * min(1.0, len(raw_bullet_lines) / 8)
    if 300 <= word_count <= 900:
        struct += 20
    elif 200 <= word_count <= 1200:
        struct += 10
    dims["structure"] = (
        struct,
        f"{len(sections)} recognized section(s), {len(raw_bullet_lines)} bullet point(s), {word_count} words.",
    )

    # 7. completeness
    expected_sections = {"summary": 10, "experience": 25, "projects": 20, "education": 20, "skills": 20}
    comp = sum(w for s, w in expected_sections.items() if s in sections)
    if "certifications" in sections or "achievements" in sections:
        comp += 5
    missing_sections = [s for s in expected_sections if s not in sections]
    dims["completeness"] = (
        comp,
        "All key sections present." if not missing_sections else f"Missing: {', '.join(missing_sections)}.",
    )

    # 8. education
    edu = 0.0
    if profile.education:
        e0 = profile.education[0]
        edu = 55 + (15 if e0.institution else 0) + (10 if e0.end or e0.start else 0) + (10 if e0.gpa else 0)
        edu += 10 if e0.field or re.search(r"computer|engineering|science|math|statistics", e0.degree, re.I) else 0
    dims["education"] = (edu, profile.education[0].degree if profile.education else "No education entry detected.")

    # 9. formatting / parsing
    fmt = 100.0
    if any("Multi-column" in w for w in problems):
        fmt -= 20
    if any("Tables" in w for w in problems):
        fmt -= 15
    if any("Images" in w for w in problems):
        fmt -= 10
    if any("header" in w for w in problems):
        fmt -= 10
    long_lines = [ln for ln in text.splitlines() if len(ln) > 260]
    if long_lines:
        fmt -= min(15, 5 * len(long_lines))
        problems.append(
            f"{len(long_lines)} very long line(s); dense paragraphs are hard for parsers and recruiters to scan."
        )
    if word_count < 200:
        fmt -= 20
        problems.append("The resume is very short; ATS parsers may find too little content to match.")
    if word_count > 1200 or (page_count and page_count > 2):
        fmt -= 15
        problems.append("The resume is long (over two pages); consider trimming to the most relevant content.")
    odd = len(re.findall(r"[^\x00-\x7F•–—’‘“”€£₹é]", text))
    if odd > 30:
        fmt -= 10
        problems.append("Unusual symbols or icon fonts detected; they can turn into garbage characters in ATS parsers.")
    if not sections:
        fmt -= 25
        problems.append("No standard section headings (Experience, Education, Skills) were recognized.")
    if not raw_bullet_lines and bullets == []:
        problems.append("No bullet points detected; ATS and recruiters scan bullets far more easily than paragraphs.")
    dims["formatting"] = (fmt, "Based on layout signals, length and character set.")

    # 10. action verbs
    if bullets:
        starts = [strip_bullet(b).split()[0].lower().strip(",.") for b in bullets if strip_bullet(b)]
        verb_ratio = sum(1 for w in starts if w in ACTION_VERBS) / len(starts)
        weak_hits = [p for p in WEAK_PHRASES if p in low]
        av = 100 * min(1.0, verb_ratio / 0.8) - 8 * len(weak_hits)
        dims["action_verbs"] = (av, f"{round(verb_ratio * 100)}% of bullets start with a strong action verb.")
    else:
        weak_hits = [p for p in WEAK_PHRASES if p in low]
        verb_ratio = 0.0
        dims["action_verbs"] = (0.0, "No bullets to evaluate.")

    # 11. contact & links
    links_low = " ".join(profile.links).lower()
    contact = (
        (35 if profile.email else 0)
        + (25 if profile.phone else 0)
        + (20 if "linkedin" in links_low else 0)
        + (
            10
            if any(k in links_low for k in ("github", "gitlab", "portfolio", "behance", "kaggle"))
            or len(profile.links) > 1
            else 0
        )
        + (10 if profile.location else 0)
    )
    dims["contact"] = (contact, "Email, phone, LinkedIn, portfolio/GitHub and location.")

    # --- recommendations, most impactful first
    if not profile.email or not profile.phone:
        recs.append("Add a professional email address and phone number at the top of the resume.")
    if "linkedin" not in links_low:
        recs.append("Add your LinkedIn profile URL to the header.")
    if missing_important:
        recs.append(
            f"If you have experience with {', '.join(missing_important[:5])}, add it with concrete evidence in a project or role."
        )
    if weak:
        recs.append(f"Back up listed skills like {', '.join(weak[:4])} with a bullet showing where you used them.")
    if dims["achievements"][0] < 70:
        recs.append("Quantify more bullets: latency, users, revenue, accuracy, time saved, team size.")
    if dims["action_verbs"][0] < 70:
        recs.append(
            "Start each bullet with a strong action verb (Built, Reduced, Designed, Led) instead of 'Responsible for' or 'Worked on'."
        )
    if weak_hits:
        recs.append(f"Replace passive phrases such as '{weak_hits[0]}' with what you actually did and its result.")
    if missing_sections:
        recs.append(f"Add clearly titled sections for: {', '.join(missing_sections)}.")
    if missing_kw and source == "job_description":
        recs.append(f"Mirror relevant job-description language where truthful, e.g. {', '.join(missing_kw[:5])}.")
    if dims["project_relevance"][0] < 60:
        recs.append(
            "Describe 2-3 projects that use the target role's technologies, with your contribution and outcome."
        )
    if any("Multi-column" in w or "Tables" in w for w in problems):
        recs.append("Use a single-column layout without tables so parsers read sections in order.")
    if not recs:
        recs.append("Your resume is in good shape. Tailor the summary and top bullets to each application.")

    dimensions = [
        ATSDimension(key=k, label=LABELS[k], score=_clamp(v), weight=round(weights[k], 4), detail=d)
        for k, (v, d) in dims.items()
    ]
    overall = round(sum(d.score * d.weight for d in dimensions), 1)
    stats = {
        "word_count": word_count,
        "bullet_count": len(bullets),
        "quantified_bullets": len(quantified),
        "action_verb_ratio": round(verb_ratio, 2),
        "sections_found": len(sections),
        "skills_found": len(profile.skill_mentions),
        "projects": len(profile.projects),
        "experience_entries": len(profile.experience),
        "experience_months": total_months,
    }
    return ATSReport(
        overall=overall,
        classification=classify_score(overall),
        dimensions=dimensions,
        matched_keywords=matched_kw + [s for s, v in imp_scores.items() if v == 1],
        missing_keywords=missing_kw,
        weak_keywords=weak[:12],
        missing_important_skills=missing_important,
        ats_problems=list(dict.fromkeys(problems)),
        recommendations=recs[:8],
        stats=stats,
        keyword_source=source,
        target_role=target_role,
        disclaimer=DISCLAIMER,
    )


def skill_evidence(text: str, skill: str) -> list[str]:
    return find_line_evidence(text, skill)
