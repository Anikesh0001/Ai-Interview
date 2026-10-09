import type {
  AnalysisOut,
  AppSettings,
  Dashboard,
  Health,
  HistoryItem,
  InterviewConfig,
  InterviewOut,
  InterviewReport,
  JDSample,
  ResumeOut,
  ResumeSummary,
} from './types'

/** Error whose message is always safe and human-readable. */
export class ApiError extends Error {
  status: number
  constructor(message: string, status: number) {
    super(message)
    this.status = status
  }
}

const BASE = '/api'

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  let res: Response
  try {
    res = await fetch(BASE + path, init)
  } catch {
    throw new ApiError(
      'Cannot reach the InterviewForge server. Make sure the backend is running (make dev) and try again.',
      0,
    )
  }
  if (res.status === 204) return undefined as T
  const isJson = res.headers.get('content-type')?.includes('application/json')
  const body = isJson ? await res.json().catch(() => null) : null
  if (!res.ok) {
    const detail = body && typeof body.detail === 'string' ? body.detail : null
    const fallback =
      res.status >= 500
        ? 'The server ran into a problem. Please try again.'
        : res.status === 404
          ? 'Not found.'
          : 'The request could not be completed.'
    throw new ApiError(detail ?? fallback, res.status)
  }
  return body as T
}

const json = (method: string, data?: unknown): RequestInit => ({
  method,
  headers: { 'Content-Type': 'application/json' },
  body: data === undefined ? undefined : JSON.stringify(data),
})

export const api = {
  health: () => request<Health>('/health'),
  dashboard: () => request<Dashboard>('/dashboard'),
  uploadResume: (file: File) => {
    const form = new FormData()
    form.append('file', file)
    return request<ResumeOut>('/resumes/upload', { method: 'POST', body: form })
  },
  listResumes: () => request<ResumeSummary[]>('/resumes'),
  getResume: (id: string) => request<ResumeOut>(`/resumes/${id}`),
  deleteResume: (id: string) => request<void>(`/resumes/${id}`, { method: 'DELETE' }),
  analyzeResume: (id: string, body: { job_description?: string; jd_id?: string; target_role: string }) =>
    request<AnalysisOut>(`/resumes/${id}/analyze`, json('POST', body)),
  jdSamples: () => request<JDSample[]>('/job-descriptions/samples'),
  createInterview: (body: {
    resume_id: string
    job_description?: string
    jd_id?: string | null
    config: InterviewConfig
  }) => request<InterviewOut>('/interviews', json('POST', body)),
  getInterview: (id: string) => request<InterviewOut>(`/interviews/${id}`),
  startInterview: (id: string) => request<InterviewOut>(`/interviews/${id}/start`, json('POST')),
  answer: (
    id: string,
    body: { question_id: string; answer: string; input_mode: 'voice' | 'text'; duration_seconds?: number },
  ) => request<InterviewOut>(`/interviews/${id}/answer`, json('POST', body)),
  skip: (id: string, questionId: string) =>
    request<InterviewOut>(`/interviews/${id}/next-question`, json('POST', { question_id: questionId })),
  finish: (id: string) => request<InterviewOut>(`/interviews/${id}/finish`, json('POST')),
  report: (id: string) => request<InterviewReport>(`/interviews/${id}/report`),
  history: () => request<HistoryItem[]>('/interviews/history'),
  activeInterviews: () => request<InterviewOut[]>('/interviews/active'),
  deleteInterview: (id: string) => request<void>(`/interviews/${id}`, { method: 'DELETE' }),
  settings: () => request<AppSettings>('/settings'),
  updateSettings: (body: { ollama_model?: string; ollama_base_url?: string }) =>
    request<AppSettings>('/settings', json('PUT', body)),
  deleteAll: () => request<void>('/data', { method: 'DELETE' }),
  reportPdfUrl: (id: string) => `${BASE}/interviews/${id}/report.pdf`,
  transcriptUrl: (id: string) => `${BASE}/interviews/${id}/transcript`,
  exportUrl: () => `${BASE}/export`,
}

export function errorMessage(err: unknown): string {
  if (err instanceof ApiError) return err.message
  return 'Something unexpected happened. Please try again.'
}
