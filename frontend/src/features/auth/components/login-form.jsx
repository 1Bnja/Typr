import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useAuth } from '../context/auth-context'
import Button from '../../../components/button'
import authService from '../services/authService'

const fieldClass = 'flex flex-col gap-2 text-sm font-semibold text-charcoal'
const inputClass =
    'w-full rounded-xl border border-[#e1e2dc] bg-white px-4 py-3 font-normal text-charcoal shadow-[0_3px_0_#e1e2dc] outline-none caret-charcoal placeholder:text-[#5f605b] selection:bg-mint/45 selection:text-charcoal focus-visible:border-[#18a98a] focus-visible:shadow-[0_3px_0_#18a98a,0_0_0_4px_rgb(47_217_180/0.45)]'

const LoginForm = ({ isRegistering }) => {
    const navigate = useNavigate()
    const { signIn } = useAuth()
    const [email, setEmail] = useState('')
    const [password, setPassword] = useState('')
    const [username, setUsername] = useState('')
    const [error, setError] = useState(null)
    const [pending, setPending] = useState(false)

    const handleSubmit = async (e) => {
        e.preventDefault()
        setError(null)
        setPending(true)
        try {
            if (isRegistering) {
                await authService.register({ username, email, password })
                await signIn({ email, password })
            } else {
                await signIn({ email, password })
            }
            navigate('/')
        } catch (err) {
            setError(err.message)
        } finally {
            setPending(false)
        }
    }

    return (
        <form className="flex flex-col gap-4" onSubmit={handleSubmit}>
            {isRegistering && (
                <label className={fieldClass}>
                    Username
                    <input
                        className={inputClass}
                        type="text"
                        name="username"
                        autoComplete="username"
                        value={username}
                        onChange={(e) => setUsername(e.target.value)}
                        placeholder="yourname"
                    />
                </label>
            )}
            <label className={fieldClass}>
                Email
                <input
                    className={inputClass}
                    type="email"
                    name="email"
                    autoComplete="email"
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    placeholder="you@email.com"
                />
            </label>
            <label className={fieldClass}>
                Password
                <input
                    className={inputClass}
                    type="password"
                    name="password"
                    autoComplete={isRegistering ? 'new-password' : 'current-password'}
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    placeholder="At least 8 characters"
                />
            </label>
            {error && (
                <p className="text-sm font-semibold text-red-600" role="alert">
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
