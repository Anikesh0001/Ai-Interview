import { useState } from 'react'
import { CheckCircle2, Database, Download, RefreshCw, Trash2, XCircle } from 'lucide-react'
import { api, errorMessage } from '../lib/api'
import { clearAll } from '../lib/storage'
import { useAsync } from '../hooks/useAsync'
import { useHealth } from '../components/HealthContext'
import { Alert, Badge, Button, Card, CardHeader, Field, PageHeader, PageSkeleton } from '../components/ui'
import { inputCls } from '../lib/cn'

const GROUP_LABELS: Record<string, string> = {
  ats: 'ATS-style score',
  answer: 'Answer score (technical)',
  behavioral_answer: 'Answer score (behavioral/HR)',
  interview: 'Interview score',
  readiness: 'Readiness score',
}

function Check({ ok, label, detail }: { ok: boolean | null; label: string; detail?: string }) {
  return (
    <li className="flex items-start gap-3 py-2.5 text-sm">
      {ok === null ? (
        <RefreshCw className="mt-0.5 size-4 text-zinc-400" />
      ) : ok ? (
        <CheckCircle2 className="mt-0.5 size-4 text-emerald-500" />
      ) : (
        <XCircle className="mt-0.5 size-4 text-amber-500" />
      )}
      <div>
        <p className="font-medium">{label}</p>
        {detail && <p className="text-zinc-500">{detail}</p>}
      </div>
    </li>
  )
}

