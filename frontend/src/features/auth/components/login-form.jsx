const LoginForm = () => {
    return (
        <form className="flex flex-col gap-2">
            <input type="email" placeholder="Email" />
            <input type="password" placeholder="Password" />
            <button type="submit">Login</button>
        </form>
    )
}

export default LoginForm