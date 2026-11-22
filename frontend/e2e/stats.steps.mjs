import assert from 'node:assert/strict'
import { execFileSync } from 'node:child_process'
import { Given, Then, When } from '@cucumber/cucumber'
import { expect } from '@playwright/test'
import { origin } from './browser.mjs'

const statsPath = '/api/v1/users/me/stats'

Given('my stats fixture contains {int} finished matches', function (count) {
  const database = process.env.TYPR_BROWSER_FIXTURE_DB
  assert.match(database ?? '', /^typr-registration-[\da-f-]{36}-db$/)
  assert.match(this.account.email, /^qa_[\da-f]{12}@example\.com$/)
  assert.ok(count === 2 || count === 35)

  const inserted = execFileSync('docker', [
    'exec', '-i', database, 'psql', '-X', '-U', 'typr_test', '-d', 'typr_registration_test',
    '-v', 'ON_ERROR_STOP=1', '-v', `email=${this.account.email}`, '-v', `count=${count}`,
  ], {
    input: `
      WITH fixture_user AS (
        SELECT id FROM users WHERE email = :'email'
      ), fixture_text AS (
        INSERT INTO texts (content, language, difficulty)
        VALUES ('Synthetic stats text for ' || :'email', 'eng', 'medium') RETURNING id
      ), fixture_room AS (
        INSERT INTO rooms (code, host_id, language, difficulty)
        SELECT 'STAT14', id, 'eng', 'medium' FROM fixture_user WHERE :count = 2
        RETURNING id
      ), fixture_matches AS (
        SELECT n, timestamptz '2026-11-01 12:00:00+00' + n * interval '1 minute' AS finished_at,
               (:count = 2 AND n = 2) AS multiplayer
        FROM generate_series(1, :count) AS n
      ), fixture_games AS (
        INSERT INTO games (text_id, room_id, mode, started_at, finished_at)
        SELECT fixture_text.id, CASE WHEN multiplayer THEN (SELECT id FROM fixture_room) END,
               (CASE WHEN multiplayer THEN 'multiplayer' ELSE 'singleplayer' END)::game_mode,
               finished_at - interval '30 seconds', finished_at
        FROM fixture_matches CROSS JOIN fixture_text
        RETURNING id, finished_at
      )
      INSERT INTO game_participants
        (game_id, user_id, time_ms, ppm, precision_pct, progress, position, score)
      SELECT fixture_games.id, fixture_user.id, 30000, 40 + n, 90 - n, 1,
             CASE WHEN multiplayer THEN 2 END, 30 + n
      FROM fixture_games JOIN fixture_matches USING (finished_at) CROSS JOIN fixture_user;
    `,
    encoding: 'utf8',
    timeout: 5_000,
  })
  assert.equal(inserted.trim(), `INSERT 0 ${count}`)
})

When('I open my personal statistics', async function () {
  const [response] = await Promise.all([
    this.page.waitForResponse(response =>
      new URL(response.url()).pathname === statsPath && response.request().method() === 'GET'),
    this.page.goto(`${origin}/practice/stats`),
  ])
  assert.equal(response.status(), 200)
  this.personalStats = await response.json()
  await expect(this.page.getByRole('heading', { name: 'Your progress', exact: true })).toBeVisible()
})

