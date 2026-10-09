import { useState, type ReactNode } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { FileText, Keyboard, Mic, PlayCircle } from 'lucide-react'
import { api, errorMessage } from '../lib/api'
import type {
  Difficulty,
  ExperienceLevel,
  InterviewConfig,
  InterviewType,
  Personality,
  ResumeSummary,
} from '../lib/types'
import { KEYS, load, save } from '../lib/storage'
import { speechRecognitionSupported, speechSynthesisSupported } from '../lib/speech'
import { fmtDate, fmtScore } from '../lib/format'
import { useAsync } from '../hooks/useAsync'
import { useHealth } from '../components/HealthContext'
import { Alert, Button, Card, CardHeader, EmptyState, Field, PageHeader, Skeleton } from '../components/ui'
import { cn, inputCls } from '../lib/cn'

const ROLES = [
  'Software Engineer',
  'Frontend Developer',
  'Backend Developer',
  'Full Stack Developer',
  'Data Analyst',
  'Data Scientist',
  'Machine Learning Engineer',
  'DevOps Engineer',
  'Product Manager',
  'Custom',
]
const LEVELS: ExperienceLevel[] = ['Student', 'Fresher', 'Junior', 'Mid-Level', 'Senior']
const TYPES: { value: InterviewType; hint: string }[] = [
  { value: 'Mixed', hint: 'Background, projects, technical, scenario and behavioral' },
  { value: 'Technical', hint: 'Concepts from your stack, coding and design' },
  { value: 'Project Deep Dive', hint: 'Architecture, decisions and claims in your projects' },
  { value: 'Behavioral', hint: 'STAR stories: conflict, failure, ownership' },
  { value: 'HR', hint: 'Motivation, goals, teamwork' },
  { value: 'Coding', hint: 'Talk through algorithms and complexity' },
  { value: 'System Design', hint: 'Design systems verbally' },
  { value: 'Custom', hint: 'Focus on topics you choose' },
]
const DIFFICULTIES: Difficulty[] = ['Easy', 'Medium', 'Hard', 'Very Hard']
const LENGTHS = [
  { label: 'Quick', n: 5 },
  { label: 'Standard', n: 10 },
  { label: 'Full', n: 15 },
]
const PERSONALITIES: Personality[] = [
  'Professional',
  'Friendly',
  'Strict',
  'Senior Engineer',
  'Hiring Manager',
  'HR',
  'CTO',
]

const DEFAULT: InterviewConfig = {
  target_role: 'Software Engineer',
  experience_level: 'Junior',
  interview_type: 'Mixed',
  difficulty: 'Medium',
  num_questions: 10,
  personality: 'Professional',
  mode: 'voice',
  custom_focus: '',
}

function Segmented<T extends string | number>({
  name,
  value,
  options,
  onChange,
}: {
  name: string
  value: T
  options: { value: T; label: ReactNode }[]
  onChange: (v: T) => void
}) {
  return (
    <div
      role="radiogroup"
      aria-label={name}
      className="flex flex-wrap gap-1 rounded-md bg-zinc-100 p-1 dark:bg-zinc-800"
    >
      {options.map((o) => (
        <button
          key={String(o.value)}
          type="button"
          role="radio"
          aria-checked={value === o.value}
          onClick={() => onChange(o.value)}
          className={cn(
            'flex-1 rounded px-3 py-1.5 text-sm font-medium whitespace-nowrap transition-colors',
            value === o.value
              ? 'bg-white text-zinc-900 shadow-sm dark:bg-zinc-950 dark:text-white'
              : 'text-zinc-600 hover:text-zinc-900 dark:text-zinc-400 dark:hover:text-white',
          )}
        >
          {o.label}
        </button>
      ))}
    </div>
  )
}

