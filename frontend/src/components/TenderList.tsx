import { useState } from 'react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { setTag, removeTag } from '../api/client'
import type { Tender } from '../types'

interface RowProps {
  tender: Tender
  index: number
  selected: boolean
  onClick: () => void
  onTagChange: () => void
}

function deadlineBadge(deadline: string | null) {
  if (!deadline) return null
  const d = new Date(deadline)
  const now = new Date()
  const days = Math.ceil((d.getTime() - now.getTime()) / 86400000)
  const label = d.toLocaleDateString('de-DE', { day: '2-digit', month: '2-digit', year: '2-digit' })
  let bg = 'var(--gray-tag)', color = 'var(--text2)'
  if (days < 0) { bg = 'var(--bg2)'; color = 'var(--text3)' }
  else if (days <= 7) { bg = 'var(--red-l)'; color = 'var(--red)' }
  else if (days <= 14) { bg = 'var(--orange-l)'; color = 'var(--orange)' }
  else if (days <= 30) { bg = 'var(--amber-l)'; color = 'var(--amber)' }
  return <span style={{ fontFamily: 'var(--mono)', fontSize: 11, fontWeight: 500, padding: '3px 7px', borderRadius: 5, background: bg, color, whiteSpace: 'nowrap' }}>{label}</span>
}

export function TenderRow({ tender, index, selected, onClick, onTagChange }: RowProps) {
  const [hovering, setHovering] = useState(false)
  const qc = useQueryClient()

  const tagMut = useMutation({
    mutationFn: async (status: 'interest' | 'ignore' | null) => {
      if (status === null) await removeTag(tender.id)
      else await setTag(tender.id, status)
    },
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['tenders'] }); onTagChange() },
  })

  const firstSource = tender.sources[0]
  const platformName = firstSource?.platform_name || 'Unbekannt'

  return (
    <div
      onClick={onClick}
      onMouseEnter={() => setHovering(true)}
      onMouseLeave={() => setHovering(false)}
      style={{
        display: 'grid', gridTemplateColumns: '86px 1fr 90px', alignItems: 'center',
        padding: '9px 18px', borderBottom: '0.5px solid var(--border)',
        background: selected ? 'var(--accent-l)' : hovering ? '#faf9f7' : 'var(--white)',
        cursor: 'pointer', position: 'relative',
        borderLeft: tender.tag_status === 'interest' ? '3px solid var(--green)' : '3px solid transparent',
        opacity: tender.tag_status === 'ignore' ? 0.4 : 1,
        transition: 'background .1s, opacity .1s',
        animationDelay: `${index * 0.03}s`,
      }}
    >
      {/* Deadline */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 3 }}>
        <button
          onClick={(e) => { e.stopPropagation(); /* bookmark */ }}
          style={{ width: 18, height: 20, background: 'transparent', border: 'none', color: 'var(--text3)', fontSize: 12, padding: 0, flexShrink: 0 }}
          title="Speichern"
        >🔖</button>
        {deadlineBadge(tender.deadline)}
      </div>

      {/* Title + meta */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: 2, padding: '0 10px', minWidth: 0 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 6, flexWrap: 'nowrap' }}>
          <span style={{ fontFamily: 'var(--mono)', fontSize: 10, padding: '1px 5px', borderRadius: 4, background: 'var(--gray-tag)', border: '0.5px solid var(--border)', color: 'var(--text2)', whiteSpace: 'nowrap' }}>
            {platformName.substring(0, 15)}
          </span>
          {tender.country !== 'DE' && (
            <span style={{ fontFamily: 'var(--mono)', fontSize: 10, padding: '1px 5px', borderRadius: 4, background: 'var(--accent-l)', border: '0.5px solid #c7d7fb', color: 'var(--accent)', whiteSpace: 'nowrap' }}>
              {tender.country === 'EU' || !tender.country ? 'EU-weit' : tender.country}
            </span>
          )}
          <span style={{ fontSize: 11, color: 'var(--text2)', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
            {tender.contracting_authority}
          </span>
        </div>
        <div style={{ fontSize: 12.5, fontWeight: 500, color: 'var(--text)', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
          {tender.title}
        </div>
      </div>

      {/* Region */}
      <div style={{ fontSize: 11.5, color: 'var(--text2)', textAlign: 'right', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
        {tender.region || tender.country}
      </div>

      {/* Hover actions */}
      {hovering && (
        <div
          onClick={(e) => e.stopPropagation()}
          style={{
            position: 'absolute', right: 104, top: '50%', transform: 'translateY(-50%)',
            background: 'var(--white)', border: '0.5px solid var(--border)', borderRadius: 'var(--r)',
            boxShadow: 'var(--sh2)', display: 'flex', alignItems: 'center', gap: 1, padding: 2, zIndex: 5,
          }}
        >
          <button
            onClick={() => tagMut.mutate(tender.tag_status === 'interest' ? null : 'interest')}
            style={{
              padding: '4px 8px', borderRadius: 4, border: 'none', fontSize: 11,
              background: tender.tag_status === 'interest' ? 'var(--green-l)' : 'transparent',
              color: tender.tag_status === 'interest' ? 'var(--green)' : 'var(--text2)',
              cursor: 'pointer',
            }}
          >Interesse</button>
          <button
            onClick={() => tagMut.mutate(tender.tag_status === 'ignore' ? null : 'ignore')}
            style={{
              padding: '4px 8px', borderRadius: 4, border: 'none', fontSize: 11,
              background: tender.tag_status === 'ignore' ? 'var(--bg2)' : 'transparent',
              color: 'var(--text2)', cursor: 'pointer',
            }}
          >Ignorieren</button>
        </div>
      )}
    </div>
  )
}

interface ListProps {
  tenders: Tender[]
  selectedId: string | null
  onSelect: (t: Tender) => void
}

export function TenderList({ tenders, selectedId, onSelect }: ListProps) {
  const qc = useQueryClient()
  return (
    <div style={{ flex: 1, overflowY: 'auto' }}>
      {tenders.map((t, i) => (
        <TenderRow
          key={t.id}
          tender={t}
          index={i}
          selected={selectedId === t.id}
          onClick={() => onSelect(t)}
          onTagChange={() => qc.invalidateQueries({ queryKey: ['tenders'] })}
        />
      ))}
    </div>
  )
}
