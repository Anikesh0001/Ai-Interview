"""Deterministic resume -> CandidateProfile extraction (no LLM required)."""

from __future__ import annotations

import re
from datetime import date

from app.data.lexicon import SECTION_HEADINGS
from app.data.skills import find_skills, skill_category, skills_in_order
from app.schemas import (
    CandidateProfile,
    EducationItem,
    ExperienceItem,
    ProjectItem,
    ResumeClaim,
)

EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
PHONE_RE = re.compile(r"(?<![\w])(\+?\d[\d\s().-]{7,}\d)(?![\w])")
URL_RE = re.compile(
    r"(?:https?://[^\s|,;)]+|(?:www\.)[^\s|,;)]+|(?:linkedin\.com|github\.com|gitlab\.com|behance\.net|"
    r"kaggle\.com|leetcode\.com|medium\.com)/[^\s|,;)]+)",
    re.IGNORECASE,
)
MONTH = r"(?:jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|jun(?:e)?|jul(?:y)?|aug(?:ust)?|sep(?:t(?:ember)?)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?)"
DATE_TOKEN = rf"(?:{MONTH}\.?\s+\d{{4}}|\d{{1,2}}/\d{{4}}|\d{{4}})"
DATE_RANGE_RE = re.compile(
    rf"({DATE_TOKEN})\s*(?:-|–|—|to|until)\s*({DATE_TOKEN}|present|current|now|ongoing|today)",
    re.IGNORECASE,
)
YEAR_RE = re.compile(r"\b(19[89]\d|20[0-4]\d)\b")
GPA_RE = re.compile(r"\b(?:c?gpa|cgpa|grade)\s*[:\-]?\s*(\d{1,2}(?:\.\d{1,2})?\s*(?:/\s*\d{1,2}(?:\.\d+)?)?)", re.I)
PERCENT_GRADE_RE = re.compile(r"\b(\d{2}(?:\.\d+)?)\s*%")
DEGREE_RE = re.compile(
    r"\b(b\.?\s?tech|m\.?\s?tech|b\.?\s?e\b|m\.?\s?e\b|b\.?\s?sc|m\.?\s?sc|b\.?\s?s\b|m\.?\s?s\b|b\.?\s?a\b|"
    r"m\.?\s?a\b|bca|mca|mba|ph\.?\s?d|bachelor(?:'s)?|master(?:'s)?|associate(?:'s)? degree|diploma|"
    r"high school|higher secondary|secondary school|class xii|class x|hsc|ssc|b\.?com|m\.?com)",
    re.IGNORECASE,
)
INSTITUTION_RE = re.compile(r"\b(university|college|institute|school|academy|iit|nit|polytechnic)\b", re.I)
EXPLICIT_YEARS_RE = re.compile(r"(\d+(?:\.\d+)?)\+?\s*(?:years?|yrs?)\s+(?:of\s+)?(?:professional\s+)?experience", re.I)
LOCATION_RE = re.compile(
    r"\b([A-Z][a-zA-Z.]+(?:\s[A-Z][a-zA-Z.]+){0,2}),\s*([A-Z][a-zA-Z]+(?:\s[A-Z][a-zA-Z]+)?|[A-Z]{2})\b"
)

METRIC_RE = re.compile(
    r"(\d+(?:\.\d+)?\s*%|\b\d+(?:\.\d+)?\s*x\b|\$\s?\d[\d,.]*\s*[kKmMbB]?|\b\d[\d,.]*\s*[kKmM]?\+?\s*"
    r"(?:users|customers|requests|transactions|records|rows|downloads|visitors|students|patients|clients|"
    r"queries|events|messages|ms|milliseconds|seconds|minutes|hours|days|members|people|engineers|teams|"
    r"services|endpoints|pages|tickets|leads|orders|tables|managers|teams|stores|records|accuracy))",
    re.IGNORECASE,
)
ARCH_RE = re.compile(
    r"\b(microservices?|scalable|distributed|architected|architecture|high[- ]availability|event[- ]driven|"
    r"fault[- ]tolerant|load[- ]balanc\w*|real[- ]time|horizontally)\b",
    re.I,
)
LEAD_RE = re.compile(r"\b(led|lead|mentored|managed a team|managed \d+|supervised|headed|spearheaded)\b", re.I)
OWNERSHIP_RE = re.compile(r"\b(single[- ]handedly|end[- ]to[- ]end|from scratch|sole developer|owned)\b", re.I)

BULLET_PREFIX = re.compile(r"^(?:[•\-*●▪◦]\s+|\d{1,2}[.)]\s+)")


def _norm_heading(line: str) -> str:
    return re.sub(r"[^a-z& ]", "", line.lower()).strip()


