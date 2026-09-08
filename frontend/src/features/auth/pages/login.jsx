import LoginForm from '../components/login-form'

const Login = () => {
    return (
        <section className="bg-red-400 flex flex-col items-center justify-center">
            <h1>Welcome back!</h1>
            <p>Lorem ipsum dolor sit amet consectetur adipisicing elit. Obcaecati, dolorem!</p>

            <div className="max-w-md bg-green-400">
                <LoginForm />
            </div>
            <p>Don't have an account?</p>
            { /* Agregar react router dom */ }
        </section>
    )
}

export default Login