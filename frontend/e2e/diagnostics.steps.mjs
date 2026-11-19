import { Given } from '@cucumber/cucumber'

Given('a test page emits a console error and an uncaught exception', async function () {
  const { context } = await this.newContext()
  const page = await context.newPage()
  const exception = page.waitForEvent('pageerror')
  await page.setContent('<script>console.error("Synthetic console error"); throw Error("Synthetic page error")</script>')
  await exception
})
