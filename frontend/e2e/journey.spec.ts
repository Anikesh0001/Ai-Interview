import { expect, test, type Page } from '@playwright/test'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const FIXTURES = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../../tests/fixtures')

const VAGUE = 'We used caching and it got faster. It was a team effort and everyone helped out.'
const STRONG =
  'First, I would clarify the requirements because it depends on the load. For example, in my hospital project I ' +
  'indexed patient_id in PostgreSQL and measured with EXPLAIN ANALYZE; queries dropped from 300 ms to 40 ms. ' +
  'The trade-off is slower writes, so I only index columns we filter by, and I verified the result in staging.'

async function answer(page: Page, text: string) {
  const before = await page.getByTestId('transcript').locator('[data-role]').count()
  await page.getByLabel('Answer', { exact: true }).fill(text)
  await page.getByTestId('submit-answer').click()
  // wait until the candidate message and the interviewer's next message are rendered
  await expect
    .poll(async () => page.getByTestId('transcript').locator('[data-role]').count())
    .toBeGreaterThan(before + 1)
}

test('complete candidate journey: resume → ATS → JD → interview → report → history', async ({ page }) => {
  // 1. open the app
  await page.goto('/')
  await expect(
    page.getByRole('heading', { name: 'Practice the interview you actually want to get.' }),
  ).toBeVisible()
  await page.getByRole('link', { name: 'Analyze My Resume' }).click()

  // 2-4. upload, parse, analyze
  await page.getByTestId('resume-input').setInputFiles(path.join(FIXTURES, 'sample_resume.pdf'))
  await expect(page.getByTestId('resume-filename')).toHaveText('sample_resume.pdf')
  await expect(page.getByTestId('candidate-name')).toHaveText('Aarav Sharma')
  await expect(page.getByTestId('ats-score')).toContainText(/\d+/)
  await expect(page.getByText('Hospital Management System').first()).toBeVisible()

  // 5. job description → JD match
  await page.getByLabel('Try a sample job description').selectOption({ label: 'Junior Software Engineer' })
  await page.getByRole('button', { name: 'Analyze match' }).click()
  await expect(page.getByTestId('jd-match')).toBeVisible()
  await expect(page.getByTestId('jd-match')).toContainText('Matched')

  // 6. configure: Software Engineer, Junior, Mixed, Medium, 10 questions, Voice mode
  await page.getByRole('button', { name: 'Configure mock interview' }).click()
  await expect(page.getByRole('heading', { name: 'Configure your interview' })).toBeVisible()
  await page.getByLabel('Target role').selectOption('Software Engineer')
  await page.getByLabel('Experience level').selectOption('Junior')
  await page.getByRole('radio', { name: /^Mixed/ }).check()
  await page.getByRole('radio', { name: 'Medium' }).click()
  await page.getByRole('radio', { name: /Standard · 10/ }).click()
  await page.getByRole('radio', { name: /Voice/ }).click()
  await expect(page.getByLabel('Job description (optional)')).not.toBeEmpty()

  // 7. start: the interviewer introduces themself and asks a question
  await page
    .getByRole('button', { name: /Start interview/ })
    .last()
    .click()
  await expect(page.getByTestId('interview-room')).toBeVisible()
  await expect(page.getByTestId('transcript')).toContainText('thanks for joining')
  await expect(page.getByTestId('question-counter')).toContainText('Question 1 of 10')
  const roomUrl = page.url()

  // 8. answer; the resume-claim question gets a vague answer → 9. follow-up
  await answer(
    page,
    'I am a final-year computer science student. I interned at BrightCart building Flask APIs and built a hospital management system with React and PostgreSQL. I want to grow as a backend engineer.',
  )
  await expect(page.getByTestId('current-question')).toContainText('Reduced API latency by 40%')
  await answer(page, VAGUE)
  await expect(page.getByText('Follow-up question')).toBeVisible()
  await expect(page.getByTestId('phase')).toHaveText('Follow-up')
  await answer(
    page,
    'I measured p95 latency in Grafana: about 450 ms before and 270 ms after, on the same traffic. I added an index and cached hot queries in Redis.',
  )

  // scores stay hidden during the interview
  await expect(page.getByText(/\/\s*100/)).toHaveCount(0)

  // 16. refresh mid-interview → session is restored
  const questionBefore = await page.getByTestId('current-question').textContent()
  await page.reload()
  await expect(page.getByTestId('current-question')).toHaveText(questionBefore ?? '')
  expect(page.url()).toBe(roomUrl)
  await expect(page.getByTestId('transcript')).toContainText('Reduced API latency by 40%')

  // keep answering through multiple phases until the interviewer closes
  const phases = new Set<string>()
  for (let i = 0; i < 25; i++) {
    if (await page.getByText('Generating your report…').or(page.getByText('Interview complete.')).isVisible())
      break
    if (!(await page.getByTestId('submit-answer').isVisible())) break
    phases.add((await page.getByTestId('phase').textContent()) ?? '')
    await answer(page, STRONG)
  }
  expect(phases.size).toBeGreaterThanOrEqual(4)

  // 10-11. interview ends professionally and the report is generated
  await page.waitForURL(/\/report$/, { timeout: 60_000 })
  await expect(page.getByTestId('report')).toBeVisible()
  await expect(
    page.getByText('That brings us to the end').or(page.getByTestId('executive-summary')),
  ).toBeVisible()

  // 12-14. ATS, interview score and the full report
  await expect(page.getByTestId('score-ats')).toContainText(/\d+/)
  await expect(page.getByTestId('score-jd')).toContainText(/\d+/)
  await expect(page.getByTestId('score-interview')).toContainText(/\d+/)
  await expect(page.getByTestId('score-readiness')).toContainText(/\d+/)
  await expect(page.getByTestId('executive-summary')).not.toBeEmpty()
  await expect(page.getByTestId('verdict')).not.toBeEmpty()
  await expect(page.getByTestId('category-scores')).toContainText('Technical')
  await expect(page.getByTestId('category-scores')).toContainText('Communication')
  await expect(page.getByTestId('category-scores')).toContainText('Problem Solving')
  await expect(page.getByTestId('category-scores')).toContainText('Project Knowledge')
  await expect(page.getByTestId('claims')).toContainText('Reduced API latency by 40%')
  expect(await page.getByTestId('question-review').locator('li').count()).toBeGreaterThanOrEqual(10)
  await expect(page.getByTestId('action-plan').locator('li').first()).toBeVisible()
  await expect(page.getByText(/Not a probability of being hired/)).toBeVisible()

  // exports
  const pdf = await page.request.get(
    page.url().replace(/\/interview\/(\w+)\/report$/, '/api/interviews/$1/report.pdf'),
  )
  expect(pdf.headers()['content-type']).toContain('application/pdf')

  // 15. history shows the interview
  await page.goto('/history')
  await expect(page.getByTestId('history-table')).toContainText('Software Engineer')
  await expect(page.getByTestId('history-table').getByRole('link', { name: 'Report' })).toBeVisible()

  // the dashboard reflects it, and the candidate can start another interview
  await page.goto('/dashboard')
  await expect(page.getByTestId('stat-completed')).toHaveText('1')
  await page.getByRole('button', { name: /Start interview/ }).click()
  await expect(page.getByRole('heading', { name: 'Configure your interview' })).toBeVisible()
})

