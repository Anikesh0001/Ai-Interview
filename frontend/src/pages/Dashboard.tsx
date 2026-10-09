import { Link, useNavigate } from 'react-router-dom'
import { ArrowRight, FileText, History, Mic, PlayCircle, Sparkles, Target } from 'lucide-react'
import { api } from '../lib/api'
import { fmtDate, fmtScore } from '../lib/format'
import { useAsync } from '../hooks/useAsync'
import { Alert, Button, Card, CardHeader, EmptyState, PageHeader, PageSkeleton } from '../components/ui'
import { ScoreBar, TrendChart } from '../components/charts'
import { useHealth } from '../components/HealthContext'

function Stat({
  label,
  value,
  hint,
  testId,
}: {
  label: string
  value: string
  hint?: string
  testId?: string
}) {
  return (
    <Card className="p-4">
      <p className="text-sm text-zinc-500 dark:text-zinc-400">{label}</p>
      <p className="mt-1 text-3xl font-semibold tracking-tight" data-testid={testId}>
        {value}
      </p>
      {hint && <p className="mt-1 text-xs text-zinc-500">{hint}</p>}
    </Card>
  )
}

export default function DashboardPage() {
  const navigate = useNavigate()
  const { data: d, error, loading, reload } = useAsync(() => api.dashboard(), [])
  const { health } = useHealth()
  if (loading) return <PageSkeleton />
  if (error || !d)
    return (
      <Alert
        tone="error"
        title="Couldn't load the dashboard"
        action={
          <Button size="sm" variant="secondary" onClick={reload}>
            Retry
          </Button>
        }
      >
        {error}
      </Alert>
    )

  const quick = [
    { to: '/resume', label: 'Upload resume', icon: FileText },
    { to: '/resume', label: 'Analyze resume', icon: Target },
    { to: '/interview/setup', label: 'Start interview', icon: Mic },
    { to: '/history', label: 'View history', icon: History },
  ]

  return (
    <div className="space-y-6">
      <PageHeader
        title="Dashboard"
        description="Your local practice history and progress."
        actions={
          <Button onClick={() => navigate(d.has_resume ? '/interview/setup' : '/resume')}>
            <PlayCircle className="size-4" /> {d.has_resume ? 'Start interview' : 'Upload resume'}
          </Button>
        }
      />

      {d.active_interviews.length > 0 && (
        <Alert
          tone="info"
          title="Interview in progress"
          action={
            <Button
              size="sm"
              variant="secondary"
              onClick={() => navigate(`/interview/${d.active_interviews[0].id}`)}
            >
              Resume Interview
            </Button>
          }
        >
          Your {d.active_interviews[0].role} interview from {fmtDate(d.active_interviews[0].created_at)} was
          saved. Pick up where you left off.
        </Alert>
      )}
      {health && health.llm !== 'ok' && !health.test_mode && (
        <Alert
          tone="warning"
          title="AI model not connected"
          action={
            <Link to="/settings" className="text-sm font-medium underline">
              Setup
            </Link>
          }
        >
          The offline engine is active: resume analysis works fully, and interviews use curated
          resume-grounded questions with rule-based scoring.
        </Alert>
      )}

      <div className="grid grid-cols-2 gap-4 lg:grid-cols-5">
        <Stat
          label="ATS score"
          value={fmtScore(d.latest_ats)}
          hint={d.resume_health?.classification}
          testId="stat-ats"
        />
        <Stat
          label="Latest interview"
          value={fmtScore(d.latest_interview_score)}
          hint={d.best_score !== null ? `Best ${fmtScore(d.best_score)}` : undefined}
          testId="stat-interview"
        />
        <Stat
          label="JD match"
          value={fmtScore(d.latest_jd_match)}
          hint={d.latest_jd_match === null ? 'Add a job description' : undefined}
        />
        <Stat label="Readiness" value={fmtScore(d.latest_readiness)} hint="Practice metric" />
        <Stat
          label="Interviews completed"
          value={String(d.interviews_completed)}
          hint={
            d.improvement !== null
              ? `${d.improvement >= 0 ? '+' : ''}${d.improvement} since first`
              : undefined
          }
          testId="stat-completed"
        />
      </div>

      <div className="grid gap-6 lg:grid-cols-[minmax(0,2fr)_minmax(0,1fr)]">
        <Card>
          <CardHeader
            title="Progress"
            subtitle="Interview and readiness scores across completed interviews"
          />
          <div className="p-5">
            {d.trend.length ? (
              <TrendChart points={d.trend} />
            ) : (
              <EmptyState icon={<Sparkles className="size-5" />} title="No completed interviews yet">
                Finish a mock interview to start tracking your progress.
              </EmptyState>
            )}
          </div>
        </Card>
        <Card>
          <CardHeader title="Quick actions" />
          <div className="grid grid-cols-2 gap-2 p-4">
            {quick.map(({ to, label, icon: Icon }) => (
              <Link
                key={label}
                to={to}
                className="flex flex-col gap-2 rounded-md border border-zinc-200 p-3 text-sm font-medium hover:border-indigo-300 hover:bg-indigo-50/40 dark:border-zinc-800 dark:hover:border-indigo-500/40 dark:hover:bg-indigo-500/5"
              >
                <Icon className="size-4 text-indigo-600 dark:text-indigo-400" aria-hidden />
                {label}
              </Link>
            ))}
          </div>
        </Card>
      </div>

      <div className="grid gap-6 lg:grid-cols-3">
        <Card>
          <CardHeader
            title="Recent interviews"
            action={
              <Link to="/history" className="text-xs text-indigo-600 hover:underline dark:text-indigo-400">
                All
              </Link>
            }
          />
          {d.recent.length ? (
            <ul className="divide-y divide-zinc-100 dark:divide-zinc-800">
              {d.recent.map((r) => (
                <li key={r.id}>
                  <Link
                    to={`/interview/${r.id}/report`}
                    className="flex items-center justify-between gap-3 px-5 py-3 text-sm hover:bg-zinc-50 dark:hover:bg-zinc-800/50"
                  >
                    <span className="min-w-0">
                      <span className="block truncate font-medium">{r.role}</span>
                      <span className="text-xs text-zinc-500">
                        {r.type} · {fmtDate(r.date)}
                      </span>
                    </span>
                    <span className="text-base font-semibold">{fmtScore(r.score)}</span>
                  </Link>
                </li>
              ))}
            </ul>
          ) : (
            <p className="px-5 py-6 text-sm text-zinc-500">Nothing here yet.</p>
          )}
        </Card>
        <Card>
          <CardHeader title="Weak skills" subtitle="Lowest average interview scores" />
          <div className="space-y-3 p-5">
            {d.weak_skills.length ? (
              d.weak_skills.map((w) => (
                <ScoreBar
                  key={w.skill}
                  label={w.skill}
                  score={w.score}
                  detail={`${w.count} interview${w.count > 1 ? 's' : ''}`}
                />
              ))
            ) : (
              <p className="text-sm text-zinc-500">No weak skills recorded yet.</p>
            )}
          </div>
        </Card>
        <Card>
          <CardHeader
            title="Resume health"
            subtitle={d.resume_health?.filename}
            action={
              d.resume_health && (
                <Link to="/resume" className="text-xs text-indigo-600 hover:underline dark:text-indigo-400">
                  Details
                </Link>
              )
            }
          />
          {d.resume_health ? (
            <div className="space-y-3 p-5">
              {d.resume_health.dimensions.slice(0, 5).map((dm) => (
                <ScoreBar key={dm.label} label={dm.label} score={dm.score} />
              ))}
              {d.resume_health.top_recommendations[0] && (
                <p className="rounded-md bg-zinc-50 p-3 text-xs text-zinc-600 dark:bg-zinc-800/50 dark:text-zinc-400">
                  Tip: {d.resume_health.top_recommendations[0]}
                </p>
              )}
            </div>
          ) : (
            <EmptyState
              icon={<FileText className="size-5" />}
              title="No resume uploaded"
              action={
                <Link
                  to="/resume"
                  className="inline-flex items-center gap-1 text-sm font-medium text-indigo-600"
                >
                  Upload <ArrowRight className="size-3.5" />
                </Link>
              }
            />
          )}
        </Card>
      </div>
    </div>
  )
}
