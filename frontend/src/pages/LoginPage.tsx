import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { login } from '../api/client'

export function LoginPage() {
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)
  const navigate = useNavigate()

  async function handleLogin(e: React.FormEvent) {
    e.preventDefault()
    setLoading(true)
    setError('')
    try {
      const data = await login(password)
      localStorage.setItem('vergabe_token', data.access_token)
      navigate('/')
    } catch {
      setError('Falsches Passwort.')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div style={{
      display: 'flex', alignItems: 'center', justifyContent: 'center',
      height: '100vh', background: 'var(--bg)',
    }}>
      <div style={{
        background: 'var(--white)', border: '0.5px solid var(--border)',
        borderRadius: 'var(--r2)', padding: '32px', width: 320,
        boxShadow: 'var(--sh2)',
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 24 }}>
          <div style={{ width: 8, height: 8, borderRadius: '50%', background: 'var(--accent)' }} />
          <span style={{ fontFamily: 'var(--mono)', fontSize: 15, fontWeight: 500 }}>vergabe.io</span>
        </div>
        <form onSubmit={handleLogin} style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
          <div>
            <label style={{ fontSize: 11, color: 'var(--text2)', fontWeight: 500, display: 'block', marginBottom: 4 }}>
              Passwort
            </label>
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="Admin-Passwort"
              autoFocus
              style={{
                width: '100%', background: 'var(--bg)', border: '0.5px solid var(--border)',
                borderRadius: 'var(--r)', padding: '8px 10px', fontSize: 13, outline: 'none',
                color: 'var(--text)',
              }}
            />
          </div>
          {error && <div style={{ fontSize: 12, color: 'var(--red)' }}>{error}</div>}
          <button
            type="submit"
            disabled={loading}
            style={{
              background: 'var(--accent)', color: 'white', border: 'none',
              borderRadius: 'var(--r)', padding: '8px 16px', fontSize: 13, fontWeight: 500,
              opacity: loading ? 0.6 : 1,
            }}
          >
            {loading ? 'Anmelden…' : 'Anmelden'}
          </button>
        </form>
      </div>
    </div>
  )
}
