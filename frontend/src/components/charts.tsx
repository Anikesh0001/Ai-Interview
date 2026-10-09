import { useId, useState } from 'react'
import { classify, fmtDate, fmtScore, scoreTone, toneBg, toneStroke } from '../lib/format'
import { cn } from '../lib/cn'

/** Circular meter: the fill carries severity, the number stays in ink, the label names the band. */
export function ScoreRing({
  score,
  label,
  size = 112,
  sublabel,
}: {
  score: number | null | undefined
  label: string
  size?: number
  sublabel?: string
}) {
  const stroke = 8
  const r = (size - stroke) / 2
  const c = 2 * Math.PI * r
  const value = score ?? 0
  const tone = scoreTone(score)
  return (
    <figure
      className="flex flex-col items-center gap-2"
      aria-label={`${label}: ${fmtScore(score)} out of 100`}
    >
      <div className="relative" style={{ width: size, height: size }}>
        <svg width={size} height={size} className="-rotate-90" aria-hidden>
          <circle
            cx={size / 2}
            cy={size / 2}
            r={r}
            fill="none"
            strokeWidth={stroke}
            className="stroke-zinc-100 dark:stroke-zinc-800"
          />
          {score !== null && score !== undefined && (
            <circle
              cx={size / 2}
              cy={size / 2}
              r={r}
              fill="none"
              strokeWidth={stroke}
              strokeLinecap="round"
              strokeDasharray={`${(c * Math.max(0, Math.min(100, value))) / 100} ${c}`}
              className={cn(toneStroke[tone], 'transition-[stroke-dasharray] duration-700')}
            />
          )}
        </svg>
        <div className="absolute inset-0 flex flex-col items-center justify-center">
          <span className="text-2xl font-semibold tracking-tight" style={{ fontSize: size > 100 ? 28 : 20 }}>
            {fmtScore(score)}
          </span>
          {score !== null && score !== undefined && <span className="text-[10px] text-zinc-500">/ 100</span>}
        </div>
      </div>
      <figcaption className="text-center">
        <div className="text-sm font-medium">{label}</div>
        <div className="text-xs text-zinc-500 dark:text-zinc-400">{sublabel ?? classify(score)}</div>
      </figcaption>
    </figure>
  )
}

/** Horizontal meter bar with label and value. */
export function ScoreBar({
  label,
  score,
  detail,
  weight,
}: {
  label: string
  score: number | null | undefined
  detail?: string
  weight?: number
}) {
  const tone = scoreTone(score)
  return (
    <div className="group" title={detail}>
      <div className="mb-1 flex items-baseline justify-between gap-3 text-sm">
        <span className="truncate text-zinc-700 dark:text-zinc-300">
          {label}
          {weight !== undefined && weight > 0 && (
            <span className="ml-1.5 text-xs text-zinc-400">{Math.round(weight * 100)}%</span>
          )}
        </span>
        <span className="font-medium tabular-nums">{fmtScore(score)}</span>
      </div>
      <div
        className="h-1.5 overflow-hidden rounded-full bg-zinc-100 dark:bg-zinc-800"
        role="meter"
        aria-label={label}
        aria-valuemin={0}
        aria-valuemax={100}
        aria-valuenow={score ?? 0}
      >
        <div
          className={cn('h-full rounded-full transition-[width] duration-700', toneBg[tone])}
          style={{ width: `${Math.max(0, Math.min(100, score ?? 0))}%` }}
        />
      </div>
      {detail && <p className="mt-1 text-xs text-zinc-500 dark:text-zinc-400">{detail}</p>}
    </div>
  )
}

