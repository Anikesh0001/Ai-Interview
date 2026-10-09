import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { act, fireEvent, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { health, mockApi, renderAt } from '../test/utils'
import { analysis, interview, report, resume } from '../test/fixtures'
import { FakeRecognition } from '../test/fakeSpeech'
import ResumePage from './Resume'
import DashboardPage from './Dashboard'
import InterviewSetup from './InterviewSetup'
import InterviewRoom from './InterviewRoom'
import ReportPage from './Report'
import HistoryPage from './History'

beforeEach(() => localStorage.clear())
afterEach(() => vi.unstubAllGlobals())

describe('Resume page', () => {
  it('uploads a resume and shows the parsed profile and ATS score', async () => {
    const fetchMock = mockApi([
      { path: '/health', respond: health },
      { path: '/job-descriptions/samples', respond: [] },
      { method: 'POST', path: '/resumes/upload', respond: resume },
      { method: 'POST', path: '/resumes/r1/analyze', respond: analysis },
    ])
    renderAt('/resume', '/resume', <ResumePage />)
    const input = await screen.findByTestId('resume-input')
    await userEvent.upload(
      input,
      new File(['%PDF-1.7 resume'], 'sample_resume.pdf', { type: 'application/pdf' }),
    )
    expect(await screen.findByTestId('candidate-name')).toHaveTextContent('Aarav Sharma')
    expect(await screen.findByTestId('ats-score')).toHaveTextContent('84')
    expect(screen.getByText('Hospital Management System')).toBeInTheDocument()
    expect(fetchMock).toHaveBeenCalledWith('/api/resumes/upload', expect.objectContaining({ method: 'POST' }))
    expect(localStorage.getItem('if-resume-id')).toBe('"r1"')
  })

  it('rejects unsupported files before uploading', async () => {
    const fetchMock = mockApi([
      { path: '/health', respond: health },
      { path: '/job-descriptions/samples', respond: [] },
    ])
    renderAt('/resume', '/resume', <ResumePage />)
    const input = await screen.findByTestId('resume-input')
    fireEvent.change(input, { target: { files: [new File(['x'], 'photo.png', { type: 'image/png' })] } })
    expect(await screen.findByText(/Unsupported file type/)).toBeInTheDocument()
    expect(fetchMock).not.toHaveBeenCalledWith('/api/resumes/upload', expect.anything())
  })
})

describe('Dashboard', () => {
  it('shows an empty state for a new user', async () => {
    mockApi([
      { path: '/health', respond: health },
      {
        path: '/dashboard',
        respond: {
          interviews_completed: 0,
          latest_interview_score: null,
          latest_readiness: null,
          latest_jd_match: null,
          latest_ats: null,
          best_score: null,
          average_score: null,
          improvement: null,
          trend: [],
          weak_skills: [],
          recent: [],
          active_interviews: [],
          resume_health: null,
          has_resume: false,
        },
      },
    ])
    renderAt('/dashboard', '/dashboard', <DashboardPage />)
    expect(await screen.findByText('No completed interviews yet')).toBeInTheDocument()
    expect(screen.getByTestId('stat-completed')).toHaveTextContent('0')
  })

  it('offers to resume an interrupted interview', async () => {
    mockApi([
      { path: '/health', respond: health },
      {
        path: '/dashboard',
        respond: {
          interviews_completed: 1,
          latest_interview_score: 70,
          latest_readiness: 72,
          latest_jd_match: null,
          latest_ats: 84,
          best_score: 70,
          average_score: 70,
          improvement: null,
          trend: [
            { id: 'x', date: '2026-10-08T10:00:00Z', interview: 70, readiness: 72, ats: 84, role: 'SE' },
          ],
          weak_skills: [{ skill: 'SQL', score: 50, count: 1 }],
          recent: [],
          active_interviews: [
            { id: 'i9', role: 'Backend Developer', state: 'TECHNICAL', created_at: '2026-10-08T10:00:00Z' },
          ],
          resume_health: null,
          has_resume: true,
        },
      },
    ])
    renderAt('/dashboard', '/dashboard', <DashboardPage />)
    expect(await screen.findByRole('button', { name: 'Resume Interview' })).toBeInTheDocument()
    expect(screen.getByTestId('stat-interview')).toHaveTextContent('70')
  })
})

describe('Interview setup', () => {
  it('creates and starts an interview with the chosen configuration', async () => {
    localStorage.setItem('if-resume-id', '"r1"')
    let created: Record<string, unknown> | null = null
    mockApi([
      { path: '/health', respond: health },
      {
        path: '/resumes',
        respond: [
          {
            id: 'r1',
            filename: 'sample_resume.pdf',
            file_type: 'pdf',
            size_bytes: 1,
            created_at: '2026-10-08T10:00:00Z',
            candidate_name: 'Aarav Sharma',
            ats_score: 84,
          },
        ],
      },
      { path: '/interviews/active', respond: [] },
      {
        method: 'POST',
        path: '/interviews',
        respond: (init: RequestInit) => {
          created = JSON.parse(String(init.body))
          return interview({ state: 'CREATED' })
        },
      },
      { method: 'POST', path: '/interviews/i1/start', respond: interview() },
    ])
    renderAt('/interview/setup', '/interview/setup', <InterviewSetup />, [
      { path: '/interview/:id', element: <div>ROOM</div> },
    ])
    await screen.findByText('Configure your interview')
    await userEvent.click(screen.getByRole('radio', { name: 'Hard' }))
    await userEvent.click(screen.getByRole('radio', { name: /Quick/ }))
    await userEvent.click(screen.getByRole('button', { name: /Start interview/ }))
    expect(await screen.findByText('ROOM')).toBeInTheDocument()
    expect(created).toMatchObject({
      resume_id: 'r1',
      config: { difficulty: 'Hard', num_questions: 5, interview_type: 'Mixed' },
    })
  })
})

describe('Interview room', () => {
  it('submits an answer, shows the follow-up and never shows scores', async () => {
    const next = interview({
      state: 'CHALLENGE',
      messages: [
        ...interview().messages,
        {
          seq: 3,
          role: 'candidate',
          text: 'I am a student who builds things.',
          question_id: 'q1',
          created_at: '2026-10-08T10:01:00Z',
          kind: 'message',
        },
        {
          seq: 4,
          role: 'interviewer',
          text: 'Can you make that more concrete?',
          question_id: 'q2',
          created_at: '2026-10-08T10:01:01Z',
          kind: 'follow_up',
        },
      ],
      current_question: {
        id: 'q2',
        text: 'Can you make that more concrete?',
        category: 'intro',
        phase: 'CHALLENGE',
        is_follow_up: true,
        number: 1,
      },
    })
    let body: Record<string, unknown> | null = null
    mockApi([
      { path: '/health', respond: health },
      { path: '/interviews/i1', respond: interview() },
      {
        method: 'POST',
        path: '/interviews/i1/answer',
        respond: (init: RequestInit) => {
          body = JSON.parse(String(init.body))
          return next
        },
      },
    ])
    renderAt('/interview/i1', '/interview/:id', <InterviewRoom />)
    expect(await screen.findByTestId('current-question')).toHaveTextContent('Tell me about yourself.')
    await userEvent.type(screen.getByLabelText('Answer'), 'I am a student who builds things.')
    await userEvent.click(screen.getByTestId('submit-answer'))
    expect(await screen.findByText('Follow-up question')).toBeInTheDocument()
    expect(body).toMatchObject({
      question_id: 'q1',
      answer: 'I am a student who builds things.',
      input_mode: 'text',
    })
    // no score or classification is ever rendered during the interview
    expect(screen.queryByText(/\/\s*100/)).not.toBeInTheDocument()
    expect(
      screen.queryByText(/^(Excellent|Strong|Acceptable|Weak|Vague|Suspicious|Incomplete)$/),
    ).not.toBeInTheDocument()
    expect(screen.getByText(/Scores are hidden until the report/)).toBeInTheDocument()
  })

  it('voice: captures the whole answer across pauses and nothing leaks into the next question', async () => {
    FakeRecognition.reset()
    vi.stubGlobal('webkitSpeechRecognition', FakeRecognition)
    const next = interview({
      messages: [
        ...interview().messages,
        {
          seq: 3,
          role: 'candidate',
          text: 'x',
          question_id: 'q1',
          created_at: '2026-10-08T10:01:00Z',
          kind: 'message',
        },
        {
          seq: 4,
          role: 'interviewer',
          text: 'Walk me through a project.',
          question_id: 'q2',
          created_at: '2026-10-08T10:01:01Z',
          kind: 'message',
        },
      ],
      current_question: {
        id: 'q2',
        text: 'Walk me through a project.',
        category: 'project',
        phase: 'PROJECT',
        is_follow_up: false,
        number: 2,
      },
    })
    let body: Record<string, unknown> | null = null
    mockApi([
      { path: '/health', respond: health },
      { path: '/interviews/i1', respond: interview({ config: { ...interview().config, mode: 'voice' } }) },
      {
        method: 'POST',
        path: '/interviews/i1/answer',
        respond: (init: RequestInit) => {
          body = JSON.parse(String(init.body))
          return next
        },
      },
    ])
    renderAt('/interview/i1', '/interview/:id', <InterviewRoom />)
    await userEvent.click(await screen.findByRole('button', { name: 'Start recording your answer' }))
    const s1 = FakeRecognition.last
    act(() => s1.final('Hello, I am a final year student'))
    act(() => s1.end()) // the browser ends the session after a pause
    await waitFor(() => expect(FakeRecognition.instances).toHaveLength(2))
    const s2 = FakeRecognition.last
    act(() => s2.final('and I am looking for a software engineer role'))
    act(() => s2.interim('where I can build'))
    s2.pendingOnStop = 'where I can build backend systems'
    expect(screen.getByLabelText('Answer')).toHaveAttribute('readonly')
    // submit while still recording: the in-flight words must not be cut off
    await userEvent.click(screen.getByTestId('submit-answer'))
    await waitFor(() => expect(body).not.toBeNull())
    expect(body).toMatchObject({
      question_id: 'q1',
      answer:
        'Hello, I am a final year student and I am looking for a software engineer role where I can build backend systems',
      input_mode: 'voice',
    })
    expect(await screen.findByTestId('current-question')).toHaveTextContent('Walk me through a project.')
    act(() => s2.final('quality')) // a late result from the old session
    expect(screen.getByLabelText('Answer')).toHaveValue('')
  })

  it('blocks empty answers with a helpful message', async () => {
    mockApi([
      { path: '/health', respond: health },
      { path: '/interviews/i1', respond: interview() },
    ])
    renderAt('/interview/i1', '/interview/:id', <InterviewRoom />)
    await screen.findByTestId('current-question')
    await userEvent.click(screen.getByTestId('submit-answer'))
    expect(await screen.findByText(/Please give an answer/)).toBeInTheDocument()
  })

  it('restores the interview from the server after a refresh', async () => {
    const mid = interview({
      state: 'TECHNICAL',
      phase: 'TECHNICAL',
      progress: { answered: 4, total: 10, follow_ups: 1, percent: 40 },
      current_question: {
        id: 'q6',
        text: 'Explain database indexes.',
        category: 'technical',
        phase: 'TECHNICAL',
        is_follow_up: false,
        number: 5,
      },
    })
    mockApi([
      { path: '/health', respond: health },
      { path: '/interviews/i1', respond: mid },
    ])
    renderAt('/interview/i1', '/interview/:id', <InterviewRoom />)
    expect(await screen.findByTestId('current-question')).toHaveTextContent('Explain database indexes.')
    expect(screen.getByTestId('question-counter')).toHaveTextContent('Question 5 of 10')
  })
})

describe('Report', () => {
  it('renders scores, review, claims and study topics', async () => {
    mockApi([
      { path: '/health', respond: health },
      { path: '/interviews/i1/report', respond: report },
    ])
    renderAt('/interview/i1/report', '/interview/:id/report', <ReportPage />)
    expect(await screen.findByTestId('executive-summary')).toHaveTextContent('struggled to explain Python')
    expect(screen.getByTestId('score-ats')).toHaveTextContent('84')
    expect(screen.getByTestId('score-interview')).toHaveTextContent('61')
    expect(screen.getByTestId('claims')).toHaveTextContent('Unable to substantiate')
    expect(screen.getByTestId('study-topics')).toHaveTextContent('Python')
    expect(screen.getByText(/Not a probability of being hired/)).toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: /Tell me about yourself/ }))
    expect(await screen.findByText('A 60-90 second narrative.')).toBeInTheDocument()
  })
})

describe('History', () => {
  it('lists interviews and links to reports', async () => {
    mockApi([
      { path: '/health', respond: health },
      {
        path: '/interviews/history',
        respond: [
          {
            id: 'i1',
            created_at: '2026-10-08T10:00:00Z',
            finished_at: '2026-10-08T10:20:00Z',
            state: 'COMPLETED',
            target_role: 'Backend Developer',
            interview_type: 'Mixed',
            difficulty: 'Medium',
            experience_level: 'Junior',
            num_questions: 10,
            interview_score: 61,
            ats_score: 84,
            jd_score: 51,
            readiness_score: 66,
            duration_seconds: 900,
            resume_filename: 'r.pdf',
            has_jd: true,
          },
        ],
      },
    ])
    renderAt('/history', '/history', <HistoryPage />)
    expect(await screen.findByText('Backend Developer')).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Report' })).toHaveAttribute('href', '/interview/i1/report')
  })

  it('shows an empty state', async () => {
    mockApi([
      { path: '/health', respond: health },
      { path: '/interviews/history', respond: [] },
    ])
    renderAt('/history', '/history', <HistoryPage />)
    await waitFor(() => expect(screen.getByText('No interviews yet')).toBeInTheDocument())
  })
})
