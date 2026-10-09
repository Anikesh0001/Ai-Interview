import { describe, expect, it } from 'vitest'
import { classify, fmtClock, fmtDuration, fmtScore, scoreTone } from './format'

describe('format helpers', () => {
  it('classifies scores into the documented bands', () => {
    expect(classify(95)).toBe('Excellent')
    expect(classify(85)).toBe('Strong')
    expect(classify(72)).toBe('Good')
    expect(classify(65)).toBe('Needs Improvement')
    expect(classify(10)).toBe('Weak')
    expect(classify(null)).toBe('Not scored')
  })
  it('formats scores, clocks and durations', () => {
    expect(fmtScore(83.6)).toBe('84')
    expect(fmtScore(null)).toBe('—')
    expect(fmtClock(75)).toBe('01:15')
    expect(fmtDuration(125)).toBe('2m 05s')
    expect(scoreTone(undefined)).toBe('none')
  })
})
