import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState } from 'react'
import { createApi } from '../api/client'
import { playSpeech } from '../lib/audio'

const AppCtx = createContext(null)

export function AppProvider({ children, merchantId = 1, api: injectedApi, pollMs = 2000 }) {
  const api = useMemo(() => injectedApi || createApi(merchantId), [injectedApi, merchantId])
  const [status, setStatus] = useState(null)
  const [version, setVersion] = useState(0)
  const [approvalQueue, setApprovalQueue] = useState([])
  const [trace, setTrace] = useState(null) // {question, reply, steps}
  const [soundbox, setSoundbox] = useState({ text: 'Vyapar Hub ready', playing: false })
  const chain = useRef(Promise.resolve())
  const seen = useRef(new Set())
  const lastEventId = useRef(null)

  const refresh = useCallback(() => setVersion((v) => v + 1), [])

  const loadStatus = useCallback(() => api.status().then(setStatus).catch(() => setStatus(null)), [api])
  useEffect(() => {
    loadStatus()
  }, [loadStatus, version])

  // Soundbox: announcements are played one after another.
  const say = useCallback(
    ({ text, audio, eventId }) => {
      if (eventId) {
        if (seen.current.has(eventId)) return chain.current
        seen.current.add(eventId)
      }
      chain.current = chain.current.then(async () => {
        setSoundbox({ text, playing: true })
        api.setSpeaker?.(true, text)?.catch?.(() => {})
        try {
          const a = audio || (await api.speak(text).catch(() => null))
          await playSpeech(a, text)
        } finally {
          setSoundbox({ text, playing: false })
          api.setSpeaker?.(false)?.catch?.(() => {})
        }
      })
      return chain.current
    },
    [api],
  )

  // Poll the Soundbox event feed (payments, scheduled reminders/briefing).
  useEffect(() => {
    if (!pollMs) return undefined
    let stop = false
    const tick = async () => {
      try {
        if (lastEventId.current === null) {
          const all = await api.soundboxEvents(0)
          lastEventId.current = all.length ? all[all.length - 1].id : 0
          all.forEach((e) => seen.current.add(e.id)) // don't replay history on load
          if (all.length) setSoundbox((s) => ({ ...s, text: all[all.length - 1].text }))
        } else {
          const fresh = await api.soundboxEvents(lastEventId.current)
          for (const e of fresh) {
            lastEventId.current = e.id
            if (!seen.current.has(e.id)) {
              say({ text: e.text, eventId: e.id })
              refresh()
            }
          }
        }
      } catch {
        /* backend offline: keep polling */
      }
      if (!stop) timer = setTimeout(tick, pollMs)
    }
    let timer = setTimeout(tick, 0)
    return () => {
      stop = true
      clearTimeout(timer)
    }
  }, [api, pollMs, say, refresh])

  const requestApproval = useCallback((actions) => {
    const pending = (actions || []).filter((a) => a.status === 'pending')
    if (pending.length) setApprovalQueue((q) => [...q, ...pending.filter((p) => !q.some((x) => x.id === p.id))])
  }, [])
  const closeApproval = useCallback((id) => setApprovalQueue((q) => q.filter((a) => a.id !== id)), [])

  // After /demo/reset the event ids restart from 1, so the poller must forget what it has seen.
  const resetSession = useCallback(() => {
    lastEventId.current = null
    seen.current = new Set()
    setApprovalQueue([])
    setTrace(null)
    setSoundbox({ text: 'Vyapar Hub ready', playing: false })
    refresh()
  }, [refresh])

  const value = {
    api, status, version, refresh, trace, setTrace, soundbox, say,
    approvalQueue, requestApproval, closeApproval, reloadStatus: loadStatus, resetSession,
  }
  return <AppCtx.Provider value={value}>{children}</AppCtx.Provider>
}

export function useApp() {
  const ctx = useContext(AppCtx)
  if (!ctx) throw new Error('useApp must be used inside AppProvider')
  return ctx
}

// Load data and re-load whenever the app-wide refresh counter changes.
export function useLoad(fn, deps = []) {
  const { version } = useApp()
  const [state, setState] = useState({ data: null, error: null, loading: true })
  const [nonce, setNonce] = useState(0)
  useEffect(() => {
    let alive = true
    setState((s) => ({ ...s, loading: true }))
    fn()
      .then((data) => alive && setState({ data, error: null, loading: false }))
      .catch((error) => alive && setState((s) => ({ data: s.data, error, loading: false })))
    return () => {
      alive = false
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [version, nonce, ...deps])
  return { ...state, reload: () => setNonce((n) => n + 1) }
}
