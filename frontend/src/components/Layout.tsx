import { useState } from 'react'
import { NavLink, Outlet, useLocation } from 'react-router-dom'
import { FileText, History, LayoutDashboard, Menu, Mic, Settings, X } from 'lucide-react'
import { Logo } from './Logo'
import { ThemeToggle } from './ThemeToggle'
import { StatusPill } from './StatusPill'
import { cn } from '../lib/cn'

const NAV = [
  { to: '/dashboard', label: 'Dashboard', icon: LayoutDashboard },
  { to: '/resume', label: 'Resume analysis', icon: FileText },
  { to: '/interview/setup', label: 'Mock interview', icon: Mic },
  { to: '/history', label: 'History', icon: History },
  { to: '/settings', label: 'Settings', icon: Settings },
]

function NavItems({ onNavigate }: { onNavigate?: () => void }) {
  return (
    <nav aria-label="Main" className="flex flex-col gap-0.5">
      {NAV.map(({ to, label, icon: Icon }) => (
        <NavLink
          key={to}
          to={to}
          onClick={onNavigate}
          className={({ isActive }) =>
            cn(
              'flex items-center gap-2.5 rounded-md px-3 py-2 text-sm font-medium transition-colors',
              isActive
                ? 'bg-zinc-100 text-zinc-900 dark:bg-zinc-800 dark:text-white'
                : 'text-zinc-600 hover:bg-zinc-50 hover:text-zinc-900 dark:text-zinc-400 dark:hover:bg-zinc-800/60 dark:hover:text-white',
            )
          }
        >
          <Icon className="size-4" aria-hidden />
          {label}
        </NavLink>
      ))}
    </nav>
  )
}

export function AppLayout() {
  const [open, setOpen] = useState(false)
  const loc = useLocation()
  const immersive = /^\/interview\/(?!setup)[^/]+$/.test(loc.pathname)
  return (
    <div className="min-h-screen">
      <a
        href="#main"
        className="sr-only focus:not-sr-only focus:absolute focus:top-2 focus:left-2 focus:z-50 focus:rounded focus:bg-white focus:px-3 focus:py-2"
      >
        Skip to content
      </a>
      {/* Desktop sidebar */}
      <aside
        className={cn(
          'no-print fixed inset-y-0 left-0 z-30 hidden w-60 flex-col border-r border-zinc-200 bg-white px-3 py-4 dark:border-zinc-800 dark:bg-zinc-900',
          !immersive && 'lg:flex',
        )}
      >
        <NavLinkHome />
        <div className="mt-6 flex-1">
          <NavItems />
        </div>
        <div className="space-y-3 border-t border-zinc-100 pt-3 dark:border-zinc-800">
          <StatusPill className="flex w-full" />
          <div className="flex items-center justify-between px-1 text-xs text-zinc-500">
            <span>Private · runs locally</span>
            <ThemeToggle />
          </div>
        </div>
      </aside>

      {/* Top bar (mobile, and immersive interview room) */}
      <header
        className={cn(
          'no-print sticky top-0 z-20 flex h-14 items-center justify-between border-b border-zinc-200 bg-white/90 px-4 backdrop-blur dark:border-zinc-800 dark:bg-zinc-900/90',
          !immersive && 'lg:hidden',
        )}
      >
        <NavLinkHome />
        <div className="flex items-center gap-1">
          <StatusPill className="hidden sm:inline-flex" />
          <ThemeToggle />
          <button
            type="button"
            className="inline-flex size-9 items-center justify-center rounded-md hover:bg-zinc-100 dark:hover:bg-zinc-800"
            aria-label={open ? 'Close menu' : 'Open menu'}
            aria-expanded={open}
            onClick={() => setOpen((o) => !o)}
          >
            {open ? <X className="size-5" /> : <Menu className="size-5" />}
          </button>
        </div>
      </header>
      {open && (
        <div
          className={cn(
            'no-print fixed inset-x-0 top-14 z-20 border-b border-zinc-200 bg-white p-3 shadow-lg dark:border-zinc-800 dark:bg-zinc-900',
            !immersive && 'lg:hidden',
          )}
        >
          <NavItems onNavigate={() => setOpen(false)} />
        </div>
      )}

      <main id="main" className={cn('px-4 py-6 sm:px-6 lg:py-8', !immersive && 'lg:pl-68')}>
        <div className={cn('mx-auto', immersive ? 'max-w-6xl' : 'max-w-6xl')}>
          <Outlet />
        </div>
      </main>
    </div>
  )
}

function NavLinkHome() {
  return (
    <NavLink to="/" className="rounded-md px-1" aria-label="InterviewForge home">
      <Logo />
    </NavLink>
  )
}
