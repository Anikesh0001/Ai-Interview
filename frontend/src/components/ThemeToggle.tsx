import { Moon, Sun } from 'lucide-react'
import { useState } from 'react'
import { KEYS } from '../lib/storage'

export function ThemeToggle({ className = '' }: { className?: string }) {
  const [dark, setDark] = useState(() => document.documentElement.classList.contains('dark'))
  const toggle = () => {
    const next = !dark
    document.documentElement.classList.toggle('dark', next)
    // stored as a raw string because index.html reads it before React loads
    try {
      localStorage.setItem(KEYS.theme, next ? 'dark' : 'light')
    } catch {
      /* ignore */
    }
    setDark(next)
  }
  return (
    <button
      type="button"
      onClick={toggle}
      aria-label={dark ? 'Switch to light theme' : 'Switch to dark theme'}
      className={`inline-flex size-9 items-center justify-center rounded-md text-zinc-600 hover:bg-zinc-100 dark:text-zinc-300 dark:hover:bg-zinc-800 ${className}`}
    >
      {dark ? <Sun className="size-4" /> : <Moon className="size-4" />}
    </button>
  )
}
