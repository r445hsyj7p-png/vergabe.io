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

export default function App() {
  const [setupRequired, setSetupRequired] = useState<boolean | null>(null)

  useEffect(() => {
    fetchSetupStatus()
      .then((s) => setSetupRequired(s.setup_required))
      .catch(() => setSetupRequired(false))
  }, [])

  if (setupRequired === null) return null

  if (setupRequired) {
    return (
      <ErrorBoundary>
        <SetupPage onDone={() => setSetupRequired(false)} />
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