/** Radar chart of 0-10 dimension averages, with a hover readout. */
export function RadarChart({ items }: { items: { label: string; score: number | null }[] }) {
  const [hover, setHover] = useState<number | null>(null)
  const size = 280
  const cx = size / 2
  const cy = size / 2
  const R = 92
  const n = items.length
  if (n < 3) return null
  const pt = (i: number, v: number) => {
    const a = (Math.PI * 2 * i) / n - Math.PI / 2
    return [cx + Math.cos(a) * R * v, cy + Math.sin(a) * R * v] as const
  }
  const poly = items.map((it, i) => pt(i, Math.max(0, Math.min(10, it.score ?? 0)) / 10).join(',')).join(' ')
  return (
    <div className="relative mx-auto w-full max-w-[400px]">
      <svg
        viewBox={`0 0 ${size} ${size}`}
        className="w-full"
        role="img"
        aria-label="Answer quality by dimension"
      >
        {[0.25, 0.5, 0.75, 1].map((f) => (
          <polygon
            key={f}
            points={items.map((_, i) => pt(i, f).join(',')).join(' ')}
            className="fill-none stroke-zinc-200 dark:stroke-zinc-800"
            strokeWidth={1}
          />
        ))}
        {items.map((_, i) => {
          const [x, y] = pt(i, 1)
          return (
            <line key={i} x1={cx} y1={cy} x2={x} y2={y} className="stroke-zinc-200 dark:stroke-zinc-800" />
          )
        })}
        <polygon
          points={poly}
          className="fill-[#2a78d6]/15 stroke-[#2a78d6] dark:fill-[#3987e5]/20 dark:stroke-[#3987e5]"
          strokeWidth={2}
          strokeLinejoin="round"
        />
        {items.map((it, i) => {
          const [x, y] = pt(i, Math.max(0, Math.min(10, it.score ?? 0)) / 10)
          const [lx, ly] = pt(i, 1.2)
          const anchor = Math.abs(lx - cx) < 8 ? 'middle' : lx > cx ? 'start' : 'end'
          return (
            <g key={it.label} onMouseEnter={() => setHover(i)} onMouseLeave={() => setHover(null)}>
              <circle cx={x} cy={y} r={14} fill="transparent" />
              <circle
                cx={x}
                cy={y}
                r={4}
                className="fill-[#2a78d6] stroke-white dark:fill-[#3987e5] dark:stroke-zinc-900"
                strokeWidth={2}
              />
              <text
                x={lx}
                y={ly}
                textAnchor={anchor}
                dominantBaseline="middle"
                className="fill-zinc-500 text-[10px] dark:fill-zinc-400"
              >
                {it.label}
              </text>
            </g>
          )
        })}
      </svg>
      {hover !== null && (
        <div className="pointer-events-none absolute top-1 left-1/2 -translate-x-1/2 rounded-md border border-zinc-200 bg-white px-2.5 py-1.5 text-xs shadow-md dark:border-zinc-700 dark:bg-zinc-900">
          <span className="text-zinc-500">{items[hover].label}</span>{' '}
          <span className="font-semibold">{items[hover].score?.toFixed(1) ?? '—'} / 10</span>
        </div>
      )}
    </div>
  )
}

const SERIES = [
  {
    key: 'interview',
    label: 'Interview',
    cls: 'stroke-[#2a78d6] dark:stroke-[#3987e5]',
    dot: 'fill-[#2a78d6] dark:fill-[#3987e5]',
    swatch: 'bg-[#2a78d6] dark:bg-[#3987e5]',
  },
  {
    key: 'readiness',
    label: 'Readiness',
    cls: 'stroke-[#eb6834] dark:stroke-[#d95926]',
    dot: 'fill-[#eb6834] dark:fill-[#d95926]',
    swatch: 'bg-[#eb6834] dark:bg-[#d95926]',
  },
] as const

type TrendPoint = {
  id: string
  date: string | null
  interview: number | null
  readiness: number | null
  role: string
}

