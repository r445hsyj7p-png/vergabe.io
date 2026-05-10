import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
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

  function Tag({ label, color, bg, border }: { label: string; color: string; bg: string; border: string }) {
    return <span style={{ fontFamily: 'var(--mono)', fontSize: 10, padding: '2px 8px', borderRadius: 4, background: bg, color, border: `0.5px solid ${border}` }}>{label}</span>
  }

  function Field({ label, value, color }: { label: string; value?: string | null; color?: string }) {
    if (!value) return null
    return (
      <div style={{ display: 'flex', flexDirection: 'column', gap: 3 }}>
        <div style={{ fontSize: 10, color: 'var(--text3)', fontWeight: 500, textTransform: 'uppercase', letterSpacing: '.04em' }}>{label}</div>
        <div style={{ fontSize: 12.5, color: color ?? 'var(--text)', lineHeight: 1.35 }}>{value}</div>
      </div>
    )
  }

  const deadline = d?.deadline ? new Date(d.deadline) : null
  const daysLeft = deadline ? Math.ceil((deadline.getTime() - Date.now()) / 86400000) : null
  const deadlineColor = daysLeft != null && daysLeft <= 7 ? 'var(--red)' : daysLeft != null && daysLeft <= 14 ? 'var(--orange)' : 'var(--text2)'

  return (
    <div style={{
      width: 380, flexShrink: 0, background: 'var(--white)',
      borderLeft: '0.5px solid var(--border)',
      display: 'flex', flexDirection: 'column', overflow: 'hidden',
    }}>
      {/* Topbar */}
      <div style={{
        display: 'flex', alignItems: 'center', justifyContent: 'space-between',
        padding: '10px 16px', borderBottom: '0.5px solid var(--border)', flexShrink: 0, gap: 8,
      }}>
        <button onClick={onClose} style={{
          display: 'flex', alignItems: 'center', gap: 5, fontSize: 11.5,
          color: 'var(--text2)', background: 'none', border: 'none',
        }}>← Schließen</button>
        <div style={{ display: 'flex', alignItems: 'center', gap: 6, fontFamily: 'var(--mono)', fontSize: 11, color: 'var(--text3)' }}>
          <span>{pos}</span>
          <button onClick={() => onNav(-1)} style={{ width: 22, height: 22, borderRadius: 4, border: '0.5px solid var(--border)', background: 'var(--white)', color: 'var(--text2)', fontSize: 11, cursor: 'pointer' }}>‹</button>
          <button onClick={() => onNav(1)} style={{ width: 22, height: 22, borderRadius: 4, border: '0.5px solid var(--border)', background: 'var(--white)', color: 'var(--text2)', fontSize: 11, cursor: 'pointer' }}>›</button>
        </div>
      </div>

      {/* Body */}
      <div style={{ flex: 1, overflowY: 'auto', padding: 16 }}>
        {/* Tags */}
        <div style={{ display: 'flex', gap: 5, flexWrap: 'wrap', marginBottom: 12 }}>
          {tender.country !== 'DE' && <Tag label="EU-weit" color="var(--accent)" bg="var(--accent-l)" border="#c7d7fb" />}
          {tender.procedure_type && <Tag label={tender.procedure_type.substring(0, 20)} color="var(--text2)" bg="var(--gray-tag)" border="var(--border)" />}
          {tender.it_category && <Tag label={tender.it_category} color="#065f46" bg="#d1fae5" border="#6ee7b7" />}
        </div>

        {/* Title */}
        <div style={{ fontSize: 15, fontWeight: 600, color: 'var(--text)', lineHeight: 1.4, marginBottom: 14 }}>
          {tender.title}
        </div>

        {/* AI Summary — on demand */}
        <SummaryButton tenderId={tender.id} />

        {/* Actions */}
        <div style={{ display: 'flex', gap: 6, marginBottom: 16, flexWrap: 'wrap' }}>
          <button
            onClick={() => tagMut.mutate(tender.tag_status === 'interest' ? null : 'interest')}
            style={{
              display: 'flex', alignItems: 'center', gap: 5, padding: '5px 11px',
              borderRadius: 'var(--r)', fontSize: 11.5, cursor: 'pointer',
              border: tender.tag_status === 'interest' ? '0.5px solid #86efac' : '0.5px solid var(--border)',
              background: tender.tag_status === 'interest' ? 'var(--green-l)' : 'var(--white)',
              color: tender.tag_status === 'interest' ? 'var(--green)' : 'var(--text2)',
              fontWeight: tender.tag_status === 'interest' ? 500 : 400,
            }}
          >{tender.tag_status === 'interest' ? '★ Interesse gesetzt' : '☆ Interesse'}</button>
          <button
            onClick={() => tagMut.mutate(tender.tag_status === 'ignore' ? null : 'ignore')}
            style={{
              display: 'flex', alignItems: 'center', gap: 5, padding: '5px 11px',
              borderRadius: 'var(--r)', fontSize: 11.5, cursor: 'pointer',
              border: '0.5px solid var(--border)',
              background: tender.tag_status === 'ignore' ? 'var(--bg2)' : 'var(--white)',
              color: 'var(--text2)',
            }}
          >✕ Ignorieren</button>
        </div>

        {/* Fristen */}
        <div style={{ marginBottom: 14 }}>
          <div style={{ fontSize: 10, fontWeight: 600, color: 'var(--text3)', textTransform: 'uppercase', letterSpacing: '.05em', marginBottom: 8 }}>Fristen & Eckdaten</div>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10 }}>
            <Field label="Angebotsfrist" value={deadline ? `${deadline.toLocaleDateString('de-DE')}${daysLeft != null ? ` (${daysLeft}T)` : ''}` : null} color={deadlineColor} />
            <Field label="Veröffentlicht" value={d?.publication_date ? new Date(d.publication_date).toLocaleDateString('de-DE') : null} />
            <Field label="Erfüllungsort" value={d?.fulfillment_location || tender.region || null} />
            <Field label="Volumen" value={fmt(tender.value_max, tender.currency) || undefined} />
          </div>
        </div>

        <div style={{ height: 1, background: 'var(--border)', margin: '14px 0' }} />

        {/* Auftraggeber */}
        <div style={{ marginBottom: 14 }}>
          <div style={{ fontSize: 10, fontWeight: 600, color: 'var(--text3)', textTransform: 'uppercase', letterSpacing: '.05em', marginBottom: 8 }}>Auftraggeber</div>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10 }}>
            <div style={{ gridColumn: '1 / -1' }}>
              <Field label="Organisation" value={tender.contracting_authority} />
            </div>
            <Field label="Adresse" value={d?.authority_address || null} />
            <div>
              {d?.authority_email && <div style={{ fontSize: 10, color: 'var(--text3)', marginBottom: 2 }}>Kontakt</div>}
              {d?.authority_email && <a href={`mailto:${d.authority_email}`} style={{ fontSize: 12.5, display: 'block' }}>{d.authority_email}</a>}
              {d?.authority_phone && <div style={{ fontSize: 12.5, color: 'var(--text2)' }}>{d.authority_phone}</div>}
            </div>
          </div>
        </div>

        {d?.description && (
          <>
            <div style={{ height: 1, background: 'var(--border)', margin: '14px 0' }} />
            <div style={{ marginBottom: 14 }}>
              <div style={{ fontSize: 10, fontWeight: 600, color: 'var(--text3)', textTransform: 'uppercase', letterSpacing: '.05em', marginBottom: 8 }}>Beschreibung</div>
              <div style={{ fontSize: 12, color: 'var(--text2)', lineHeight: 1.6 }}>{d.description.substring(0, 500)}{d.description.length > 500 ? '…' : ''}</div>
            </div>
          </>
        )}

        {d?.lots && d.lots.length > 0 && (
          <>
            <div style={{ height: 1, background: 'var(--border)', margin: '14px 0' }} />
            <div style={{ marginBottom: 14 }}>
              <div style={{ fontSize: 10, fontWeight: 600, color: 'var(--text3)', textTransform: 'uppercase', letterSpacing: '.05em', marginBottom: 8 }}>Lose ({d.lots.length})</div>
              {d.lots.map((lot) => (
                <div key={lot.id} style={{
                  background: 'var(--bg)', border: '0.5px solid var(--border)',
                  borderRadius: 'var(--r)', padding: '10px 12px', marginBottom: 8,
                }}>
                  <div style={{ fontSize: 12, fontWeight: 500, color: 'var(--text)', marginBottom: 3 }}>
                    {lot.lot_number && <span style={{ color: 'var(--text3)', marginRight: 6 }}>LOT-{lot.lot_number}</span>}
                    {lot.title}
                  </div>
                  {lot.description && (
                    <div style={{ fontSize: 11, color: 'var(--text3)', lineHeight: 1.4 }}>
                      {lot.description.substring(0, 100)}{lot.description.length > 100 ? '…' : ''}
                    </div>
                  )}
                </div>
              ))}
            </div>
          </>
        )}

        {/* Links */}
        <div style={{ height: 1, background: 'var(--border)', margin: '14px 0' }} />
        <div>
          <div style={{ fontSize: 10, fontWeight: 600, color: 'var(--text3)', textTransform: 'uppercase', letterSpacing: '.05em', marginBottom: 8 }}>Links & Dokumente</div>
          <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
            {tender.source_url && (
              <a href={tender.source_url} target="_blank" rel="noopener noreferrer" style={{
                display: 'inline-flex', alignItems: 'center', gap: 5, padding: '6px 12px',
                borderRadius: 'var(--r)', background: 'var(--accent)', color: 'white',
                fontSize: 12, fontWeight: 500, textDecoration: 'none',
              }}>↗ Ausschreibung ansehen</a>
            )}
            <span style={{
              display: 'inline-flex', alignItems: 'center', padding: '6px 12px',
              borderRadius: 'var(--r)', border: '0.5px solid var(--border)',
              fontSize: 11, color: 'var(--text3)',
            }}>{tender.sources[0]?.platform_name || 'Unbekannt'}</span>
          </div>
        </div>
      </div>
    </div>
  )
}
