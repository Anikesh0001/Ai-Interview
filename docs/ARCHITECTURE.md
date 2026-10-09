# Architecture

## Request flow

1. **Upload**: `services/extract.py` validates the file (extension, magic bytes, size, empty, corrupted,
   password-protected, scanned) and extracts normalized text.
2. **Parse**: `services/profile.py` splits the text into sections and builds a `CandidateProfile`. It covers
   contact details, skills from the taxonomy in `data/skills.py`, experience with dates and durations, projects
   with their stack, education, and **claims**: bullets with metrics or architecture, leadership or ownership
   language.
3. **Cache**: the result is keyed by the SHA-256 of the text, so re-uploading identical content reuses the parse.
   ATS/JD analyses are cached per (resume, JD, role).
4. **Enrich (optional)**: a background task asks the LLM for a summary and skills. `merge_enrichment` only fills
   empty fields, and only with skills that literally appear in the resume text.
5. **Analyze**: `services/ats.py` and `services/jd.py` are pure functions of (text, profile, JD, role, weights).

## Interview engine

```
create ─► CREATED ─start─► PREPARING ─► INTRO ─► RESUME ─► PROJECT ─► TECHNICAL ─► PROBLEM_SOLVING ─► BEHAVIORAL
                                          │  ▲        any question phase may enter CHALLENGE (follow-up) │
                                          ▼  │                                                       ▼
                                       CHALLENGE ◄──────────────────────────────────────────────── CLOSING
                                                                                                      │
                                        FAILED ◄──── EVALUATING ◄─────────── finish (or end early) ◄─┘
                                          └─ retry ──►    └──► COMPLETED (terminal)
```

- **State machine** (`interview/state.py`): transitions are validated, and every transition is persisted as an
  `interview_events` row. An invalid action returns 409.
- **Planner** (`interview/planner.py`): splits *N* main questions across categories by interview type, using
  largest-remainder allocation with minimums. It then assigns focuses:
  - the top **claims** go to resume questions
  - several angles on the **most relevant project**, chosen by overlap between its tech and the target skills
  - **JD-required skills the candidate has** first, then the resume's strongest skills (low-signal skills like
    Git/Agile come last)
  - one **JD gap** question
- **Generator** (`interview/generator.py`):
  - With an LLM: a versioned prompt plus `LLMQuestion` schema validation, with rejection if the question repeats
    an earlier one or mentions prompts.
  - Otherwise, and on any failure: the curated bank in `data/question_bank.py`, chosen by nearest difficulty,
    rotated by a per-interview seed (fixed to 0 in TEST_MODE).
  - The intro question is always templated.
- **Evaluator** (`interview/evaluator.py`):
  - Produces 7 dimension scores (0–10), either `AnswerEvaluationLLM` from the LLM or a transparent heuristic over
    observable signals: concept coverage, specificity, reasoning markers, structure, STAR markers, hedges,
    fillers and length.
  - **The backend always computes the final score** from the dimensions with configurable weights, and assigns
    the classification with explicit rules.
- **Follow-ups** (`interview/followups.py`):
  - Budget: `max(2, 0.4·N)`. Follow-ups never go more than one level deep, except Suspicious/Incorrect answers,
    which may go two levels.
  - Excellent: no follow-up, and the difficulty goes up one level.
  - Strong: occasionally a "deeper" probe.
  - Acceptable project answers that name a technique (caching, indexes, microservices…) get a targeted probe.
  - Weak, Vague, Incomplete, Incorrect and Suspicious answers get a clarifying, concrete-detail, missing-part,
    challenge or verification question respectively.
  - Two weak answers in a row lower the difficulty.
- **Persistence**: everything is committed after every answer, so a refresh calls `GET /interviews/{id}` and
  restores the transcript, current question, phase and progress. Answer drafts live in `localStorage`.
- **Report** (`interview/report.py`): aggregates the stored evaluations into category scores, skill table, claims,
  gaps, study topics, action plan and readiness. When an LLM is available it only rewrites the summary, verdict and
  communication feedback, and the output is rejected if it mentions hiring probability.

## LLM safety pipeline

`LLMProvider.complete_structured(system, user, Schema, validator)`:

1. Calls Ollama `/api/chat`, passing `format: <JSON schema>` for constrained decoding.
2. Runs `extract_json` on the reply: it handles code fences and surrounding prose, finds a balanced object, and
   repairs trailing commas, Python literals, smart quotes and unquoted keys.
3. Validates with Pydantic, then the optional semantic validator.
4. On failure, retries once with the validation error appended.
5. Otherwise returns `None`, and the caller uses the deterministic path.

Network errors and timeouts also return `None`. Ollama availability is cached for 15 seconds, so an absent server
costs one quick connection attempt.

## Data model (SQLite)

| Table | Holds |
|---|---|
| `resumes` | file metadata, extracted text and hash, parse warnings |
| `candidate_profiles` | the profile JSON, a cached general ATS report, and whether the LLM enriched it |
| `job_descriptions` | JD text, hash and analysis |
| `resume_analyses` | cached ATS + JD-match results |
| `interviews` | config, plan, state, plan index, follow-up count, asked hashes, runtime (difficulty, streak, history), scores, timestamps |
| `interview_questions` | text, phase, category, difficulty, skill, source, expected concepts, rubric, ideal answer, claim, follow-up parent |
| `answers` | answer text, input mode, duration, skipped flag |
| `evaluations` | dimensions, score, classification, strengths, weaknesses, missing points, feedback, claim confidence, evaluator |
| `interview_events` | the ordered transcript and state transitions |
| `reports` | the full report JSON |
| `skill_scores` | per-skill scores, which feed the dashboard's weak skills |
| `settings` | model/URL chosen in the UI |

Resume and interview deletes cascade. `DELETE /api/data` clears every data table and the uploads folder; the
`settings` table, which holds UI preferences and no personal data, is kept.
