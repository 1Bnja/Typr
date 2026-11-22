import { mkdir, mkdtemp, rm } from 'node:fs/promises'
import { After, Before, Status, setDefaultTimeout } from '@cucumber/cucumber'
import { chromium } from '@playwright/test'
import { RegistrationPage } from './registration.page.mjs'

export const origin = process.env.TYPR_BROWSER_ORIGIN ?? 'http://127.0.0.1:5173'
const results = process.env.TYPR_BROWSER_RESULTS ?? 'test-results'
export const disconnected = /^Failed to load resource: net::ERR_INTERNET_DISCONNECTED$/
export const httpError = status => new RegExp(`^Failed to load resource: the server responded with a status of ${status}\\b`)
setDefaultTimeout(15_000)

Before(async function () {
  this.contexts = []
  this.browserErrors = { 'console.error': 0, 'uncaught page error': 0 }
  await mkdir(results, { recursive: true })
  this.artifacts = await mkdtemp(`${results}/scenario-`)
  this.browser = await chromium.launch({
    executablePath: process.env.TYPR_CHROMIUM_PATH,
    headless: process.env.GITHUB_ACTIONS === 'true' || process.env.CI === 'true'
      || process.env.TYPR_HEADLESS === '1',
  })

  this.newContext = async ({ storageState } = {}) => {
    const number = this.contexts.length + 1
    const context = await this.browser.newContext({
      storageState,
      recordVideo: { dir: `${this.artifacts}/context-${number}` },
    })
    const recording = { context, number, tracing: false }
    this.contexts.push(recording)
    context.setDefaultTimeout(5_000)
    const expected = []
    context.on('console', message => {
      if (message.type() !== 'error') return
      // Only consume one matching Chromium resource error per explicit expectation.
      const index = expected.findIndex(({ url, text }) =>
        message.location().url === url && text.test(message.text()))
      if (index === -1) this.browserErrors['console.error']++
      else expected.splice(index, 1)
    })
    context.on('weberror', () => this.browserErrors['uncaught page error']++)
    await context.tracing.start({ screenshots: true, snapshots: true })
    recording.tracing = true
    return { context, expected }
  }

  const { context, expected } = await this.newContext()
  this.expectResourceError = (path, text) => expected.push({ url: `${origin}${path}`, text })
  this.page = await context.newPage()
  this.request = this.page.request
  this.registration = new RegistrationPage(this.page)
})

After({ timeout: 30_000 }, async function ({ result }) {
  const problems = []
  try {
    for (const { context, number, tracing } of this.contexts ?? []) {
      try {
        if (tracing) await context.tracing.stop({ path: `${this.artifacts}/trace-${number}.zip` })
      } catch {
        problems.push(`Could not save trace for context ${number}`)
      }
      try {
        await context.close() // Flush video before deciding whether to retain it.
      } catch {
        problems.push(`Could not finalize video for context ${number}`)
      }
    }
  } finally {
    try {
      await this.browser?.close()
    } catch {
      problems.push('Could not close Chromium')
    }
  }

  for (const [kind, count] of Object.entries(this.browserErrors ?? {})) {
    if (count) problems.push(`Unexpected browser ${kind}: ${count}`)
  }
  if (this.artifacts && (result?.status !== Status.PASSED || problems.length)) {
    this.log(`Browser artifacts: ${this.artifacts}`)
  } else if (this.artifacts) {
    await rm(this.artifacts, { recursive: true, force: true })
  }
  if (problems.length) throw new Error(problems.join('\n'))
})
