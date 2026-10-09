// Mirrors backend/app/schemas.py and the report dict built in backend/app/interview/report.py.

export interface ExperienceItem {
  title: string
  company: string
  start: string
  end: string
  duration_months: number | null
  bullets: string[]
  technologies: string[]
}
export interface ProjectItem {
  name: string
  description: string
  technologies: string[]
  bullets: string[]
  links: string[]
}
export interface EducationItem {
  degree: string
  field: string
  institution: string
  start: string
  end: string
  gpa: string
}
export interface ResumeClaim {
  text: string
  kind: string
  section: string
  subject: string
}
export interface CandidateProfile {
  name: string
  email: string
  phone: string
  location: string
  summary: string
  skills: string[]
  programming_languages: string[]
  frameworks: string[]
  databases: string[]
  tools: string[]
  concepts: string[]
  experience: ExperienceItem[]
  projects: ProjectItem[]
  education: EducationItem[]
  certifications: string[]
  achievements: string[]
  links: string[]
  years_of_experience: number | null
  claims: ResumeClaim[]
  sections: string[]
  ai_summary?: string
}
export interface ResumeOut {
  id: string
  filename: string
  file_type: string
  size_bytes: number
  page_count: number | null
  created_at: string
  warnings: string[]
  profile: CandidateProfile
  llm_enriched: boolean
  word_count: number
}
export interface ResumeSummary {
  id: string
  filename: string
  file_type: string
  size_bytes: number
  created_at: string
  candidate_name: string
  ats_score: number | null
}
export interface ATSDimension {
  key: string
  label: string
  score: number
  weight: number
  detail: string
}
export interface ATSReport {
  overall: number
  classification: string
  dimensions: ATSDimension[]
  matched_keywords: string[]
  missing_keywords: string[]
  weak_keywords: string[]
  missing_important_skills: string[]
  ats_problems: string[]
  recommendations: string[]
  stats: Record<string, number | string>
  keyword_source: 'job_description' | 'role_template'
  target_role: string
  disclaimer: string
}
export interface JDAnalysis {
  title: string
  seniority: string
  required_skills: string[]
  preferred_skills: string[]
  technologies: string[]
  responsibilities: string[]
  experience_years_min: number | null
  education_requirements: string[]
  keywords: string[]
  domain_terms: string[]
  warnings: string[]
}
export interface RequirementMatch {
  requirement: string
  kind: 'required_skill' | 'preferred_skill' | 'experience' | 'education' | 'keyword'
  status: 'matched' | 'partial' | 'missing'
  evidence: string[]
  note: string
}
export interface JDMatch {
  score: number
  classification: string
  requirements: RequirementMatch[]
  matched: string[]
  partial: string[]
  missing: string[]
  summary: string
  breakdown: Record<string, number>
}
export interface AnalysisOut {
  resume_id: string
  jd_id: string | null
  ats: ATSReport
  jd_match: JDMatch | null
  jd_analysis: JDAnalysis | null
}

export type ExperienceLevel = 'Student' | 'Fresher' | 'Junior' | 'Mid-Level' | 'Senior'
export type InterviewType =
  'Technical' | 'Behavioral' | 'HR' | 'Project Deep Dive' | 'Coding' | 'System Design' | 'Mixed' | 'Custom'
export type Difficulty = 'Easy' | 'Medium' | 'Hard' | 'Very Hard'
export type Personality =
  'Friendly' | 'Professional' | 'Strict' | 'Senior Engineer' | 'Hiring Manager' | 'HR' | 'CTO'

export interface InterviewConfig {
  target_role: string
  experience_level: ExperienceLevel
  interview_type: InterviewType
  difficulty: Difficulty
  num_questions: number
  personality: Personality
  mode: 'voice' | 'text'
  custom_focus: string
}
export interface MessageOut {
  seq: number
  role: 'interviewer' | 'candidate' | 'system'
  text: string
  question_id: string | null
  created_at: string
  kind: string
}
export interface CurrentQuestion {
  id: string
  text: string
  category: string
  phase: string
  is_follow_up: boolean
  number: number
}
export interface InterviewOut {
  id: string
  state: string
  phase: string | null
  config: InterviewConfig
  resume_id: string
  jd_id: string | null
  candidate_name: string
  created_at: string
  started_at: string | null
  finished_at: string | null
  messages: MessageOut[]
  current_question: CurrentQuestion | null
  progress: { answered: number; total: number; follow_ups: number; percent: number }
  interviewer: { name: string; title: string; personality: string }
  ai_mode: 'llm' | 'offline'
  error: string | null
}
export interface HistoryItem {
  id: string
  created_at: string
  finished_at: string | null
  state: string
  target_role: string
  interview_type: string
  difficulty: string
  experience_level: string
  num_questions: number
  interview_score: number | null
  ats_score: number | null
  jd_score: number | null
  readiness_score: number | null
  duration_seconds: number | null
  resume_filename: string
  has_jd: boolean
}

