"""Pydantic schemas: domain objects, LLM output contracts and API payloads."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

# ---------------------------------------------------------------- enums

ExperienceLevel = Literal["Student", "Fresher", "Junior", "Mid-Level", "Senior"]
InterviewType = Literal[
    "Technical", "Behavioral", "HR", "Project Deep Dive", "Coding", "System Design", "Mixed", "Custom"
]
Difficulty = Literal["Easy", "Medium", "Hard", "Very Hard"]
Personality = Literal["Friendly", "Professional", "Strict", "Senior Engineer", "Hiring Manager", "HR", "CTO"]
VoiceMode = Literal["voice", "text"]
Category = Literal[
    "intro",
    "resume",
    "project",
    "skills",
    "technical",
    "coding",
    "system_design",
    "behavioral",
    "hr",
    "situational",
    "problem_solving",
    "role_specific",
    "jd_specific",
    "claim_verification",
    "closing",
]
Source = Literal["resume", "job_description", "previous_answer", "question_bank", "role_template"]
Classification = Literal[
    "Excellent", "Strong", "Acceptable", "Weak", "Vague", "Incorrect", "Off-topic", "Suspicious", "Incomplete"
]
Phase = Literal["INTRO", "RESUME", "PROJECT", "TECHNICAL", "PROBLEM_SOLVING", "BEHAVIORAL", "CHALLENGE", "CLOSING"]

DIMENSIONS = (
    "technical_correctness",
    "relevance",
    "depth",
    "completeness",
    "problem_solving",
    "communication",
    "confidence_indicators",
)


# ---------------------------------------------------------------- candidate profile


class ExperienceItem(BaseModel):
    title: str = ""
    company: str = ""
    start: str = ""
    end: str = ""
    duration_months: int | None = None
    bullets: list[str] = Field(default_factory=list)
    technologies: list[str] = Field(default_factory=list)


class ProjectItem(BaseModel):
    name: str
    description: str = ""
    technologies: list[str] = Field(default_factory=list)
    bullets: list[str] = Field(default_factory=list)
    links: list[str] = Field(default_factory=list)


class EducationItem(BaseModel):
    degree: str = ""
    field: str = ""
    institution: str = ""
    start: str = ""
    end: str = ""
    gpa: str = ""


class ResumeClaim(BaseModel):
    text: str
    kind: Literal["metric", "architecture", "leadership", "scale", "ownership"]
    section: str = ""
    subject: str = ""  # project/company the claim belongs to, when known


class CandidateProfile(BaseModel):
    name: str = ""
    email: str = ""
    phone: str = ""
    location: str = ""
    summary: str = ""
    skills: list[str] = Field(default_factory=list)
    programming_languages: list[str] = Field(default_factory=list)
    frameworks: list[str] = Field(default_factory=list)
    databases: list[str] = Field(default_factory=list)
    tools: list[str] = Field(default_factory=list)
    concepts: list[str] = Field(default_factory=list)
    experience: list[ExperienceItem] = Field(default_factory=list)
    projects: list[ProjectItem] = Field(default_factory=list)
    education: list[EducationItem] = Field(default_factory=list)
    certifications: list[str] = Field(default_factory=list)
    achievements: list[str] = Field(default_factory=list)
    links: list[str] = Field(default_factory=list)
    years_of_experience: float | None = None
    claims: list[ResumeClaim] = Field(default_factory=list)
    sections: list[str] = Field(default_factory=list)
    skill_mentions: dict[str, int] = Field(default_factory=dict)


# ---------------------------------------------------------------- ATS / JD


class ATSDimension(BaseModel):
    key: str
    label: str
    score: float = Field(ge=0, le=100)
    weight: float
    detail: str = ""


class ATSReport(BaseModel):
    overall: float = Field(ge=0, le=100)
    classification: str
    dimensions: list[ATSDimension]
    matched_keywords: list[str]
    missing_keywords: list[str]
    weak_keywords: list[str]
    missing_important_skills: list[str]
    ats_problems: list[str]
    recommendations: list[str]
    stats: dict[str, float | int | str]
    keyword_source: Literal["job_description", "role_template"]
    target_role: str
    disclaimer: str


class JDAnalysis(BaseModel):
    title: str = ""
    seniority: str = ""
    required_skills: list[str] = Field(default_factory=list)
    preferred_skills: list[str] = Field(default_factory=list)
    technologies: list[str] = Field(default_factory=list)
    responsibilities: list[str] = Field(default_factory=list)
    experience_years_min: float | None = None
    education_requirements: list[str] = Field(default_factory=list)
    keywords: list[str] = Field(default_factory=list)
    domain_terms: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class RequirementMatch(BaseModel):
    requirement: str
    kind: Literal["required_skill", "preferred_skill", "experience", "education", "keyword"]
    status: Literal["matched", "partial", "missing"]
    evidence: list[str] = Field(default_factory=list)
    note: str = ""


class JDMatch(BaseModel):
    score: float = Field(ge=0, le=100)
    classification: str
    requirements: list[RequirementMatch]
    matched: list[str]
    partial: list[str]
    missing: list[str]
    summary: str
    breakdown: dict[str, float]


# ---------------------------------------------------------------- interview config / questions


class InterviewConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    target_role: str = Field(default="Software Engineer", min_length=2, max_length=80)
    experience_level: ExperienceLevel = "Junior"
    interview_type: InterviewType = "Mixed"
    difficulty: Difficulty = "Medium"
    num_questions: int = Field(default=10, ge=3, le=25)
    personality: Personality = "Professional"
    mode: VoiceMode = "text"
    custom_focus: str = Field(default="", max_length=300)

    @field_validator("target_role", "custom_focus")
    @classmethod
    def _strip(cls, v: str) -> str:
        return " ".join(v.split())


class QuestionSchema(BaseModel):
    """Validated metadata for every question, whether from the bank or an LLM."""

    question: str = Field(min_length=8, max_length=600)
    category: Category
    difficulty: Difficulty
    skill: str = ""
    source: Source
    expected_concepts: list[str] = Field(default_factory=list, max_length=12)
    evaluation_rubric: list[str] = Field(default_factory=list, max_length=10)
    ideal_answer: str = ""
    claim: str | None = None


class LLMQuestion(BaseModel):
    """Shape requested from the LLM for question generation."""

    question: str = Field(min_length=8, max_length=500)
    expected_concepts: list[str] = Field(default_factory=list, max_length=10)
    evaluation_rubric: list[str] = Field(default_factory=list, max_length=8)
    ideal_answer: str = Field(default="", max_length=1200)


class LLMFollowUp(BaseModel):
    acknowledgement: str = Field(default="", max_length=240)
    question: str = Field(min_length=8, max_length=400)
    expected_concepts: list[str] = Field(default_factory=list, max_length=8)


class AnswerEvaluationLLM(BaseModel):
    """Dimension scores and feedback produced by the LLM. Final score is computed by the backend."""

    technical_correctness: int = Field(ge=0, le=10)
    relevance: int = Field(ge=0, le=10)
    depth: int = Field(ge=0, le=10)
    completeness: int = Field(ge=0, le=10)
    problem_solving: int = Field(ge=0, le=10)
    communication: int = Field(ge=0, le=10)
    confidence_indicators: int = Field(ge=0, le=10)
    is_incorrect: bool = False
    is_off_topic: bool = False
    is_vague: bool = False
    covered_concepts: list[str] = Field(default_factory=list, max_length=12)
    strengths: list[str] = Field(default_factory=list, max_length=6)
    weaknesses: list[str] = Field(default_factory=list, max_length=6)
    missing_points: list[str] = Field(default_factory=list, max_length=8)
    feedback: str = Field(default="", max_length=800)
    improvement: str = Field(default="", max_length=800)
    follow_up_required: bool = False


class EvaluationResult(BaseModel):
    dimensions: dict[str, int]
    score: float  # 0-100
    classification: Classification
    covered_concepts: list[str]
    strengths: list[str]
    weaknesses: list[str]
    missing_points: list[str]
    feedback: str
    improvement: str
    follow_up_required: bool
    claim_confidence: Literal["High", "Medium", "Low"] | None = None
    evaluator: Literal["llm", "heuristic"]


class LLMReportNarrative(BaseModel):
    executive_summary: str = Field(min_length=20, max_length=1200)
    verdict: str = Field(min_length=10, max_length=600)
    communication_feedback: str = Field(default="", max_length=800)


# ---------------------------------------------------------------- API payloads


class ResumeOut(BaseModel):
    id: str
    filename: str
    file_type: str
    size_bytes: int
    page_count: int | None
    created_at: datetime
    warnings: list[str]
    profile: CandidateProfile
    llm_enriched: bool
    word_count: int


class ResumeSummary(BaseModel):
    id: str
    filename: str
    file_type: str
    size_bytes: int
    created_at: datetime
    candidate_name: str
    ats_score: float | None


class AnalyzeRequest(BaseModel):
    job_description: str | None = Field(default=None, max_length=20000)
    jd_id: str | None = None
    target_role: str = Field(default="Software Engineer", max_length=80)


class AnalysisOut(BaseModel):
    resume_id: str
    jd_id: str | None
    ats: ATSReport
    jd_match: JDMatch | None
    jd_analysis: JDAnalysis | None


class JDAnalyzeRequest(BaseModel):
    text: str = Field(min_length=1, max_length=20000)
    title: str = Field(default="", max_length=200)


class JDOut(BaseModel):
    id: str
    title: str
    analysis: JDAnalysis


class CreateInterviewRequest(BaseModel):
    resume_id: str
    job_description: str | None = Field(default=None, max_length=20000)
    jd_id: str | None = None
    config: InterviewConfig = Field(default_factory=InterviewConfig)


class AnswerRequest(BaseModel):
    question_id: str
    answer: str = Field(max_length=6000)
    input_mode: VoiceMode = "text"
    duration_seconds: int | None = Field(default=None, ge=0, le=7200)


class SkipRequest(BaseModel):
    question_id: str


class MessageOut(BaseModel):
    seq: int
    role: Literal["interviewer", "candidate", "system"]
    text: str
    question_id: str | None
    created_at: datetime
    kind: str = "message"


class CurrentQuestionOut(BaseModel):
    id: str
    text: str
    category: str
    phase: str
    is_follow_up: bool
    number: int  # main question number (1-based)


class ProgressOut(BaseModel):
    answered: int
    total: int
    follow_ups: int
    percent: float


class InterviewerOut(BaseModel):
    name: str
    title: str
    personality: str


class InterviewOut(BaseModel):
    id: str
    state: str
    phase: str | None
    config: InterviewConfig
    resume_id: str
    jd_id: str | None
    candidate_name: str
    created_at: datetime
    started_at: datetime | None
    finished_at: datetime | None
    messages: list[MessageOut]
    current_question: CurrentQuestionOut | None
    progress: ProgressOut
    interviewer: InterviewerOut
    ai_mode: Literal["llm", "offline"]
    error: str | None = None


class HistoryItem(BaseModel):
    id: str
    created_at: datetime
    finished_at: datetime | None
    state: str
    target_role: str
    interview_type: str
    difficulty: str
    experience_level: str
    num_questions: int
    interview_score: float | None
    ats_score: float | None
    jd_score: float | None
    readiness_score: float | None
    duration_seconds: int | None
    resume_filename: str
    has_jd: bool
