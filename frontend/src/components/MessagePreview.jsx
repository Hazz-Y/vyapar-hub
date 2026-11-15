// WhatsApp-style preview bubble. Messages are previews only: nothing is sent off the device.
export default function MessagePreview({ body, to, time, compact = false }) {
  const parts = String(body || '').split(/(upi:\/\/pay\?\S+)/)
  return (
    <div className={`rounded-2xl bg-[#e7ddd3] p-3 ${compact ? '' : 'mt-2'}`} aria-label="Message preview">
      <div className="mb-1 flex items-center justify-between text-[11px] text-stone-600">
        <span>{to ? `To ${to}` : 'Customer'}</span>
        <span className="rounded-full bg-white/70 px-2 py-0.5 font-medium">Preview · not sent</span>
      </div>
      <div className="ml-auto max-w-[92%] rounded-xl rounded-tr-sm bg-[#d9fdd3] px-3 py-2 text-[13px] leading-snug text-stone-900 shadow-sm">
        {parts.map((p, i) =>
          p.startsWith('upi://') ? (
            <a key={i} href={p} className="break-all text-sky-700 underline">
              {p}
            </a>
          ) : (
            <span key={i}>{p}</span>
          ),
        )}
        <div className="mt-1 text-right text-[10px] text-stone-500">{time || 'abhi'} ✓✓</div>
      </div>
    </div>
  )
}
