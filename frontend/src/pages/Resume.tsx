import { useCallback, useEffect, useRef, useState, type DragEvent } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import {
  ArrowRight,
  Briefcase,
  CheckCircle2,
  CircleDashed,
  FileText,
  FolderGit2,
  GraduationCap,
  Mail,
  MapPin,
  Phone,
  RefreshCw,
  Trash2,
  UploadCloud,
  XCircle,
} from 'lucide-react'
import { api, errorMessage } from '../lib/api'
import type { AnalysisOut, JDSample, RequirementMatch, ResumeOut } from '../lib/types'
import { KEYS, load, remove, save } from '../lib/storage'
import { fmtBytes } from '../lib/format'
import {
  Alert,
  Badge,
  Button,
  Card,
  CardHeader,
  EmptyState,
  Field,
  PageHeader,
  Skeleton,
  type BadgeTone,
} from '../components/ui'
import { inputCls } from '../lib/cn'
import { ScoreBar, ScoreRing } from '../components/charts'

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
]
const ACCEPT = ['pdf', 'docx', 'txt', 'doc']
const MAX_MB = 10

type Stage = 'idle' | 'uploading' | 'parsing'

export default function ResumePage() {
  const navigate = useNavigate()
  const [resume, setResume] = useState<ResumeOut | null>(null)
  const [loadingResume, setLoadingResume] = useState(() => load<string | null>(KEYS.resumeId, null) !== null)
  const [stage, setStage] = useState<Stage>('idle')
  const [uploadError, setUploadError] = useState<string | null>(null)
  const [pendingFile, setPendingFile] = useState<File | null>(null)
  const [role, setRole] = useState<string>(() => load(KEYS.role, 'Software Engineer'))
  const [jdText, setJdText] = useState<string>(() => load<{ text: string } | null>(KEYS.jd, null)?.text ?? '')
  const [analysis, setAnalysis] = useState<AnalysisOut | null>(null)
  const [analyzing, setAnalyzing] = useState(false)
  const [analysisError, setAnalysisError] = useState<string | null>(null)
  const [samples, setSamples] = useState<JDSample[]>([])

  useEffect(() => {
    api
      .jdSamples()
      .then(setSamples)
      .catch(() => setSamples([]))
    const id = load<string | null>(KEYS.resumeId, null)
    if (!id) return
    api
      .getResume(id)
      .then(setResume)
      .catch(() => remove(KEYS.resumeId))
      .finally(() => setLoadingResume(false))
  }, [])

  const runAnalysis = useCallback(async (r: ResumeOut, text: string, targetRole: string) => {
    setAnalyzing(true)
    setAnalysisError(null)
    try {
      const res = await api.analyzeResume(r.id, {
        job_description: text.trim() || undefined,
        target_role: targetRole,
      })
      setAnalysis(res)
      save(KEYS.jd, text.trim() ? { text: text.trim(), jd_id: res.jd_id } : null)
    } catch (e) {
      setAnalysisError(errorMessage(e))
    } finally {
      setAnalyzing(false)
    }
  }, [])

  // analyze automatically once a resume is available
  const autoRan = useRef<string | null>(null)
  useEffect(() => {
    if (resume && autoRan.current !== resume.id) {
      autoRan.current = resume.id
      runAnalysis(resume, jdText, role)
    }
  }, [resume, jdText, role, runAnalysis])

  const handleFile = async (file: File) => {
    setUploadError(null)
    const ext = file.name.split('.').pop()?.toLowerCase() ?? ''
    if (!ACCEPT.includes(ext)) {
      setUploadError('Unsupported file type. Please upload a PDF, DOCX or TXT resume.')
      return
    }
    if (file.size === 0) {
      setUploadError('The selected file is empty.')
      return
    }
    if (file.size > MAX_MB * 1024 * 1024) {
      setUploadError(`The file is too large. The maximum size is ${MAX_MB} MB.`)
      return
    }
    setPendingFile(file)
    setStage('uploading')
    const t = setTimeout(() => setStage('parsing'), 350)
    try {
      const r = await api.uploadResume(file)
      save(KEYS.resumeId, r.id)
      setAnalysis(null)
      setResume(r)
    } catch (e) {
      setUploadError(errorMessage(e))
    } finally {
      clearTimeout(t)
      setStage('idle')
      setPendingFile(null)
    }
  }

  const handleDelete = async () => {
    if (!resume) return
    if (!window.confirm('Delete this resume and every interview that used it? This cannot be undone.')) return
    try {
      await api.deleteResume(resume.id)
      remove(KEYS.resumeId)
      setResume(null)
      setAnalysis(null)
    } catch (e) {
      setUploadError(errorMessage(e))
    }
  }

  const startInterview = () => {
    save(KEYS.role, role)
    navigate('/interview/setup')
  }

  if (loadingResume) {
    return (
      <div className="space-y-4">
        <Skeleton className="h-8 w-60" />
        <Skeleton className="h-48" />
      </div>
    )
  }

  return (
    <div className="space-y-6">
      <PageHeader
        title="Resume analysis"
        description="Parsed locally on this device. Nothing is uploaded to external services."
        actions={
          resume && (
            <Button onClick={startInterview}>
              Start interview <ArrowRight className="size-4" />
            </Button>
          )
        }
      />

      {!resume ? (
        <Dropzone stage={stage} pendingFile={pendingFile} error={uploadError} onFile={handleFile} />
      ) : (
        <>
          <FileCard resume={resume} onReplace={handleFile} onDelete={handleDelete} busy={stage !== 'idle'} />
          {uploadError && <Alert tone="error">{uploadError}</Alert>}

          <Card>
            <CardHeader
              title="Target role & job description"
              subtitle="Optional. Paste a job description to get a JD match score and tailored keywords."
            />
            <div className="grid gap-4 p-5 lg:grid-cols-[260px_1fr]">
              <div className="space-y-4">
                <Field label="Target role" htmlFor="role">
                  <select
                    id="role"
                    className={inputCls}
                    value={role}
                    onChange={(e) => setRole(e.target.value)}
                  >
                    {ROLES.map((r) => (
                      <option key={r}>{r}</option>
                    ))}
                  </select>
                </Field>
                {samples.length > 0 && (
                  <Field label="Try a sample job description" htmlFor="sample">
                    <select
                      id="sample"
                      className={inputCls}
                      value=""
                      onChange={(e) => {
                        const s = samples.find((x) => x.id === e.target.value)
                        if (s) setJdText(s.text)
                      }}
                    >
                      <option value="">Choose a sample…</option>
                      {samples.map((s) => (
                        <option key={s.id} value={s.id}>
                          {s.title}
                        </option>
                      ))}
                    </select>
                  </Field>
                )}
              </div>
              <div>
                <Field
                  label="Job description"
                  htmlFor="jd"
                  hint={`${jdText.length.toLocaleString()} / 20,000 characters`}
                >
                  <textarea
                    id="jd"
                    rows={7}
                    maxLength={20000}
                    className={inputCls}
                    placeholder="Paste the full job posting, including responsibilities and requirements…"
                    value={jdText}
                    onChange={(e) => setJdText(e.target.value)}
                  />
                </Field>
                <div className="mt-3 flex flex-wrap gap-2">
                  <Button onClick={() => runAnalysis(resume, jdText, role)} loading={analyzing}>
                    {jdText.trim() ? 'Analyze match' : 'Analyze resume'}
                  </Button>
                  {jdText && (
                    <Button
                      variant="ghost"
                      onClick={() => {
                        setJdText('')
                        runAnalysis(resume, '', role)
                      }}
                    >
                      Clear job description
                    </Button>
                  )}
                </div>
              </div>
            </div>
          </Card>

          {analysisError && <Alert tone="error">{analysisError}</Alert>}
          {analyzing && !analysis && <Skeleton className="h-72" />}
          {analysis && <AnalysisView analysis={analysis} />}
          <ProfileView resume={resume} />
          <div className="flex justify-end">
            <Button size="lg" onClick={startInterview}>
              Configure mock interview <ArrowRight className="size-4" />
            </Button>
          </div>
        </>
      )}
    </div>
  )
}

