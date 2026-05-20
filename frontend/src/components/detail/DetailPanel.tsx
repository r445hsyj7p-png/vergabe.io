import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { ChevronLeft, ChevronRight, X, ExternalLink, Star, EyeOff } from 'lucide-react'
import { fetchTender, setTag, removeTag } from '../../api/client'
import type { Tender } from '../../types'
import { SummaryButton } from './SummaryButton'

interface Props {
  tender: Tender | null
  onClose: () => void
  onNav: (dir: -1 | 1) => void
  pos: string
}

function fmt(cents: number | null, currency = 'EUR') {
  if (!cents) return null
  const val = cents / 100
  if (val >= 1_000_000) return `${(val / 1_000_000).toFixed(1)} Mio ${currency}`
  return `${val.toLocaleString('de-DE')} ${currency}`
}

function Tag({ label, color, bg, border }: { label: string; color: string; bg: string; border: string }) {
  return (
    <span
      className="font-mono text-[10px] px-2 py-[2px] rounded"
      style={{ background: bg, color, border: `0.5px solid ${border}` }}
    >
      {label}
    </span>
  )
}

function Field({ label, value, color }: { label: string; value?: string | null; color?: string }) {
  if (!value) return null
  return (
    <div className="flex flex-col gap-[3px]">
      <div
        className="text-[10px] font-medium uppercase tracking-[0.04em]"
        style={{ color: 'var(--color-ink3)' }}
      >
        {label}
      </div>
      <div className="text-[12.5px] leading-[1.35]" style={{ color: color ?? 'var(--color-ink)' }}>
        {value}
      </div>
    </div>
  )
}