Then('the speed chart shows only the latest 30 matches, oldest to newest', async function () {
  const expectedSpeeds = Array.from({ length: 30 }, (_, i) => 46 + i)
  assert.equal(this.personalStats.summary.totalMatches, 35)
  assert.deepEqual(this.personalStats.trend.map(point => [
    new Date(point.finishedAt).toISOString(), point.ppm,
  ]), expectedSpeeds.map((ppm, i) => [
    new Date(Date.UTC(2026, 10, 1, 12, 6 + i)).toISOString(), ppm,
  ]))
  this.log('HTTP 200; 35 saved matches; API trend: 12:06–12:35 UTC and 46–75 WPM, oldest first')

  const trend = this.page.getByRole('region', { name: 'Recent trend' })
  await expect(trend.getByText('Last 30 matches', { exact: true })).toBeVisible()
  const description = 'Over your last 30 matches your speed went up 29 words per minute, from 46 to 75.'
  await expect(trend.getByText(description, { exact: true })).toBeVisible()
  const chart = trend.getByRole('img', { name: description, exact: true })
  await expect(chart).toBeVisible()
  const curve = chart.locator('.stats-line--ppm path.recharts-line-curve')
  await expect(curve).toBeVisible()
  const points = await curve.evaluate(path => {
    const length = path.getTotalLength()
    const transform = path.getScreenCTM()
    return Array.from({ length: 30 }, (_, i) => {
      const { x, y } = path.getPointAtLength(length * i / 29).matrixTransform(transform)
      return { x, y }
    })
  })
  assert.ok(points.slice(1).every(({ x, y }, i) => x > points[i].x && y < points[i].y),
    'Expected the rendered speed line to rise from left to right')
  this.log('Visible caption and accessible chart name describe +29 WPM; SVG curve rises left to right')

  for (const i of [0, 14, 29]) {
    const { x, y } = points[i]
    // Stay just inside the chart's hover range at either endpoint.
    await this.page.mouse.move(x + (i === 0 ? 2 : i === 29 ? -2 : 0), y)
    const match = 6 + i
    const ppm = expectedSpeeds[i]
    await expect(chart.getByText(`Match ${match} · Practice`, { exact: true })).toBeVisible()
    await expect(chart.getByText(`${ppm} WPM`, { exact: true })).toBeVisible()
    this.log(`Visible hover tooltip: match ${match}, ${ppm} WPM`)
  }
})

Then('the API and match history show the expected details for both modes', async function () {
  const expected = [
    ['2026-11-01T12:02:00.000Z', 'multiplayer', 42, 88, 32, 2],
    ['2026-11-01T12:01:00.000Z', 'singleplayer', 41, 89, 31, null],
  ]
  assert.deepEqual(this.personalStats.history.map(match => [
    new Date(match.finishedAt).toISOString(), match.mode, match.ppm,
    match.precisionPct, match.score, match.position,
  ]), expected)

  const table = this.page.getByRole('table', { name: 'Your finished matches, newest first' })
  await expect(table).toBeVisible()
  const rows = table.locator('tbody tr')
  await expect(rows).toHaveCount(2)
  for (const [index, [date]] of expected.entries()) {
    const row = rows.nth(index)
    const timestamp = row.locator('time')
    await expect(timestamp).toHaveText(index === 0 ? 'Nov 1, 09:02 AM' : 'Nov 1, 09:01 AM')
    assert.equal(new Date(await timestamp.getAttribute('datetime')).toISOString(), date)
    await expect(row.getByRole('rowheader')).toContainText('English · Medium')
    await expect(row.getByRole('cell')).toHaveText(index === 0
      ? ['Multiplayer 2nd place', '42 WPM', '88%', '0:30', '32']
      : ['Practice', '41 WPM', '89%', '0:30', '31'], { useInnerText: true })
  }
  this.log('HTTP 200 and two visible rows, newest first: multiplayer 42 WPM / 88% / 32; practice 41 WPM / 89% / 31')
})

Then('I see the first-match guidance instead of a chart or history', async function () {
  const { summary, trend, history } = this.personalStats
  assert.deepEqual([summary.totalMatches, trend, history], [0, [], []])
  await expect(this.page.getByRole('heading', { name: 'Play your first match to see your progress.' })).toBeVisible()
  for (const name of ['Start a practice test', 'Race other typists']) {
    await expect(this.page.getByRole('link', { name, exact: true })).toBeVisible()
  }
  await expect(this.page.getByRole('heading', { name: 'Recent trend' })).toHaveCount(0)
  await expect(this.page.getByRole('heading', { name: 'Match history' })).toHaveCount(0)
  await expect(this.page.getByRole('alert')).toHaveCount(0)
  this.log('HTTP 200; zero matches; first-match guidance and both links visible; no chart, history or error')
})
