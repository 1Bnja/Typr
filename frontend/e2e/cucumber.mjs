const support = { import: ['browser.mjs', '*.steps.mjs'] }

export default {
  ...support,
  paths: ['*.feature'],
  format: ['progress', ['html', 'test-results/report.html']],
}

export const diagnostics = {
  ...support,
  paths: ['fixtures/diagnostics.feature'],
  format: ['progress', ['html', 'test-results/diagnostics.html']],
}