_HEADING_LOOKUP: dict[str, str] = {}
for _section, _names in SECTION_HEADINGS.items():
    for _n in _names:
        _HEADING_LOOKUP[_norm_heading(_n)] = _section


def detect_heading(line: str) -> str | None:
    stripped = line.strip().rstrip(":").strip()
    if not stripped or len(stripped) > 45 or BULLET_PREFIX.match(stripped):
        return None
    key = _norm_heading(stripped)
    if key in _HEADING_LOOKUP:
        return _HEADING_LOOKUP[key]
    return None


def split_sections(text: str) -> tuple[list[str], dict[str, list[str]]]:
    """Return (header lines, section -> lines). Repeated sections are concatenated."""
    header: list[str] = []
    sections: dict[str, list[str]] = {}
    current: str | None = None
    for raw in text.splitlines():
        line = raw.strip()
        heading = detect_heading(line)
        if heading:
            current = heading
            sections.setdefault(current, [])
            continue
        if current is None:
            if line:
                header.append(line)
        else:
            sections[current].append(line)
    return header, sections


def is_bullet(line: str) -> bool:
    return bool(BULLET_PREFIX.match(line))


def strip_bullet(line: str) -> str:
    return BULLET_PREFIX.sub("", line).strip()


def _merge_wrapped(lines: list[str]) -> list[str]:
    """Join visual line wraps (a bullet continued on the next line) back together."""
    out: list[str] = []
    for line in lines:
        if not line:
            out.append("")
            continue
        if (
            out
            and out[-1]
            and not is_bullet(line)
            and is_bullet(out[-1])
            and (line[0].islower() or out[-1].rstrip().endswith((",", "and", "of", "the", "to", "with", "for")))
        ):
            out[-1] = out[-1].rstrip() + " " + line
        else:
            out.append(line)
    return out


def _parse_month_year(token: str, is_end: bool) -> date | None:
    token = token.strip().lower().rstrip(".")
    if token in {"present", "current", "now", "ongoing", "today"}:
        return date.today()
    m = re.match(r"(\d{1,2})/(\d{4})", token)
    if m:
        return date(int(m.group(2)), max(1, min(12, int(m.group(1)))), 1)
    m = re.match(rf"({MONTH})\.?\s+(\d{{4}})", token, re.I)
    if m:
        months = ["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"]
        return date(int(m.group(2)), months.index(m.group(1)[:3].lower()) + 1, 1)
    m = re.match(r"(\d{4})", token)
    if m:
        return date(int(m.group(1)), 12 if is_end else 1, 1)
    return None


def _months_between(start: str, end: str) -> int | None:
    s = _parse_month_year(start, False)
    e = _parse_month_year(end, True)
    if not s or not e or e < s:
        return None
    return (e.year - s.year) * 12 + (e.month - s.month) + 1


def _split_title_company(line: str) -> tuple[str, str]:
    line = DATE_RANGE_RE.sub("", line).strip(" |,–—-()")
    for sep in (" | ", " — ", " – ", " - ", " at ", " @ ", ", "):
        if sep in line:
            a, b = line.split(sep, 1)
            return a.strip(" |,–—-"), b.strip(" |,–—-")
    return line.strip(), ""


def parse_experience(lines: list[str]) -> list[ExperienceItem]:
    items: list[ExperienceItem] = []
    lines = [ln for ln in _merge_wrapped(lines)]
    current: ExperienceItem | None = None
    pending_header: list[str] = []
    for line in lines:
        if not line:
            continue
        if is_bullet(line):
            if current is None:
                current = ExperienceItem()
                items.append(current)
                if pending_header:
                    current.title, current.company = _split_title_company(pending_header[0])
                    pending_header = []
            current.bullets.append(strip_bullet(line))
            continue
        date_match = DATE_RANGE_RE.search(line)
        if date_match:
            title_part = DATE_RANGE_RE.sub("", line).strip(" |,–—-()")
            if current is not None and not current.bullets and not current.start:
                target = current
            else:
                target = ExperienceItem()
                items.append(target)
                if pending_header:
                    target.title, target.company = _split_title_company(pending_header[0])
                    if len(pending_header) > 1 and not target.company:
                        target.company = pending_header[1]
                    pending_header = []
            target.start, target.end = date_match.group(1), date_match.group(2)
            target.duration_months = _months_between(target.start, target.end)
            if title_part:
                t, c = _split_title_company(title_part)
                if not target.title:
                    target.title, target.company = t, c or target.company
                elif not target.company:
                    target.company = title_part
            current = target
            continue
        # a non-bullet, non-date line: either a new entry header or a continuation line
        if current is not None and current.bullets:
            if len(line.split()) <= 12 and not line.endswith("."):
                current = None
                pending_header = [line]
            else:
                current.bullets.append(line)
        elif current is not None and not current.company and len(line.split()) <= 8:
            current.company = line
        elif current is not None and not current.bullets and len(line.split()) > 12:
            current.bullets.append(line)
        else:
            pending_header.append(line)
    for item in items:
        item.technologies = sorted(find_skills(" ".join([item.title, *item.bullets])).keys())
    return [i for i in items if i.title or i.company or i.bullets]


