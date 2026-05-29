import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { login } from '../api/client'

export function LoginPage() {
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)
  const navigate = useNavigate()

  async function handleLogin(e: React.FormEvent) {
    e.preventDefault()
    setLoading(true)
    setError('')
    try {
      const data = await login(email.trim().toLowerCase(), password)
      sessionStorage.setItem('vergabe_token', data.access_token)
      navigate('/')
    } catch {
      setError('E-Mail oder Passwort falsch.')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="flex items-center justify-center h-screen" style={{ background: 'var(--color-bg)' }}>
      <div
        className="flex flex-col rounded-lg p-8 w-80"
        style={{ background: 'var(--color-surface)', border: '0.5px solid var(--color-border)', boxShadow: '0 4px 24px rgba(0,0,0,.06)' }}
      >
        <div className="flex items-center gap-2 mb-6">
          <div className="w-2 h-2 rounded-full" style={{ background: 'var(--color-brand)' }} />
          <span className="font-mono text-[15px] font-medium" style={{ color: 'var(--color-ink)' }}>vergabe.io</span>
        </div>

        <form onSubmit={handleLogin} className="flex flex-col gap-3">
          <div>
            <label className="block text-[11px] font-medium mb-1" style={{ color: 'var(--color-ink2)' }}>
              E-Mail
            </label>
            <input
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="max@beispiel.de"
              autoFocus
              autoComplete="email"
              className="w-full px-3 py-2 text-[13px] rounded-md outline-none"
              style={{ background: 'var(--color-bg)', border: '0.5px solid var(--color-border)', color: 'var(--color-ink)' }}
            />
          </div>

          <div>
            <label className="block text-[11px] font-medium mb-1" style={{ color: 'var(--color-ink2)' }}>
              Passwort
            </label>
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="Passwort"
              autoComplete="current-password"
              className="w-full px-3 py-2 text-[13px] rounded-md outline-none"
              style={{ background: 'var(--color-bg)', border: '0.5px solid var(--color-border)', color: 'var(--color-ink)' }}
            />
          </div>

          {error && (
            <div className="text-[12px]" style={{ color: 'var(--color-rose)' }}>
              {error}
            </div>
          )}

          <button
            type="submit"
            disabled={loading || !email || !password}
            className="text-white rounded-md py-2 px-4 text-[13px] font-medium transition-opacity mt-1"
            style={{
              background: 'var(--color-brand)',
              opacity: (loading || !email || !password) ? 0.6 : 1,
              cursor: (loading || !email || !password) ? 'default' : 'pointer',
            }}
          >
            {loading ? 'Anmelden…' : 'Anmelden'}
          </button>
        </form>
      </div>
    </div>
  )
}
