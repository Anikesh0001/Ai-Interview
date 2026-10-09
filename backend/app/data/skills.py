"""Skill taxonomy used for deterministic extraction and matching.

Each canonical skill has aliases (matched case-insensitively on word boundaries unless it
is listed in CASE_SENSITIVE), a category, and a "family" used to award partial credit
(e.g. a JD asking for PostgreSQL is partially satisfied by MySQL experience).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from functools import lru_cache


@dataclass(frozen=True)
class Skill:
    name: str
    category: str
    aliases: tuple[str, ...] = ()
    family: str = ""
    related: tuple[str, ...] = field(default=())


_RAW: list[tuple[str, str, list[str], str]] = [
    # name, category, aliases, family
    # --- programming languages
    ("Python", "programming_languages", ["python3", "py"], "lang"),
    ("Java", "programming_languages", [], "lang"),
    ("JavaScript", "programming_languages", ["js", "ecmascript", "es6"], "lang-web"),
    ("TypeScript", "programming_languages", ["ts"], "lang-web"),
    ("C++", "programming_languages", ["cpp"], "lang-sys"),
    ("C#", "programming_languages", ["csharp", "c sharp"], "lang"),
    ("C", "programming_languages", [], "lang-sys"),
    ("Go", "programming_languages", ["golang"], "lang-sys"),
    ("Rust", "programming_languages", [], "lang-sys"),
    ("Kotlin", "programming_languages", [], "lang"),
    ("Swift", "programming_languages", [], "lang"),
    ("Ruby", "programming_languages", [], "lang"),
    ("PHP", "programming_languages", [], "lang"),
    ("R", "programming_languages", [], "lang-data"),
    ("Scala", "programming_languages", [], "lang"),
    ("SQL", "programming_languages", ["t-sql", "pl/sql", "plsql"], "sql"),
    ("Bash", "programming_languages", ["shell scripting", "shell"], "shell"),
    ("HTML", "programming_languages", ["html5"], "web-markup"),
    ("CSS", "programming_languages", ["css3", "scss", "sass"], "web-markup"),
    # --- frameworks / libraries
    ("React", "frameworks", ["react.js", "reactjs"], "fe-framework"),
    ("Next.js", "frameworks", ["nextjs"], "fe-framework"),
    ("Angular", "frameworks", ["angularjs"], "fe-framework"),
    ("Vue", "frameworks", ["vue.js", "vuejs"], "fe-framework"),
    ("Svelte", "frameworks", [], "fe-framework"),
    ("Redux", "frameworks", [], "fe-state"),
    ("Tailwind CSS", "frameworks", ["tailwind", "tailwindcss"], "css-framework"),
    ("Bootstrap", "frameworks", [], "css-framework"),
    ("Node.js", "frameworks", ["node", "nodejs"], "be-framework"),
    ("Express", "frameworks", ["express.js", "expressjs"], "be-framework"),
    ("Flask", "frameworks", [], "be-framework"),
    ("Django", "frameworks", [], "be-framework"),
    ("FastAPI", "frameworks", [], "be-framework"),
    ("Spring Boot", "frameworks", ["spring", "springboot"], "be-framework"),
    ("ASP.NET", "frameworks", [".net", "dotnet", ".net core"], "be-framework"),
    ("Ruby on Rails", "frameworks", ["rails"], "be-framework"),
    ("GraphQL", "frameworks", [], "api"),
    ("REST APIs", "concepts", ["rest", "restful", "rest api", "restful apis", "api development"], "api"),
    ("gRPC", "frameworks", [], "api"),
    ("Pandas", "frameworks", [], "data-lib"),
    ("NumPy", "frameworks", ["numpy"], "data-lib"),
    ("scikit-learn", "frameworks", ["sklearn", "scikit learn"], "ml-lib"),
    ("TensorFlow", "frameworks", ["tensorflow", "keras"], "dl-lib"),
    ("PyTorch", "frameworks", ["pytorch", "torch"], "dl-lib"),
    ("Hugging Face", "frameworks", ["huggingface", "transformers"], "dl-lib"),
    ("LangChain", "frameworks", [], "llm"),
    ("Matplotlib", "frameworks", ["seaborn"], "viz"),
    ("Jest", "tools", [], "testing"),
    ("Pytest", "tools", ["pytest"], "testing"),
    ("JUnit", "tools", [], "testing"),
    ("Selenium", "tools", [], "testing"),
    ("Playwright", "tools", [], "testing"),
    # --- databases
    ("PostgreSQL", "databases", ["postgres", "postgresql", "psql"], "rdbms"),
    ("MySQL", "databases", ["mariadb"], "rdbms"),
    ("SQLite", "databases", [], "rdbms"),
    ("Oracle", "databases", ["oracle db"], "rdbms"),
    ("SQL Server", "databases", ["mssql", "microsoft sql server"], "rdbms"),
    ("MongoDB", "databases", ["mongo", "mongoose"], "nosql"),
    ("Redis", "databases", [], "cache"),
    ("Cassandra", "databases", [], "nosql"),
    ("DynamoDB", "databases", [], "nosql"),
    ("Elasticsearch", "databases", ["elastic search", "opensearch"], "search"),
    ("Firebase", "databases", ["firestore"], "nosql"),
    # --- cloud / devops / tools
    ("AWS", "tools", ["amazon web services", "ec2", "s3", "lambda"], "cloud"),
    ("Azure", "tools", ["microsoft azure"], "cloud"),
    ("GCP", "tools", ["google cloud", "google cloud platform"], "cloud"),
    ("Docker", "tools", ["containers", "containerization", "dockerfile"], "containers"),
    ("Kubernetes", "tools", ["k8s"], "orchestration"),
    ("Terraform", "tools", [], "iac"),
    ("Ansible", "tools", [], "iac"),
    ("Jenkins", "tools", [], "ci"),
    ("GitHub Actions", "tools", ["github actions"], "ci"),
    ("CI/CD", "concepts", ["ci/cd", "continuous integration", "continuous deployment", "cicd"], "ci"),
    ("Git", "tools", ["github", "gitlab", "bitbucket", "version control"], "vcs"),
    ("Linux", "tools", ["unix", "ubuntu"], "os"),
    ("Nginx", "tools", [], "web-server"),
    ("Kafka", "tools", ["apache kafka"], "messaging"),
    ("RabbitMQ", "tools", [], "messaging"),
    ("Spark", "tools", ["apache spark", "pyspark"], "big-data"),
    ("Hadoop", "tools", [], "big-data"),
    ("Airflow", "tools", ["apache airflow"], "pipeline"),
    ("Tableau", "tools", [], "bi"),
    ("Power BI", "tools", ["powerbi"], "bi"),
    ("Excel", "tools", ["ms excel", "microsoft excel", "spreadsheets"], "bi"),
    ("Jira", "tools", [], "pm-tool"),
    ("Figma", "tools", [], "design"),
    ("Postman", "tools", [], "api-tool"),
    ("Prometheus", "tools", ["grafana"], "observability"),
    ("Webpack", "tools", ["vite"], "bundler"),
    # --- concepts
    ("Data Structures", "concepts", ["data structures", "algorithms", "dsa", "data structures and algorithms"], "cs"),
    ("Object-Oriented Programming", "concepts", ["oop", "object oriented", "object-oriented"], "cs"),
    ("System Design", "concepts", ["distributed systems", "scalability", "high availability"], "arch"),
    ("Microservices", "concepts", ["microservice", "micro-services", "service-oriented"], "arch"),
    ("Machine Learning", "concepts", ["ml", "machine-learning"], "ml"),
    ("Deep Learning", "concepts", ["neural networks", "cnn", "rnn", "lstm"], "ml"),
    ("NLP", "concepts", ["natural language processing"], "ml"),
    ("Computer Vision", "concepts", ["opencv"], "ml"),
    ("LLMs", "concepts", ["llm", "large language models", "generative ai", "genai", "prompt engineering"], "llm"),
    ("Statistics", "concepts", ["statistical analysis", "hypothesis testing", "a/b testing", "regression"], "stats"),
    ("Data Analysis", "concepts", ["data analytics", "exploratory data analysis", "eda"], "analysis"),
    ("Data Visualization", "concepts", ["dashboards", "data visualisation"], "viz"),
    ("ETL", "concepts", ["data pipelines", "data pipeline", "elt"], "pipeline"),
    ("Authentication", "concepts", ["jwt", "oauth", "oauth2", "authorization", "session management"], "security"),
    ("Security", "concepts", ["owasp", "application security", "encryption"], "security"),
    ("Testing", "concepts", ["unit testing", "integration testing", "tdd", "test automation"], "testing"),
    ("Agile", "concepts", ["scrum", "kanban", "sprint"], "process"),
    ("Caching", "concepts", ["cache", "memcached", "cdn"], "cache"),
    ("Database Design", "concepts", ["schema design", "normalization", "indexing", "data modeling"], "sql"),
    ("Responsive Design", "concepts", ["responsive web design", "mobile-first"], "web-markup"),
    ("Accessibility", "concepts", ["a11y", "wcag", "aria"], "web-markup"),
    ("Web Performance", "concepts", ["lighthouse", "core web vitals", "lazy loading"], "web-perf"),
    ("Monitoring", "concepts", ["observability", "logging", "alerting"], "observability"),
    ("Networking", "concepts", ["tcp/ip", "dns", "http", "load balancing", "load balancer"], "net"),
    ("Product Management", "concepts", ["roadmap", "product roadmap", "prd", "user stories"], "product"),
    ("Stakeholder Management", "concepts", ["stakeholders", "cross-functional"], "product"),
    ("Leadership", "soft", ["mentoring", "mentored", "team lead", "led a team"], "soft"),
    ("Communication", "soft", ["presentation", "public speaking", "technical writing"], "soft"),
    ("Problem Solving", "soft", ["problem-solving", "analytical"], "soft"),
]

CASE_SENSITIVE = {"C", "R", "Go", "TS", "PHP", "ML"}
# Aliases that are too ambiguous to match on their own in free text.
AMBIGUOUS_ALIASES = {"py", "ts", "node", "shell", "cache", "rest", "ml", "spring", "sprint", "http", "logging"}


def _build() -> dict[str, Skill]:
    skills: dict[str, Skill] = {}
    for name, category, aliases, family in _RAW:
        skills[name] = Skill(name=name, category=category, aliases=tuple(aliases), family=family)
    return skills


SKILLS: dict[str, Skill] = _build()


def _alias_pattern(alias: str, case_sensitive: bool) -> re.Pattern[str]:
    escaped = re.escape(alias)
    # word-ish boundaries that also work for terms like C++, C#, .NET, Node.js
    pattern = rf"(?<![A-Za-z0-9_+#.-]){escaped}(?![A-Za-z0-9_+#-])"
    if alias in ("C",):
        # "C" only when not followed by "++"/"#" and not part of an initial like "C." or "C-level".
        pattern = r"(?<![A-Za-z0-9_+#.\-/])C(?![A-Za-z0-9_+#.\-/])"
    if alias in ("R",):
        pattern = r"(?<![A-Za-z0-9_+#.\-/&'])R(?![A-Za-z0-9_+#.\-/&'])"
    if alias == "Go":
        pattern = r"(?<![A-Za-z0-9_])Go(?![A-Za-z0-9_])(?!\s+(?:to|back|live|through|beyond)\b)"
    return re.compile(pattern, 0 if case_sensitive else re.IGNORECASE)


@lru_cache(maxsize=1)
def _compiled() -> list[tuple[str, list[re.Pattern[str]], list[re.Pattern[str]]]]:
    """Returns (skill, strong patterns, weak patterns). Weak patterns only count with context."""
    out = []
    for skill in SKILLS.values():
        strong: list[re.Pattern[str]] = []
        weak: list[re.Pattern[str]] = []
        seen_aliases: set[str] = set()
        for alias in (skill.name, *skill.aliases):
            if alias.lower() in seen_aliases:
                continue
            seen_aliases.add(alias.lower())
            cs = alias in CASE_SENSITIVE
            pat = _alias_pattern(alias, cs)
            (weak if alias.lower() in AMBIGUOUS_ALIASES else strong).append(pat)
        out.append((skill.name, strong, weak))
    return out


def find_skills(text: str, *, include_weak: bool = False) -> dict[str, int]:
    """Return canonical skill -> number of mentions found in ``text``."""
    found: dict[str, int] = {}
    for name, strong, weak in _compiled():
        spans: set[int] = set()
        for p in strong + (weak if include_weak else []):
            spans.update(m.start() for m in p.finditer(text))
        if spans:
            found[name] = len(spans)
    return found


def skill_family(name: str) -> str:
    s = SKILLS.get(name)
    return s.family if s else ""


def skill_category(name: str) -> str:
    s = SKILLS.get(name)
    return s.category if s else "other"


def canonical(name: str) -> str | None:
    """Map a free-form skill string to its canonical name, if known."""
    key = name.strip().lower()
    for skill in SKILLS.values():
        if key == skill.name.lower() or key in (a.lower() for a in skill.aliases):
            return skill.name
    return None


def find_line_evidence(text: str, skill: str, limit: int = 2) -> list[str]:
    """Return up to ``limit`` resume lines mentioning ``skill`` (any alias)."""
    entry = next((c for c in _compiled() if c[0] == skill), None)
    if entry is None:
        return []
    patterns = entry[1] + entry[2]
    lines = []
    for line in text.splitlines():
        stripped = line.strip(" \t•-*●▪◦")
        if len(stripped) < 8:
            continue
        if any(p.search(stripped) for p in patterns):
            lines.append(stripped[:220])
            if len(lines) >= limit:
                break
    return lines


def skills_in_order(text: str) -> list[str]:
    """Canonical skills found in ``text``, ordered by first appearance."""
    first: dict[str, int] = {}
    for name, strong, _weak in _compiled():
        positions = [m.start() for p in strong for m in p.finditer(text)]
        if positions:
            first[name] = min(positions)
    return sorted(first, key=first.__getitem__)
