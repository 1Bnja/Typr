import { expect } from '@playwright/test'

export class RegistrationPage {
  constructor(page) {
    this.page = page
    this.form = page.locator('form')
    this.username = this.form.getByLabel('Username', { exact: true })
    this.email = this.form.getByLabel('Email', { exact: true })
    this.password = this.form.getByLabel('Password', { exact: true })
    this.alert = this.form.getByRole('alert').filter({ hasText: /\S/ })
  }

  async open(origin) {
    await this.page.goto(`${origin}/login`)
    await this.page.getByRole('button', { name: 'Register', exact: true }).click()
  }

  async submit({ username, email, password }) {
    await this.username.fill(username)
    await this.email.fill(email)
    await this.password.fill(password)
    const [response] = await Promise.all([
      this.page.waitForResponse((response) =>
        new URL(response.url()).pathname === '/api/v1/auth/register' && response.request().method() === 'POST'),
      this.form.getByRole('button', { name: 'Create account' }).click(),
    ])
    return response.status()
  }

  async expectEmailError(message) {
    await expect(this.alert).toBeVisible()
    await expect(this.alert).toHaveText(message)
    await expect(this.email).toHaveAttribute('aria-invalid', 'true')
    await expect(this.email).toHaveAccessibleDescription(message)
    await expect(this.email.locator('xpath=../following-sibling::*[1]')).toHaveText(message)
  }

  async expectFormError(message) {
    await expect(this.alert).toBeVisible()
    await expect(this.alert).toHaveText(message)
    await expect(this.email).not.toHaveAttribute('aria-invalid', 'true')
    await expect(this.email).not.toHaveAccessibleDescription(message)
  }

  async expectValues({ username, email, password }) {
    await expect(this.username).toHaveValue(username)
    await expect(this.email).toHaveValue(email)
    await expect(this.password).toHaveValue(password)
    await expect(this.page).toHaveURL(/\/login$/)
  }
}
