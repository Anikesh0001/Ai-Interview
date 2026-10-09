// Browser-native speech. Recognition uses the Web Speech API where available;
// synthesis uses window.speechSynthesis. Both are optional: the interview works without them.

/* eslint-disable @typescript-eslint/no-explicit-any */
type RecognitionCtor = new () => any

export function getRecognitionCtor(): RecognitionCtor | null {
  if (typeof window === 'undefined') return null
  const w = window as any
  return (w.SpeechRecognition || w.webkitSpeechRecognition || null) as RecognitionCtor | null
}

export const speechRecognitionSupported = (): boolean => getRecognitionCtor() !== null
export const speechSynthesisSupported = (): boolean =>
  typeof window !== 'undefined' &&
  'speechSynthesis' in window &&
  typeof SpeechSynthesisUtterance !== 'undefined'

export type DictationState = 'idle' | 'listening' | 'stopping'

export interface DictationHandlers {
  /** `text` is the full answer so far (including any text that existed before recording); `interim` is unconfirmed. */
  onUpdate: (text: string, interim: string) => void
  onError: (message: string) => void
  onStateChange: (state: DictationState) => void
}

const FATAL_ERRORS: Record<string, string> = {
  'not-allowed': 'Microphone permission was denied. You can type your answer instead.',
  'service-not-allowed': 'Speech recognition is blocked in this browser. You can type your answer instead.',
  'audio-capture': 'No microphone was found. You can type your answer instead.',
  'language-not-supported':
    "Speech recognition doesn't support your browser language. You can type your answer instead.",
  network: 'Speech recognition needs a network connection in this browser. You can type your answer instead.',
}

/** Joins transcript fragments with single spaces. */
export function joinText(...parts: string[]): string {
  return parts
    .map((p) => p.replace(/\s+/g, ' ').trim())
    .filter(Boolean)
    .join(' ')
}

/**
 * Long-form dictation on top of the Web Speech API.
 *
 * Browsers end a recognition session on their own after a pause, a "no-speech" timeout or about a minute of
 * audio. While the user is recording, those endings are restarted transparently and the text is kept, so a
 * whole answer with pauses is captured. Every session carries a generation number: results that arrive after
 * a session was cancelled or replaced are ignored, so they can never leak into another answer.
 */
export class Dictation {
  private rec: any = null
  private wanted = false
  private gen = 0
  private committed = ''
  /** Phrases from earlier result lists of this session (the browser may restart the list mid-session). */
  private banked = ''
  /** Finalized phrases of the current result list, by result index. */
  private sessionFinals: (string | undefined)[] = []
  private sessionInterim = ''
  private restartTimer: ReturnType<typeof setTimeout> | null = null
  private restarts: number[] = []
  private waiters: ((text: string) => void)[] = []
  private state: DictationState = 'idle'
  private readonly Ctor: RecognitionCtor | null
  private readonly handlers: DictationHandlers
  /** Android Chrome repeats earlier text in continuous mode, so it gets one utterance per session. */
  private readonly continuous: boolean

  constructor(handlers: DictationHandlers, Ctor: RecognitionCtor | null = getRecognitionCtor()) {
    this.handlers = handlers
    this.Ctor = Ctor
    this.continuous = !(typeof navigator !== 'undefined' && /android/i.test(navigator.userAgent))
  }

  get supported(): boolean {
    return this.Ctor !== null
  }

  /** The best available transcript, including words not yet confirmed by the browser. */
  get text(): string {
    return joinText(this.committed, this.sessionFinal, this.sessionInterim)
  }

  private get sessionFinal(): string {
    return joinText(this.banked, ...this.finalsList())
  }

  private finalsList(): string[] {
    return this.sessionFinals.filter((f): f is string => f !== undefined)
  }

  start(existingText = ''): void {
    if (!this.Ctor || this.state !== 'idle') return
    this.committed = joinText(existingText)
    this.banked = ''
    this.sessionFinals = []
    this.sessionInterim = ''
    this.restarts = []
    this.wanted = true
    this.setState('listening')
    this.begin()
  }

  /** Stop recording, wait (briefly) for the browser to finalize the last words, and return the full text. */
  stop(timeoutMs = 2000): Promise<string> {
    if (this.state === 'idle') return Promise.resolve(this.text)
    this.wanted = false
    if (this.restartTimer !== null || !this.rec) {
      // between sessions: nothing in flight
      this.finishIdle()
      return Promise.resolve(this.text)
    }
    this.setState('stopping')
    const promise = new Promise<string>((resolve) => this.waiters.push(resolve))
    const gen = this.gen
    try {
      this.rec.stop()
    } catch {
      /* already stopped */
    }
    setTimeout(() => {
      // the browser never sent "end": keep what we have and ignore anything that arrives later
      if (this.gen === gen && this.state === 'stopping') {
        this.gen++
        this.foldSession()
        this.abortRec()
        this.finishIdle()
      }
    }, timeoutMs)
    return promise
  }

  /** Discard the session immediately; no further updates will be delivered. */
  cancel(): void {
    this.wanted = false
    this.gen++
    this.abortRec()
    this.waiters = []
    this.banked = ''
    this.sessionFinals = []
    this.sessionInterim = ''
    if (this.state !== 'idle') this.setState('idle')
  }

