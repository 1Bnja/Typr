import { useId, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useAuth } from '../context/auth-context'
import Button from '../../../components/button'
import authService, { DuplicateEmailError, RegistrationFieldError } from '../services/authService'

const fieldClass = 'flex flex-col gap-2 text-sm font-semibold text-charcoal'
const inputClass =
    'w-full rounded-xl border border-divider bg-surface px-4 py-3 font-normal text-charcoal shadow-[0_3px_0_var(--line)] outline-none caret-charcoal placeholder:text-muted selection:bg-mint/45 selection:text-charcoal focus-visible:border-[color:var(--auth-field-focus-border)] focus-visible:shadow-[0_3px_0_var(--auth-field-focus-border),0_0_0_4px_var(--focus-ring)]'
const fieldErrorClass = '-mt-2 text-sm font-semibold text-danger empty:-mt-4'

const LoginForm = ({ isRegistering, draft, onDraftChange }) => {
    const navigate = useNavigate()
    const { signIn } = useAuth()
    const { email, password, username } = draft
    const [error, setError] = useState(null)
    const [emailError, setEmailError] = useState(null)
    const [fieldErrors, setFieldErrors] = useState({})
    const usernameErrorId = useId()
    const emailErrorId = useId()
    const passwordErrorId = useId()
    const [pending, setPending] = useState(false)

    const handleSubmit = async (e) => {
        e.preventDefault()
        setError(null)
        setEmailError(null)
        setFieldErrors({})
        setPending(true)
        try {
            if (isRegistering) {
                await authService.register({ username, email, password })
                await signIn({ email, password })
            } else {
                await signIn({ email, password })
            }
            navigate('/profile')
        } catch (err) {
            if (err instanceof DuplicateEmailError) {
                setEmailError(err.message)
            } else if (isRegistering && err instanceof RegistrationFieldError) {
                setFieldErrors(err.fields)
            } else {
                setError(err.message)
            }
        } finally {
            setPending(false)
        }
    }

    return (
        <form className="auth-form flex flex-col gap-4" onSubmit={handleSubmit}>
            {isRegistering && (
                <>
                    <label className={fieldClass}>
                        Username
                        <input
                            className={inputClass}
                            type="text"
                            name="username"
                            autoComplete="username"
                            aria-invalid={fieldErrors.username ? true : undefined}
                            aria-describedby={fieldErrors.username ? usernameErrorId : undefined}
                            value={username}
                            onChange={(e) => {
                                onDraftChange('username', e.target.value)
                                setFieldErrors((current) => ({ ...current, username: undefined }))
                            }}
                            placeholder="yourname"
                        />
                    </label>
                    <div id={usernameErrorId} role="alert" className={fieldErrorClass}>
                        {fieldErrors.username}
                    </div>
                </>
            )}
            <label className={fieldClass}>
                Email
                <input
                    className={inputClass}
                    type="email"
                    name="email"
                    autoComplete="email"
                    aria-invalid={emailError ? true : undefined}
                    aria-describedby={emailError ? emailErrorId : undefined}
                    value={email}
                    onChange={(e) => {
                        onDraftChange('email', e.target.value)
                        setEmailError(null)
                    }}
                    placeholder="you@email.com"
                />
            </label>
            {isRegistering && (
                <div id={emailErrorId} role="alert" className={fieldErrorClass}>
                    {emailError}
                </div>
            )}
            <label className={fieldClass}>
                Password
                <input
                    className={inputClass}
                    type="password"
                    name="password"
                    autoComplete={isRegistering ? 'new-password' : 'current-password'}
                    aria-invalid={fieldErrors.password ? true : undefined}
                    aria-describedby={fieldErrors.password ? passwordErrorId : undefined}
                    value={password}
                    onChange={(e) => {
                        onDraftChange('password', e.target.value)
                        if (isRegistering) {
                            setFieldErrors((current) => ({ ...current, password: undefined }))
                        }
                    }}
                    placeholder="At least 8 characters"
                />
            </label>
            {isRegistering && (
                <div id={passwordErrorId} role="alert" className={fieldErrorClass}>
                    {fieldErrors.password}
                </div>
            )}
            {error && (
                <p className="text-sm font-semibold text-danger" role="alert">
                    {error}
                </p>
            )}
            <Button className="mt-2 w-full" type="submit" variant="primary" isLoading={pending}>
                {isRegistering ? 'Create account' : 'Sign in'}
            </Button>
        </form>
    )
}

export default LoginForm
