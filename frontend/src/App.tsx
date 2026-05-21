import React from 'react'
import { Routes, Route, Navigate } from 'react-router-dom'
import { LoginPage } from './pages/LoginPage'
import { SearchPage } from './pages/SearchPage'
import { AdminPage } from './pages/AdminPage'

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
