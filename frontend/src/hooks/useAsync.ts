import { useCallback, useEffect, useRef, useState } from 'react'
import { errorMessage } from '../lib/api'

export interface AsyncState<T> {
  data: T | null
  error: string | null
  loading: boolean
  reload: () => void
  setData: (d: T | null) => void
}

interface Result<T> {
  key: string
  data: T | null
  error: string | null
}

/** Load data on mount (and when deps change); exposes loading/error/reload. */
export function useAsync<T>(fn: () => Promise<T>, deps: unknown[] = []): AsyncState<T> {
  const [tick, setTick] = useState(0)
  const [result, setResult] = useState<Result<T> | null>(null)
  const fnRef = useRef(fn)
  const key = JSON.stringify([tick, ...deps])

  useEffect(() => {
    fnRef.current = fn
  })

  useEffect(() => {
    let alive = true
    fnRef
      .current()
      .then((data) => alive && setResult({ key, data, error: null }))
      .catch((e) => alive && setResult({ key, data: null, error: errorMessage(e) }))
    return () => {
      alive = false
    }
  }, [key])

  const reload = useCallback(() => setTick((t) => t + 1), [])
  const setData = useCallback((d: T | null) => setResult({ key, data: d, error: null }), [key])
  return {
    data: result?.data ?? null,
    error: result?.key === key ? result.error : null,
    loading: result?.key !== key && result === null,
    reload,
    setData,
  }
}
