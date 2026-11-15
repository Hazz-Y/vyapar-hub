import { useEffect, useState } from 'react'
import { api } from './api/client'

export default function App() {
  const [status, setStatus] = useState('checking…')
  useEffect(() => {
    api.health().then((r) => setStatus(r.status)).catch(() => setStatus('down'))
  }, [])
  return (
    <main className="min-h-screen bg-white p-6 text-navy">
      <h1 className="text-2xl font-bold">Vyapar Hub</h1>
      <p className="mt-2">backend: {status}</p>
    </main>
  )
}
