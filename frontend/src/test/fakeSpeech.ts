/* eslint-disable @typescript-eslint/no-explicit-any */
// A scriptable stand-in for Chrome's SpeechRecognition, used to reproduce real-world behaviour:
// sessions that end by themselves after a pause, final results that arrive after stop(), and
// events from sessions that are already gone.

type Result = { transcript: string; isFinal: boolean }

export class FakeRecognition {
  static instances: FakeRecognition[] = []
  continuous = false
  interimResults = false
  maxAlternatives = 1
  lang = ''
  onresult: ((e: any) => void) | null = null
  onerror: ((e: any) => void) | null = null
  onend: (() => void) | null = null
  started = false
  stopped = false
  aborted = false
  results: Result[] = []
  /** Start a new result list after each final phrase, as recent Chrome builds do in continuous mode. */
  resetsAfterFinal = false
  private listDone = false
  /** Words the "browser" is still processing; delivered as final when stop() is called. */
  pendingOnStop: string | null = null

  constructor() {
    FakeRecognition.instances.push(this)
  }
  static reset() {
    FakeRecognition.instances = []
  }
  static get last(): FakeRecognition {
    return FakeRecognition.instances[FakeRecognition.instances.length - 1]
  }
  start() {
    this.started = true
  }
  stop() {
    this.stopped = true
    // Chrome finalizes in-flight speech shortly after stop(), then fires "end".
    setTimeout(() => {
      if (this.pendingOnStop) this.final(this.pendingOnStop)
      this.end()
    }, 30)
  }
  abort() {
    this.aborted = true
    setTimeout(() => this.end(), 0)
  }
  private emit() {
    const list = this.results.map((r) =>
      Object.assign([{ transcript: r.transcript }], { isFinal: r.isFinal }),
    )
    this.onresult?.({ resultIndex: 0, results: list })
  }
  /** Replace the trailing interim result (like the browser refining a guess). */
  interim(text: string) {
    this.maybeReset()
    if (this.results.length && !this.results[this.results.length - 1].isFinal) this.results.pop()
    this.results.push({ transcript: text, isFinal: false })
    this.emit()
  }
  final(text: string) {
    this.maybeReset()
    if (this.results.length && !this.results[this.results.length - 1].isFinal) this.results.pop()
    this.results.push({ transcript: text, isFinal: true })
    this.emit()
    if (this.resetsAfterFinal) this.listDone = true
  }
  private maybeReset() {
    if (this.listDone) this.results = []
    this.listDone = false
  }
  error(code: string) {
    this.onerror?.({ error: code })
  }
  end() {
    this.onend?.()
  }
}
