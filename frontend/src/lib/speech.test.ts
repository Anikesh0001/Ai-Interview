import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { Dictation, joinText, type DictationState } from './speech'
import { FakeRecognition } from '../test/fakeSpeech'

function setup(existing = '') {
  const updates: { text: string; interim: string }[] = []
  const states: DictationState[] = []
  const errors: string[] = []
  const d = new Dictation(
    {
      onUpdate: (text, interim) => updates.push({ text, interim }),
      onError: (m) => errors.push(m),
      onStateChange: (s) => states.push(s),
    },
    FakeRecognition as never,
  )
  d.start(existing)
  const shown = () => {
    const u = updates[updates.length - 1]
    return u ? joinText(u.text, u.interim) : existing
  }
  return { d, updates, states, errors, shown }
}

beforeEach(() => {
  FakeRecognition.reset()
  vi.useFakeTimers()
})
afterEach(() => vi.useRealTimers())

describe('Dictation', () => {
  it('keeps recording across the pauses where the browser ends a session', async () => {
    const { d, shown } = setup()
    const s1 = FakeRecognition.last
    expect(s1.continuous).toBe(true)
    s1.final('hello I am searching')
    s1.end() // Chrome stops by itself after a pause
    await vi.advanceTimersByTimeAsync(200)
    expect(FakeRecognition.instances).toHaveLength(2) // restarted automatically
    FakeRecognition.last.final('for a software engineer role')
    expect(shown()).toBe('hello I am searching for a software engineer role')
    FakeRecognition.last.error('no-speech') // long silence: not an error for the user
    FakeRecognition.last.end()
    await vi.advanceTimersByTimeAsync(200)
    FakeRecognition.last.final('where I can build backend systems')
    const done = d.stop()
    await vi.advanceTimersByTimeAsync(100)
    expect(await done).toBe(
      'hello I am searching for a software engineer role where I can build backend systems',
    )
  })

  it('waits for the words still being processed when stopping', async () => {
    const { d } = setup()
    const s = FakeRecognition.last
    s.final('I improved the API latency')
    s.interim('by adding')
    s.pendingOnStop = 'by adding an index and a cache'
    const done = d.stop()
    await vi.advanceTimersByTimeAsync(100)
    expect(await done).toBe('I improved the API latency by adding an index and a cache')
  })

  it('keeps unconfirmed words when a session ends without finalizing them', async () => {
    const { d } = setup()
    FakeRecognition.last.interim('quality assurance testing')
    FakeRecognition.last.end()
    await vi.advanceTimersByTimeAsync(200)
    const done = d.stop()
    await vi.advanceTimersByTimeAsync(100)
    expect(await done).toBe('quality assurance testing')
  })

  it('does not duplicate words when the browser repeats the result list', () => {
    const { shown } = setup()
    const s = FakeRecognition.last
    s.final('one two')
    s.final('three')
    s.final('four') // each event carries the whole list
    expect(shown()).toBe('one two three four')
  })

  it('keeps earlier phrases when the browser starts a new result list after a pause', async () => {
    const { d, shown } = setup()
    const s = FakeRecognition.last
    s.resetsAfterFinal = true
    s.final('I worked on a payments service')
    s.interim('where I')
    expect(shown()).toBe('I worked on a payments service where I')
    s.final('where I reduced latency')
    s.final('by forty percent')
    s.pendingOnStop = 'using caching'
    const done = d.stop()
    await vi.advanceTimersByTimeAsync(100)
    expect(await done).toBe(
      'I worked on a payments service where I reduced latency by forty percent using caching',
    )
  })

  it('appends to text that was already in the answer box', async () => {
    const { d } = setup('I typed this first.')
    FakeRecognition.last.final('then I spoke this')
    const done = d.stop()
    await vi.advanceTimersByTimeAsync(100)
    expect(await done).toBe('I typed this first. then I spoke this')
  })

  it('ignores results that arrive after the recording was cancelled', async () => {
    const { d, updates } = setup()
    const s = FakeRecognition.last
    s.final('first answer')
    d.cancel()
    const count = updates.length
    s.final('quality') // late result from the old session
    s.end()
    await vi.advanceTimersByTimeAsync(500)
    expect(updates).toHaveLength(count)
    expect(FakeRecognition.instances).toHaveLength(1) // no restart either
  })

  it('stops and reports permission errors instead of restarting', async () => {
    const { errors, states } = setup()
    FakeRecognition.last.error('not-allowed')
    FakeRecognition.last.end()
    await vi.advanceTimersByTimeAsync(500)
    expect(errors[0]).toMatch(/Microphone permission was denied/)
    expect(states[states.length - 1]).toBe('idle')
    expect(FakeRecognition.instances).toHaveLength(1)
  })

  it('gives up instead of spinning when the browser keeps ending immediately', async () => {
    const { errors, states } = setup()
    for (let i = 0; i < 20; i++) {
      FakeRecognition.last.end()
      await vi.advanceTimersByTimeAsync(150)
    }
    expect(errors[0]).toMatch(/keeps stopping/)
    expect(states[states.length - 1]).toBe('idle')
    expect(FakeRecognition.instances.length).toBeLessThanOrEqual(9)
  })

  it('resolves stop() even if the browser never sends "end"', async () => {
    const { d } = setup()
    const s = FakeRecognition.last
    s.final('stuck session')
    s.stop = () => {} // browser bug: never ends
    const done = d.stop(500)
    await vi.advanceTimersByTimeAsync(600)
    expect(await done).toBe('stuck session')
  })
})
