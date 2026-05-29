import { useState } from 'react'
import { completeSetup } from '../api/client'

interface Props {
  onDone: () => void
}

export function SetupPage({ onDone }: Props) {
  const [name, setName] = useState('')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [confirm, setConfirm] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    setError(null)

    if (!name.trim()) {
      setError('Bitte gib deinen Namen ein.')
      return
    }
    if (!email.includes('@')) {
      setError('Bitte gib eine gültige E-Mail-Adresse ein.')
      return
    }
    if (password.length < 8) {
      setError('Passwort muss mindestens 8 Zeichen haben.')
      return
    }
    if (password !== confirm) {
      setError('Passwörter stimmen nicht überein.')
      return
    }

    setLoading(true)
    try {
      await completeSetup(name.trim(), email.trim().toLowerCase(), password)
      onDone()
    } catch {
      setError('Fehler beim Speichern. Bitte erneut versuchen.')
    } finally {
      setLoading(false)
    }
  }

  const canSubmit = !loading && !!name.trim() && !!email && !!password && !!confirm

  return (
    <div
      className="min-h-screen flex items-center justify-center"
      style={{ background: 'var(--color-bg)' }}
    >
      <div
        className="w-full max-w-sm rounded-xl p-8"
        style={{ background: 'var(--color-surface)', border: '0.5px solid var(--color-border)' }}
      >
        <div className="mb-6">
          <div className="text-[11px] font-semibold uppercase tracking-widest mb-1" style={{ color: 'var(--color-brand)' }}>
            vergabe.io
          </div>
          <h1 className="text-[18px] font-semibold" style={{ color: 'var(--color-ink)' }}>
            Ersteinrichtung
          </h1>
          <p className="text-[12.5px] mt-1" style={{ color: 'var(--color-ink3)' }}>
            Lege deinen Admin-Account an. Dieser Schritt ist nur einmalig erforderlich.
          </p>
        </div>

        <form onSubmit={handleSubmit} className="flex flex-col gap-3">
          <div>
            <label className="block text-[11px] font-medium mb-[3px]" style={{ color: 'var(--color-ink2)' }}>
              Name
            </label>
            <input
              type="text"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="Max Mustermann"
              autoFocus
              autoComplete="name"
              className="w-full rounded-[5px] text-[13px] px-[10px] py-[8px] outline-none"
              style={{ background: 'var(--color-bg)', border: '0.5px solid var(--color-border)', color: 'var(--color-ink)' }}
            />
          </div>

          <div>
            <label className="block text-[11px] font-medium mb-[3px]" style={{ color: 'var(--color-ink2)' }}>
              E-Mail
            </label>
            <input
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="max@beispiel.de"
              autoComplete="email"
              className="w-full rounded-[5px] text-[13px] px-[10px] py-[8px] outline-none"
              style={{ background: 'var(--color-bg)', border: '0.5px solid var(--color-border)', color: 'var(--color-ink)' }}
            />
          </div>

          <div>
            <label className="block text-[11px] font-medium mb-[3px]" style={{ color: 'var(--color-ink2)' }}>
              Passwort
            </label>
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="Mindestens 8 Zeichen"
              autoComplete="new-password"
              className="w-full rounded-[5px] text-[13px] px-[10px] py-[8px] outline-none"
              style={{ background: 'var(--color-bg)', border: '0.5px solid var(--color-border)', color: 'var(--color-ink)' }}
            />
          </div>

          <div>
            <label className="block text-[11px] font-medium mb-[3px]" style={{ color: 'var(--color-ink2)' }}>
              Passwort bestätigen
            </label>
            <input
              type="password"
              value={confirm}
              onChange={(e) => setConfirm(e.target.value)}
              placeholder="Passwort wiederholen"
              autoComplete="new-password"
              className="w-full rounded-[5px] text-[13px] px-[10px] py-[8px] outline-none"
              style={{ background: 'var(--color-bg)', border: '0.5px solid var(--color-border)', color: 'var(--color-ink)' }}
            />
          </div>

          {error && (
            <div
              className="rounded px-[10px] py-2 text-[12px]"
              style={{ background: 'var(--color-rose-light)', border: '0.5px solid #fecaca', color: 'var(--color-rose)' }}
            >
              {error}
            </div>
          )}

          <button
            type="submit"
            disabled={!canSubmit}
            className="w-full text-white rounded-md py-[9px] text-[13px] font-medium mt-1 transition-opacity"
            style={{
              background: 'var(--color-brand)',
              opacity: canSubmit ? 1 : 0.5,
              cursor: canSubmit ? 'pointer' : 'default',
            }}
          >
            {loading ? 'Speichern…' : 'Account anlegen'}
          </button>
        </form>
      </div>
    </div>
  )
}
