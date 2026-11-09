const Stat = ({ label, value, large = false }) => (
  <div className="flex flex-col rounded-xl border border-[#e1e2dc] bg-white px-4 py-3 shadow-[0_3px_0_#e1e2dc]">
    <span className="text-xs font-semibold uppercase tracking-wide text-neutral-500">{label}</span>
    <span className={`font-extrabold text-charcoal tabular-nums ${large ? 'text-4xl' : 'text-2xl'}`}>{value}</span>
  </div>
)

export default Stat