def parse_projects(lines: list[str]) -> list[ProjectItem]:
    projects: list[ProjectItem] = []
    current: ProjectItem | None = None
    for line in _merge_wrapped(lines):
        if not line:
            continue
        if is_bullet(line):
            if current is None:
                current = ProjectItem(name="Project")
                projects.append(current)
            current.bullets.append(strip_bullet(line))
            continue
        looks_like_title = len(line.split()) <= 14 and not line.endswith(".")
        if looks_like_title or current is None:
            name = line
            tech_part = ""
            for sep in (" | ", " — ", " – ", " - ", ": "):
                if sep in name:
                    name, tech_part = name.split(sep, 1)
                    break
            m = re.match(r"^(.*?)\s*\((.+)\)\s*$", name)
            if m and find_skills(m.group(2)):
                name, tech_part = m.group(1), m.group(2) + " " + tech_part
            name = DATE_RANGE_RE.sub("", name).strip(" |,–—-")
            current = ProjectItem(name=name[:120] or "Project", description=tech_part.strip())
            projects.append(current)
        else:
            if current.description and not current.bullets:
                current.description += " " + line
            elif not current.bullets:
                current.description = line
            else:
                current.bullets.append(line)
    for p in projects:
        blob = " ".join([p.name, p.description, *p.bullets])
        p.technologies = skills_in_order(blob)
        p.links = URL_RE.findall(blob)
    return [p for p in projects if p.bullets or p.description or p.name != "Project"]


def parse_education(lines: list[str]) -> list[EducationItem]:
    items: list[EducationItem] = []
    current: EducationItem | None = None
    for raw in lines:
        line = strip_bullet(raw) if raw else raw
        if not line:
            continue
        deg = DEGREE_RE.search(line)
        inst = INSTITUTION_RE.search(line)
        if (
            deg
            and (current is None or current.degree)
            or inst
            and current is not None
            and current.institution
            and not deg
            or current is None
        ):
            current = EducationItem()
            items.append(current)
        parts = [p.strip() for p in re.split(r"\s+\|\s+|\s+[–—-]\s+|,\s+(?=[A-Z])", line) if p.strip()]
        for part in parts:
            if DEGREE_RE.search(part) and not current.degree:
                cleaned = DATE_RANGE_RE.sub("", part).strip(" ,")
                m = re.search(r"\b(?:in|of)\s+(.+)$", cleaned, re.I)
                current.degree = cleaned[:120]
                if m:
                    current.field = m.group(1).strip()[:80]
            elif INSTITUTION_RE.search(part) and not current.institution:
                current.institution = DATE_RANGE_RE.sub("", part).strip(" ,")[:120]
        dr = DATE_RANGE_RE.search(line)
        if dr:
            current.start, current.end = dr.group(1), dr.group(2)
        else:
            years = YEAR_RE.findall(line)
            if years and not current.end:
                current.end = years[-1]
                if len(years) > 1:
                    current.start = years[0]
        g = GPA_RE.search(line)
        if g:
            current.gpa = g.group(1).replace(" ", "")
        elif not current.gpa:
            pg = PERCENT_GRADE_RE.search(line)
            if pg and "grade" not in line.lower() and current.degree:
                current.gpa = pg.group(1) + "%"
    return [i for i in items if i.degree or i.institution]


def extract_claims(profile: CandidateProfile) -> list[ResumeClaim]:
    claims: list[ResumeClaim] = []
    seen: set[str] = set()

    def consider(text: str, section: str, subject: str) -> None:
        key = text.lower()[:80]
        if key in seen or len(text) < 15:
            return
        kind = None
        if METRIC_RE.search(text):
            kind = "metric"
        elif ARCH_RE.search(text):
            kind = "architecture"
        elif LEAD_RE.search(text):
            kind = "leadership"
        elif OWNERSHIP_RE.search(text):
            kind = "ownership"
        if kind:
            seen.add(key)
            claims.append(ResumeClaim(text=text[:300], kind=kind, section=section, subject=subject))

    for exp in profile.experience:
        for b in exp.bullets:
            consider(b, "experience", exp.company or exp.title)
    for proj in profile.projects:
        for b in [proj.description, *proj.bullets]:
            if b:
                consider(b, "projects", proj.name)
    for a in profile.achievements:
        consider(a, "achievements", "")
    # metric claims are the most verifiable; keep them first
    order = {"metric": 0, "architecture": 1, "scale": 2, "leadership": 3, "ownership": 4}
    claims.sort(key=lambda c: order[c.kind])
    return claims[:12]