test('rejects a scanned PDF with a clear message', async ({ page }) => {
  await page.goto('/resume')
  await page.getByTestId('resume-input').setInputFiles(path.join(FIXTURES, 'scanned_resume.pdf'))
  await expect(
    page.getByText('Your PDF appears to be scanned/image-based. Please upload a text-based PDF or DOCX.'),
  ).toBeVisible()
})

test('text mode works without speech APIs, and the interview can end early', async ({ browser }) => {
  const context = await browser.newContext()
  await context.addInitScript(() => {
    // simulate a browser with no speech support at all
    // @ts-expect-error test override
    delete window.SpeechRecognition
    // @ts-expect-error test override
    delete window.webkitSpeechRecognition
    // @ts-expect-error test override
    delete window.speechSynthesis
  })
  const page = await context.newPage()
  await page.goto('/resume')
  await page.getByTestId('resume-input').setInputFiles(path.join(FIXTURES, 'sample_resume.docx'))
  await expect(page.getByTestId('candidate-name')).toHaveText('Aarav Sharma')
  await page.goto('/interview/setup')
  await page.getByRole('radio', { name: /Quick · 5/ }).click()
  await page.getByRole('radio', { name: /^Behavioral/ }).check()
  await page
    .getByRole('button', { name: /Start interview/ })
    .last()
    .click()
  await expect(page.getByTestId('interview-room')).toBeVisible()
  await page.getByRole('radio', { name: /Voice/ }).click()
  await expect(page.getByText(/Speech recognition isn't available/)).toBeVisible()
  await answer(page, STRONG)
  page.once('dialog', (d) => d.accept())
  await page.getByRole('button', { name: 'End interview' }).click()
  await page.waitForURL(/\/report$/)
  await expect(page.getByTestId('score-interview')).toContainText(/\d+/)
  await context.close()
})
