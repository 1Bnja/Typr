const support = { import: ['browser.mjs', '*.steps.mjs'] }
const results = process.env.TYPR_BROWSER_RESULTS ?? 'test-results'

export default {
  ...support,
  paths: ['*.feature'],
  format: ['progress', ['html', `${results}/report.html`]],
}

export const diagnostics = {
  ...support,
  paths: ['fixtures/diagnostics.feature'],
  format: ['progress', ['html', `${results}/diagnostics.html`]],
}
