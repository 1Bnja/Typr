import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useAuth } from '../context/auth-provider'
import Button from '../../../components/button'
import './login-form.css'
import authService from '../services/authService'

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
        <form className="auth-form" onSubmit={handleSubmit}>
            {isRegistering && (
                <label className="auth-field">
                    Username
                    <input
                        type="text"
                        name="username"
                        autoComplete="username"
                        value={username}
                        onChange={(e) => setUsername(e.target.value)}
                        placeholder="yourname"
                    />
                </label>
            )}
            <label className="auth-field">
                Email
                <input
                    type="email"
                    name="email"
                    autoComplete="email"
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    placeholder="you@email.com"
                />
            </label>
            <label className="auth-field">
                Password
                <input
                    type="password"
                    name="password"
                    autoComplete={isRegistering ? 'new-password' : 'current-password'}
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    placeholder="At least 8 characters"
                />
            </label>
            <Button className="auth-submit" type="submit" variant="primary">
                {isRegistering ? 'Create account' : 'Sign in'}
            </Button>
        </form>
    )
}

export default LoginForm
