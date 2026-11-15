export default function Card({ title, action, children, className = '' }) {
  return (
    <section className={`rounded-2xl bg-white p-4 shadow-sm ring-1 ring-slate-200 ${className}`}>
      {(title || action) && (
        <div className="mb-2 flex items-center justify-between gap-2">
          {title && <h2 className="text-[15px] font-semibold text-navy">{title}</h2>}
          {action}
        </div>
      )}
      {children}
    </section>
  )
}

export function Loading({ label = 'Load ho raha hai…' }) {
  return <p className="py-6 text-center text-sm text-slate-400">{label}</p>
}

export function ErrorNote({ error }) {
  if (!error) return null
  return <p className="rounded-xl bg-red-50 p-2 text-sm text-red-800" role="alert">{error.message || String(error)}</p>
}

export function Button({ children, variant = 'primary', className = '', ...props }) {
  const styles = {
    primary: 'bg-navy text-white hover:bg-navy/90',
    sky: 'bg-sky text-navy hover:bg-sky/90',
    ghost: 'bg-slate-100 text-navy hover:bg-slate-200',
    danger: 'bg-red-50 text-red-800 hover:bg-red-100',
  }
  return (
    <button className={`rounded-full px-4 py-2 text-sm font-semibold disabled:opacity-50 ${styles[variant]} ${className}`} {...props}>
      {children}
    </button>
  )
}
