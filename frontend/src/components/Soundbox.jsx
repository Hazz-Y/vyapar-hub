import { useApp } from '../context/AppContext'

// Simulated Paytm AI Soundbox: a display line and an LED that pulses while it speaks.
export default function Soundbox({ compact = false }) {
  const { soundbox } = useApp()
  return (
    <div className={`flex ${compact ? 'items-center gap-3' : 'flex-col items-center'}`} aria-label="Soundbox simulator">
      <div className={`relative ${compact ? 'h-14 w-14' : 'h-52 w-44'} rounded-[2rem] bg-gradient-to-b from-slate-800 to-slate-950 p-3 shadow-xl ring-1 ring-black/40`}>
        {!compact && (
          <>
            <div className="mx-auto mt-1 w-fit rounded-md bg-sky px-2 py-0.5 text-[10px] font-bold tracking-wide text-navy">paytm soundbox</div>
            <div className="mt-3 grid grid-cols-6 gap-1.5 px-2" aria-hidden>
              {Array.from({ length: 30 }, (_, i) => (
                <span key={i} className="h-1.5 w-1.5 rounded-full bg-slate-700" />
              ))}
            </div>
          </>
        )}
        <span
          data-testid="soundbox-led"
          aria-hidden
          className={`absolute ${compact ? 'right-2 top-2' : 'bottom-4 left-1/2 -translate-x-1/2'} h-3 w-3 rounded-full ${soundbox.playing ? 'animate-pulse bg-sky shadow-[0_0_12px_4px_rgba(0,185,241,0.7)]' : 'bg-slate-600'}`}
        />
      </div>
      <div
        className={`${compact ? 'flex-1' : 'mt-4 w-64'} rounded-xl bg-slate-900 px-3 py-2 font-mono text-[12px] leading-snug text-sky-200 shadow-inner`}
        role="status"
        aria-live="polite"
      >
        {soundbox.playing ? '🔊 ' : ''}
        {soundbox.text}
      </div>
    </div>
  )
}