function Dropzone({
  stage,
  pendingFile,
  error,
  onFile,
}: {
  stage: Stage
  pendingFile: File | null
  error: string | null
  onFile: (f: File) => void
}) {
  const [over, setOver] = useState(false)
  const inputRef = useRef<HTMLInputElement>(null)
  const busy = stage !== 'idle'
  const onDrop = (e: DragEvent) => {
    e.preventDefault()
    setOver(false)
    const f = e.dataTransfer.files?.[0]
    if (f && !busy) onFile(f)
  }
  return (
    <div className="space-y-3">
      <div
        onDragOver={(e) => {
          e.preventDefault()
          setOver(true)
        }}
        onDragLeave={() => setOver(false)}
        onDrop={onDrop}
        className={`rounded-lg border-2 border-dashed bg-white px-6 py-14 text-center transition-colors dark:bg-zinc-900 ${
          over
            ? 'border-indigo-500 bg-indigo-50/50 dark:bg-indigo-500/5'
            : 'border-zinc-300 dark:border-zinc-700'
        }`}
      >
        {busy ? (
          <div className="mx-auto max-w-sm" role="status" aria-live="polite">
            <RefreshCw className="mx-auto size-8 animate-spin text-indigo-500" aria-hidden />
            <p className="mt-3 text-sm font-medium">
              {stage === 'uploading' ? 'Uploading' : 'Parsing resume'}
              {pendingFile ? ` · ${pendingFile.name}` : ''}
            </p>
            <p className="mt-1 text-xs text-zinc-500">
              {pendingFile ? fmtBytes(pendingFile.size) : ''} · Extracting skills, projects, experience and
              claims…
            </p>
          </div>
        ) : (
          <>
            <UploadCloud className="mx-auto size-9 text-zinc-400" aria-hidden />
            <p className="mt-3 text-sm font-medium">Drag and drop your resume here</p>
            <p className="mt-1 text-xs text-zinc-500">
              PDF, DOCX or TXT · up to {MAX_MB} MB · text-based (not scanned)
            </p>
            <Button className="mt-5" variant="secondary" onClick={() => inputRef.current?.click()}>
              Choose file
            </Button>
          </>
        )}
        <input
          ref={inputRef}
          type="file"
          className="sr-only"
          accept=".pdf,.docx,.txt,.doc,application/pdf,application/vnd.openxmlformats-officedocument.wordprocessingml.document,text/plain"
          aria-label="Upload resume file"
          data-testid="resume-input"
          onChange={(e) => {
            const f = e.target.files?.[0]
            if (f) onFile(f)
            e.target.value = ''
          }}
        />
      </div>
      {error && (
        <Alert tone="error" title="Upload failed">
          {error}
        </Alert>
      )}
      <p className="text-xs text-zinc-500">
        Your resume, transcript and interview history are stored locally on this device.
      </p>
    </div>
  )
}

