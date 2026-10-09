import { render } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import type { ReactElement } from 'react'
import { vi } from 'vitest'
import { HealthProvider } from '../components/HealthContext'

type Handler = (init: RequestInit | undefined, url: string) => unknown | Response
export interface MockRoute {
  method?: string
  path: string | RegExp
  respond: Handler | unknown
  status?: number
}

/** Install a fetch mock that answers /api routes; returns the vi.fn for call assertions. */
export function mockApi(routes: MockRoute[]) {
  const fn = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const url = typeof input === 'string' ? input : input.toString()
    const method = (init?.method ?? 'GET').toUpperCase()
    const path = url.replace(/^\/api/, '')
    const route = routes.find(
      (r) =>
        (r.method ?? 'GET') === method && (typeof r.path === 'string' ? r.path === path : r.path.test(path)),
    )
    if (!route)
      return new Response(JSON.stringify({ detail: `No mock for ${method} ${path}` }), {
        status: 404,
        headers: { 'content-type': 'application/json' },
      })
    const body = typeof route.respond === 'function' ? (route.respond as Handler)(init, url) : route.respond
    if (body instanceof Response) return body
    if (route.status === 204) return new Response(null, { status: 204 })
    return new Response(JSON.stringify(body), {
      status: route.status ?? 200,
      headers: { 'content-type': 'application/json' },
    })
  })
  vi.stubGlobal('fetch', fn)
  return fn
}

export function renderAt(
  path: string,
  routePath: string,
  element: ReactElement,
  extra: { path: string; element: ReactElement }[] = [],
) {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <HealthProvider>
        <Routes>
          <Route path={routePath} element={element} />
          {extra.map((r) => (
            <Route key={r.path} path={r.path} element={r.element} />
          ))}
        </Routes>
      </HealthProvider>
    </MemoryRouter>,
  )
}

export const health = {
  status: 'ok',
  application: 'ok',
  database: 'ok',
  resume_parser: 'ok',
  llm: 'disabled',
  llm_provider: 'none',
  ollama_server: 'disabled',
  ollama_model: 'unknown',
  model: '',
  llm_detail: 'Test mode',
  installed_models: [],
  test_mode: true,
  voice_enabled: true,
  version: '1.0.0',
}
