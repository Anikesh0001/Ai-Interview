// localStorage is only used for per-device conveniences (current resume, drafts, theme).
// Every access is guarded: private windows or blocked storage must never break the app.

export function load<T>(key: string, fallback: T): T {
  try {
    const raw = localStorage.getItem(key)
    return raw === null ? fallback : (JSON.parse(raw) as T)
  } catch {
    return fallback
  }
}

export function save(key: string, value: unknown): void {
  try {
    localStorage.setItem(key, JSON.stringify(value))
  } catch {
    /* storage unavailable */
  }
}

export function remove(key: string): void {
  try {
    localStorage.removeItem(key)
  } catch {
    /* storage unavailable */
  }
}

export const KEYS = {
  resumeId: 'if-resume-id',
  jd: 'if-jd',
  role: 'if-role',
  setup: 'if-setup',
  draft: (interviewId: string) => `if-draft-${interviewId}`,
  muted: 'if-muted',
  theme: 'if-theme',
}

export function clearAll(): void {
  try {
    Object.keys(localStorage)
      .filter((k) => k.startsWith('if-') && k !== KEYS.theme)
      .forEach((k) => localStorage.removeItem(k))
  } catch {
    /* storage unavailable */
  }
}
