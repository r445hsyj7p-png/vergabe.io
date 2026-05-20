import { cn } from '@/lib/utils'
import type { TenderFilters } from '../../types'

interface Props {
  filters: TenderFilters
  onChange: (f: TenderFilters) => void
}

const IT_CATS = ['Software Dev', 'Cybersecurity', 'Cloud Services', 'Data / AI', 'IT-Infrastruktur', 'IT Consulting']

export function FilterSidebar({ filters, onChange }: Props) {
  const set = (key: keyof TenderFilters, val: string | undefined) =>
    onChange({ ...filters, [key]: val, page: 1 })

  function Pill({ label, value, filterKey, thisVal }: {
    label: string
    value: string | undefined
    filterKey: keyof TenderFilters
    thisVal: string
  }) {
    const active = value === thisVal
    return (
      <button
        onClick={() => set(filterKey, active ? undefined : thisVal)}
        className={cn(
          'px-[9px] py-[3px] rounded-full text-[11px] cursor-pointer transition-colors',
          active
            ? 'border-[0.5px]'
            : 'border-[0.5px]'
        )}
        style={{
          border: `0.5px solid ${active ? 'var(--color-brand)' : 'var(--color-border)'}`,
          background: active ? 'var(--color-brand-light)' : 'transparent',
          color: active ? 'var(--color-brand)' : 'var(--color-ink2)',
        }}
      >
        {label}
      </button>
    )
  }

  return (
    <div
      className="w-48 shrink-0 overflow-y-auto flex flex-col gap-4 py-[14px] px-3"
      style={{ background: 'var(--color-surface)', borderRight: '0.5px solid var(--color-border)', paddingBottom: 20 }}
    >
      <div className="flex justify-between items-center">
        <span className="text-[12px] font-semibold" style={{ color: 'var(--color-ink)' }}>Filter</span>
        <button
          onClick={() => onChange({ status: 'open', page: 1, page_size: 25 })}
          className="text-[11px]"
          style={{ background: 'none', border: 'none', color: 'var(--color-brand)' }}
        >
          Zurücksetzen
        </button>
      </div>

      {/* Status */}
      <div>
        <div className="text-[11px] font-medium mb-[5px]" style={{ color: 'var(--color-ink2)' }}>Status</div>
        <div className="flex flex-wrap gap-1">
          <Pill label="Nur offene" value={filters.status} filterKey="status" thisVal="open" />
          <Pill label="Alle" value={filters.status} filterKey="status" thisVal="all" />
        </div>
      </div>

      {/* IT Category */}
      <div>
        <div className="text-[11px] font-medium mb-[5px]" style={{ color: 'var(--color-ink2)' }}>IT-Kategorie</div>
        <div className="flex flex-wrap gap-1">
          {IT_CATS.map((cat) => (
            <Pill key={cat} label={cat} value={filters.it_category} filterKey="it_category" thisVal={cat} />
          ))}
        </div>
      </div>

      {/* CPV */}
      <div>
        <div className="text-[11px] font-medium mb-[5px]" style={{ color: 'var(--color-ink2)' }}>CPV-Code</div>
        <input
          value={filters.cpv || ''}
          onChange={(e) => set('cpv', e.target.value || undefined)}
          placeholder="z.B. 72220000"
          className="w-full rounded text-[11px] px-[7px] py-1 outline-none"
          style={{ background: 'var(--color-bg)', border: '0.5px solid var(--color-border)', color: 'var(--color-ink)' }}
        />
      </div>

      {/* Region */}
      <div>
        <div className="text-[11px] font-medium mb-[5px]" style={{ color: 'var(--color-ink2)' }}>Region</div>
        <input
          value={filters.region || ''}
          onChange={(e) => set('region', e.target.value || undefined)}
          placeholder="Stadt, Bundesland…"
          className="w-full rounded text-[11px] px-[7px] py-1 outline-none"
          style={{ background: 'var(--color-bg)', border: '0.5px solid var(--color-border)', color: 'var(--color-ink)' }}
        />
      </div>

      {/* Auftraggeber */}
      <div>
        <div className="text-[11px] font-medium mb-[5px]" style={{ color: 'var(--color-ink2)' }}>Auftraggeber</div>
        <input
          value={filters.auftraggeber || ''}
          onChange={(e) => set('auftraggeber', e.target.value || undefined)}
          placeholder="Suche…"
          className="w-full rounded text-[11px] px-[7px] py-1 outline-none"
          style={{ background: 'var(--color-bg)', border: '0.5px solid var(--color-border)', color: 'var(--color-ink)' }}
        />
      </div>

      {/* My status */}
      <div>
        <div className="text-[11px] font-medium mb-[5px]" style={{ color: 'var(--color-ink2)' }}>Mein Status</div>
        <div className="flex flex-wrap gap-1">
          <Pill label="Interesse" value={filters.tag_status} filterKey="tag_status" thisVal="interest" />
          <Pill label="Ignoriert" value={filters.tag_status} filterKey="tag_status" thisVal="ignore" />
        </div>
      </div>
    </div>
  )
}