export function DetailPanel({ tender, onClose, onNav, pos }: Props) {
  const qc = useQueryClient()

  const { data: detail } = useQuery({
    queryKey: ['tender', tender?.id],
    queryFn: () => fetchTender(tender!.id),
    enabled: !!tender,
  })

  const tagMut = useMutation({
    mutationFn: async (status: 'interest' | 'ignore' | null) => {
      if (status === null) await removeTag(tender!.id)
      else await setTag(tender!.id, status)
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: ['tenders'] }),
  })

  if (!tender) return null
  const d = detail

  const deadline = d?.deadline ? new Date(d.deadline) : null
  const daysLeft = deadline ? Math.ceil((deadline.getTime() - Date.now()) / 86400000) : null
  const deadlineColor = daysLeft != null && daysLeft <= 7
    ? 'var(--color-rose)'
    : daysLeft != null && daysLeft <= 14
    ? 'var(--color-orange)'
    : 'var(--color-ink2)'

  return (
    <div
      className="flex flex-col overflow-hidden shrink-0"
      style={{ width: 380, background: 'var(--color-surface)', borderLeft: '0.5px solid var(--color-border)' }}
    >
      {/* Topbar */}
      <div
        className="flex items-center justify-between px-4 py-2.5 shrink-0 gap-2"
        style={{ borderBottom: '0.5px solid var(--color-border)' }}
      >
        <button
          onClick={onClose}
          className="flex items-center gap-[5px] text-[11.5px]"
          style={{ color: 'var(--color-ink2)', background: 'none', border: 'none' }}
        >
          <X size={13} />
          Schließen
        </button>
        <div className="flex items-center gap-1.5 font-mono text-[11px]" style={{ color: 'var(--color-ink3)' }}>
          <span>{pos}</span>
          <button
            onClick={() => onNav(-1)}
            className="w-[22px] h-[22px] rounded flex items-center justify-center cursor-pointer"
            style={{ border: '0.5px solid var(--color-border)', background: 'var(--color-surface)', color: 'var(--color-ink2)' }}
          >
            <ChevronLeft size={13} />
          </button>
          <button
            onClick={() => onNav(1)}
            className="w-[22px] h-[22px] rounded flex items-center justify-center cursor-pointer"
            style={{ border: '0.5px solid var(--color-border)', background: 'var(--color-surface)', color: 'var(--color-ink2)' }}
          >
            <ChevronRight size={13} />
          </button>
        </div>
      </div>

      {/* Body */}
      <div className="flex-1 overflow-y-auto p-4">
        {/* Tags */}
        <div className="flex gap-[5px] flex-wrap mb-3">
          {tender.country !== 'DE' && (
            <Tag label="EU-weit" color="var(--color-brand)" bg="var(--color-brand-light)" border="#c7d7fb" />
          )}
          {tender.procedure_type && (
            <Tag
              label={tender.procedure_type.substring(0, 20)}
              color="var(--color-ink2)"
              bg="var(--color-chip)"
              border="var(--color-border)"
            />
          )}
          {tender.it_category && (
            <Tag label={tender.it_category} color="#065f46" bg="#d1fae5" border="#6ee7b7" />
          )}
        </div>

        {/* Title */}
        <div className="text-[15px] font-semibold leading-snug mb-[14px]" style={{ color: 'var(--color-ink)' }}>
          {tender.title}
        </div>

        {/* AI Summary */}
        <SummaryButton tenderId={tender.id} />

        {/* Actions */}
        <div className="flex gap-1.5 mb-4 flex-wrap">
          <button
            onClick={() => tagMut.mutate(tender.tag_status === 'interest' ? null : 'interest')}
            className="flex items-center gap-[5px] px-[11px] py-[5px] rounded text-[11.5px] cursor-pointer"
            style={{
              border: tender.tag_status === 'interest' ? '0.5px solid #86efac' : '0.5px solid var(--color-border)',
              background: tender.tag_status === 'interest' ? 'var(--color-emerald-light)' : 'var(--color-surface)',
              color: tender.tag_status === 'interest' ? 'var(--color-emerald)' : 'var(--color-ink2)',
              fontWeight: tender.tag_status === 'interest' ? 500 : 400,
            }}
          >
            <Star size={12} fill={tender.tag_status === 'interest' ? 'currentColor' : 'none'} />
            {tender.tag_status === 'interest' ? 'Interesse gesetzt' : 'Interesse'}
          </button>
          <button
            onClick={() => tagMut.mutate(tender.tag_status === 'ignore' ? null : 'ignore')}
            className="flex items-center gap-[5px] px-[11px] py-[5px] rounded text-[11.5px] cursor-pointer"
            style={{
              border: '0.5px solid var(--color-border)',
              background: tender.tag_status === 'ignore' ? 'var(--color-bg2)' : 'var(--color-surface)',
              color: 'var(--color-ink2)',
            }}
          >
            <EyeOff size={12} />
            Ignorieren
          </button>
        </div>

        {/* Fristen */}
        <div className="mb-[14px]">
          <div
            className="text-[10px] font-semibold uppercase tracking-[0.05em] mb-2"
            style={{ color: 'var(--color-ink3)' }}
          >
            Fristen & Eckdaten
          </div>
          <div className="grid grid-cols-2 gap-2.5">
            <Field
              label="Angebotsfrist"
              value={deadline
                ? `${deadline.toLocaleDateString('de-DE')}${daysLeft != null ? ` (${daysLeft}T)` : ''}`
                : null
              }
              color={deadlineColor}
            />
            <Field
              label="Veröffentlicht"
              value={d?.publication_date ? new Date(d.publication_date).toLocaleDateString('de-DE') : null}
            />
            <Field label="Erfüllungsort" value={d?.fulfillment_location || tender.region || null} />
            <Field label="Volumen" value={fmt(tender.value_max, tender.currency) ?? undefined} />
          </div>
        </div>

        <div className="h-px my-[14px]" style={{ background: 'var(--color-border)' }} />

        {/* Auftraggeber */}
        <div className="mb-[14px]">
          <div
            className="text-[10px] font-semibold uppercase tracking-[0.05em] mb-2"
            style={{ color: 'var(--color-ink3)' }}
          >
            Auftraggeber
          </div>
          <div className="grid grid-cols-2 gap-2.5">
            <div className="col-span-2">
              <Field label="Organisation" value={tender.contracting_authority} />
            </div>
            <Field label="Adresse" value={d?.authority_address || null} />
            <div>
              {d?.authority_email && (
                <div className="text-[10px] mb-0.5" style={{ color: 'var(--color-ink3)' }}>Kontakt</div>
              )}
              {d?.authority_email && (
                <a href={`mailto:${d.authority_email}`} className="text-[12.5px] block">
                  {d.authority_email}
                </a>
              )}
              {d?.authority_phone && (
                <div className="text-[12.5px]" style={{ color: 'var(--color-ink2)' }}>{d.authority_phone}</div>
              )}
            </div>
          </div>
        </div>

        {d?.description && (
          <>
            <div className="h-px my-[14px]" style={{ background: 'var(--color-border)' }} />
            <div className="mb-[14px]">
              <div
                className="text-[10px] font-semibold uppercase tracking-[0.05em] mb-2"
                style={{ color: 'var(--color-ink3)' }}
              >
                Beschreibung
              </div>
              <div className="text-[12px] leading-relaxed" style={{ color: 'var(--color-ink2)' }}>
                {d.description.substring(0, 500)}{d.description.length > 500 ? '…' : ''}
              </div>
            </div>
          </>
        )}

        {d?.lots && d.lots.length > 0 && (
          <>
            <div className="h-px my-[14px]" style={{ background: 'var(--color-border)' }} />
            <div className="mb-[14px]">
              <div
                className="text-[10px] font-semibold uppercase tracking-[0.05em] mb-2"
                style={{ color: 'var(--color-ink3)' }}
              >
                Lose ({d.lots.length})
              </div>
              {d.lots.map((lot) => (
                <div
                  key={lot.id}
                  className="rounded px-3 py-2.5 mb-2"
                  style={{ background: 'var(--color-bg)', border: '0.5px solid var(--color-border)' }}
                >
                  <div className="text-[12px] font-medium mb-[3px]" style={{ color: 'var(--color-ink)' }}>
                    {lot.lot_number && (
                      <span className="mr-1.5" style={{ color: 'var(--color-ink3)' }}>LOT-{lot.lot_number}</span>
                    )}
                    {lot.title}
                  </div>
                  {lot.description && (
                    <div className="text-[11px] leading-snug" style={{ color: 'var(--color-ink3)' }}>
                      {lot.description.substring(0, 100)}{lot.description.length > 100 ? '…' : ''}
                    </div>
                  )}
                </div>
              ))}
            </div>
          </>
        )}

        {/* Links */}
        <div className="h-px my-[14px]" style={{ background: 'var(--color-border)' }} />
        <div>
          <div
            className="text-[10px] font-semibold uppercase tracking-[0.05em] mb-2"
            style={{ color: 'var(--color-ink3)' }}
          >
            Links & Dokumente
          </div>
          <div className="flex gap-2 flex-wrap">
            {tender.source_url && (
              <a
                href={tender.source_url}
                target="_blank"
                rel="noopener noreferrer"
                className="inline-flex items-center gap-[5px] px-3 py-[6px] rounded text-white text-[12px] font-medium no-underline"
                style={{ background: 'var(--color-brand)' }}
              >
                <ExternalLink size={12} />
                Ausschreibung ansehen
              </a>
            )}
            <span
              className="inline-flex items-center px-3 py-[6px] rounded text-[11px]"
              style={{ border: '0.5px solid var(--color-border)', color: 'var(--color-ink3)' }}
            >
              {tender.sources[0]?.platform_name || 'Unbekannt'}
            </span>
          </div>
        </div>
      </div>
    </div>
  )
}