/** Score trend over completed interviews: one 0-100 axis, two series, legend + end labels + hover. */
export function TrendChart({ points }: { points: TrendPoint[] }) {
  const [hover, setHover] = useState<number | null>(null)
  const clipId = useId()
  const W = 640
  const H = 220
  const pad = { l: 32, r: 96, t: 12, b: 28 }
  const iw = W - pad.l - pad.r
  const ih = H - pad.t - pad.b
  const x = (i: number) => pad.l + (points.length <= 1 ? iw / 2 : (iw * i) / (points.length - 1))
  const y = (v: number) => pad.t + ih - (ih * v) / 100
  const pathFor = (key: 'interview' | 'readiness') =>
    points
      .map((p, i) => (p[key] === null ? null : `${x(i)},${y(p[key] as number)}`))
      .filter(Boolean)
      .map((s, i) => (i === 0 ? `M${s}` : `L${s}`))
      .join(' ')
  const last = points[points.length - 1]
  return (
    <div>
      <div className="mb-2 flex gap-4 text-xs text-zinc-600 dark:text-zinc-400" aria-hidden>
        {SERIES.map((s) => (
          <span key={s.key} className="inline-flex items-center gap-1.5">
            <span className={cn('inline-block h-0.5 w-4 rounded', s.swatch)} />
            {s.label}
          </span>
        ))}
      </div>
      <div className="relative">
        <svg
          viewBox={`0 0 ${W} ${H}`}
          className="w-full"
          role="img"
          aria-label="Interview and readiness scores over time"
        >
          <defs>
            <clipPath id={clipId}>
              <rect x={0} y={0} width={W} height={H} />
            </clipPath>
          </defs>
          {[0, 25, 50, 75, 100].map((v) => (
            <g key={v}>
              <line
                x1={pad.l}
                x2={W - pad.r}
                y1={y(v)}
                y2={y(v)}
                className="stroke-zinc-100 dark:stroke-zinc-800"
              />
              <text
                x={pad.l - 8}
                y={y(v)}
                textAnchor="end"
                dominantBaseline="middle"
                className="fill-zinc-400 text-[10px]"
              >
                {v}
              </text>
            </g>
          ))}
          {points.map((p, i) =>
            points.length <= 8 || i % Math.ceil(points.length / 8) === 0 ? (
              <text key={p.id} x={x(i)} y={H - 8} textAnchor="middle" className="fill-zinc-400 text-[10px]">
                {fmtDate(p.date).replace(/, \d{4}$/, '')}
              </text>
            ) : null,
          )}
          {hover !== null && (
            <line
              x1={x(hover)}
              x2={x(hover)}
              y1={pad.t}
              y2={pad.t + ih}
              className="stroke-zinc-300 dark:stroke-zinc-600"
            />
          )}
          <g clipPath={`url(#${clipId})`}>
            {SERIES.map((s) => (
              <path
                key={s.key}
                d={pathFor(s.key)}
                fill="none"
                strokeWidth={2}
                strokeLinejoin="round"
                strokeLinecap="round"
                className={s.cls}
              />
            ))}
            {SERIES.map((s) =>
              points.map((p, i) =>
                p[s.key] === null ? null : (
                  <circle
                    key={`${s.key}-${p.id}`}
                    cx={x(i)}
                    cy={y(p[s.key] as number)}
                    r={4}
                    strokeWidth={2}
                    className={cn(s.dot, 'stroke-white dark:stroke-zinc-900')}
                  />
                ),
              ),
            )}
          </g>
          {last &&
            SERIES.map((s, si) => {
              const v = last[s.key]
              if (v === null) return null
              const other = last[SERIES[1 - si].key]
              const nudge = other !== null && Math.abs(y(v) - y(other)) < 12 ? (v >= other ? -7 : 7) : 0
              return (
                <text
                  key={s.key}
                  x={x(points.length - 1) + 10}
                  y={y(v) + nudge}
                  dominantBaseline="middle"
                  className="fill-zinc-600 text-[11px] dark:fill-zinc-300"
                >
                  {s.label} {Math.round(v)}
                </text>
              )
            })}
          {points.map((p, i) => (
            <rect
              key={p.id}
              x={x(i) - iw / Math.max(2, points.length) / 2}
              y={pad.t}
              width={iw / Math.max(2, points.length)}
              height={ih}
              fill="transparent"
              onMouseEnter={() => setHover(i)}
              onMouseLeave={() => setHover(null)}
            />
          ))}
        </svg>
        {hover !== null && (
          <div
            className="pointer-events-none absolute top-0 rounded-md border border-zinc-200 bg-white px-3 py-2 text-xs shadow-md dark:border-zinc-700 dark:bg-zinc-900"
            style={{
              left: `${(x(hover) / W) * 100}%`,
              transform: `translateX(${hover > points.length / 2 ? '-105%' : '5%'})`,
            }}
          >
            <div className="mb-1 font-medium">
              {fmtDate(points[hover].date)} · {points[hover].role}
            </div>
            {SERIES.map((s) => (
              <div key={s.key} className="flex items-center gap-2">
                <span className={cn('inline-block size-2 rounded-full', s.swatch)} />
                <span className="text-zinc-500">{s.label}</span>
                <span className="ml-auto pl-3 font-medium">{fmtScore(points[hover][s.key])}</span>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}

/** Per-question score timeline: thin columns, follow-ups marked, hover readout. */
export function QuestionTimeline({
  items,
}: {
  items: { number: number; score: number; classification: string; category: string; is_follow_up: boolean }[]
}) {
  const [hover, setHover] = useState<number | null>(null)
  return (
    <div className="relative">
      <div className="flex h-28 items-end gap-[2px]" role="img" aria-label="Score for each question in order">
        {items.map((it, i) => (
          <div
            key={i}
            className="relative flex h-full flex-1 items-end"
            onMouseEnter={() => setHover(i)}
            onMouseLeave={() => setHover(null)}
          >
            <div
              className={cn(
                'w-full rounded-t-[4px]',
                toneBg[scoreTone(it.score)],
                it.is_follow_up && 'opacity-60',
              )}
              style={{ height: `${Math.max(3, it.score)}%` }}
            />
          </div>
        ))}
      </div>
      <div className="mt-1 flex gap-[2px] text-[10px] text-zinc-400">
        {items.map((it, i) => (
          <div key={i} className="flex-1 text-center">
            {it.is_follow_up ? '↳' : `Q${it.number}`}
          </div>
        ))}
      </div>
      {hover !== null && (
        <div className="pointer-events-none absolute -top-2 left-1/2 -translate-x-1/2 -translate-y-full rounded-md border border-zinc-200 bg-white px-2.5 py-1.5 text-xs shadow-md dark:border-zinc-700 dark:bg-zinc-900">
          {items[hover].is_follow_up ? `Follow-up to Q${items[hover].number}` : `Q${items[hover].number}`} ·{' '}
          <span className="font-semibold">{Math.round(items[hover].score)}</span> ·{' '}
          {items[hover].classification}
        </div>
      )}
    </div>
  )
}
