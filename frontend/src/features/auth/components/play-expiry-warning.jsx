import { useEffect, useState } from 'react'
import { getAbsoluteDeadline } from '../utils/session'
import { rejectSession } from '../utils/session-fetch'

const WARNING_MS = 5 * 60_000

export default function PlayExpiryWarning({ token, expiryNotice }) {
    const deadline = getAbsoluteDeadline(token)
    const warnAt = deadline - WARNING_MS
    const [warning, setWarning] = useState(() => Date.now() >= warnAt)

    useEffect(() => {
        if (!Number.isFinite(deadline)) return
        let timer
        function checkDeadline() {
            clearTimeout(timer)
            const now = Date.now()
            if (now >= deadline) {
                rejectSession(token, expiryNotice)
                return
            }
            setWarning(now >= warnAt)
            const next = now >= warnAt ? deadline : warnAt
            timer = setTimeout(checkDeadline, next - now)
        }

        const now = Date.now()
        timer = setTimeout(checkDeadline, Math.max(0, (now >= warnAt ? deadline : warnAt) - now))
        document.addEventListener('visibilitychange', checkDeadline)
        return () => {
            clearTimeout(timer)
            document.removeEventListener('visibilitychange', checkDeadline)
        }
    }, [deadline, expiryNotice, token, warnAt])

    return <p className="play-expiry-warning" role="status">
        {warning ? 'Your session expires in 5 minutes or less.' : ''}
    </p>
}
