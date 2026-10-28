import { useEffect, useState } from 'react'

type BackendStatus = 'loading' | 'ok' | 'error'

function App() {
  const [status, setStatus] = useState<BackendStatus>('loading')

  useEffect(() => {
    fetch('/api/health')
      .then((res) => (res.ok ? res.json() : Promise.reject(res)))
      .then((body: { status: string }) => setStatus(body.status === 'ok' ? 'ok' : 'error'))
      .catch(() => setStatus('error'))
  }, [])

  return (
    <main>
      <h1>KI-aware-DocMgmt</h1>
      <p>Backend: {status}</p>
    </main>
  )
}

export default App
