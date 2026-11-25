const REPO = 'https://github.com/1Bnja/Typr'

const InfoPage = ({ title, children, href, linkLabel }) => (
    <section className="mx-auto flex w-full max-w-md flex-col items-center px-6 py-10 text-center">
        <h1 className="text-4xl font-extrabold tracking-tight text-charcoal">{title}</h1>
        <p className="mt-4 text-base leading-relaxed text-muted">{children}</p>
        <a
            href={href}
            target="_blank"
            rel="noreferrer"
            className="mt-6 font-semibold text-charcoal underline decoration-[#18a98a] underline-offset-4 outline-none focus-visible:rounded-sm focus-visible:shadow-[0_0_0_4px_var(--focus-ring)]"
        >
            {linkLabel}
        </a>
    </section>
)

export const About = () => (
    <InfoPage title="About Typr" href={REPO} linkLabel="View the project on GitHub">
        Typr is a typing practice app. Take individual tests in Spanish or English, follow your
        progress, compare results in the monthly ranking and race other typists in real time.
    </InfoPage>
)

export const Contact = () => (
    <InfoPage title="Contact" href={`${REPO}/issues`} linkLabel="Open an issue on GitHub">
        Found a problem or have a suggestion? Tell us through the project&apos;s issue tracker.
    </InfoPage>
)
