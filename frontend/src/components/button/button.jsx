import './button.css'

const Button = ({
  children,
  variant = 'primary',
  size = 'md',
  isLoading = false,
  disabled = false,
  className = '',
  type = 'button',
  ...props
}) => {
  const isOff = disabled || isLoading
  const classes = [
    'button',
    `button--${variant}`,
    size === 'sm' ? 'button--sm' : '',
    isLoading ? 'button--loading' : '',
    disabled && !isLoading ? 'button--off' : '',
    className,
  ]
    .filter(Boolean)
    .join(' ')

  return (
    <button
      type={type}
      className={classes}
      disabled={isOff}
      aria-busy={isLoading || undefined}
      {...props}
    >
      {children}
    </button>
  )
}

export default Button
