import { useCallback, useEffect, useRef, useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import {
  CheckCircle2,
  Clock,
  Keyboard,
  Loader2,
  Mic,
  MicOff,
  SkipForward,
  Square,
  Volume2,
  VolumeX,
  XCircle,
} from 'lucide-react'
import { api, ApiError, errorMessage } from '../lib/api'
import type { InterviewOut, MessageOut } from '../lib/types'
import { KEYS, load, remove, save } from '../lib/storage'
import {
  Dictation,
  joinText,
  speak,
  speechRecognitionSupported,
  speechSynthesisSupported,
  stopSpeaking,
} from '../lib/speech'
import { fmtClock, phaseLabel } from '../lib/format'
import { Alert, Badge, Button, Card, Skeleton } from '../components/ui'
import { cn } from '../lib/cn'

function InterviewerAvatar({ name, speaking }: { name: string; speaking: boolean }) {
  const initials = name
    .split(' ')
    .map((p) => p[0])
    .join('')
    .slice(0, 2)
  return (
    <div className="relative size-14 shrink-0 sm:size-16" aria-hidden>
      {speaking && <span className="absolute inset-0 animate-pulse-ring rounded-full bg-indigo-400" />}
      <div className="relative flex size-full items-center justify-center overflow-hidden rounded-full bg-gradient-to-br from-indigo-500 to-indigo-700 text-white shadow-md">
        <svg viewBox="0 0 64 64" className="absolute inset-0 size-full opacity-25">
          <circle cx="32" cy="25" r="11" fill="white" />
          <path d="M12 60c2-12 11-18 20-18s18 6 20 18" fill="white" />
        </svg>
        <span className="relative text-lg font-semibold">{initials}</span>
      </div>
      {speaking && (
        <span className="absolute -right-1 -bottom-1 flex h-5 items-end gap-[2px] rounded-full bg-white px-1.5 py-1 shadow dark:bg-zinc-900">
          {[0, 1, 2].map((i) => (
            <span
              key={i}
              className="block h-full w-[3px] origin-bottom animate-bar rounded-full bg-indigo-500"
              style={{ animationDelay: `${i * 0.15}s` }}
            />
          ))}
        </span>
      )}
    </div>
  )
}

function Transcript({
  messages,
  interviewerName,
  candidateName,
}: {
  messages: MessageOut[]
  interviewerName: string
  candidateName: string
}) {
  const endRef = useRef<HTMLDivElement>(null)
  useEffect(() => {
    // Scroll the transcript pane itself, never the page (on mobile that would hide the question).
    const pane = endRef.current?.closest('[data-scroll-pane]')
    if (!pane) return
    if (typeof pane.scrollTo === 'function') pane.scrollTo({ top: pane.scrollHeight, behavior: 'smooth' })
    else pane.scrollTop = pane.scrollHeight
  }, [messages.length])
  return (
    <div className="space-y-4" aria-live="polite" aria-relevant="additions" data-testid="transcript">
      {messages.map((m) => {
        const mine = m.role === 'candidate'
        return (
          <div key={m.seq} className={cn('flex animate-fade-in', mine ? 'justify-end' : 'justify-start')}>
            <div className={cn('max-w-[85%] sm:max-w-[75%]')}>
              <div className={cn('mb-1 text-xs text-zinc-500', mine && 'text-right')}>
                {mine ? candidateName || 'You' : interviewerName}
                {m.kind === 'follow_up' && (
                  <span className="ml-1.5 text-indigo-600 dark:text-indigo-400">· follow-up</span>
                )}
              </div>
              <div
                className={cn(
                  'rounded-lg px-3.5 py-2.5 text-sm leading-relaxed whitespace-pre-wrap',
                  mine
                    ? 'bg-indigo-600 text-white'
                    : 'border border-zinc-200 bg-white text-zinc-800 dark:border-zinc-800 dark:bg-zinc-900 dark:text-zinc-200',
                )}
                data-role={m.role}
              >
                {m.text}
              </div>
            </div>
          </div>
        )
      })}
      <div ref={endRef} />
    </div>
  )
}

export default function InterviewRoom() {
  const { id = '' } = useParams()
  const navigate = useNavigate()
  const [iv, setIv] = useState<InterviewOut | null>(null)
  const [loadError, setLoadError] = useState<string | null>(null)
  const [actionError, setActionError] = useState<string | null>(null)
  const [answer, setAnswer] = useState('')
  const [interim, setInterim] = useState('')
  const [submitting, setSubmitting] = useState(false)
  const [finishing, setFinishing] = useState(false)
  const [mode, setMode] = useState<'voice' | 'text'>('text')
  const [listening, setListening] = useState(false)
  const [stoppingMic, setStoppingMic] = useState(false)
  const [usedVoice, setUsedVoice] = useState(false)
  const [voiceError, setVoiceError] = useState<string | null>(null)
  const [muted, setMuted] = useState<boolean>(() => load(KEYS.muted, false))
  const [speaking, setSpeaking] = useState(false)
  const [now, setNow] = useState(() => Date.now())
  const [dictation] = useState(
    () =>
      new Dictation({
        onUpdate: (text, interimText) => {
          setAnswer(text)
          setInterim(interimText)
          if (text || interimText) setUsedVoice(true)
        },
        onError: (msg) => setVoiceError(msg),
        onStateChange: (state) => {
          setListening(state !== 'idle')
          setStoppingMic(state === 'stopping')
          if (state === 'idle') setInterim('')
        },
      }),
  )
  const spokenSeq = useRef<number>(-1)
  const finishStarted = useRef(false)
  const canRecognize = speechRecognitionSupported()
  const canSpeak = speechSynthesisSupported()

  const questionId = iv?.current_question?.id ?? null

  // ---- closing -> generate the report automatically
  const finish = useCallback(async () => {
    if (finishStarted.current) return
    finishStarted.current = true
    setFinishing(true)
    setActionError(null)
    dictation.cancel()
    try {
      const done = await api.finish(id)
      setIv(done)
      remove(KEYS.draft(id))
      // give the closing line a moment to be read/heard
      setTimeout(() => navigate(`/interview/${id}/report`), 1200)
    } catch (e) {
      setActionError(errorMessage(e))
      finishStarted.current = false
      setFinishing(false)
    }
  }, [id, navigate, dictation])

  // ---- load (and recover) the interview
  useEffect(() => {
    let alive = true
    ;(async () => {
      try {
        let data = await api.getInterview(id)
        if (data.state === 'CREATED') data = await api.startInterview(id)
        if (!alive) return
        // After a refresh, don't re-read the whole transcript: only what followed the last answer.
        const lastAnswer = [...data.messages].reverse().find((m) => m.role === 'candidate')
        spokenSeq.current = lastAnswer ? lastAnswer.seq : -1
        setMode(data.config.mode)
        setIv(data)
        if (data.state === 'CLOSING' || data.state === 'EVALUATING' || data.state === 'FAILED') finish()
      } catch (e) {
        if (alive)
          setLoadError(
            e instanceof ApiError && e.status === 404
              ? 'This interview does not exist or was deleted.'
              : errorMessage(e),
          )
      }
    })()
    return () => {
      alive = false
      stopSpeaking()
      dictation.cancel()
    }
  }, [id, finish, dictation])

  // A recording always belongs to one question: discard it if the question changes underneath it.
  useEffect(() => () => dictation.cancel(), [questionId, dictation])

  // ---- when the question changes, restore any saved draft for it (state adjusted during render)
  const [draftFor, setDraftFor] = useState<string | null>(null)
  if (questionId && questionId !== draftFor) {
    const draft = load<{ q: string; text: string } | null>(KEYS.draft(id), null)
    setDraftFor(questionId)
    setAnswer(draft && draft.q === questionId ? draft.text : '')
    setInterim('')
    setUsedVoice(false)
  }
  // The question was asked when its interviewer message was created (survives refreshes).
  const askedAt = iv?.messages.findLast?.(
    (m) => m.question_id === questionId && m.role === 'interviewer',
  )?.created_at
  const questionStart = askedAt ? new Date(askedAt).getTime() : now

  useEffect(() => {
    if (questionId) save(KEYS.draft(id), { q: questionId, text: answer })
  }, [answer, questionId, id])

  // ---- clock
  useEffect(() => {
    const t = setInterval(() => setNow(Date.now()), 1000)
    return () => clearInterval(t)
  }, [])

  // ---- interviewer speech for new messages (voice mode only)
  useEffect(() => {
    if (!iv || mode !== 'voice' || muted || !canSpeak) return
    const fresh = iv.messages.filter((m) => m.role === 'interviewer' && m.seq > spokenSeq.current)
    if (!fresh.length) return
    spokenSeq.current = fresh[fresh.length - 1].seq
    const cancel = speak(
      fresh.map((m) => m.text).join(' '),
      () => setSpeaking(false),
      () => setSpeaking(true),
    )
    return () => {
      cancel()
    }
  }, [iv, mode, muted, canSpeak])

  const toggleMute = () => {
    const next = !muted
    if (next) {
      stopSpeaking()
      setSpeaking(false)
    }
    save(KEYS.muted, next)
    setMuted(next)
  }

  // ---- voice input
  const startListening = () => {
    if (!dictation.supported) {
      setVoiceError('Speech recognition is not supported in this browser. Please type your answer.')
      return
    }
    setVoiceError(null)
    stopSpeaking()
    setSpeaking(false)
    dictation.start(answer)
  }
  const stopListening = () => {
    void dictation.stop()
  }

  const submit = async () => {
    if (!iv?.current_question || submitting) return
    const questionId = iv.current_question.id
    setSubmitting(true)
    setActionError(null)
    // When recording, wait for the browser to finalize the last words instead of cutting them off.
    let text = listening ? await dictation.stop() : joinText(answer, interim)
    text = text.trim()
    dictation.cancel()
    if (!text) {
      setActionError('Please give an answer before submitting, or skip the question.')
      setSubmitting(false)
      return
    }
    try {
      const next = await api.answer(id, {
        question_id: questionId,
        answer: text,
        input_mode: usedVoice ? 'voice' : 'text',
        duration_seconds: Math.round((Date.now() - questionStart) / 1000),
      })
      remove(KEYS.draft(id))
      setAnswer('')
      setInterim('')
      setIv(next)
      if (next.state === 'CLOSING') finish()
    } catch (e) {
      setAnswer(text)
      setActionError(errorMessage(e))
      if (e instanceof ApiError && e.status === 409) {
        api
          .getInterview(id)
          .then(setIv)
          .catch(() => {})
      }
    } finally {
      setSubmitting(false)
    }
  }

  const skip = async () => {
    if (!iv?.current_question) return
    dictation.cancel()
    setSubmitting(true)
    setActionError(null)
    try {
      const next = await api.skip(id, iv.current_question.id)
      setIv(next)
      remove(KEYS.draft(id))
      if (next.state === 'CLOSING') finish()
    } catch (e) {
      setActionError(errorMessage(e))
    } finally {
      setSubmitting(false)
    }
  }

  const endEarly = async () => {
    if (!window.confirm('End the interview now? Your report will cover the questions answered so far.'))
      return
    stopSpeaking()
    await finish()
  }

  const elapsed = iv?.started_at
    ? Math.max(
        0,
        ((iv.finished_at ? new Date(iv.finished_at).getTime() : now) - new Date(iv.started_at).getTime()) /
          1000,
      )
    : 0

  if (loadError) {
    return (
      <div className="mx-auto max-w-lg py-10">
        <Alert tone="error" title="Couldn't open this interview">
          {loadError}
        </Alert>
        <div className="mt-4 flex gap-2">
          <Link to="/interview/setup" className="text-sm font-medium text-indigo-600 hover:underline">
            Start a new interview
          </Link>
        </div>
      </div>
    )
  }
  if (!iv) {
    return (
      <div className="space-y-4" aria-busy="true">
        <Skeleton className="h-28" />
        <Skeleton className="h-80" />
      </div>
    )
  }

  const q = iv.current_question
  const done = !q
  const closingText =
    iv.state === 'COMPLETED'
      ? 'Interview complete.'
      : iv.state === 'FAILED'
        ? 'Report generation failed.'
        : 'Generating your report…'
  const lastInterviewer = [...iv.messages].reverse().find((m) => m.role === 'interviewer')
  const progressPct = iv.progress.percent

  return (
    <div className="flex flex-col gap-4 lg:h-[calc(100vh-7.5rem)]" data-testid="interview-room">
      {/* Header strip */}
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="min-w-0">
          <h1 className="truncate text-lg font-semibold">
            {iv.config.experience_level} {iv.config.target_role} interview
          </h1>
          <p className="text-xs text-zinc-500">
            {iv.config.interview_type} · {iv.config.difficulty} ·{' '}
            {iv.ai_mode === 'llm' ? 'Local AI interviewer' : 'Offline interviewer engine'}
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Badge tone="neutral">
            <Clock className="size-3" /> <span data-testid="timer">{fmtClock(elapsed)}</span>
          </Badge>
          <Badge tone="indigo">
            <span data-testid="phase">
              {phaseLabel(iv.state === 'CHALLENGE' ? 'CHALLENGE' : (iv.phase ?? iv.state))}
            </span>
          </Badge>
          {canSpeak && (
            <Button
              variant="ghost"
              size="sm"
              onClick={toggleMute}
              aria-label={muted ? 'Unmute interviewer voice' : 'Mute interviewer voice'}
              aria-pressed={muted}
            >
              {muted ? <VolumeX className="size-4" /> : <Volume2 className="size-4" />}
            </Button>
          )}
          {!done && (
            <Button variant="secondary" size="sm" onClick={endEarly} disabled={finishing}>
              End interview
            </Button>
          )}
        </div>
      </div>

      {/* Progress */}
      <div>
        <div className="mb-1 flex justify-between text-xs text-zinc-500">
          <span data-testid="question-counter">
            {q
              ? `Question ${Math.min(q.number, iv.progress.total)} of ${iv.progress.total}${q.is_follow_up ? ' · follow-up' : ''}`
              : `${iv.progress.answered} of ${iv.progress.total} answered`}
          </span>
          <span>{Math.round(progressPct)}%</span>
        </div>
        <div
          className="h-1 overflow-hidden rounded-full bg-zinc-200 dark:bg-zinc-800"
          role="progressbar"
          aria-label="Interview progress"
          aria-valuenow={Math.round(progressPct)}
          aria-valuemin={0}
          aria-valuemax={100}
        >
          <div
            className="h-full rounded-full bg-indigo-600 transition-[width] duration-500"
            style={{ width: `${progressPct}%` }}
          />
        </div>
      </div>

      <div className="grid min-h-0 flex-1 gap-4 lg:grid-cols-[minmax(0,1fr)_380px]">
        {/* Interviewer + transcript */}
        <Card className="flex min-h-0 flex-col">
          <div className="flex items-start gap-4 border-b border-zinc-100 p-4 sm:p-5 dark:border-zinc-800">
            <InterviewerAvatar name={iv.interviewer.name} speaking={speaking} />
            <div className="min-w-0 flex-1">
              <p className="text-sm font-medium">
                {iv.interviewer.name}{' '}
                <span className="font-normal text-zinc-500">· {iv.interviewer.title}</span>
              </p>
              <p
                className="mt-1.5 text-base leading-relaxed text-zinc-800 sm:text-lg dark:text-zinc-100"
                data-testid="current-question"
              >
                {q ? q.text : lastInterviewer?.text}
              </p>
              {q?.is_follow_up && (
                <p className="mt-1 text-xs text-indigo-600 dark:text-indigo-400">Follow-up question</p>
              )}
            </div>
          </div>
          <div
            data-scroll-pane
            className="max-h-[50vh] min-h-[220px] flex-1 overflow-y-auto p-4 sm:p-5 lg:max-h-none"
          >
            <Transcript
              messages={iv.messages}
              interviewerName={iv.interviewer.name}
              candidateName={iv.candidate_name}
            />
          </div>
        </Card>

        {/* Answer panel */}
        <Card className="flex flex-col">
          {done ? (
            <div
              className="flex flex-1 flex-col items-center justify-center gap-3 p-8 text-center"
              role="status"
            >
              {iv.state === 'COMPLETED' ? (
                <CheckCircle2 className="size-10 text-emerald-500" />
              ) : iv.state === 'FAILED' ? (
                <XCircle className="size-10 text-rose-500" />
              ) : (
                <Loader2 className="size-10 animate-spin text-indigo-500" />
              )}
              <p className="font-medium">{closingText}</p>
              <p className="text-sm text-zinc-500">
                {iv.progress.answered} questions · {iv.progress.follow_ups} follow-ups · {fmtClock(elapsed)}
              </p>
              {actionError && <Alert tone="error">{actionError}</Alert>}
              {(iv.state === 'COMPLETED' || iv.state === 'FAILED' || actionError) && (
                <div className="flex gap-2">
                  {iv.state === 'COMPLETED' ? (
                    <Button onClick={() => navigate(`/interview/${id}/report`)}>View report</Button>
                  ) : (
                    <Button onClick={finish} loading={finishing}>
                      Retry report
                    </Button>
                  )}
                </div>
              )}
            </div>
          ) : (
            <div className="flex flex-1 flex-col gap-4 p-4 sm:p-5">
              <div className="flex items-center justify-between">
                <span className="text-sm font-medium">Your answer</span>
                <div
                  role="radiogroup"
                  aria-label="Answer mode"
                  className="flex rounded-md bg-zinc-100 p-0.5 text-xs dark:bg-zinc-800"
                >
                  {(['voice', 'text'] as const).map((m) => (
                    <button
                      key={m}
                      type="button"
                      role="radio"
                      aria-checked={mode === m}
                      onClick={() => {
                        if (m === 'text') stopListening()
                        setMode(m)
                      }}
                      className={cn(
                        'inline-flex items-center gap-1 rounded px-2.5 py-1 font-medium',
                        mode === m ? 'bg-white shadow-sm dark:bg-zinc-950' : 'text-zinc-500',
                      )}
                    >
                      {m === 'voice' ? <Mic className="size-3" /> : <Keyboard className="size-3" />}
                      {m === 'voice' ? 'Voice' : 'Text'}
                    </button>
                  ))}
                </div>
              </div>

              {mode === 'voice' && (
                <div className="flex flex-col items-center gap-2 rounded-lg border border-dashed border-zinc-200 py-4 dark:border-zinc-800">
                  {canRecognize ? (
                    <>
                      <button
                        type="button"
                        onClick={listening ? stopListening : startListening}
                        disabled={stoppingMic || submitting}
                        aria-label={listening ? 'Stop recording' : 'Start recording your answer'}
                        aria-pressed={listening}
                        className={cn(
                          'relative flex size-16 items-center justify-center rounded-full text-white shadow-md transition-colors disabled:opacity-60',
                          listening ? 'bg-rose-600 hover:bg-rose-500' : 'bg-indigo-600 hover:bg-indigo-500',
                        )}
                      >
                        {listening && (
                          <span className="absolute inset-0 animate-pulse-ring rounded-full bg-rose-500" />
                        )}
                        {listening ? (
                          <Square className="relative size-6" />
                        ) : (
                          <Mic className="relative size-7" />
                        )}
                      </button>
                      <span className="text-xs text-zinc-500" aria-live="polite">
                        {stoppingMic
                          ? 'Finishing transcription…'
                          : listening
                            ? "Listening — pauses are fine. Tap stop when you're done."
                            : answer
                              ? 'Tap to continue recording'
                              : 'Tap to answer out loud'}
                      </span>
                    </>
                  ) : (
                    <p className="flex items-center gap-2 px-4 text-center text-xs text-zinc-500">
                      <MicOff className="size-4 shrink-0" /> Speech recognition isn't available in this
                      browser. Type your answer below.
                    </p>
                  )}
                </div>
              )}
              {voiceError && <Alert tone="warning">{voiceError}</Alert>}

              <div className="flex flex-1 flex-col">
                <label htmlFor="answer" className="sr-only">
                  Answer
                </label>
                <textarea
                  id="answer"
                  className="min-h-[160px] w-full flex-1 resize-none rounded-md border border-zinc-300 bg-white px-3 py-2.5 text-sm leading-relaxed shadow-sm focus:border-indigo-500 focus:ring-2 focus:ring-indigo-500/30 focus:outline-none dark:border-zinc-700 dark:bg-zinc-950"
                  placeholder={
                    listening
                      ? 'Listening… your words will appear here.'
                      : mode === 'voice'
                        ? 'Your transcribed answer appears here. You can edit it before submitting.'
                        : 'Type your answer… (Ctrl+Enter to submit)'
                  }
                  // Only normalize while speech is arriving; trimming typed text would swallow every space.
                  value={interim ? joinText(answer, interim) : answer}
                  // Editing while recording would race the transcription; stop first, then edit.
                  readOnly={listening}
                  aria-describedby={listening ? 'answer-recording-hint' : undefined}
                  onChange={(e) => {
                    setInterim('')
                    setAnswer(e.target.value)
                  }}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter' && (e.ctrlKey || e.metaKey)) {
                      e.preventDefault()
                      submit()
                    }
                  }}
                  maxLength={6000}
                  disabled={submitting}
                />
                <div className="mt-1 flex justify-between text-xs text-zinc-400">
                  <span id="answer-recording-hint">
                    {joinText(answer, interim).split(' ').filter(Boolean).length} words
                    {listening && ' · stop recording to edit'}
                  </span>
                  <span className="inline-flex items-center gap-1">
                    <Clock className="size-3" /> {fmtClock((now - questionStart) / 1000)} on this question
                  </span>
                </div>
              </div>

              {actionError && <Alert tone="error">{actionError}</Alert>}
              <div className="flex gap-2">
                <Button
                  className="flex-1"
                  onClick={submit}
                  loading={submitting}
                  disabled={finishing}
                  data-testid="submit-answer"
                >
                  {submitting && stoppingMic ? 'Finishing transcription…' : 'Submit answer'}
                </Button>
                <Button
                  variant="secondary"
                  onClick={skip}
                  disabled={submitting || finishing}
                  aria-label="Skip this question"
                >
                  <SkipForward className="size-4" /> Skip
                </Button>
              </div>
              <p className="text-center text-xs text-zinc-400">
                Scores are hidden until the report. Progress is saved after every answer.
              </p>
            </div>
          )}
        </Card>
      </div>
    </div>
  )
}
