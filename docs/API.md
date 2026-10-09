# API reference

Base path: `/api`. Requests and responses are JSON unless noted. Errors look like this:

```json
{ "detail": "Human-readable message", "code": "resume_parse_error", "request_id": "a1b2c3d4e5f6" }
```

| Status | Meaning |
|---|---|
| 404 | Not found |
| 409 | Wrong state (e.g. answering a stale question) |
| 413 | File too large |
| 415 | Unsupported type |
| 422 | Validation or unparseable input (scanned PDF, empty answer, invalid JD) |
| 500/503 | Server or database error; the message is generic and the details are only in the server log |

Interactive OpenAPI docs are available at `/docs` while the backend runs.

## Health & settings

- `GET /health` returns:
  - `status`, `application`, `database`, `resume_parser`
  - `llm` (`ok` | `unavailable` | `disabled`), `ollama_server`, `ollama_model` (`available` | `not_installed` |
    `unknown`), `model`, `llm_detail`, `installed_models`
  - `test_mode`, `voice_enabled`, `version`
- `GET /config` returns the public limits and the role list.
- `GET /settings` returns the LLM status, current weights for every group, and flags.
- `PUT /settings` takes `{ "ollama_model"?: str, "ollama_base_url"?: "http(s)://host[:port]" }`. The values are
  persisted and applied immediately.

## Resumes

- `POST /resumes/upload` is a multipart upload with a `file` field (pdf/docx/txt). It returns `201` with a
  `ResumeOut` containing:
  - `id`, `filename`, `file_type`, `size_bytes`, `page_count`, `created_at`
  - `warnings`, `word_count`, `llm_enriched`
  - `profile`: a `CandidateProfile`

  Identical content returns the existing resume.
- `GET /resumes` lists summaries; `GET /resumes/{id}` returns a `ResumeOut`; `DELETE /resumes/{id}` returns `204`
  and also deletes that resume's interviews and file.
- `POST /resumes/{id}/analyze` takes `{ "target_role": str, "job_description"?: str, "jd_id"?: str }` and returns
  `{ resume_id, jd_id, ats: ATSReport, jd_match: JDMatch | null, jd_analysis: JDAnalysis | null }`.

`ATSReport` contains `overall`, `classification`, `dimensions[] {key,label,score,weight,detail}`,
`matched_keywords`, `missing_keywords`, `weak_keywords`, `missing_important_skills`, `ats_problems`,
`recommendations`, `stats`, `keyword_source`, `target_role` and `disclaimer`.

`JDMatch` contains `score`, `classification`, `requirements[] {requirement, kind, status, evidence[], note}`,
`matched`, `partial`, `missing`, `summary` and `breakdown`.

## Job descriptions

- `POST /job-descriptions/analyze` takes `{ "text": str, "title"?: str }` and returns `{ id, title, analysis }`.
  Text that is too short or doesn't look like a JD returns 422.
- `GET /job-descriptions/samples` returns the 4 bundled sample JDs.

## Interviews

- `POST /interviews` takes this body and returns `201` with an `InterviewOut` in state `CREATED`:

  ```json
  {
    "resume_id": "…",
    "job_description": "optional text",
    "jd_id": "optional",
    "config": {
      "target_role": "Software Engineer", "experience_level": "Junior", "interview_type": "Mixed",
      "difficulty": "Medium", "num_questions": 10, "personality": "Professional", "mode": "voice",
      "custom_focus": ""
    }
  }
  ```

  The allowed config values are:

  | Field | Values |
  |---|---|
  | `experience_level` | Student, Fresher, Junior, Mid-Level, Senior |
  | `interview_type` | Technical, Behavioral, HR, Project Deep Dive, Coding, System Design, Mixed, Custom |
  | `difficulty` | Easy, Medium, Hard, Very Hard |
  | `num_questions` | 3–25 |
  | `personality` | Friendly, Professional, Strict, Senior Engineer, Hiring Manager, HR, CTO |
  | `mode` | voice, text |

- `POST /interviews/{id}/start` returns an `InterviewOut` with the greeting and first question. It is idempotent.
- `GET /interviews/{id}` returns an `InterviewOut`, which is used for session recovery. It contains:
  - `id`, `state`, `phase`, `config`, `resume_id`, `jd_id`, `candidate_name`
  - `created_at`, `started_at`, `finished_at`
  - `messages[] {seq, role, text, question_id, created_at, kind}`
  - `current_question {id, text, category, phase, is_follow_up, number} | null`
  - `progress {answered, total, follow_ups, percent}`
  - `interviewer {name, title, personality}`, `ai_mode` (`llm` | `offline`), `error`

  **Scores are never included.**
- `POST /interviews/{id}/answer` takes `{ "question_id": str, "answer": str (≤6000), "input_mode": "voice"|"text",
  "duration_seconds"?: int }` and returns an `InterviewOut` holding either a follow-up, the next question, or the
  `CLOSING` state.
  - Empty answer: 422.
  - Stale question: 409.
  - Re-submitting an already-answered question: no-op 200.
- `POST /interviews/{id}/next-question` takes `{ "question_id": str }`, skips that question and returns an
  `InterviewOut`.
- `POST /interviews/{id}/finish` closes the interview (also when ending early), generates the report and returns
  `COMPLETED`. On failure the state is `FAILED` and a retry is allowed.
- `GET /interviews/{id}/report` returns the report JSON (`InterviewReport` in `frontend/src/lib/types.ts`);
  `GET /interviews/{id}/report.pdf` returns `application/pdf`; `GET /interviews/{id}/transcript` returns
  `text/plain`.
- `GET /interviews/history` lists `HistoryItem[]`; `GET /interviews/active` lists interviews in progress.
- `DELETE /interviews/{id}` returns `204`.

## Dashboard & data

- `GET /dashboard` returns `interviews_completed`, `latest_*`, `best_score`, `average_score`, `improvement`,
  `trend[]`, `weak_skills[]`, `recent[]`, `active_interviews[]`, `resume_health` and `has_resume`.
- `GET /export` returns a JSON download of all interviews and reports.
- `DELETE /data` deletes every resume, JD, interview, report and uploaded file, and returns `204`.
