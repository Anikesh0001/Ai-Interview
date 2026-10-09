import { Link } from 'react-router-dom'
import { useHealth } from './HealthContext'
import { cn } from '../lib/cn'

export function StatusPill({ className = 'inline-flex' }: { className?: string }) {
  const { health, error } = useHealth()
  let dot = 'bg-zinc-400'
  let text = 'Checking…'
  let title = ''
  if (error) {
    dot = 'bg-rose-500'
    text = 'Server offline'
    title = error
  } else if (health) {
    if (health.llm === 'ok') {
      dot = 'bg-emerald-500'
      text = `Local AI · ${health.model}`
    } else if (health.test_mode) {
      dot = 'bg-sky-500'
      text = 'Test mode · offline engine'
    } else {
      dot = 'bg-amber-500'
      text = 'Offline engine'
    }
    title = health.llm_detail
  }
  return (
    <Link
      to="/settings"
      title={title}
      className={cn(
        'items-center gap-2 rounded-full border border-zinc-200 bg-white px-2.5 py-1 text-xs text-zinc-600 hover:bg-zinc-50 dark:border-zinc-800 dark:bg-zinc-900 dark:text-zinc-300 dark:hover:bg-zinc-800',
        className,
      )}
    >
      <span className={cn('size-1.5 rounded-full', dot)} aria-hidden />
      <span className="truncate">{text}</span>
    </Link>
  )
}