export default function InterviewSetup() {
  const navigate = useNavigate()
  const { health } = useHealth()
  const resumes = useAsync(() => api.listResumes(), [])
  const active = useAsync(() => api.activeInterviews(), [])
  const [chosenResumeId, setResumeId] = useState<string | null>(() => load(KEYS.resumeId, null))
  const saved = load<Partial<InterviewConfig>>(KEYS.setup, {})
  const [cfg, setCfg] = useState<InterviewConfig>(() => ({
    ...DEFAULT,
    ...saved,
    target_role: load(KEYS.role, saved.target_role ?? DEFAULT.target_role),
  }))
  const [customRole, setCustomRole] = useState(ROLES.includes(cfg.target_role) ? '' : cfg.target_role)
  const [customLength, setCustomLength] = useState(![5, 10, 15].includes(cfg.num_questions))
  const [jd, setJd] = useState<string>(() => load<{ text: string } | null>(KEYS.jd, null)?.text ?? '')
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const voiceInput = speechRecognitionSupported()
  const voiceOutput = speechSynthesisSupported()

  const resumeId = resumes.data?.some((r) => r.id === chosenResumeId)
    ? chosenResumeId
    : (resumes.data?.[0]?.id ?? null)

  const set = <K extends keyof InterviewConfig>(k: K, v: InterviewConfig[K]) =>
    setCfg((c) => ({ ...c, [k]: v }))
  const roleSelect = ROLES.includes(cfg.target_role) ? cfg.target_role : 'Custom'

  const start = async () => {
    if (!resumeId) return
    const role = roleSelect === 'Custom' ? customRole.trim() : cfg.target_role
    if (role.length < 2) {
      setError('Please enter the role you are interviewing for.')
      return
    }
    setSubmitting(true)
    setError(null)
    const config = { ...cfg, target_role: role }
    try {
      save(KEYS.setup, config)
      save(KEYS.role, role)
      save(KEYS.resumeId, resumeId)
      const created = await api.createInterview({
        resume_id: resumeId,
        job_description: jd.trim() || undefined,
        config,
      })
      save(KEYS.jd, jd.trim() ? { text: jd.trim(), jd_id: created.jd_id } : null)
      await api.startInterview(created.id)
      navigate(`/interview/${created.id}`)
    } catch (e) {
      setError(errorMessage(e))
      setSubmitting(false)
    }
  }

  if (resumes.loading) {
    return (
      <div className="space-y-4">
        <Skeleton className="h-8 w-64" />
        <Skeleton className="h-96" />
      </div>
    )
  }
  if (resumes.error) return <Alert tone="error">{resumes.error}</Alert>
  if (!resumes.data?.length) {
    return (
      <>
        <PageHeader title="Mock interview" />
        <Card>
          <EmptyState
            icon={<FileText className="size-5" />}
            title="Upload a resume first"
            action={
              <Link
                to="/resume"
                className="inline-flex h-10 items-center rounded-md bg-indigo-600 px-4 text-sm font-medium text-white hover:bg-indigo-500"
              >
                Upload resume
              </Link>
            }
          >
            The interviewer plans every question from your actual resume — projects, skills and claims.
          </EmptyState>
        </Card>
      </>
    )
  }

  return (
    <div className="space-y-6">
      <PageHeader
        title="Configure your interview"
        description="Choose the role and format. You can practise as many times as you like."
      />

      {active.data && active.data.length > 0 && (
        <Alert
          tone="info"
          title="You have an interview in progress"
          action={
            <Button
              size="sm"
              variant="secondary"
              onClick={() => navigate(`/interview/${active.data![0].id}`)}
            >
              Resume interview
            </Button>
          }
        >
          {active.data[0].config.target_role} · {active.data[0].progress.answered} of{' '}
          {active.data[0].progress.total} questions answered
        </Alert>
      )}
      {health && health.llm !== 'ok' && (
        <Alert
          tone="warning"
          title={health.test_mode ? 'Test mode: offline engine' : 'Local AI model unavailable'}
        >
          {health.test_mode
            ? 'Questions and scoring come from the deterministic offline engine.'
            : 'The interview will use the offline engine: curated, resume-grounded questions and transparent rule-based scoring. '}
          {!health.test_mode && (
            <Link to="/settings" className="font-medium underline">
              Set up Ollama for AI-generated questions and evaluation.
            </Link>
          )}
        </Alert>
      )}

      <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_320px]">
        <Card>
          <CardHeader title="Interview settings" />
          <div className="space-y-6 p-5">
            <div className="grid gap-4 sm:grid-cols-2">
              <Field label="Target role" htmlFor="target-role">
                <select
                  id="target-role"
                  className={inputCls}
                  value={roleSelect}
                  onChange={(e) =>
                    set('target_role', e.target.value === 'Custom' ? customRole || 'Custom' : e.target.value)
                  }
                >
                  {ROLES.map((r) => (
                    <option key={r}>{r}</option>
                  ))}
                </select>
              </Field>
              {roleSelect === 'Custom' ? (
                <Field label="Custom role title" htmlFor="custom-role">
                  <input
                    id="custom-role"
                    className={inputCls}
                    value={customRole}
                    maxLength={80}
                    placeholder="e.g. Android Developer"
                    onChange={(e) => setCustomRole(e.target.value)}
                  />
                </Field>
              ) : (
                <Field label="Experience level" htmlFor="level">
                  <select
                    id="level"
                    className={inputCls}
                    value={cfg.experience_level}
                    onChange={(e) => set('experience_level', e.target.value as ExperienceLevel)}
                  >
                    {LEVELS.map((l) => (
                      <option key={l}>{l}</option>
                    ))}
                  </select>
                </Field>
              )}
              {roleSelect === 'Custom' && (
                <Field label="Experience level" htmlFor="level">
                  <select
                    id="level"
                    className={inputCls}
                    value={cfg.experience_level}
                    onChange={(e) => set('experience_level', e.target.value as ExperienceLevel)}
                  >
                    {LEVELS.map((l) => (
                      <option key={l}>{l}</option>
                    ))}
                  </select>
                </Field>
              )}
            </div>

            <fieldset>
              <legend className="mb-2 text-sm font-medium">Interview type</legend>
              <div className="grid gap-2 sm:grid-cols-2">
                {TYPES.map((t) => (
                  <label
                    key={t.value}
                    className={cn(
                      'flex cursor-pointer gap-3 rounded-md border p-3 text-sm transition-colors',
                      cfg.interview_type === t.value
                        ? 'border-indigo-500 bg-indigo-50/60 ring-1 ring-indigo-500 dark:bg-indigo-500/10'
                        : 'border-zinc-200 hover:border-zinc-300 dark:border-zinc-800 dark:hover:border-zinc-700',
                    )}
                  >
                    <input
                      type="radio"
                      name="interview-type"
                      value={t.value}
                      checked={cfg.interview_type === t.value}
                      onChange={() => set('interview_type', t.value)}
                      className="mt-0.5 accent-indigo-600"
                    />
                    <span>
                      <span className="block font-medium">{t.value}</span>
                      <span className="block text-xs text-zinc-500">{t.hint}</span>
                    </span>
                  </label>
                ))}
              </div>
            </fieldset>
            {cfg.interview_type === 'Custom' && (
              <Field
                label="Focus topics"
                htmlFor="focus"
                hint="Skills or topics to emphasise, e.g. 'React, SQL, system design'."
              >
                <input
                  id="focus"
                  className={inputCls}
                  maxLength={300}
                  value={cfg.custom_focus}
                  onChange={(e) => set('custom_focus', e.target.value)}
                />
              </Field>
            )}

            <div className="grid gap-5 sm:grid-cols-2">
              <div>
                <p className="mb-2 text-sm font-medium" id="difficulty-label">
                  Difficulty
                </p>
                <Segmented
                  name="Difficulty"
                  value={cfg.difficulty}
                  onChange={(v) => set('difficulty', v)}
                  options={DIFFICULTIES.map((d) => ({ value: d, label: d }))}
                />
              </div>
              <div>
                <p className="mb-2 text-sm font-medium">Interview length</p>
                <Segmented
                  name="Interview length"
                  value={customLength ? -1 : cfg.num_questions}
                  onChange={(v) => {
                    if (v === -1) setCustomLength(true)
                    else {
                      setCustomLength(false)
                      set('num_questions', v)
                    }
                  }}
                  options={[
                    ...LENGTHS.map((l) => ({ value: l.n, label: `${l.label} · ${l.n}` })),
                    { value: -1, label: 'Custom' },
                  ]}
                />
                {customLength && (
                  <div className="mt-2 flex items-center gap-2">
                    <label htmlFor="num-q" className="text-sm text-zinc-600 dark:text-zinc-400">
                      Questions
                    </label>
                    <input
                      id="num-q"
                      type="number"
                      min={3}
                      max={25}
                      className={cn(inputCls, 'w-24')}
                      value={cfg.num_questions}
                      onChange={(e) =>
                        set('num_questions', Math.max(3, Math.min(25, Number(e.target.value) || 3)))
                      }
                    />
                  </div>
                )}
              </div>
            </div>

            <div className="grid gap-5 sm:grid-cols-2">
              <Field label="Interviewer personality" htmlFor="personality">
                <select
                  id="personality"
                  className={inputCls}
                  value={cfg.personality}
                  onChange={(e) => set('personality', e.target.value as Personality)}
                >
                  {PERSONALITIES.map((p) => (
                    <option key={p}>{p}</option>
                  ))}
                </select>
              </Field>
              <div>
                <p className="mb-2 text-sm font-medium">Answer mode</p>
                <Segmented
                  name="Answer mode"
                  value={cfg.mode}
                  onChange={(v) => set('mode', v)}
                  options={[
                    {
                      value: 'voice',
                      label: (
                        <span className="inline-flex items-center gap-1.5">
                          <Mic className="size-3.5" />
                          Voice
                        </span>
                      ),
                    },
                    {
                      value: 'text',
                      label: (
                        <span className="inline-flex items-center gap-1.5">
                          <Keyboard className="size-3.5" />
                          Text
                        </span>
                      ),
                    },
                  ]}
                />
                {cfg.mode === 'voice' && (
                  <p className="mt-1.5 text-xs text-zinc-500">
                    {voiceInput
                      ? `Speech recognition available${voiceOutput ? ' · interviewer will speak' : ''}. You can always type instead.`
                      : 'This browser has no speech recognition — you can still hear the interviewer and type answers.'}
                  </p>
                )}
              </div>
            </div>

            <Field
              label="Job description (optional)"
              htmlFor="setup-jd"
              hint="Questions will target its requirements, including gaps in your resume."
            >
              <textarea
                id="setup-jd"
                rows={5}
                maxLength={20000}
                className={inputCls}
                value={jd}
                onChange={(e) => setJd(e.target.value)}
                placeholder="Paste a job description…"
              />
            </Field>
          </div>
        </Card>

        <div className="space-y-4">
          <Card>
            <CardHeader title="Resume" />
            <div className="space-y-2 p-4">
              {resumes.data.map((r: ResumeSummary) => (
                <label
                  key={r.id}
                  className={cn(
                    'flex cursor-pointer items-center gap-3 rounded-md border p-3 text-sm',
                    resumeId === r.id
                      ? 'border-indigo-500 ring-1 ring-indigo-500'
                      : 'border-zinc-200 dark:border-zinc-800',
                  )}
                >
                  <input
                    type="radio"
                    name="resume"
                    className="accent-indigo-600"
                    checked={resumeId === r.id}
                    onChange={() => setResumeId(r.id)}
                  />
                  <span className="min-w-0 flex-1">
                    <span className="block truncate font-medium">{r.candidate_name || r.filename}</span>
                    <span className="block truncate text-xs text-zinc-500">
                      {r.filename} · {fmtDate(r.created_at)} · ATS {fmtScore(r.ats_score)}
                    </span>
                  </span>
                </label>
              ))}
              <Link
                to="/resume"
                className="block pt-1 text-sm text-indigo-600 hover:underline dark:text-indigo-400"
              >
                Upload a different resume
              </Link>
            </div>
          </Card>
          <Card>
            <div className="space-y-3 p-4 text-sm">
              <h2 className="font-semibold">What to expect</h2>
              <ul className="space-y-1.5 text-zinc-600 dark:text-zinc-400">
                <li>
                  • {cfg.num_questions} main questions, plus follow-ups when an answer needs more detail.
                </li>
                <li>• Scores stay hidden until the report, just like a real interview.</li>
                <li>• Progress is saved after every answer — you can close the tab and resume.</li>
              </ul>
              {error && <Alert tone="error">{error}</Alert>}
              <Button size="lg" className="w-full" onClick={start} loading={submitting} disabled={!resumeId}>
                <PlayCircle className="size-4" /> {submitting ? 'Preparing interview…' : 'Start interview'}
              </Button>
            </div>
          </Card>
        </div>
      </div>
    </div>
  )
}
