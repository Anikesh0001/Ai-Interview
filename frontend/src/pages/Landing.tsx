import { Link } from 'react-router-dom'
import {
  ArrowRight,
  AudioLines,
  BarChart3,
  BadgeDollarSign,
  BrainCircuit,
  FileSearch,
  LockKeyhole,
} from 'lucide-react'
import { Logo } from '../components/Logo'
import { ThemeToggle } from '../components/ThemeToggle'
import { StatusPill } from '../components/StatusPill'

const FEATURES = [
  {
    icon: FileSearch,
    title: 'Resume Intelligence',
    body: 'Local parsing of PDF, DOCX and TXT into a structured profile, with a transparent ATS-style score and job-description match.',
  },
  {
    icon: BrainCircuit,
    title: 'Adaptive Interviews',
    body: 'Questions grounded in your projects and claims. Vague answers get follow-ups; strong answers get harder questions.',
  },
  {
    icon: AudioLines,
    title: 'Voice Practice',
    body: 'Answer out loud with in-browser speech recognition and hear the interviewer speak. Text mode is always available.',
  },
  {
    icon: BarChart3,
    title: 'Detailed Scoring',
    body: 'Every answer scored on seven dimensions with documented weights, plus a question-by-question review and study plan.',
  },
  {
    icon: LockKeyhole,
    title: 'Private & Local',
    body: 'Your resume, transcript and history stay in a SQLite file on this device. No analytics, no tracking.',
  },
  {
    icon: BadgeDollarSign,
    title: 'Zero API Cost',
    body: 'Runs on a local Ollama model, with a deterministic offline engine when no model is installed. No keys, no subscriptions.',
  },
]

const STEPS = [
  ['Upload your resume', 'We extract skills, projects, experience and every quantified claim.'],
  ['Add a job description', 'See matched, partial and missing requirements before you interview.'],
  ['Face the interviewer', 'A realistic, phase-by-phase interview that probes what you wrote.'],
  ['Review your report', 'Scores, gaps, unsupported claims and exactly what to study next.'],
]

export default function Landing() {
  return (
    <div className="min-h-screen">
      <header className="mx-auto flex h-16 max-w-6xl items-center justify-between px-4 sm:px-6">
        <Logo />
        <nav aria-label="Primary" className="flex items-center gap-1 sm:gap-2">
          <StatusPill className="hidden md:inline-flex" />
          <Link
            to="/dashboard"
            className="rounded-md px-3 py-2 text-sm font-medium text-zinc-700 hover:bg-zinc-100 dark:text-zinc-300 dark:hover:bg-zinc-800"
          >
            Dashboard
          </Link>
          <ThemeToggle />
        </nav>
      </header>

      <main>
        <section className="mx-auto max-w-6xl px-4 pt-14 pb-16 sm:px-6 sm:pt-20">
          <div className="max-w-3xl animate-fade-in">
            <p className="mb-4 inline-flex items-center gap-2 rounded-full border border-zinc-200 bg-white px-3 py-1 text-xs font-medium text-zinc-600 dark:border-zinc-800 dark:bg-zinc-900 dark:text-zinc-300">
              <span className="size-1.5 rounded-full bg-emerald-500" aria-hidden />
              Open source · runs entirely on your machine
            </p>
            <h1 className="text-4xl font-semibold tracking-tight text-balance sm:text-5xl">
              Practice the interview you actually want to get.
            </h1>
            <p className="mt-5 max-w-2xl text-lg text-zinc-600 dark:text-zinc-400">
              Upload your resume, choose a role, and face an adaptive AI interviewer that asks questions based
              on your real experience.
            </p>
            <div className="mt-8 flex flex-wrap gap-3">
              <Link
                to="/resume"
                className="inline-flex h-11 items-center gap-2 rounded-md bg-indigo-600 px-5 text-sm font-medium text-white shadow-sm hover:bg-indigo-500"
              >
                Analyze My Resume <ArrowRight className="size-4" aria-hidden />
              </Link>
              <Link
                to="/interview/setup"
                className="inline-flex h-11 items-center rounded-md border border-zinc-300 bg-white px-5 text-sm font-medium shadow-sm hover:bg-zinc-50 dark:border-zinc-700 dark:bg-zinc-900 dark:hover:bg-zinc-800"
              >
                Start Mock Interview
              </Link>
            </div>
          </div>

          <ol className="mt-16 grid gap-px overflow-hidden rounded-lg border border-zinc-200 bg-zinc-200 sm:grid-cols-2 lg:grid-cols-4 dark:border-zinc-800 dark:bg-zinc-800">
            {STEPS.map(([title, body], i) => (
              <li key={title} className="bg-white p-5 dark:bg-zinc-900">
                <span className="text-xs font-medium text-indigo-600 dark:text-indigo-400">Step {i + 1}</span>
                <h2 className="mt-1 text-sm font-semibold">{title}</h2>
                <p className="mt-1 text-sm text-zinc-500 dark:text-zinc-400">{body}</p>
              </li>
            ))}
          </ol>
        </section>

        <section
          aria-labelledby="features"
          className="border-t border-zinc-200 bg-white py-16 dark:border-zinc-800 dark:bg-zinc-900/40"
        >
          <div className="mx-auto max-w-6xl px-4 sm:px-6">
            <h2 id="features" className="text-2xl font-semibold tracking-tight">
              More than a chatbot asking interview questions
            </h2>
            <p className="mt-2 max-w-2xl text-zinc-600 dark:text-zinc-400">
              Resume intelligence, an ATS-style analyzer, an adaptive interviewer, an evaluator and a progress
              tracker — in one local app.
            </p>
            <div className="mt-10 grid gap-x-8 gap-y-10 sm:grid-cols-2 lg:grid-cols-3">
              {FEATURES.map(({ icon: Icon, title, body }) => (
                <div key={title}>
                  <div className="flex size-9 items-center justify-center rounded-md bg-indigo-50 text-indigo-600 dark:bg-indigo-500/10 dark:text-indigo-400">
                    <Icon className="size-5" aria-hidden />
                  </div>
                  <h3 className="mt-3 text-sm font-semibold">{title}</h3>
                  <p className="mt-1 text-sm leading-relaxed text-zinc-600 dark:text-zinc-400">{body}</p>
                </div>
              ))}
            </div>
          </div>
        </section>

        <section className="mx-auto max-w-6xl px-4 py-14 sm:px-6">
          <div className="rounded-lg border border-zinc-200 bg-white p-6 sm:p-8 dark:border-zinc-800 dark:bg-zinc-900">
            <h2 className="text-lg font-semibold">Honest by design</h2>
            <ul className="mt-3 grid gap-2 text-sm text-zinc-600 sm:grid-cols-2 dark:text-zinc-400">
              <li>
                • The ATS score is an <em>ATS-style compatibility</em> estimate — real ATS systems differ.
              </li>
              <li>• The Readiness Score is a practice metric, never a probability of being hired.</li>
              <li>• Answers are judged on content only — never accent, voice or identity.</li>
              <li>• When no local model is available, the app says so and uses its offline engine.</li>
            </ul>
          </div>
        </section>
      </main>

      <footer className="border-t border-zinc-200 py-8 text-center text-xs text-zinc-500 dark:border-zinc-800">
        InterviewForge · Your resume, transcript and interview history are stored locally on this device.
      </footer>
    </div>
  )
}