def _guess_name(header: list[str]) -> str:
    for line in header[:6]:
        candidate = re.split(r"\s[|•]\s", line)[0].strip()
        if EMAIL_RE.search(candidate) or PHONE_RE.search(candidate) or URL_RE.search(candidate):
            continue
        words = candidate.split()
        if (
            2 <= len(words) <= 4
            and all(re.fullmatch(r"[A-Za-z][A-Za-z.'\-]*", w) for w in words)
            and detect_heading(candidate) is None
        ):
            return " ".join(w if not w.isupper() or len(w) <= 2 else w.title() for w in words)
    return ""


def _guess_location(header: list[str]) -> str:
    for line in header[:8]:
        for part in re.split(r"\s*[|•·]\s*", line):
            if EMAIL_RE.search(part) or URL_RE.search(part) or PHONE_RE.search(part):
                continue
            m = LOCATION_RE.search(part)
            if m and len(part.split()) <= 6:
                return m.group(0)
    return ""


def _skill_section_extras(lines: list[str]) -> list[str]:
    extras: list[str] = []
    for line in lines:
        body = strip_bullet(line)
        if ":" in body:
            body = body.split(":", 1)[1]
        for token in re.split(r"[,;|/•]", body):
            token = token.strip(" .()")
            if (
                1 < len(token) <= 30
                and len(token.split()) <= 3
                and not find_skills(token, include_weak=True)
                and re.search(r"[A-Za-z]", token)
            ):
                extras.append(token)
    return extras[:20]


def build_profile(text: str) -> CandidateProfile:
    header, sections = split_sections(text)
    profile = CandidateProfile()
    profile.sections = list(sections.keys())

    header_blob = "\n".join(header[:10])
    emails = EMAIL_RE.findall(header_blob) or EMAIL_RE.findall(text)
    profile.email = emails[0] if emails else ""
    phones = [p for p in PHONE_RE.findall(header_blob or text) if 10 <= len(re.sub(r"\D", "", p)) <= 15]
    if not phones:
        phones = [p for p in PHONE_RE.findall(text[:1500]) if 10 <= len(re.sub(r"\D", "", p)) <= 15]
    profile.phone = phones[0].strip() if phones else ""
    links = []
    for url in URL_RE.findall(text):
        url = url.rstrip(".")
        if url not in links and "@" not in url:
            links.append(url)
    profile.links = links[:10]
    profile.name = _guess_name(header)
    profile.location = _guess_location(header)

    profile.summary = " ".join(ln for ln in sections.get("summary", []) if ln)[:1200]

    mentions = find_skills(text)
    section_mentions = find_skills("\n".join(sections.get("skills", [])), include_weak=True)
    for k, v in section_mentions.items():
        mentions[k] = max(mentions.get(k, 0), v)
    profile.skill_mentions = dict(sorted(mentions.items(), key=lambda kv: (-kv[1], kv[0])))
    ordered = list(profile.skill_mentions.keys())
    buckets = {
        "programming_languages": profile.programming_languages,
        "frameworks": profile.frameworks,
        "databases": profile.databases,
        "tools": profile.tools,
        "concepts": profile.concepts,
    }
    for skill in ordered:
        cat = skill_category(skill)
        if cat in buckets:
            buckets[cat].append(skill)
    profile.skills = [s for s in ordered if skill_category(s) != "soft"] + _skill_section_extras(
        sections.get("skills", [])
    )

    profile.experience = parse_experience(sections.get("experience", []))
    profile.projects = parse_projects(sections.get("projects", []))
    profile.education = parse_education(sections.get("education", []))
    profile.certifications = [strip_bullet(ln) for ln in sections.get("certifications", []) if ln][:15]
    profile.achievements = [strip_bullet(ln) for ln in _merge_wrapped(sections.get("achievements", [])) if ln][:15]

    total_months = sum(e.duration_months or 0 for e in profile.experience)
    explicit = [float(m) for m in EXPLICIT_YEARS_RE.findall(text[:3000])]
    years = round(total_months / 12, 1) if total_months else None
    if explicit:
        years = max(years or 0, max(explicit))
    profile.years_of_experience = years
    profile.claims = extract_claims(profile)
    return profile
