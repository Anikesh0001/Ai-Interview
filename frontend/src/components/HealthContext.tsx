import { createContext, useContext, type ReactNode } from 'react'
import { api } from '../lib/api'
import type { Health } from '../lib/types'
import { useAsync } from '../hooks/useAsync'

interface HealthCtx {
  health: Health | null
  error: string | null
  reload: () => void
}

const Ctx = createContext<HealthCtx>({ health: null, error: null, reload: () => {} })

export function HealthProvider({ children }: { children: ReactNode }) {
  const { data, error, reload } = useAsync(() => api.health(), [])
  return <Ctx.Provider value={{ health: data, error, reload }}>{children}</Ctx.Provider>
}

// eslint-disable-next-line react-refresh/only-export-components
export const useHealth = () => useContext(Ctx)