function FileCard({
  resume,
  onReplace,
  onDelete,
  busy,
}: {
  resume: ResumeOut
  onReplace: (f: File) => void
  onDelete: () => void
  busy: boolean
}) {
  const inputRef = useRef<HTMLInputElement>(null)
  return (
    <Card>
      <div className="flex flex-col gap-4 p-5 sm:flex-row sm:items-center">
        <div className="flex size-11 items-center justify-center rounded-md bg-indigo-50 text-indigo-600 dark:bg-indigo-500/10 dark:text-indigo-400">
          <FileText className="size-5" aria-hidden />
        </div>
        <div className="min-w-0 flex-1">
          <p className="truncate font-medium" data-testid="resume-filename">
            {resume.filename}
          </p>
          <p className="text-sm text-zinc-500">
            {resume.file_type.toUpperCase()} · {fmtBytes(resume.size_bytes)}
            {resume.page_count
              ? ` · ${resume.page_count} page${resume.page_count > 1 ? 's' : ''}`
              : ''} · {resume.word_count} words
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Badge tone="green">
            <CheckCircle2 className="size-3" /> Parsed
          </Badge>
          {resume.llm_enriched && <Badge tone="indigo">AI-enriched</Badge>}
          <Button variant="secondary" size="sm" onClick={() => inputRef.current?.click()} loading={busy}>
            Replace
          </Button>
          <Button variant="ghost" size="sm" onClick={onDelete} aria-label="Delete resume">
            <Trash2 className="size-4" />
          </Button>
          <input
            ref={inputRef}
            type="file"
            className="sr-only"
            accept=".pdf,.docx,.txt,.doc"
            aria-label="Replace resume file"
            onChange={(e) => {
              const f = e.target.files?.[0]
              if (f) onReplace(f)
              e.target.value = ''
            }}
          />
        </div>
      </div>
      {resume.warnings.length > 0 && (
        <div className="border-t border-zinc-100 px-5 py-3 dark:border-zinc-800">
          {resume.warnings.map((w) => (
            <p key={w} className="text-sm text-amber-700 dark:text-amber-300">
              ⚠ {w}
            </p>
          ))}
        </div>
      )}
    </Card>
  )
}

