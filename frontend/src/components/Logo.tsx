export function Logo({ compact = false }: { compact?: boolean }) {
  return (
    <span className="inline-flex items-center gap-2 font-semibold tracking-tight">
      <svg viewBox="0 0 32 32" className="size-7" aria-hidden>
        <rect width="32" height="32" rx="7" className="fill-indigo-600" />
        <path d="M10 9h12v3h-8.5v3.2H21v3h-7.5V23H10z" fill="#fff" />
      </svg>
      {!compact && <span className="text-[15px]">InterviewForge</span>}
    </span>
  )
}
