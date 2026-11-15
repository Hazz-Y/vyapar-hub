import { useCallback, useEffect, useRef, useState } from 'react'

export const MAX_RECORDING_MS = 25_000 // Sarvam's sync STT takes at most 30 s; stay well under

function pickMime() {
  if (typeof MediaRecorder === 'undefined') return null
  for (const t of ['audio/webm;codecs=opus', 'audio/webm', 'audio/mp4', 'audio/ogg;codecs=opus']) {
    if (MediaRecorder.isTypeSupported?.(t)) return t
  }
  return ''
}

// Records one voice command; auto-stops at 25 s. onDone(blob) gets the browser's native output.
export function useRecorder(onDone) {
  const [recording, setRecording] = useState(false)
  const [elapsed, setElapsed] = useState(0)
  const [error, setError] = useState(null)
  const rec = useRef(null)
  const timers = useRef([])
  const supported = typeof navigator !== 'undefined' && !!navigator.mediaDevices?.getUserMedia && pickMime() !== null

  const clear = () => {
    timers.current.forEach(clearInterval)
    timers.current.forEach(clearTimeout)
    timers.current = []
  }

  const stop = useCallback(() => {
    if (rec.current && rec.current.state !== 'inactive') rec.current.stop()
  }, [])

  const start = useCallback(async () => {
    setError(null)
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true })
      const mime = pickMime()
      const r = new MediaRecorder(stream, mime ? { mimeType: mime } : undefined)
      const chunks = []
      r.ondataavailable = (e) => e.data.size && chunks.push(e.data)
      r.onstop = () => {
        clear()
        stream.getTracks().forEach((t) => t.stop())
        setRecording(false)
        const blob = new Blob(chunks, { type: r.mimeType || mime || 'audio/webm' })
        if (blob.size) onDone(blob)
      }
      rec.current = r
      r.start()
      setRecording(true)
      const t0 = Date.now()
      setElapsed(0)
      timers.current.push(setInterval(() => setElapsed(Date.now() - t0), 200))
      timers.current.push(setTimeout(() => stop(), MAX_RECORDING_MS))
    } catch (e) {
      setError(e?.name === 'NotAllowedError' ? 'Mic ki permission nahi mili. Type karke likhiye.' : 'Mic nahi chal raha.')
    }
  }, [onDone, stop])

  useEffect(() => () => clear(), [])
  return { supported, recording, elapsed, error, start, stop }
}