export default function SettingsPage() {
  const { data, error, loading, setData } = useAsync(() => api.settings(), [])
  const { health, reload: reloadHealth } = useHealth()
  const [modelInput, setModel] = useState<string | null>(null)
  const [urlInput, setUrl] = useState<string | null>(null)
  const [saving, setSaving] = useState(false)
  const [msg, setMsg] = useState<{ tone: 'success' | 'error'; text: string } | null>(null)
  const [deleting, setDeleting] = useState(false)

  if (loading) return <PageSkeleton />
  if (error || !data) return <Alert tone="error">{error}</Alert>
  const model = modelInput ?? data.ollama_model
  const url = urlInput ?? data.ollama_base_url

  const saveLlm = async () => {
    setSaving(true)
    setMsg(null)
    try {
      const next = await api.updateSettings({ ollama_model: model.trim(), ollama_base_url: url.trim() })
      setData(next)
      reloadHealth()
      setMsg({
        tone: 'success',
        text: next.llm_status.available ? `Connected to ${next.ollama_model}.` : next.llm_status.detail,
      })
    } catch (e) {
      setMsg({ tone: 'error', text: errorMessage(e) })
    } finally {
      setSaving(false)
    }
  }

  const deleteAll = async () => {
    if (
      !window.confirm(
        'Permanently delete ALL resumes, job descriptions, interviews and reports stored on this device?',
      )
    )
      return
    setDeleting(true)
    try {
      await api.deleteAll()
      clearAll()
      setMsg({ tone: 'success', text: 'All local data was deleted.' })
    } catch (e) {
      setMsg({ tone: 'error', text: errorMessage(e) })
    } finally {
      setDeleting(false)
    }
  }

  const st = data.llm_status
  return (
    <div className="space-y-6">
      <PageHeader
        title="Settings"
        description="Everything runs locally. No API keys, no accounts, no tracking."
      />
      {msg && <Alert tone={msg.tone}>{msg.text}</Alert>}

      <div className="grid gap-6 lg:grid-cols-2">
        <Card>
          <CardHeader
            title="System status"
            action={
              <Button size="sm" variant="ghost" onClick={reloadHealth}>
                <RefreshCw className="size-4" /> Recheck
              </Button>
            }
          />
          <ul className="divide-y divide-zinc-100 px-5 dark:divide-zinc-800" data-testid="system-status">
            <Check
              ok={health ? health.application === 'ok' : null}
              label="Application"
              detail={health ? `Version ${health.version}` : undefined}
            />
            <Check
              ok={health ? health.database === 'ok' : null}
              label="Database"
              detail="SQLite file on this device"
            />
            <Check
              ok={health ? health.resume_parser === 'ok' : null}
              label="Resume parser"
              detail="PyMuPDF + python-docx (local)"
            />
            <Check
              ok={health ? health.llm === 'ok' : null}
              label="Local AI model (Ollama)"
              detail={health?.llm_detail}
            />
          </ul>
          {data.test_mode && (
            <p className="border-t border-zinc-100 px-5 py-3 text-xs text-zinc-500 dark:border-zinc-800">
              TEST_MODE is on: the deterministic engine is used for automated testing.
            </p>
          )}
        </Card>

        <Card>
          <CardHeader
            title="Local AI model"
            subtitle="Ollama runs open models on your own hardware for free."
          />
          <div className="space-y-4 p-5">
            <Field
              label="Model"
              htmlFor="model"
              hint={
                st.installed_models.length
                  ? `Installed: ${st.installed_models.join(', ')}`
                  : 'Recommended: qwen2.5:3b (fast) or qwen2.5:7b / llama3.1:8b (better quality)'
              }
            >
              <input
                id="model"
                className={inputCls}
                value={model}
                onChange={(e) => setModel(e.target.value)}
                disabled={data.test_mode}
              />
            </Field>
            <Field label="Ollama URL" htmlFor="url">
              <input
                id="url"
                className={inputCls}
                value={url}
                onChange={(e) => setUrl(e.target.value)}
                disabled={data.test_mode}
              />
            </Field>
            <div className="flex items-center gap-3">
              <Button onClick={saveLlm} loading={saving} disabled={data.test_mode}>
                Save & test connection
              </Button>
              <Badge tone={st.available ? 'green' : 'amber'}>
                {st.available ? 'Connected' : st.server === 'disabled' ? 'Disabled' : 'Not connected'}
              </Badge>
            </div>
            <div className="rounded-md bg-zinc-50 p-3 text-xs leading-relaxed text-zinc-600 dark:bg-zinc-800/50 dark:text-zinc-400">
              <p className="font-medium text-zinc-800 dark:text-zinc-200">Setup</p>
              <ol className="mt-1 list-decimal space-y-0.5 pl-4">
                <li>Install Ollama from ollama.com (free).</li>
                <li>
                  Run <code className="font-mono">ollama pull {model || 'qwen2.5:3b'}</code>
                </li>
                <li>
                  Keep <code className="font-mono">ollama serve</code> running, then press Save &amp; test.
                </li>
              </ol>
              <p className="mt-2">
                Without a model, resume analysis works fully and interviews use the offline engine.
              </p>
            </div>
          </div>
        </Card>
      </div>

      <Card>
        <CardHeader
          title="Scoring weights"
          subtitle="Transparent and configurable via *_WEIGHTS environment variables (see README). Scores are computed by the backend, never invented by the AI."
        />
        <div className="grid gap-6 p-5 sm:grid-cols-2 lg:grid-cols-3">
          {Object.entries(data.weights).map(([group, weights]) => (
            <div key={group}>
              <h3 className="mb-2 text-sm font-semibold">{GROUP_LABELS[group] ?? group}</h3>
              <dl className="space-y-1 text-xs">
                {Object.entries(weights).map(([k, v]) => (
                  <div key={k} className="flex justify-between gap-3">
                    <dt className="text-zinc-500">{k.replace(/_/g, ' ')}</dt>
                    <dd className="font-medium tabular-nums">{Math.round(v * 100)}%</dd>
                  </div>
                ))}
              </dl>
            </div>
          ))}
        </div>
      </Card>

      <Card>
        <CardHeader
          title={
            <span className="inline-flex items-center gap-2">
              <Database className="size-4 text-zinc-400" />
              Privacy & local data
            </span>
          }
        />
        <div className="space-y-4 p-5 text-sm">
          <p>
            Your resume, transcript and interview history are stored locally on this device. Nothing is sent
            to external services, and there is no analytics or tracking.
          </p>
          <div className="flex flex-wrap gap-2">
            <a
              href={api.exportUrl()}
              download
              className="inline-flex h-10 items-center gap-2 rounded-md border border-zinc-300 bg-white px-4 text-sm font-medium shadow-sm hover:bg-zinc-50 dark:border-zinc-700 dark:bg-zinc-900 dark:hover:bg-zinc-800"
            >
              <Download className="size-4" /> Export history (JSON)
            </a>
            <Button variant="danger" onClick={deleteAll} loading={deleting}>
              <Trash2 className="size-4" /> Delete all local data
            </Button>
          </div>
        </div>
      </Card>
    </div>
  )
}