function ChipList({ items, tone, empty }: { items: string[]; tone: BadgeTone; empty: string }) {
  if (!items.length) return <p className="text-sm text-zinc-500">{empty}</p>
  return (
    <div className="flex flex-wrap gap-1.5">
      {items.map((k) => (
        <Badge key={k} tone={tone}>
          {k}
        </Badge>
      ))}
    </div>
  )
}

const statusBadge: Record<
  RequirementMatch['status'],
  { tone: BadgeTone; label: string; Icon: typeof CheckCircle2 }
> = {
  matched: { tone: 'green', label: 'Matched', Icon: CheckCircle2 },
  partial: { tone: 'amber', label: 'Partial', Icon: CircleDashed },
  missing: { tone: 'red', label: 'Missing', Icon: XCircle },
}
const kindLabel: Record<RequirementMatch['kind'], string> = {
  required_skill: 'Required',
  preferred_skill: 'Preferred',
  experience: 'Experience',
  education: 'Education',
  keyword: 'Keyword',
}

function AnalysisView({ analysis }: { analysis: AnalysisOut }) {
  const { ats, jd_match: jd } = analysis
  const reqs = jd?.requirements.filter((r) => r.kind !== 'keyword') ?? []
  return (
    <div className="space-y-6" data-testid="analysis">
      <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_minmax(0,1fr)]">
        <Card>
          <CardHeader
            title="ATS-style compatibility score"
            subtitle={`Keywords from ${ats.keyword_source === 'job_description' ? 'the job description' : `the ${ats.target_role} role template`}`}
          />
          <div className="grid gap-6 p-5 sm:grid-cols-[auto_1fr]">
            <div data-testid="ats-score">
              <ScoreRing score={ats.overall} label="ATS score" sublabel={ats.classification} />
            </div>
            <div className="space-y-3">
              {ats.dimensions.map((d) => (
                <ScoreBar key={d.key} label={d.label} score={d.score} weight={d.weight} />
              ))}
            </div>
          </div>
          <p className="border-t border-zinc-100 px-5 py-3 text-xs text-zinc-500 dark:border-zinc-800">
            {ats.disclaimer}
          </p>
        </Card>

        {jd ? (
          <Card data-testid="jd-match">
            <CardHeader title="Job description match" subtitle={jd.summary} />
            <div className="grid gap-6 p-5 sm:grid-cols-[auto_1fr]">
              <ScoreRing score={jd.score} label="JD match" sublabel={jd.classification} />
              <div className="space-y-3">
                {Object.entries(jd.breakdown).map(([k, v]) => (
                  <ScoreBar
                    key={k}
                    label={k.replace('_', ' ').replace(/^./, (c) => c.toUpperCase())}
                    score={v}
                  />
                ))}
              </div>
            </div>
            <div className="relative max-h-80 overflow-auto border-t border-zinc-100 dark:border-zinc-800">
              <table className="w-full text-sm">
                <caption className="sr-only">Requirement matching</caption>
                <thead className="sticky top-0 bg-zinc-50 text-left text-xs text-zinc-500 dark:bg-zinc-900">
                  <tr>
                    <th className="px-5 py-2 font-medium">Requirement</th>
                    <th className="px-2 py-2 font-medium">Status</th>
                    <th className="px-5 py-2 font-medium">Evidence</th>
                  </tr>
                </thead>
                <tbody>
                  {reqs.map((r) => {
                    const st = statusBadge[r.status]
                    return (
                      <tr
                        key={r.kind + r.requirement}
                        className="border-t border-zinc-100 align-top dark:border-zinc-800"
                      >
                        <td className="px-5 py-2">
                          <div className="font-medium">{r.requirement}</div>
                          <div className="text-xs text-zinc-500">{kindLabel[r.kind]}</div>
                        </td>
                        <td className="px-2 py-2">
                          <Badge tone={st.tone}>
                            <st.Icon className="size-3" /> {st.label}
                          </Badge>
                        </td>
                        <td className="px-5 py-2 text-xs text-zinc-600 dark:text-zinc-400">
                          {r.evidence[0] ?? r.note ?? ''}
                          {r.evidence[0] && r.note ? <div className="text-zinc-400">{r.note}</div> : null}
                        </td>
                      </tr>
                    )
                  })}
                </tbody>
              </table>
            </div>
          </Card>
        ) : (
          <Card>
            <CardHeader title="Job description match" />
            <EmptyState icon={<Briefcase className="size-5" />} title="No job description yet">
              Paste a job description above to see matched, partial and missing requirements with evidence
              from your resume.
            </EmptyState>
          </Card>
        )}
      </div>

      <div className="grid gap-6 lg:grid-cols-2">
        <Card>
          <CardHeader title="Keywords & skills" />
          <div className="space-y-5 p-5">
            <div>
              <h3 className="mb-2 text-xs font-medium tracking-wide text-zinc-500 uppercase">
                Matched keywords
              </h3>
              <ChipList items={ats.matched_keywords} tone="green" empty="No target keywords found." />
            </div>
            <div>
              <h3 className="mb-2 text-xs font-medium tracking-wide text-zinc-500 uppercase">
                Missing keywords
              </h3>
              <ChipList items={ats.missing_keywords} tone="red" empty="None — nice coverage." />
            </div>
            <div>
              <h3 className="mb-2 text-xs font-medium tracking-wide text-zinc-500 uppercase">
                Weak keywords <span className="normal-case">(listed but not demonstrated)</span>
              </h3>
              <ChipList
                items={ats.weak_keywords}
                tone="amber"
                empty="Every listed skill is backed by evidence."
              />
            </div>
            <div>
              <h3 className="mb-2 text-xs font-medium tracking-wide text-zinc-500 uppercase">
                Important skills not found
              </h3>
              <ChipList items={ats.missing_important_skills} tone="red" empty="All key skills are present." />
            </div>
          </div>
        </Card>
        <Card>
          <CardHeader title="Recommendations" />
          <div className="space-y-5 p-5">
            <ol className="space-y-2 text-sm">
              {ats.recommendations.map((r, i) => (
                <li key={r} className="flex gap-3">
                  <span className="flex size-5 shrink-0 items-center justify-center rounded-full bg-indigo-50 text-xs font-medium text-indigo-700 dark:bg-indigo-500/10 dark:text-indigo-300">
                    {i + 1}
                  </span>
                  <span>{r}</span>
                </li>
              ))}
            </ol>
            <div>
              <h3 className="mb-2 text-xs font-medium tracking-wide text-zinc-500 uppercase">
                Possible ATS problems
              </h3>
              {ats.ats_problems.length ? (
                <ul className="space-y-1 text-sm text-amber-800 dark:text-amber-300">
                  {ats.ats_problems.map((p) => (
                    <li key={p}>⚠ {p}</li>
                  ))}
                </ul>
              ) : (
                <p className="text-sm text-zinc-500">No parsing problems detected.</p>
              )}
            </div>
          </div>
        </Card>
      </div>
    </div>
  )
}

