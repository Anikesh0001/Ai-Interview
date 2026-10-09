import { afterEach, describe, expect, it, vi } from 'vitest'
import { api, ApiError } from './api'

afterEach(() => vi.unstubAllGlobals())

describe('api client', () => {
  it('surfaces the server detail message', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(
        async () =>
          new Response(JSON.stringify({ detail: 'Your PDF appears to be scanned/image-based.' }), {
            status: 422,
            headers: { 'content-type': 'application/json' },
          }),
      ),
    )
    await expect(api.health()).rejects.toThrow('scanned/image-based')
  })
  it('turns network failures into a friendly message', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(async () => {
        throw new TypeError('Failed to fetch')
      }),
    )
    const err = await api.health().catch((e) => e)
    expect(err).toBeInstanceOf(ApiError)
    expect(err.message).toMatch(/Cannot reach the InterviewForge server/)
  })
  it('never exposes raw server errors for 500s', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(async () => new Response('Traceback (most recent call last)', { status: 500 })),
    )
    const err = await api.health().catch((e) => e)
    expect(err.message).not.toMatch(/Traceback/)
  })
})
