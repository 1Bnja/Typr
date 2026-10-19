import { useState } from 'react'
import LoginForm from '../components/login-form'

const Login = () => {
    const [isRegistering, setIsRegistering] = useState(false)

    return (
        <section className="mx-auto flex w-full max-w-md flex-col px-6 py-10">
            <div className="flex w-full flex-col">
                <h1 className="text-center text-4xl font-extrabold tracking-tight text-charcoal">
                    {isRegistering ? 'Create an account' : 'Welcome back!'}
                </h1>
                <p className="mt-4 text-center text-base leading-relaxed text-[#575853]">
                    {isRegistering
                        ? 'Save your tests and come back to your speed.'
                        : 'Sign in to pick up your tests and your speed.'}
                </p>

                <div className="mt-8">
                    <LoginForm
                        key={isRegistering ? 'register' : 'login'}
                        isRegistering={isRegistering}
                    />
                </div>

                <p className="mt-6 text-center text-[#575853]">
                    {isRegistering ? 'Already have an account? ' : "Don't have an account? "}
                    <button
                        type="button"
                        className="font-semibold text-charcoal underline decoration-[#18a98a] underline-offset-4 outline-none focus-visible:rounded-sm focus-visible:shadow-[0_0_0_4px_rgb(47_217_180/0.45)]"
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
