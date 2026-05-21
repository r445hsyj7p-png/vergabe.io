import { useState } from 'react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { Bookmark, Globe } from 'lucide-react'
import { setTag, removeTag } from '../api/client'
import { cn } from '@/lib/utils'
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

  let bg = 'var(--color-chip)'
  let color = 'var(--color-ink2)'
  if (days < 0) { bg = 'var(--color-bg2)'; color = 'var(--color-ink3)' }
  else if (days <= 7) { bg = 'var(--color-rose-light)'; color = 'var(--color-rose)' }
  else if (days <= 14) { bg = 'var(--color-orange-light)'; color = 'var(--color-orange)' }
  else if (days <= 30) { bg = 'var(--color-amber-light)'; color = 'var(--color-amber)' }

  return (
    <span
      className="font-mono text-[11px] font-medium px-[7px] py-[3px] rounded-[5px] whitespace-nowrap"
      style={{ background: bg, color }}
    >
      {label}
    </span>
  )
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
      className={cn(
        'grid items-center px-[18px] py-[9px] cursor-pointer relative transition-[background,opacity] duration-100',
      )}
      style={{
        gridTemplateColumns: '86px 1fr 90px',
        borderBottom: '0.5px solid var(--color-border)',
        borderLeft: tender.tag_status === 'interest' ? '3px solid var(--color-emerald)' : '3px solid transparent',
        background: selected ? 'var(--color-brand-light)' : hovering ? '#faf9f7' : 'var(--color-surface)',
        opacity: tender.tag_status === 'ignore' ? 0.4 : 1,
        animationDelay: `${index * 0.03}s`,
      }}
    >
      {/* Deadline */}
      <div className="flex items-center gap-[3px]">
        <button
          onClick={(e) => e.stopPropagation()}
          className="w-[18px] h-5 flex items-center justify-center shrink-0"
          style={{ background: 'transparent', border: 'none', color: 'var(--color-ink3)' }}
          title="Speichern"
        >
          <Bookmark size={12} />
        </button>
        {deadlineBadge(tender.deadline)}
      </div>

      {/* Title + meta */}
      <div className="flex flex-col gap-[2px] px-[10px] min-w-0">
        <div className="flex items-center gap-[6px] flex-nowrap">
          <span
            className="font-mono text-[10px] px-[5px] py-[1px] rounded whitespace-nowrap"
            style={{ background: 'var(--color-chip)', border: '0.5px solid var(--color-border)', color: 'var(--color-ink2)' }}
          >
            {platformName.substring(0, 15)}
          </span>
          {tender.country !== 'DE' && (
            <span
              className="font-mono text-[10px] px-[5px] py-[1px] rounded flex items-center gap-1 whitespace-nowrap"
              style={{ background: 'var(--color-brand-light)', border: '0.5px solid #c7d7fb', color: 'var(--color-brand)' }}
            >
              <Globe size={9} />
              {tender.country === 'EU' || !tender.country ? 'EU-weit' : tender.country}
            </span>
          )}
          <span className="text-[11px] whitespace-nowrap overflow-hidden text-ellipsis" style={{ color: 'var(--color-ink2)' }}>
            {tender.contracting_authority}
          </span>
        </div>
        <div
          className="text-[12.5px] font-medium whitespace-nowrap overflow-hidden text-ellipsis"
          style={{ color: 'var(--color-ink)' }}
        >
          {tender.title}
        </div>
      </div>

      {/* Region */}
      <div
        className="text-[11.5px] text-right whitespace-nowrap overflow-hidden text-ellipsis"
        style={{ color: 'var(--color-ink2)' }}
      >
        {tender.region || tender.country}
      </div>

      {/* Hover actions */}
      {hovering && (
        <div
          onClick={(e) => e.stopPropagation()}
          className="absolute top-1/2 -translate-y-1/2 flex items-center gap-[1px] p-[2px] rounded z-[5]"
          style={{
            right: 104,
            background: 'var(--color-surface)',
            border: '0.5px solid var(--color-border)',
            boxShadow: '0 2px 8px rgba(0,0,0,.06)',
          }}
        >
          <button
            onClick={() => tagMut.mutate(tender.tag_status === 'interest' ? null : 'interest')}
            disabled={tagMut.isPending}
            className="px-2 py-1 rounded text-[11px]"
            style={{
              border: 'none',
              background: tender.tag_status === 'interest' ? 'var(--color-emerald-light)' : 'transparent',
              color: tender.tag_status === 'interest' ? 'var(--color-emerald)' : 'var(--color-ink2)',
              opacity: tagMut.isPending ? 0.5 : 1,
              cursor: tagMut.isPending ? 'default' : 'pointer',
            }}
          >
            {tagMut.isPending ? '…' : 'Interesse'}
          </button>
          <button
            onClick={() => tagMut.mutate(tender.tag_status === 'ignore' ? null : 'ignore')}
            disabled={tagMut.isPending}
            className="px-2 py-1 rounded text-[11px]"
            style={{
              border: 'none',
              background: tender.tag_status === 'ignore' ? 'var(--color-bg2)' : 'transparent',
              color: 'var(--color-ink2)',
              opacity: tagMut.isPending ? 0.5 : 1,
              cursor: tagMut.isPending ? 'default' : 'pointer',
            }}
          >
            {tagMut.isPending ? '…' : 'Ignorieren'}
          </button>
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
    <div className="flex-1 overflow-y-auto">
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