  private begin(): void {
    this.restartTimer = null
    const gen = ++this.gen
    const rec = new this.Ctor!()
    rec.continuous = this.continuous
    rec.interimResults = true
    rec.maxAlternatives = 1
    rec.lang = (typeof navigator !== 'undefined' && navigator.language) || 'en-US'
    rec.onresult = (event: any) => {
      if (gen !== this.gen) return
      const list = event.results
      const n: number = list.length
      const at = (i: number) => ({ t: String(list[i]?.[0]?.transcript ?? ''), final: !!list[i]?.isFinal })
      // A finalized phrase never changes, so if one now reads differently the browser has started a new
      // result list (recent Chrome does this after each pause). Bank what was said so it isn't overwritten.
      const reset = this.sessionFinals.some((f, i) => {
        if (f === undefined || i >= n) return false
        const r = at(i)
        return !r.final || r.t !== f
      })
      if (reset) {
        this.banked = joinText(this.banked, ...this.finalsList())
        this.sessionFinals = []
      }
      // Rebuild from the full list: idempotent, so repeated events never duplicate words.
      const interims: string[] = []
      for (let i = 0; i < n; i++) {
        const r = at(i)
        if (r.final) this.sessionFinals[i] = r.t
        else interims.push(r.t)
      }
      this.sessionInterim = joinText(...interims)
      this.emit()
    }
    rec.onerror = (event: any) => {
      if (gen !== this.gen) return
      const code = String(event?.error ?? '')
      if (code in FATAL_ERRORS) {
        this.wanted = false
        this.handlers.onError(FATAL_ERRORS[code])
      }
      // "no-speech" and "aborted" are normal: the session ends and is restarted while recording.
    }
    rec.onend = () => {
      if (gen !== this.gen) return
      this.foldSession()
      this.rec = null
      if (this.wanted) this.scheduleRestart()
      else this.finishIdle()
    }
    this.rec = rec
    try {
      rec.start()
    } catch {
      this.wanted = false
      this.rec = null
      this.handlers.onError('Could not start the microphone. You can type your answer instead.')
      this.finishIdle()
    }
  }

  private scheduleRestart(): void {
    const now = Date.now()
    this.restarts = this.restarts.filter((t) => now - t < 10_000)
    if (this.restarts.length >= 8) {
      // the browser keeps ending immediately (e.g. the mic is busy); don't spin
      this.wanted = false
      this.handlers.onError(
        'Speech recognition keeps stopping. Tap the microphone to try again, or type your answer.',
      )
      this.finishIdle()
      return
    }
    this.restarts.push(now)
    this.restartTimer = setTimeout(() => {
      if (this.wanted) this.begin()
      else this.finishIdle()
    }, 120)
  }

  /** Move the session's text (including unconfirmed words, which would otherwise be lost) into the answer. */
  private foldSession(): void {
    this.committed = joinText(this.committed, this.sessionFinal, this.sessionInterim)
    this.banked = ''
    this.sessionFinals = []
    this.sessionInterim = ''
    this.emit()
  }

  private abortRec(): void {
    if (this.restartTimer !== null) {
      clearTimeout(this.restartTimer)
      this.restartTimer = null
    }
    if (this.rec) {
      try {
        this.rec.abort()
      } catch {
        /* ignore */
      }
      this.rec = null
    }
  }

  private finishIdle(): void {
    if (this.restartTimer !== null) {
      clearTimeout(this.restartTimer)
      this.restartTimer = null
    }
    const text = this.text
    const waiters = this.waiters
    this.waiters = []
    waiters.forEach((w) => w(text))
    if (this.state !== 'idle') this.setState('idle')
  }

  private emit(): void {
    this.handlers.onUpdate(joinText(this.committed, this.sessionFinal), this.sessionInterim)
  }

  private setState(s: DictationState): void {
    this.state = s
    this.handlers.onStateChange(s)
  }
}

function pickVoice(): SpeechSynthesisVoice | null {
  const voices = window.speechSynthesis.getVoices()
  if (!voices.length) return null
  const lang = (navigator.language || 'en-US').slice(0, 2)
  return (
    voices.find((v) => v.lang.startsWith(lang) && /natural|neural|google|samantha|daniel/i.test(v.name)) ??
    voices.find((v) => v.lang.startsWith(lang)) ??
    voices[0]
  )
}

export function speak(text: string, onEnd?: () => void, onStart?: () => void): () => void {
  if (!speechSynthesisSupported() || !text) {
    onEnd?.()
    return () => {}
  }
  const synth = window.speechSynthesis
  synth.cancel()
  const u = new SpeechSynthesisUtterance(text)
  const voice = pickVoice()
  if (voice) u.voice = voice
  u.rate = 1.0
  u.pitch = 1.0
  let done = false
  const finish = () => {
    if (!done) {
      done = true
      onEnd?.()
    }
  }
  u.onstart = () => onStart?.()
  u.onend = finish
  u.onerror = finish
  synth.speak(u)
  return () => {
    synth.cancel()
    finish()
  }
}

export function stopSpeaking(): void {
  if (speechSynthesisSupported()) window.speechSynthesis.cancel()
}
