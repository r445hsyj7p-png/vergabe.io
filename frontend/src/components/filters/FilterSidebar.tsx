import type { TenderFilters } from '../../types'

interface Props {
  filters: TenderFilters
  onChange: (f: TenderFilters) => void
}

const IT_CATS = ['Software Dev', 'Cybersecurity', 'Cloud Services', 'Data / AI', 'IT-Infrastruktur', 'IT Consulting']

export function FilterSidebar({ filters, onChange }: Props) {
  const set = (key: keyof TenderFilters, val: any) => onChange({ ...filters, [key]: val, page: 1 })

  const pill = (label: string, value: string | undefined, key: keyof TenderFilters, thisVal: string) => {
    const active = value === thisVal
    return (
      <button key={thisVal} onClick={() => set(key, active ? undefined : thisVal)} style={{
        padding: '3px 9px', borderRadius: 20,
        border: `0.5px solid ${active ? 'var(--accent)' : 'var(--border)'}`,
        background: active ? 'var(--accent-l)' : 'transparent',
        color: active ? 'var(--accent)' : 'var(--text2)',
        fontSize: 11, cursor: 'pointer',
      }}>{label}</button>
    )
  }

  return (
    <div style={{
      width: 192, flexShrink: 0, background: 'var(--white)',
      borderRight: '0.5px solid var(--border)', padding: '14px 12px 20px',
      overflowY: 'auto', display: 'flex', flexDirection: 'column', gap: 16,
    }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <span style={{ fontSize: 12, fontWeight: 600 }}>Filter</span>
        <button onClick={() => onChange({ status: 'open', page: 1, page_size: 25 })} style={{
          fontSize: 11, color: 'var(--accent)', background: 'none', border: 'none',
        }}>Zurücksetzen</button>
      </div>

      {/* Status */}
      <div>
        <div style={{ fontSize: 11, color: 'var(--text2)', fontWeight: 500, marginBottom: 5 }}>Status</div>
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 4 }}>
          {pill('Nur offene', filters.status, 'status', 'open')}
          {pill('Alle', filters.status, 'status', 'all')}
        </div>
      </div>

      {/* IT Category */}
      <div>
        <div style={{ fontSize: 11, color: 'var(--text2)', fontWeight: 500, marginBottom: 5 }}>IT-Kategorie</div>
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 4 }}>
          {IT_CATS.map((cat) => pill(cat, filters.it_category, 'it_category', cat))}
        </div>
      </div>

      {/* CPV */}
      <div>
        <div style={{ fontSize: 11, color: 'var(--text2)', fontWeight: 500, marginBottom: 5 }}>CPV-Code</div>
        <input
          value={filters.cpv || ''}
          onChange={(e) => set('cpv', e.target.value || undefined)}
          placeholder="z.B. 72220000"
          style={{ width: '100%', background: 'var(--bg)', border: '0.5px solid var(--border)', borderRadius: 'var(--r)', fontSize: 11, padding: '4px 7px', outline: 'none', color: 'var(--text)' }}
        />
      </div>

      {/* Region */}
      <div>
        <div style={{ fontSize: 11, color: 'var(--text2)', fontWeight: 500, marginBottom: 5 }}>Region</div>
        <input
          value={filters.region || ''}
          onChange={(e) => set('region', e.target.value || undefined)}
          placeholder="Stadt, Bundesland…"
          style={{ width: '100%', background: 'var(--bg)', border: '0.5px solid var(--border)', borderRadius: 'var(--r)', fontSize: 11, padding: '4px 7px', outline: 'none', color: 'var(--text)' }}
        />
      </div>

      {/* Auftraggeber */}
      <div>
        <div style={{ fontSize: 11, color: 'var(--text2)', fontWeight: 500, marginBottom: 5 }}>Auftraggeber</div>
        <input
          value={filters.auftraggeber || ''}
          onChange={(e) => set('auftraggeber', e.target.value || undefined)}
          placeholder="Suche…"
          style={{ width: '100%', background: 'var(--bg)', border: '0.5px solid var(--border)', borderRadius: 'var(--r)', fontSize: 11, padding: '4px 7px', outline: 'none', color: 'var(--text)' }}
        />
      </div>

      {/* My status */}
      <div>
        <div style={{ fontSize: 11, color: 'var(--text2)', fontWeight: 500, marginBottom: 5 }}>Mein Status</div>
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 4 }}>
          {pill('Interesse', filters.tag_status, 'tag_status', 'interest')}
          {pill('Ignoriert', filters.tag_status, 'tag_status', 'ignore')}
        </div>
      </div>
    </div>
  )
}
