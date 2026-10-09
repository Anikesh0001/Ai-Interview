import { useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import {
  AlertTriangle,
  BookOpen,
  ChevronDown,
  ClipboardCopy,
  Download,
  FileJson,
  FileText,
  Printer,
  RotateCcw,
  ShieldCheck,
  TrendingDown,
  TrendingUp,
} from 'lucide-react'
import { api } from '../lib/api'
import type { InterviewReport, ReportQuestion } from '../lib/types'
import { categoryLabel, fmtDateTime, fmtDuration, fmtScore } from '../lib/format'
import { useAsync } from '../hooks/useAsync'
import { Alert, Badge, Button, Card, CardHeader, PageSkeleton, type BadgeTone } from '../components/ui'
import { cn } from '../lib/cn'
import { QuestionTimeline, RadarChart, ScoreBar, ScoreRing } from '../components/charts'

const classTone: Record<string, BadgeTone> = {
  Excellent: 'green',
  Strong: 'green',
  Acceptable: 'blue',
  Weak: 'red',
  Vague: 'amber',
  Incorrect: 'red',
  'Off-topic': 'red',
  Suspicious: 'amber',
  Incomplete: 'amber',
}
const confTone: Record<string, BadgeTone> = { High: 'green', Medium: 'amber', Low: 'red' }

function reportToText(r: InterviewReport): string {
  const s = r.scores
  const lines = [
    `InterviewForge report — ${r.config.experience_level} ${r.config.target_role} (${r.config.interview_type})`,
    '',
    `ATS-style score: ${fmtScore(s.ats)} | JD match: ${fmtScore(s.jd_match)} | Interview: ${fmtScore(s.interview)} | Readiness: ${fmtScore(s.readiness)}`,
    '',
    'Summary',
    r.executive_summary,
    '',
    'Verdict',
    r.verdict,
    '',
    'Category scores',
    ...r.category_scores.map((c) => `- ${c.label}: ${fmtScore(c.score)}`),
    '',
    'Strongest areas',
    ...r.strongest_areas.map((a) => `- ${a.area}: ${a.detail}`),
    '',
    'Weakest areas',
    ...r.weakest_areas.map((a) => `- ${a.area}: ${a.detail}`),
    '',
    'Recommended study topics',
    ...r.study_topics.map((t) => `- [${t.priority}] ${t.topic}: ${t.reason}`),
    '',
    'Action plan',
    ...r.action_plan.map((a, i) => `${i + 1}. ${a}`),
    '',
    'Questions',
    ...r.questions.flatMap((q) => [
      `${q.is_follow_up ? '  ↳ Follow-up' : `Q${q.number}`} [${fmtScore(q.score)} · ${q.classification}] ${q.question}`,
      `   Answer: ${q.answer || '(skipped)'}`,
      `   Improve: ${q.improvement}`,
    ]),
    '',
    ...r.disclaimers,
  ]
  return lines.join('\n')
}

function download(name: string, content: string, type: string) {
  const blob = new Blob([content], { type })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = name
  document.body.appendChild(a)
  a.click()
  a.remove()
  setTimeout(() => URL.revokeObjectURL(url), 1000)
}

function QuestionReview({ q }: { q: ReportQuestion }) {
  const [open, setOpen] = useState(false)
  return (
    <li
      className={cn(
        'print-break',
        q.is_follow_up && 'ml-4 border-l-2 border-indigo-100 pl-3 sm:ml-6 dark:border-indigo-500/20',
      )}
    >
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        aria-expanded={open}
        className="flex w-full items-start gap-3 rounded-md px-2 py-3 text-left hover:bg-zinc-50 dark:hover:bg-zinc-800/50"
      >
        <span className="mt-0.5 w-12 shrink-0 text-xs font-medium text-zinc-500">
          {q.is_follow_up ? '↳ F/U' : `Q${q.number}`}
        </span>
        <span className="min-w-0 flex-1">
          <span className="block text-sm font-medium">{q.question}</span>
          <span className="mt-1 flex flex-wrap gap-1.5">
            <Badge>{categoryLabel(q.category)}</Badge>
            <Badge tone={classTone[q.classification] ?? 'neutral'}>{q.classification}</Badge>
            {q.skill && <Badge tone="indigo">{q.skill}</Badge>}
            {q.claim_confidence && (
              <Badge tone={confTone[q.claim_confidence]}>Claim confidence: {q.claim_confidence}</Badge>
            )}
          </span>
        </span>
        <span className="w-10 shrink-0 text-right text-sm font-semibold tabular-nums">
          {fmtScore(q.score)}
        </span>
        <ChevronDown
          className={cn('mt-0.5 size-4 shrink-0 text-zinc-400 transition-transform', open && 'rotate-180')}
          aria-hidden
        />
      </button>
      {open && (
        <div className="mb-3 space-y-3 px-2 pb-2 text-sm sm:pl-17">
          <div>
            <h4 className="text-xs font-medium text-zinc-500 uppercase">Your answer</h4>
            <p className="mt-1 whitespace-pre-wrap text-zinc-700 dark:text-zinc-300">
              {q.answer || '(skipped)'}
            </p>
          </div>
          <div className="grid gap-3 sm:grid-cols-2">
            <div>
              <h4 className="text-xs font-medium text-emerald-700 uppercase dark:text-emerald-400">
                What was good
              </h4>
              {q.strengths.length ? (
                <ul className="mt-1 list-disc space-y-0.5 pl-4">
                  {q.strengths.map((s) => (
                    <li key={s}>{s}</li>
                  ))}
                </ul>
              ) : (
                <p className="mt-1 text-zinc-500">—</p>
              )}
            </div>
            <div>
              <h4 className="text-xs font-medium text-rose-700 uppercase dark:text-rose-400">
                What was missing
              </h4>
              {q.missing.length || q.weaknesses.length ? (
                <ul className="mt-1 list-disc space-y-0.5 pl-4">
                  {q.weaknesses.map((s) => (
                    <li key={s}>{s}</li>
                  ))}
                  {q.missing.length > 0 && !q.weaknesses.some((w) => w.startsWith('Did not address')) && (
                    <li>Not covered: {q.missing.join(', ')}</li>
                  )}
                </ul>
              ) : (
                <p className="mt-1 text-zinc-500">Nothing major.</p>
              )}
            </div>
          </div>
          <div>
            <h4 className="text-xs font-medium text-zinc-500 uppercase">How to improve</h4>
            <p className="mt-1">{q.improvement}</p>
          </div>
          {q.ideal_answer && (
            <div className="rounded-md border border-zinc-200 bg-zinc-50 p-3 dark:border-zinc-800 dark:bg-zinc-800/40">
              <h4 className="text-xs font-medium text-zinc-500 uppercase">Ideal answer structure</h4>
              <p className="mt-1">{q.ideal_answer}</p>
            </div>
          )}
          <div className="grid grid-cols-2 gap-x-6 gap-y-1.5 sm:grid-cols-4">
            {Object.entries(q.dimensions).map(([k, v]) => (
              <div key={k} className="text-xs">
                <span className="text-zinc-500">{k.replace(/_/g, ' ')}</span>{' '}
                <span className="font-medium">{v}/10</span>
              </div>
            ))}
          </div>
        </div>
      )}
    </li>
  )
}

export default function ReportPage() {
  const { id = '' } = useParams()
  const navigate = useNavigate()
  const { data: r, error, loading } = useAsync(() => api.report(id), [id])
  const [copied, setCopied] = useState(false)

  if (loading) return <PageSkeleton />
  if (error || !r)
    return (
      <div className="mx-auto max-w-lg py-8">
        <Alert tone="error" title="Report unavailable">
          {error}
        </Alert>
        <Link to={`/interview/${id}`} className="mt-4 inline-block text-sm text-indigo-600 hover:underline">
          Back to interview
        </Link>
      </div>
    )

  const s = r.scores
  const copy = async () => {
    try {
      await navigator.clipboard.writeText(reportToText(r))
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    } catch {
      download(`interviewforge-report-${id.slice(0, 8)}.txt`, reportToText(r), 'text/plain')
    }
  }

  return (
    <div className="space-y-6" data-testid="report">
      <div className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
        <div>
          <p className="text-sm text-zinc-500">
            {fmtDateTime(r.generated_at)} · {fmtDuration(r.duration_seconds)} ·{' '}
            {r.ai_mode === 'llm'
              ? `Evaluated with local model ${r.model ?? ''}`
              : 'Evaluated by the offline rule-based engine'}
          </p>
          <h1 className="mt-1 text-2xl font-semibold tracking-tight">
            Interview report{r.candidate_name ? ` · ${r.candidate_name}` : ''}
          </h1>
          <p className="mt-1 text-sm text-zinc-500">
            {r.config.experience_level} {r.config.target_role} · {r.config.interview_type} ·{' '}
            {r.config.difficulty} · {r.config.personality} interviewer
          </p>
        </div>
        <div className="no-print flex flex-wrap gap-2">
          <Button variant="secondary" size="sm" onClick={() => window.print()}>
            <Printer className="size-4" /> Print
          </Button>
          <a
            href={api.reportPdfUrl(id)}
            className="inline-flex h-8 items-center gap-2 rounded-md border border-zinc-300 bg-white px-3 text-sm font-medium shadow-sm hover:bg-zinc-50 dark:border-zinc-700 dark:bg-zinc-900 dark:hover:bg-zinc-800"
            download
          >
            <Download className="size-4" /> PDF
          </a>
          <Button
            variant="secondary"
            size="sm"
            onClick={() =>
              download(
                `interviewforge-report-${id.slice(0, 8)}.json`,
                JSON.stringify(r, null, 2),
                'application/json',
              )
            }
          >
            <FileJson className="size-4" /> JSON
          </Button>
          <a
            href={api.transcriptUrl(id)}
            className="inline-flex h-8 items-center gap-2 rounded-md border border-zinc-300 bg-white px-3 text-sm font-medium shadow-sm hover:bg-zinc-50 dark:border-zinc-700 dark:bg-zinc-900 dark:hover:bg-zinc-800"
            download
          >
            <FileText className="size-4" /> Transcript
          </a>
          <Button variant="secondary" size="sm" onClick={copy} aria-live="polite">
            <ClipboardCopy className="size-4" /> {copied ? 'Copied' : 'Copy'}
          </Button>
          <Button size="sm" onClick={() => navigate('/interview/setup')}>
            <RotateCcw className="size-4" /> New interview
          </Button>
        </div>
      </div>

      {/* 1. Executive summary & 11. verdict */}
      <Card>
        <div className="grid gap-6 p-5 lg:grid-cols-[1fr_1fr]">
          <div>
            <h2 className="text-xs font-medium tracking-wide text-zinc-500 uppercase">Executive summary</h2>
            <p className="mt-2 text-base leading-relaxed" data-testid="executive-summary">
              {r.executive_summary}
            </p>
          </div>
          <div className="lg:border-l lg:border-zinc-100 lg:pl-6 dark:lg:border-zinc-800">
            <h2 className="text-xs font-medium tracking-wide text-zinc-500 uppercase">Interviewer verdict</h2>
            <p className="mt-2 text-base leading-relaxed" data-testid="verdict">
              {r.verdict}
            </p>
          </div>
        </div>
      </Card>

      {/* 2. Overall scores */}
      <Card>
        <CardHeader title="Overall scores" subtitle={r.readiness_formula.note} />
        <div className="grid grid-cols-2 gap-6 p-5 md:grid-cols-4">
          <div data-testid="score-ats">
            <ScoreRing score={s.ats} label="ATS-style score" sublabel={s.ats_classification} />
          </div>
          <div data-testid="score-jd">
            <ScoreRing
              score={s.jd_match}
              label="JD match"
              sublabel={s.jd_match === null ? 'No job description' : undefined}
            />
          </div>
          <div data-testid="score-interview">
            <ScoreRing
              score={s.interview}
              label="Interview score"
              sublabel={s.interview_classification ?? undefined}
            />
          </div>
          <div data-testid="score-readiness">
            <ScoreRing
              score={s.readiness}
              label="Readiness"
              sublabel={s.readiness_classification ?? undefined}
            />
          </div>
        </div>
        <div className="border-t border-zinc-100 px-5 py-3 text-xs text-zinc-500 dark:border-zinc-800">
          <span className="font-medium text-zinc-700 dark:text-zinc-300">{r.readiness_formula.label}</span> ={' '}
          {r.readiness_formula.components
            .filter((c) => c.weight > 0)
            .map((c) => `${Math.round(c.weight * 100)}% ${c.label} (${fmtScore(c.score)})`)
            .join(' + ')}
          . Not a probability of being hired.
        </div>
      </Card>

      <div className="grid gap-6 lg:grid-cols-2">
        <Card>
          <CardHeader
            title="Interview score breakdown"
            subtitle="Weighted categories; weights are configurable."
          />
          <div className="space-y-3.5 p-5" data-testid="category-scores">
            {r.category_scores.map((c) => (
              <ScoreBar key={c.key} label={c.label} score={c.score} weight={c.weight} />
            ))}
          </div>
        </Card>
        <Card>
          <CardHeader title="Answer quality by dimension" subtitle="Average of per-answer scores (0–10)." />
          <div className="p-5">
            <RadarChart
              items={r.dimension_averages.map((d) => ({
                label: d.label
                  .replace('Confidence indicators', 'Confidence')
                  .replace('Technical correctness', 'Correctness'),
                score: d.score,
              }))}
            />
            <dl className="mt-4 grid grid-cols-2 gap-x-6 gap-y-1 text-xs">
              {r.dimension_averages.map((d) => (
                <div key={d.key} className="flex justify-between">
                  <dt className="text-zinc-500">{d.label}</dt>
                  <dd className="font-medium">{d.score?.toFixed(1) ?? '—'}</dd>
                </div>
              ))}
            </dl>
          </div>
        </Card>
      </div>

      {/* 3. Skill evaluation */}
      <Card>
        <CardHeader title="Skill evaluation" />
        {r.skills.length ? (
          <div className="relative overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="text-left text-xs text-zinc-500">
                <tr className="border-b border-zinc-100 dark:border-zinc-800">
                  <th className="px-5 py-2 font-medium">Skill</th>
                  <th className="px-3 py-2 font-medium">Score</th>
                  <th className="px-3 py-2 font-medium">Evidence</th>
                  <th className="px-5 py-2 font-medium">Recommendation</th>
                </tr>
              </thead>
              <tbody>
                {r.skills.map((sk) => (
                  <tr
                    key={sk.skill}
                    className="border-b border-zinc-50 align-top last:border-0 dark:border-zinc-800/60"
                  >
                    <td className="px-5 py-3 font-medium">{sk.skill}</td>
                    <td className="w-36 px-3 py-3">
                      <ScoreBar label="" score={sk.score} />
                    </td>
                    <td className="px-3 py-3 text-zinc-600 dark:text-zinc-400">{sk.evidence}</td>
                    <td className="px-5 py-3 text-zinc-600 dark:text-zinc-400">{sk.recommendation}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <p className="p-5 text-sm text-zinc-500">
            No skill-specific questions were answered in this interview.
          </p>
        )}
      </Card>

      {/* 4. Question by question */}
      <Card>
        <CardHeader
          title="Question-by-question review"
          subtitle={`${r.stats.questions_answered} answered · ${r.stats.questions_skipped} skipped · ${r.stats.follow_ups} follow-ups`}
        />
        <div className="px-5 pt-6 pb-2">
          <QuestionTimeline items={r.timeline} />
        </div>
        <ul className="divide-y divide-zinc-100 px-3 pb-3 dark:divide-zinc-800" data-testid="question-review">
          {r.questions.map((q) => (
            <QuestionReview key={q.id} q={q} />
          ))}
        </ul>
        {r.unanswered_questions.length > 0 && (
          <p className="border-t border-zinc-100 px-5 py-3 text-xs text-zinc-500 dark:border-zinc-800">
            {r.unanswered_questions.length} question(s) were not reached before the interview ended.
          </p>
        )}
      </Card>

      {/* 5 & 6 */}
      <div className="grid gap-6 lg:grid-cols-2">
        <Card>
          <CardHeader
            title={
              <span className="inline-flex items-center gap-2">
                <TrendingUp className="size-4 text-emerald-500" />
                Strongest areas
              </span>
            }
          />
          <ul className="space-y-3 p-5 text-sm">
            {r.strongest_areas.length ? (
              r.strongest_areas.map((a) => (
                <li key={a.area}>
                  <div className="flex justify-between font-medium">
                    <span>{a.area}</span>
                    <span>{fmtScore(a.score)}</span>
                  </div>
                  <p className="text-zinc-500">{a.detail}</p>
                </li>
              ))
            ) : (
              <li className="text-zinc-500">No area scored 65 or above yet — keep practising.</li>
            )}
          </ul>
        </Card>
        <Card>
          <CardHeader
            title={
              <span className="inline-flex items-center gap-2">
                <TrendingDown className="size-4 text-rose-500" />
                Weakest areas
              </span>
            }
          />
          <ul className="space-y-3 p-5 text-sm">
            {r.weakest_areas.length ? (
              r.weakest_areas.map((a) => (
                <li key={a.area}>
                  <div className="flex justify-between font-medium">
                    <span>{a.area}</span>
                    <span>{fmtScore(a.score)}</span>
                  </div>
                  <p className="text-zinc-500">{a.detail}</p>
                </li>
              ))
            ) : (
              <li className="text-zinc-500">No area scored below 60.</li>
            )}
          </ul>
        </Card>
      </div>

      {/* 7. Claims */}
      <Card>
        <CardHeader
          title={
            <span className="inline-flex items-center gap-2">
              <ShieldCheck className="size-4 text-zinc-400" />
              Resume claims verification
            </span>
          }
          subtitle="Claims the interviewer probed, and how well they were substantiated."
        />
        {r.claims.length ? (
          <ul className="divide-y divide-zinc-100 dark:divide-zinc-800" data-testid="claims">
            {r.claims.map((c) => (
              <li key={c.claim} className="flex flex-col gap-2 px-5 py-3 text-sm sm:flex-row sm:items-start">
                <Badge tone={confTone[c.confidence]} className="shrink-0">
                  {c.confidence} confidence
                </Badge>
                <div>
                  <p className="font-medium">“{c.claim}”</p>
                  <p className="text-zinc-500">{c.note}</p>
                </div>
              </li>
            ))}
          </ul>
        ) : (
          <p className="p-5 text-sm text-zinc-500">
            No specific resume claims were probed in this interview.
          </p>
        )}
      </Card>

      {/* 8, 9 */}
      <div className="grid gap-6 lg:grid-cols-2">
        <Card>
          <CardHeader title="Communication feedback" subtitle="Based only on answer content and structure." />
          <p className="p-5 text-sm leading-relaxed">{r.communication_feedback}</p>
        </Card>
        <Card>
          <CardHeader
            title={
              <span className="inline-flex items-center gap-2">
                <AlertTriangle className="size-4 text-amber-500" />
                Technical gaps
              </span>
            }
          />
          {r.technical_gaps.length ? (
            <ul className="list-disc space-y-1 p-5 pl-9 text-sm">
              {r.technical_gaps.map((g) => (
                <li key={g}>{g}</li>
              ))}
            </ul>
          ) : (
            <p className="p-5 text-sm text-zinc-500">No significant technical gaps detected.</p>
          )}
        </Card>
      </div>

      {/* 10. Study topics + action plan */}
      <div className="grid gap-6 lg:grid-cols-2">
        <Card>
          <CardHeader
            title={
              <span className="inline-flex items-center gap-2">
                <BookOpen className="size-4 text-zinc-400" />
                Recommended study topics
              </span>
            }
          />
          {r.study_topics.length ? (
            <ul className="divide-y divide-zinc-100 dark:divide-zinc-800" data-testid="study-topics">
              {r.study_topics.map((t) => (
                <li key={t.topic} className="flex items-start gap-3 px-5 py-2.5 text-sm">
                  <Badge tone={t.priority === 'High' ? 'red' : 'amber'} className="mt-0.5 shrink-0">
                    {t.priority}
                  </Badge>
                  <div>
                    <p className="font-medium">{t.topic}</p>
                    <p className="text-zinc-500">{t.reason}</p>
                  </div>
                </li>
              ))}
            </ul>
          ) : (
            <p className="p-5 text-sm text-zinc-500">Nothing urgent — try a harder difficulty next time.</p>
          )}
        </Card>
        <Card>
          <CardHeader title="Action plan" />
          <ol className="space-y-2.5 p-5 text-sm" data-testid="action-plan">
            {r.action_plan.map((a, i) => (
              <li key={a} className="flex gap-3">
                <span className="flex size-5 shrink-0 items-center justify-center rounded-full bg-indigo-50 text-xs font-medium text-indigo-700 dark:bg-indigo-500/10 dark:text-indigo-300">
                  {i + 1}
                </span>
                <span>{a}</span>
              </li>
            ))}
          </ol>
        </Card>
      </div>

      {(r.jd || r.ats.recommendations.length > 0) && (
        <Card>
          <CardHeader title="Resume & job match" subtitle={r.jd?.summary} />
          <div className="grid gap-6 p-5 md:grid-cols-2 text-sm">
            <div>
              <h3 className="mb-2 text-xs font-medium text-zinc-500 uppercase">Top resume improvements</h3>
              <ul className="list-disc space-y-1 pl-4">
                {r.ats.recommendations.map((x) => (
                  <li key={x}>{x}</li>
                ))}
              </ul>
            </div>
            {r.jd && (
              <div>
                <h3 className="mb-2 text-xs font-medium text-zinc-500 uppercase">
                  Job requirements missing from your resume
                </h3>
                <div className="flex flex-wrap gap-1.5">
                  {r.jd.missing.length ? (
                    r.jd.missing.map((m) => (
                      <Badge key={m} tone="red">
                        {m}
                      </Badge>
                    ))
                  ) : (
                    <span className="text-zinc-500">None</span>
                  )}
                </div>
              </div>
            )}
          </div>
        </Card>
      )}

      <div className="space-y-1 text-xs text-zinc-500">
        {r.disclaimers.map((d) => (
          <p key={d}>{d}</p>
        ))}
      </div>
    </div>
  )
}
