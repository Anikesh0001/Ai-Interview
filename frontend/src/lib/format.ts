export function scoreTone(score: number | null | undefined): 'good' | 'ok' | 'warn' | 'bad' | 'none' {
  if (score === null || score === undefined || Number.isNaN(score)) return 'none'
  if (score >= 80) return 'good'
  if (score >= 70) return 'ok'
  if (score >= 60) return 'warn'
  return 'bad'
}

export const toneText: Record<ReturnType<typeof scoreTone>, string> = {
  good: 'text-emerald-600 dark:text-emerald-400',
  ok: 'text-sky-600 dark:text-sky-400',
  warn: 'text-amber-600 dark:text-amber-400',
  bad: 'text-rose-600 dark:text-rose-400',
  none: 'text-zinc-400',
}
export const toneBg: Record<ReturnType<typeof scoreTone>, string> = {
  good: 'bg-emerald-500',
  ok: 'bg-sky-500',
  warn: 'bg-amber-500',
  bad: 'bg-rose-500',
  none: 'bg-zinc-300 dark:bg-zinc-700',
}
export const toneStroke: Record<ReturnType<typeof scoreTone>, string> = {
  good: 'stroke-emerald-500',
  ok: 'stroke-sky-500',
  warn: 'stroke-amber-500',
  bad: 'stroke-rose-500',
  none: 'stroke-zinc-300 dark:stroke-zinc-700',
}

export function classify(score: number | null | undefined): string {
  if (score === null || score === undefined) return 'Not scored'
  if (score >= 90) return 'Excellent'
  if (score >= 80) return 'Strong'
  if (score >= 70) return 'Good'
  if (score >= 60) return 'Needs Improvement'
  return 'Weak'
}

export function fmtScore(score: number | null | undefined): string {
  return score === null || score === undefined ? '—' : String(Math.round(score))
}

export function fmtDate(iso: string | null | undefined): string {
  if (!iso) return '—'
  const d = new Date(iso)
  return d.toLocaleDateString(undefined, { month: 'short', day: 'numeric', year: 'numeric' })
}

export function fmtDateTime(iso: string | null | undefined): string {
  if (!iso) return '—'
  const d = new Date(iso)
  return d.toLocaleString(undefined, { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' })
}

export function fmtDuration(seconds: number | null | undefined): string {
  if (seconds === null || seconds === undefined) return '—'
  const m = Math.floor(seconds / 60)
  const s = seconds % 60
  if (m >= 60) return `${Math.floor(m / 60)}h ${m % 60}m`
  return m ? `${m}m ${String(s).padStart(2, '0')}s` : `${s}s`
}

export function fmtClock(seconds: number): string {
  const m = Math.floor(seconds / 60)
  const s = Math.floor(seconds % 60)
  return `${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}`
}

export function fmtBytes(n: number): string {
  if (n < 1024) return `${n} B`
  if (n < 1024 * 1024) return `${(n / 1024).toFixed(0)} KB`
  return `${(n / 1024 / 1024).toFixed(1)} MB`
}

export const categoryLabel = (c: string): string =>
  ({
    intro: 'Introduction',
    resume: 'Resume',
    claim_verification: 'Resume claim',
    project: 'Project deep dive',
    technical: 'Technical',
    skills: 'Skills',
    coding: 'Coding',
    system_design: 'System design',
    problem_solving: 'Problem solving',
    situational: 'Situational',
    behavioral: 'Behavioral',
    hr: 'HR',
    jd_specific: 'Job requirement',
    role_specific: 'Role-specific',
  })[c] ?? c.replace(/_/g, ' ')

export const phaseLabel = (p: string | null | undefined): string =>
  ({
    INTRO: 'Introduction',
    RESUME: 'Resume walkthrough',
    PROJECT: 'Project deep dive',
    TECHNICAL: 'Technical',
    PROBLEM_SOLVING: 'Problem solving',
    BEHAVIORAL: 'Behavioral',
    CHALLENGE: 'Follow-up',
    CLOSING: 'Closing',
    EVALUATING: 'Evaluating',
    COMPLETED: 'Completed',
    FAILED: 'Failed',
    CREATED: 'Ready',
    PREPARING: 'Preparing',
  })[p ?? ''] ??
  p ??
  ''
