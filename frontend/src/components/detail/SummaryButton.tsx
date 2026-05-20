import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { Sparkles, RefreshCw } from 'lucide-react'
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
    <span
      className="font-mono text-[10px] px-[6px] py-[1px] rounded whitespace-nowrap"
      style={{
        background: isLocal ? 'var(--color-emerald-light)' : 'var(--color-brand-light)',
        color: isLocal ? 'var(--color-emerald)' : 'var(--color-brand)',
        border: `0.5px solid ${isLocal ? '#86efac' : '#c7d7fb'}`,
      }}
    >
      {PROVIDER_LABELS[provider] || provider}
    </span>
  )
}

function Spinner() {
  return (
    <RefreshCw
      size={14}
      className="animate-spin"
      style={{ color: 'var(--color-brand)' }}
    />
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
    } catch (e: unknown) {
      const err = e as { response?: { data?: { detail?: string } } }
      const detail = err?.response?.data?.detail || 'Fehler beim Generieren der Zusammenfassung.'
      setError(detail)
    } finally {
      setGenerating(false)
    }
  }

  if (statusLoading) return null

  // Summary already exists
  if (status?.exists && status.summary) {
    const s = status.summary
    const date = new Date(s.created_at).toLocaleDateString('de-DE')
    const costLabel = s.cost_cents === 0
      ? 'kostenfrei'
      : `${(s.cost_cents / 100).toFixed(3)} €`

    return (
      <div className="mb-4">
        <div className="flex items-center justify-between mb-2">
          <div className="flex items-center gap-1.5">
            <span
              className="text-[10px] font-semibold uppercase tracking-wider"
              style={{ color: 'var(--color-ink3)' }}
            >
              KI-Zusammenfassung
            </span>
            <ProviderBadge provider={s.provider} />
          </div>
          <button
            onClick={() => deleteMut.mutate()}
            title="Zusammenfassung löschen und neu generieren"
            className="flex items-center gap-1 text-[11px] px-1 py-[2px] rounded transition-colors"
            style={{ background: 'none', border: 'none', color: 'var(--color-ink3)', cursor: 'pointer' }}
            onMouseEnter={(e) => { e.currentTarget.style.color = 'var(--color-rose)' }}
            onMouseLeave={(e) => { e.currentTarget.style.color = 'var(--color-ink3)' }}
          >
            <RefreshCw size={11} />
            Neu generieren
          </button>
        </div>

        <div
          className="rounded px-3 py-2.5"
          style={{ background: 'var(--color-brand-light)', border: '0.5px solid #c7d7fb' }}
        >
          <p className="text-[12.5px] leading-[1.65]" style={{ color: 'var(--color-ink)' }}>
            {s.summary_text}
          </p>
        </div>

        <div className="flex gap-2 mt-[5px]">
          <span className="font-mono text-[10px]" style={{ color: 'var(--color-ink3)' }}>{s.model}</span>
          <span className="text-[10px]" style={{ color: 'var(--color-ink3)' }}>·</span>
          <span className="font-mono text-[10px]" style={{ color: 'var(--color-ink3)' }}>{costLabel}</span>
          <span className="text-[10px]" style={{ color: 'var(--color-ink3)' }}>·</span>
          <span className="text-[10px]" style={{ color: 'var(--color-ink3)' }}>{date}</span>
        </div>
      </div>
    )
  }

  // No summary yet
  const providerName = status?.provider_configured || 'anthropic'
  const isLocal = providerName === 'ollama'

  return (
    <div className="mb-4">
      {error && (
        <div
          className="rounded px-[10px] py-2 mb-2 text-[12px] leading-relaxed"
          style={{ background: 'var(--color-rose-light)', border: '0.5px solid #fecaca', color: 'var(--color-rose)' }}
        >
          {error}
        </div>
      )}

      <button
        onClick={handleGenerate}
        disabled={generating}
        className="inline-flex items-center gap-[7px] px-[13px] py-[7px] rounded w-full justify-center text-[12.5px] transition-all"
        style={{
          border: '0.5px solid var(--color-border)',
          background: generating ? 'var(--color-bg2)' : 'var(--color-surface)',
          color: generating ? 'var(--color-ink3)' : 'var(--color-ink2)',
          cursor: generating ? 'not-allowed' : 'pointer',
        }}
        onMouseEnter={(e) => {
          if (!generating) {
            e.currentTarget.style.borderColor = 'var(--color-brand)'
            e.currentTarget.style.color = 'var(--color-brand)'
          }
        }}
        onMouseLeave={(e) => {
          if (!generating) {
            e.currentTarget.style.borderColor = 'var(--color-border)'
            e.currentTarget.style.color = 'var(--color-ink2)'
          }
        }}
      >
        {generating ? (
          <>
            <Spinner />
            Zusammenfassung wird generiert…
          </>
        ) : (
          <>
            <Sparkles size={14} />
            KI-Zusammenfassung erstellen
            <ProviderBadge provider={providerName} />
            {isLocal && (
              <span className="font-mono text-[10px]" style={{ color: 'var(--color-emerald)' }}>
                kostenlos
              </span>
            )}
          </>
        )}
      </button>

      {!generating && (
        <div className="text-[10.5px] mt-[5px] text-center" style={{ color: 'var(--color-ink3)' }}>
          Einmalig generiert · danach gespeichert · kein weiterer Aufruf
        </div>
      )}
    </div>
  )
}
