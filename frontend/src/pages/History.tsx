import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { History as HistoryIcon, Trash2 } from 'lucide-react'
import { api, errorMessage } from '../lib/api'
import { fmtDateTime, fmtDuration, fmtScore, phaseLabel } from '../lib/format'
import { useAsync } from '../hooks/useAsync'
import { Alert, Badge, Button, Card, EmptyState, PageHeader, PageSkeleton } from '../components/ui'

export default function HistoryPage() {
  const navigate = useNavigate()
  const { data, error, loading, reload } = useAsync(() => api.history(), [])
  const [actionError, setActionError] = useState<string | null>(null)

  if (loading) return <PageSkeleton />
  if (error) return <Alert tone="error">{error}</Alert>

  const remove = async (id: string) => {
    if (!window.confirm('Delete this interview and its report?')) return
    try {
      await api.deleteInterview(id)
      reload()
    } catch (e) {
      setActionError(errorMessage(e))
    }
  }

  return (
    <div className="space-y-6">
      <PageHeader
        title="Interview history"
        description="Every interview is stored locally in SQLite on this device."
        actions={<Button onClick={() => navigate('/interview/setup')}>New interview</Button>}
      />
      {actionError && <Alert tone="error">{actionError}</Alert>}
      {!data?.length ? (
        <Card>
          <EmptyState
            icon={<HistoryIcon className="size-5" />}
            title="No interviews yet"
            action={<Button onClick={() => navigate('/interview/setup')}>Start your first interview</Button>}
          >
            Completed interviews and their reports will appear here.
          </EmptyState>
        </Card>
      ) : (
        <Card className="overflow-hidden">
          <div className="relative overflow-x-auto">
            <table className="w-full text-sm" data-testid="history-table">
              <caption className="sr-only">Past interviews</caption>
              <thead className="bg-zinc-50 text-left text-xs text-zinc-500 dark:bg-zinc-900">
                <tr>
                  <th className="px-5 py-2.5 font-medium">Date</th>
                  <th className="px-3 py-2.5 font-medium">Role</th>
                  <th className="px-3 py-2.5 font-medium">Type</th>
                  <th className="px-3 py-2.5 text-right font-medium">Interview</th>
                  <th className="px-3 py-2.5 text-right font-medium">ATS</th>
                  <th className="px-3 py-2.5 text-right font-medium">JD</th>
                  <th className="px-3 py-2.5 text-right font-medium">Readiness</th>
                  <th className="px-3 py-2.5 font-medium">Duration</th>
                  <th className="px-5 py-2.5">
                    <span className="sr-only">Actions</span>
                  </th>
                </tr>
              </thead>
              <tbody className="divide-y divide-zinc-100 dark:divide-zinc-800">
                {data.map((h) => {
                  const done = h.state === 'COMPLETED'
                  return (
                    <tr key={h.id} className="hover:bg-zinc-50 dark:hover:bg-zinc-800/40">
                      <td className="px-5 py-3 whitespace-nowrap">{fmtDateTime(h.created_at)}</td>
                      <td className="px-3 py-3">
                        <div className="font-medium">{h.target_role}</div>
                        <div className="text-xs text-zinc-500">
                          {h.experience_level} · {h.difficulty}
                        </div>
                      </td>
                      <td className="px-3 py-3 whitespace-nowrap">{h.interview_type}</td>
                      <td className="px-3 py-3 text-right font-semibold tabular-nums">
                        {fmtScore(h.interview_score)}
                      </td>
                      <td className="px-3 py-3 text-right tabular-nums">{fmtScore(h.ats_score)}</td>
                      <td className="px-3 py-3 text-right tabular-nums">{fmtScore(h.jd_score)}</td>
                      <td className="px-3 py-3 text-right tabular-nums">{fmtScore(h.readiness_score)}</td>
                      <td className="px-3 py-3 whitespace-nowrap">{fmtDuration(h.duration_seconds)}</td>
                      <td className="px-5 py-3">
                        <div className="flex items-center justify-end gap-2">
                          {done ? (
                            <Link
                              to={`/interview/${h.id}/report`}
                              className="text-sm font-medium text-indigo-600 hover:underline dark:text-indigo-400"
                            >
                              Report
                            </Link>
                          ) : h.state === 'FAILED' || h.state === 'CREATED' ? (
                            <Badge tone="amber">{phaseLabel(h.state)}</Badge>
                          ) : (
                            <Link
                              to={`/interview/${h.id}`}
                              className="text-sm font-medium text-indigo-600 hover:underline dark:text-indigo-400"
                            >
                              Resume
                            </Link>
                          )}
                          <button
                            type="button"
                            onClick={() => remove(h.id)}
                            className="rounded p-1 text-zinc-400 hover:bg-zinc-100 hover:text-rose-600 dark:hover:bg-zinc-800"
                            aria-label={`Delete interview from ${fmtDateTime(h.created_at)}`}
                          >
                            <Trash2 className="size-4" />
                          </button>
                        </div>
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        </Card>
      )}
    </div>
  )
}
