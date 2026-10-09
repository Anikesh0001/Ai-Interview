import type { ButtonHTMLAttributes, ReactNode } from 'react'
import { AlertTriangle, CheckCircle2, Info, Loader2, XCircle } from 'lucide-react'
import { cn } from '../lib/cn'

type Variant = 'primary' | 'secondary' | 'ghost' | 'danger'
const variants: Record<Variant, string> = {
  primary:
    'bg-indigo-600 text-white hover:bg-indigo-500 shadow-sm disabled:bg-indigo-400 dark:disabled:bg-indigo-800',
  secondary:
    'bg-white text-zinc-800 border border-zinc-300 hover:bg-zinc-50 shadow-sm dark:bg-zinc-900 dark:text-zinc-100 dark:border-zinc-700 dark:hover:bg-zinc-800',
  ghost: 'text-zinc-700 hover:bg-zinc-100 dark:text-zinc-300 dark:hover:bg-zinc-800',
  danger: 'bg-rose-600 text-white hover:bg-rose-500 shadow-sm',
}

export function Button({
  variant = 'primary',
  size = 'md',
  loading = false,
  className,
  children,
  disabled,
  ...rest
}: ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: Variant
  size?: 'sm' | 'md' | 'lg'
  loading?: boolean
}) {
  const sizes = { sm: 'h-8 px-3 text-sm', md: 'h-10 px-4 text-sm', lg: 'h-12 px-5 text-base' }
  return (
    <button
      {...rest}
      disabled={disabled || loading}
      className={cn(
        'inline-flex items-center justify-center gap-2 rounded-md font-medium transition-colors disabled:cursor-not-allowed',
        variants[variant],
        sizes[size],
        className,
      )}
    >
      {loading && <Loader2 className="size-4 animate-spin" aria-hidden />}
      {children}
    </button>
  )
}

export function Card({
  className,
  children,
  ...rest
}: { className?: string; children: ReactNode } & React.HTMLAttributes<HTMLElement>) {
  return (
    <section
      {...rest}
      className={cn(
        'rounded-lg border border-zinc-200 bg-white shadow-sm dark:border-zinc-800 dark:bg-zinc-900',
        className,
      )}
    >
      {children}
    </section>
  )
}

export function CardHeader({
  title,
  subtitle,
  action,
  id,
}: {
  title: ReactNode
  subtitle?: ReactNode
  action?: ReactNode
  id?: string
}) {
  return (
    <div className="flex items-start justify-between gap-4 border-b border-zinc-100 px-5 py-4 dark:border-zinc-800">
      <div className="min-w-0">
        <h2 id={id} className="text-sm font-semibold text-zinc-900 dark:text-zinc-100">
          {title}
        </h2>
        {subtitle && <p className="mt-0.5 text-sm text-zinc-500 dark:text-zinc-400">{subtitle}</p>}
      </div>
      {action}
    </div>
  )
}

const badgeTones = {
  neutral: 'bg-zinc-100 text-zinc-700 ring-zinc-200 dark:bg-zinc-800 dark:text-zinc-300 dark:ring-zinc-700',
  green:
    'bg-emerald-50 text-emerald-700 ring-emerald-200 dark:bg-emerald-500/10 dark:text-emerald-300 dark:ring-emerald-500/30',
  red: 'bg-rose-50 text-rose-700 ring-rose-200 dark:bg-rose-500/10 dark:text-rose-300 dark:ring-rose-500/30',
  amber:
    'bg-amber-50 text-amber-800 ring-amber-200 dark:bg-amber-500/10 dark:text-amber-300 dark:ring-amber-500/30',
  blue: 'bg-sky-50 text-sky-700 ring-sky-200 dark:bg-sky-500/10 dark:text-sky-300 dark:ring-sky-500/30',
  indigo:
    'bg-indigo-50 text-indigo-700 ring-indigo-200 dark:bg-indigo-500/10 dark:text-indigo-300 dark:ring-indigo-500/30',
}
export type BadgeTone = keyof typeof badgeTones

export function Badge({
  tone = 'neutral',
  children,
  className,
}: {
  tone?: BadgeTone
  children: ReactNode
  className?: string
}) {
  return (
    <span
      className={cn(
        'inline-flex items-center gap-1 rounded-md px-2 py-0.5 text-xs font-medium ring-1 ring-inset',
        badgeTones[tone],
        className,
      )}
    >
      {children}
    </span>
  )
}