function ProfileView({ resume }: { resume: ResumeOut }) {
  const p = resume.profile
  const groups: [string, string[]][] = [
    ['Languages', p.programming_languages],
    ['Frameworks & libraries', p.frameworks],
    ['Databases', p.databases],
    ['Tools & platforms', p.tools],
    ['Concepts', p.concepts],
  ]
  return (
    <Card data-testid="profile">
      <CardHeader
        title="Parsed candidate profile"
        subtitle="Extracted deterministically; the interviewer uses this to plan questions."
      />
      <div className="grid gap-6 p-5 lg:grid-cols-3">
        <div className="space-y-4">
          <div>
            <p className="text-lg font-semibold" data-testid="candidate-name">
              {p.name || 'Name not detected'}
            </p>
            {p.years_of_experience !== null && (
              <p className="text-sm text-zinc-500">~{p.years_of_experience} years of experience</p>
            )}
          </div>
          <ul className="space-y-1.5 text-sm text-zinc-600 dark:text-zinc-400">
            {p.email && (
              <li className="flex items-center gap-2">
                <Mail className="size-4" aria-hidden /> {p.email}
              </li>
            )}
            {p.phone && (
              <li className="flex items-center gap-2">
                <Phone className="size-4" aria-hidden /> {p.phone}
              </li>
            )}
            {p.location && (
              <li className="flex items-center gap-2">
                <MapPin className="size-4" aria-hidden /> {p.location}
              </li>
            )}
            {p.links.map((l) => (
              <li key={l} className="truncate text-indigo-600 dark:text-indigo-400">
                {l}
              </li>
            ))}
          </ul>
          {groups.map(([label, items]) =>
            items.length ? (
              <div key={label}>
                <h3 className="mb-1.5 text-xs font-medium tracking-wide text-zinc-500 uppercase">{label}</h3>
                <ChipList items={items} tone="neutral" empty="" />
              </div>
            ) : null,
          )}
        </div>

        <div className="space-y-5 lg:col-span-2">
          <section>
            <h3 className="mb-2 flex items-center gap-2 text-sm font-semibold">
              <Briefcase className="size-4 text-zinc-400" aria-hidden /> Experience
            </h3>
            {p.experience.length ? (
              <ul className="space-y-3">
                {p.experience.map((e, i) => (
                  <li key={i} className="text-sm">
                    <div className="flex flex-wrap items-baseline justify-between gap-2">
                      <span className="font-medium">
                        {e.title}
                        {e.company && <span className="font-normal text-zinc-500"> · {e.company}</span>}
                      </span>
                      <span className="text-xs text-zinc-500">
                        {e.start}
                        {e.end && ` – ${e.end}`}
                      </span>
                    </div>
                    <ul className="mt-1 list-disc space-y-0.5 pl-5 text-zinc-600 dark:text-zinc-400">
                      {e.bullets.map((b) => (
                        <li key={b}>{b}</li>
                      ))}
                    </ul>
                  </li>
                ))}
              </ul>
            ) : (
              <p className="text-sm text-zinc-500">No work experience detected.</p>
            )}
          </section>
          <section>
            <h3 className="mb-2 flex items-center gap-2 text-sm font-semibold">
              <FolderGit2 className="size-4 text-zinc-400" aria-hidden /> Projects
            </h3>
            {p.projects.length ? (
              <ul className="grid gap-3 sm:grid-cols-2">
                {p.projects.map((pr) => (
                  <li
                    key={pr.name}
                    className="rounded-md border border-zinc-200 p-3 text-sm dark:border-zinc-800"
                  >
                    <p className="font-medium">{pr.name}</p>
                    <div className="mt-1.5 flex flex-wrap gap-1">
                      {pr.technologies.map((t) => (
                        <Badge key={t}>{t}</Badge>
                      ))}
                    </div>
                    <p className="mt-2 line-clamp-3 text-zinc-600 dark:text-zinc-400">
                      {pr.bullets[0] ?? pr.description}
                    </p>
                  </li>
                ))}
              </ul>
            ) : (
              <p className="text-sm text-zinc-500">No projects detected.</p>
            )}
          </section>
          <section>
            <h3 className="mb-2 flex items-center gap-2 text-sm font-semibold">
              <GraduationCap className="size-4 text-zinc-400" aria-hidden /> Education
            </h3>
            {p.education.length ? (
              <ul className="space-y-1 text-sm">
                {p.education.map((e, i) => (
                  <li key={i}>
                    <span className="font-medium">{e.degree}</span>
                    {e.institution && <span className="text-zinc-500"> · {e.institution}</span>}
                    {(e.end || e.gpa) && (
                      <span className="text-zinc-500">
                        {' '}
                        · {[e.end, e.gpa && `GPA ${e.gpa}`].filter(Boolean).join(' · ')}
                      </span>
                    )}
                  </li>
                ))}
              </ul>
            ) : (
              <p className="text-sm text-zinc-500">No education detected.</p>
            )}
          </section>
          {p.claims.length > 0 && (
            <section>
              <h3 className="mb-2 text-sm font-semibold">Claims the interviewer may ask you to back up</h3>
              <ul className="space-y-1.5 text-sm">
                {p.claims.slice(0, 6).map((c) => (
                  <li key={c.text} className="flex gap-2">
                    <Badge tone={c.kind === 'metric' ? 'blue' : 'indigo'} className="shrink-0 capitalize">
                      {c.kind}
                    </Badge>
                    <span className="text-zinc-600 dark:text-zinc-400">{c.text}</span>
                  </li>
                ))}
              </ul>
            </section>
          )}
          {(p.certifications.length > 0 || p.achievements.length > 0) && (
            <section className="grid gap-4 sm:grid-cols-2">
              {p.certifications.length > 0 && (
                <div>
                  <h3 className="mb-1.5 text-sm font-semibold">Certifications</h3>
                  <ul className="list-disc space-y-0.5 pl-5 text-sm text-zinc-600 dark:text-zinc-400">
                    {p.certifications.map((c) => (
                      <li key={c}>{c}</li>
                    ))}
                  </ul>
                </div>
              )}
              {p.achievements.length > 0 && (
                <div>
                  <h3 className="mb-1.5 text-sm font-semibold">Achievements</h3>
                  <ul className="list-disc space-y-0.5 pl-5 text-sm text-zinc-600 dark:text-zinc-400">
                    {p.achievements.map((c) => (
                      <li key={c}>{c}</li>
                    ))}
                  </ul>
                </div>
              )}
            </section>
          )}
        </div>
      </div>
      <div className="border-t border-zinc-100 px-5 py-3 text-xs text-zinc-500 dark:border-zinc-800">
        Wrong details? Fix them in your resume file and upload it again.{' '}
        <Link className="underline" to="/settings">
          Manage local data
        </Link>
      </div>
    </Card>
  )
}
