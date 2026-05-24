import React, { useEffect, useState } from 'react'
import { Routes, Route, Navigate } from 'react-router-dom'
import { LoginPage } from './pages/LoginPage'
import { SearchPage } from './pages/SearchPage'
import { AdminPage } from './pages/AdminPage'
import { SetupPage } from './pages/SetupPage'
import { fetchSetupStatus } from './api/client'

class ErrorBoundary extends React.Component<
  { children: React.ReactNode },
  { error: Error | null }
> {
  state: { error: Error | null } = { error: null }

  static getDerivedStateFromError(error: Error) {
    return { error }
  }

  render() {
    if (this.state.error) {
      return (
        <div style={{ padding: 32, fontFamily: 'monospace', color: '#ef4444', background: 'var(--color-bg)', minHeight: '100vh' }}>
          <strong>Fehler:</strong> {this.state.error.message}
          <br />
          <button
            style={{ marginTop: 16, cursor: 'pointer', padding: '6px 12px' }}
            onClick={() => this.setState({ error: null })}
          >
            Zurücksetzen
          </button>
        </div>
      )
    }
    return this.props.children
  }
}

function isLoggedIn() {
  return !!sessionStorage.getItem('vergabe_token')
}

function PrivateRoute({ children }: { children: React.ReactNode }) {
  return isLoggedIn() ? <>{children}</> : <Navigate to="/login" replace />
}

type AppState = 'loading' | 'setup' | 'ready' | 'error'

async function pollSetupStatus(retries = 8, delayMs = 1500): Promise<boolean> {
  for (let i = 0; i < retries; i++) {
    try {
      const s = await fetchSetupStatus()
      return s.setup_required
    } catch {
      if (i < retries - 1) {
        await new Promise((r) => setTimeout(r, delayMs))
      }
    }
  }
  throw new Error('Backend nicht erreichbar')
}

export default function App() {
  const [state, setState] = useState<AppState>('loading')

  useEffect(() => {
    pollSetupStatus()
      .then((required) => setState(required ? 'setup' : 'ready'))
      .catch(() => setState('error'))
  }, [])

  if (state === 'loading') {
    return (
      <div style={{
        minHeight: '100vh', display: 'flex', alignItems: 'center', justifyContent: 'center',
        background: 'var(--color-bg)', color: 'var(--color-ink3)', fontSize: 13, fontFamily: 'monospace',
      }}>
        Verbinde mit Server…
      </div>
    )
  }

  if (state === 'error') {
    return (
      <div style={{
        minHeight: '100vh', display: 'flex', flexDirection: 'column',
        alignItems: 'center', justifyContent: 'center',
        background: 'var(--color-bg)', color: 'var(--color-rose)', gap: 12,
      }}>
        <div style={{ fontSize: 14 }}>Backend nicht erreichbar — bitte Seite neu laden.</div>
        <button
          onClick={() => window.location.reload()}
          style={{ fontSize: 12, padding: '6px 14px', cursor: 'pointer', borderRadius: 6, border: '1px solid currentColor' }}
        >
          Neu laden
        </button>
      </div>
    )
  }

  if (state === 'setup') {
    return (
      <ErrorBoundary>
        <SetupPage onDone={() => setState('ready')} />
      </ErrorBoundary>
    )
  }

  return (
    <ErrorBoundary>
      <Routes>
        <Route path="/login" element={<LoginPage />} />
        <Route path="/" element={<PrivateRoute><SearchPage /></PrivateRoute>} />
        <Route path="/admin" element={<PrivateRoute><AdminPage /></PrivateRoute>} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </ErrorBoundary>
  )
}