export interface ScoreItem {
  key: string
  label: string
  score: number | null
  weight: number
}
export interface ReportQuestion {
  id: string
  number: number
  question: string
  category: string
  phase: string
  difficulty: string
  skill: string
  source: string
  is_follow_up: boolean
  answer: string
  skipped: boolean
  input_mode: string
  score: number
  classification: string
  dimensions: Record<string, number>
  strengths: string[]
  missing: string[]
  weaknesses: string[]
  feedback: string
  improvement: string
  ideal_answer: string
  claim: string | null
  claim_confidence: 'High' | 'Medium' | 'Low' | null
  evaluator: string
}
export interface InterviewReport {
  interview_id: string
  generated_at: string
  candidate_name: string
  config: InterviewConfig
  duration_seconds: number | null
  ai_mode: 'llm' | 'offline'
  model: string | null
  evaluators: Record<string, number>
  narrative_source: string
  prompt_version: string
  scores: {
    ats: number
    ats_classification: string
    jd_match: number | null
    interview: number | null
    interview_classification: string | null
    readiness: number | null
    readiness_classification: string | null
  }
  readiness_formula: {
    label: string
    components: {
      key: string
      label: string
      score: number | null
      weight: number
      configured_weight: number
    }[]
    note: string
  }
  category_scores: ScoreItem[]
  dimension_averages: { key: string; label: string; score: number | null }[]
  executive_summary: string
  verdict: string
  communication_feedback: string
  skills: { skill: string; score: number; evidence: string; recommendation: string; questions: number }[]
  questions: ReportQuestion[]
  unanswered_questions: string[]
  strongest_areas: { area: string; score: number | null; detail: string }[]
  weakest_areas: { area: string; score: number | null; detail: string }[]
  claims: {
    claim: string
    confidence: 'High' | 'Medium' | 'Low'
    note: string
    question: string
    skipped: boolean
  }[]
  technical_gaps: string[]
  study_topics: { topic: string; reason: string; priority: 'High' | 'Medium' | 'Low' }[]
  action_plan: string[]
  ats: {
    overall: number
    classification: string
    recommendations: string[]
    missing_important_skills: string[]
    dimensions: ATSDimension[]
  }
  jd: {
    score: number
    classification: string
    matched: string[]
    missing: string[]
    partial: string[]
    summary: string
  } | null
  timeline: {
    number: number
    score: number
    classification: string
    category: string
    is_follow_up: boolean
  }[]
  stats: {
    questions_answered: number
    questions_skipped: number
    follow_ups: number
    average_answer_words: number
  }
  disclaimers: string[]
}

export interface Health {
  status: string
  application: string
  database: string
  resume_parser: string
  llm: 'ok' | 'unavailable' | 'disabled'
  llm_provider: string
  ollama_server: string
  ollama_model: string
  model: string
  llm_detail: string
  installed_models: string[]
  test_mode: boolean
  voice_enabled: boolean
  version: string
}
export interface Dashboard {
  interviews_completed: number
  latest_interview_score: number | null
  latest_readiness: number | null
  latest_jd_match: number | null
  latest_ats: number | null
  best_score: number | null
  average_score: number | null
  improvement: number | null
  trend: {
    id: string
    date: string | null
    interview: number | null
    readiness: number | null
    ats: number | null
    role: string
  }[]
  weak_skills: { skill: string; score: number; count: number }[]
  recent: {
    id: string
    date: string
    role: string
    type: string
    score: number | null
    readiness: number | null
  }[]
  active_interviews: { id: string; role: string; state: string; created_at: string }[]
  resume_health: {
    resume_id: string
    filename: string
    ats_score: number | null
    classification: string
    top_recommendations: string[]
    dimensions: { label: string; score: number }[]
  } | null
  has_resume: boolean
}
export interface AppSettings {
  llm_provider: string
  ollama_model: string
  ollama_base_url: string
  llm_status: {
    provider: string
    model: string
    available: boolean
    server: string
    model_available: boolean
    detail: string
    installed_models: string[]
  }
  test_mode: boolean
  voice_enabled: boolean
  max_resume_size_mb: number
  weights: Record<string, Record<string, number>>
  database_url: string
}
export interface JDSample {
  id: string
  title: string
  text: string
}