const alertStyles = {
  info: {
    cls: 'border-sky-200 bg-sky-50 text-sky-900 dark:border-sky-500/30 dark:bg-sky-500/10 dark:text-sky-200',
    Icon: Info,
  },
  success: {
    cls: 'border-emerald-200 bg-emerald-50 text-emerald-900 dark:border-emerald-500/30 dark:bg-emerald-500/10 dark:text-emerald-200',
    Icon: CheckCircle2,
  },
  warning: {
    cls: 'border-amber-200 bg-amber-50 text-amber-900 dark:border-amber-500/30 dark:bg-amber-500/10 dark:text-amber-200',
    Icon: AlertTriangle,
  },
  error: {
    cls: 'border-rose-200 bg-rose-50 text-rose-900 dark:border-rose-500/30 dark:bg-rose-500/10 dark:text-rose-200',
    Icon: XCircle,
  },
}

export function Alert({
  tone = 'info',
  title,
  children,
  action,
  className,
}: {
  tone?: keyof typeof alertStyles
  title?: ReactNode
  children?: ReactNode
  action?: ReactNode
  className?: string
}) {
  const { cls, Icon } = alertStyles[tone]
  return (
    <div
      role={tone === 'error' ? 'alert' : 'status'}
      className={cn('flex gap-3 rounded-lg border px-4 py-3 text-sm', cls, className)}
    >
      <Icon className="mt-0.5 size-4 shrink-0" aria-hidden />
      <div className="min-w-0 flex-1">
        {title && <p className="font-medium">{title}</p>}
        {children && <div className={cn(title ? 'mt-0.5' : '', 'opacity-90')}>{children}</div>}
      </div>
      {action}
    </div>
  )
}

export function Skeleton({ className }: { className?: string }) {
  return (
    <div aria-hidden className={cn('animate-pulse rounded-md bg-zinc-200/80 dark:bg-zinc-800', className)} />
  )
}

export function PageSkeleton() {
  return (
    <div className="space-y-4" aria-busy="true" aria-label="Loading">
      <Skeleton className="h-8 w-56" />
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        {[0, 1, 2, 3].map((i) => (
          <Skeleton key={i} className="h-28" />
        ))}
      </div>
      <Skeleton className="h-64" />
    </div>
  )
}

export function EmptyState({
  icon,
  title,
  children,
  action,
}: {
  icon: ReactNode
  title: string
  children?: ReactNode
  action?: ReactNode
}) {
  return (
    <div className="flex flex-col items-center justify-center px-6 py-12 text-center">
      <div className="mb-3 flex size-11 items-center justify-center rounded-full bg-zinc-100 text-zinc-500 dark:bg-zinc-800 dark:text-zinc-400">
        {icon}
      </div>
      <h3 className="text-sm font-semibold">{title}</h3>
      {children && <p className="mt-1 max-w-sm text-sm text-zinc-500 dark:text-zinc-400">{children}</p>}
      {action && <div className="mt-4">{action}</div>}
    </div>
  )
}

export function PageHeader({
  title,
  description,
  actions,
}: {
  title: string
  description?: ReactNode
  actions?: ReactNode
}) {
  return (
    <div className="mb-6 flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">{title}</h1>
        {description && <p className="mt-1 text-sm text-zinc-500 dark:text-zinc-400">{description}</p>}
      </div>
      {actions && <div className="flex flex-wrap gap-2">{actions}</div>}
    </div>
  )
}

export function Field({
  label,
  htmlFor,
  hint,
  children,
}: {
  label: string
  htmlFor: string
  hint?: ReactNode
  children: ReactNode
}) {
  return (
    <div>
      <label htmlFor={htmlFor} className="mb-1.5 block text-sm font-medium text-zinc-800 dark:text-zinc-200">
        {label}
      </label>
      {children}
      {hint && <p className="mt-1 text-xs text-zinc-500 dark:text-zinc-400">{hint}</p>}
    </div>
  )
}

export function Chip({ children, tone = 'neutral' }: { children: ReactNode; tone?: BadgeTone }) {
  return <Badge tone={tone}>{children}</Badge>
}

export function SectionTitle({ children, id }: { children: ReactNode; id?: string }) {
  return (
    <h2 id={id} className="mb-3 text-base font-semibold tracking-tight">
      {children}
    </h2>
  )
}
