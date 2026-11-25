import { useState } from 'react'
import LoginForm from '../components/login-form'
import { useAuth } from '../context/auth-context'

const emptyDraft = { username: '', email: '', password: '' }

const Login = ({ initialRegistering = false }) => {
    const [isRegistering, setIsRegistering] = useState(initialRegistering)
    const [drafts, setDrafts] = useState({ login: emptyDraft, register: emptyDraft })
    const { notice } = useAuth()
    const mode = isRegistering ? 'register' : 'login'

    return (
        <section className="mx-auto flex w-full max-w-md flex-col px-6 py-10">
            <div className="flex w-full flex-col">
                <h1 className="text-center text-4xl font-extrabold tracking-tight text-charcoal">
                    {isRegistering ? 'Create an account' : 'Welcome back!'}
                </h1>
                <p className="mt-4 text-center text-base leading-relaxed text-muted">
                    {isRegistering
                        ? 'Save your tests and come back to your speed.'
                        : 'Sign in to pick up your tests and your speed.'}
                </p>

                {notice && <p role="alert" className="mt-4 text-center text-danger">{notice}</p>}
                <div className="mt-8">
                    <LoginForm
                        key={mode}
                        isRegistering={isRegistering}
                        draft={drafts[mode]}
                        onDraftChange={(field, value) => setDrafts((current) => ({
                            ...current,
                            [mode]: { ...current[mode], [field]: value },
                        }))}
                    />
                </div>

                <p className="mt-6 text-center text-muted">
                    {isRegistering ? 'Already have an account? ' : "Don't have an account? "}
                    <button
                        type="button"
                        className="font-semibold text-charcoal underline decoration-[#18a98a] underline-offset-4 outline-none focus-visible:rounded-sm focus-visible:shadow-[0_0_0_4px_var(--focus-ring)]"
                        onClick={() => setIsRegistering((current) => !current)}
                    >
                        {isRegistering ? 'Sign in' : 'Register'}
                    </button>
                </p>
            </div>
        </section>
    )
}

export default Login
