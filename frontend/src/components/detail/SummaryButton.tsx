import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { fetchSummaryStatus, generateSummary, deleteSummary } from '../../api/client'

interface Props {
  tenderId: string
}

const PROVIDER_LABELS: Record<string, string> = {
  anthropic: 'Claude Haiku',
  ollama:    'Lokales LLM (Ollama)',
  openai:    'GPT-4o mini',
}

function ProviderBadge({ provider }: { provider: string }) {
  const isLocal = provider === 'ollama'
  return (
    <span style={{
      fontSize: 10,
      fontFamily: 'var(--mono)',
      padding: '1px 6px',
      borderRadius: 4,
      background: isLocal ? 'var(--green-l)' : 'var(--accent-l)',
      color: isLocal ? 'var(--green)' : 'var(--accent)',
      border: `0.5px solid ${isLocal ? '#86efac' : '#c7d7fb'}`,
      whiteSpace: 'nowrap',
    }}>
      {PROVIDER_LABELS[provider] || provider}
    </span>
  )
}

export function SummaryButton({ tenderId }: Props) {
  const qc = useQueryClient()
  const [generating, setGenerating] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const { data: status, isLoading: statusLoading } = useQuery({
    queryKey: ['summary-status', tenderId],
    queryFn: () => fetchSummaryStatus(tenderId),
    staleTime: 60_000,
  })

  const deleteMut = useMutation({
    mutationFn: () => deleteSummary(tenderId),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['summary-status', tenderId] })
      setError(null)
    },
  })

  async function handleGenerate() {
    setGenerating(true)
    setError(null)
    try {
      await generateSummary(tenderId)
      qc.invalidateQueries({ queryKey: ['summary-status', tenderId] })
    } catch (e: any) {
      const detail = e?.response?.data?.detail || 'Fehler beim Generieren der Zusammenfassung.'
      setError(detail)
    } finally {
      setGenerating(false)
    }
  }

  if (statusLoading) return null

  // ── Summary already exists ───────────────────────────────────────────
  if (status?.exists && status.summary) {
    const s = status.summary
    const date = new Date(s.created_at).toLocaleDateString('de-DE')
    const costLabel = s.cost_cents === 0
      ? 'kostenfrei'
      : `${(s.cost_cents / 100).toFixed(3)} €`

    return (
      <div style={{ marginBottom: 16 }}>
        {/* Header */}
        <div style={{
          display: 'flex', alignItems: 'center', justifyContent: 'space-between',
          marginBottom: 8,
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
            <span style={{ fontSize: 10, fontWeight: 600, color: 'var(--text3)', textTransform: 'uppercase', letterSpacing: '.05em' }}>
              KI-Zusammenfassung
            </span>
            <ProviderBadge provider={s.provider} />
          </div>
          <button
            onClick={() => deleteMut.mutate()}
            title="Zusammenfassung löschen und neu generieren"
            style={{
              background: 'none', border: 'none', cursor: 'pointer',
              fontSize: 11, color: 'var(--text3)', padding: '2px 4px', borderRadius: 4,
              transition: 'color .1s',
            }}
            onMouseEnter={(e) => (e.currentTarget.style.color = 'var(--red)')}
            onMouseLeave={(e) => (e.currentTarget.style.color = 'var(--text3)')}
          >↺ Neu generieren</button>
        </div>

        {/* Summary text */}
        <div style={{
          background: 'var(--accent-l)',
          border: '0.5px solid #c7d7fb',
          borderRadius: 'var(--r)',
          padding: '10px 12px',
        }}>
          <p style={{ fontSize: 12.5, color: 'var(--text)', lineHeight: 1.65 }}>
            {s.summary_text}
          </p>
        </div>

        {/* Meta */}
        <div style={{ display: 'flex', gap: 8, marginTop: 5 }}>
          <span style={{ fontSize: 10, color: 'var(--text3)', fontFamily: 'var(--mono)' }}>
            {s.model}
          </span>
          <span style={{ fontSize: 10, color: 'var(--text3)' }}>·</span>
          <span style={{ fontSize: 10, color: 'var(--text3)', fontFamily: 'var(--mono)' }}>
            {costLabel}
          </span>
          <span style={{ fontSize: 10, color: 'var(--text3)' }}>·</span>
          <span style={{ fontSize: 10, color: 'var(--text3)' }}>{date}</span>
        </div>
      </div>
    )
  }

  // ── No summary yet ───────────────────────────────────────────────────
  const providerName = status?.provider_configured || 'anthropic'
  const isLocal = providerName === 'ollama'

  return (
    <div style={{ marginBottom: 16 }}>
      {error && (
        <div style={{
          background: 'var(--red-l)', border: '0.5px solid #fecaca',
          borderRadius: 'var(--r)', padding: '8px 10px', marginBottom: 8,
          fontSize: 12, color: 'var(--red)', lineHeight: 1.5,
        }}>
          {error}
        </div>
      )}

      <button
        onClick={handleGenerate}
        disabled={generating}
        style={{
          display: 'inline-flex', alignItems: 'center', gap: 7,
          padding: '7px 13px', borderRadius: 'var(--r)',
          border: '0.5px solid var(--border)',
          background: generating ? 'var(--bg2)' : 'var(--white)',
          color: generating ? 'var(--text3)' : 'var(--text2)',
          fontSize: 12.5, cursor: generating ? 'not-allowed' : 'pointer',
          transition: 'all .12s',
          width: '100%', justifyContent: 'center',
        }}
        onMouseEnter={(e) => { if (!generating) { e.currentTarget.style.borderColor = 'var(--accent)'; e.currentTarget.style.color = 'var(--accent)' } }}
        onMouseLeave={(e) => { if (!generating) { e.currentTarget.style.borderColor = 'var(--border)'; e.currentTarget.style.color = 'var(--text2)' } }}
      >
        {generating ? (
          <>
            <Spinner />
            Zusammenfassung wird generiert…
          </>
        ) : (
          <>
            <span style={{ fontSize: 14 }}>✦</span>
            KI-Zusammenfassung erstellen
            <ProviderBadge provider={providerName} />
            {isLocal && (
              <span style={{ fontSize: 10, color: 'var(--green)', fontFamily: 'var(--mono)' }}>
                kostenlos
              </span>
            )}
          </>
        )}
      </button>

      {!generating && (
        <div style={{ fontSize: 10.5, color: 'var(--text3)', marginTop: 5, textAlign: 'center' }}>
          Einmalig generiert · danach gespeichert · kein weiterer Aufruf
        </div>
      )}
    </div>
  )
}

function Spinner() {
  return (
    <svg width="14" height="14" viewBox="0 0 14 14" fill="none"
      style={{ animation: 'spin 1s linear infinite' }}>
      <style>{`@keyframes spin { to { transform: rotate(360deg) } }`}</style>
      <circle cx="7" cy="7" r="5.5" stroke="var(--border2)" strokeWidth="1.5"/>
      <path d="M7 1.5A5.5 5.5 0 0 1 12.5 7" stroke="var(--accent)" strokeWidth="1.5" strokeLinecap="round"/>
    </svg>
  )
}
