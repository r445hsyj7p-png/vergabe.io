import { useState } from 'react'
import { useQuery, keepPreviousData } from '@tanstack/react-query'
import { fetchTenders, exportUrl } from '../api/client'
import type { Tender, TenderFilters, SearchProfile } from '../types'
import { Topbar } from '../components/Topbar'
import { FilterSidebar } from '../components/filters/FilterSidebar'
import { TenderList } from '../components/TenderList'
import { DetailPanel } from '../components/detail/DetailPanel'

const DEFAULT_FILTERS: TenderFilters = { status: 'open', page: 1, page_size: 25 }

export function SearchPage() {
  const [filters, setFilters] = useState<TenderFilters>(DEFAULT_FILTERS)
  const [activeProfile, setActiveProfile] = useState<SearchProfile | null>(null)
  const [selected, setSelected] = useState<Tender | null>(null)
  const [selectedIdx, setSelectedIdx] = useState<number>(-1)

  const { data, isLoading } = useQuery({
    queryKey: ['tenders', filters],
    queryFn: () => fetchTenders(filters),
    placeholderData: keepPreviousData,
  })

  const tenders = data?.items || []

  function handleSelect(t: Tender) {
    const idx = tenders.findIndex((x) => x.id === t.id)
    setSelected(t)
    setSelectedIdx(idx)
  }

  function handleNav(dir: -1 | 1) {
    const newIdx = Math.max(0, Math.min(tenders.length - 1, selectedIdx + dir))
    if (newIdx !== selectedIdx) {
      setSelectedIdx(newIdx)
      setSelected(tenders[newIdx])
    }
  }

  return (
    <>
      <Topbar filters={filters} onFiltersChange={setFilters} activeProfile={activeProfile} onProfileSelect={setActiveProfile} />
      <div style={{ display: 'flex', flex: 1, minHeight: 0, overflow: 'hidden' }}>
        <FilterSidebar filters={filters} onChange={setFilters} />
        <div style={{ flex: 1, display: 'flex', flexDirection: 'column', minWidth: 0, overflow: 'hidden' }}>
          <div style={{ display: 'grid', gridTemplateColumns: '86px 1fr 90px', padding: '7px 18px', background: 'var(--white)', borderBottom: '0.5px solid var(--border)', fontSize: 11, color: 'var(--text3)', fontWeight: 500, letterSpacing: '.04em', textTransform: 'uppercase', flexShrink: 0 }}>
            <div>Frist</div>
            <div style={{ paddingLeft: 10 }}>Titel</div>
            <div style={{ textAlign: 'right' }}>Region</div>
          </div>
          {isLoading && (
            <div style={{ flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center', color: 'var(--text3)' }}>Lädt…</div>
          )}
          {!isLoading && tenders.length === 0 && (
            <div style={{ flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center', color: 'var(--text3)', fontSize: 13 }}>Keine Ausschreibungen gefunden.</div>
          )}
          {!isLoading && tenders.length > 0 && (
            <TenderList tenders={tenders} selectedId={selected?.id || null} onSelect={handleSelect} />
          )}
          <div style={{ display: 'flex', alignItems: 'center', gap: 10, padding: '5px 18px', background: 'var(--white)', borderTop: '0.5px solid var(--border)', fontSize: 11, color: 'var(--text3)', flexShrink: 0 }}>
            <div style={{ width: 5, height: 5, borderRadius: '50%', background: 'var(--green)' }} />
            <span>{data?.total || 0} Ausschreibungen{filters.q ? ` für „${filters.q}"` : ''}</span>
            <span style={{ color: 'var(--border2)' }}>·</span>
            <span>Seite {filters.page || 1} von {Math.ceil((data?.total || 0) / (filters.page_size || 25))}</span>
            <div style={{ marginLeft: 'auto', display: 'flex', gap: 3 }}>
              <button onClick={() => setFilters({ ...filters, page: Math.max(1, (filters.page || 1) - 1) })} disabled={(filters.page || 1) <= 1}
                style={{ width: 28, height: 28, borderRadius: 6, border: '0.5px solid var(--border)', background: 'var(--white)', color: 'var(--text2)', fontSize: 11, cursor: 'pointer', opacity: (filters.page || 1) <= 1 ? 0.4 : 1 }}>‹</button>
              <button onClick={() => setFilters({ ...filters, page: (filters.page || 1) + 1 })} disabled={!data?.has_more}
                style={{ width: 28, height: 28, borderRadius: 6, border: '0.5px solid var(--border)', background: 'var(--white)', color: 'var(--text2)', fontSize: 11, cursor: 'pointer', opacity: !data?.has_more ? 0.4 : 1 }}>›</button>
            </div>
            <a href={exportUrl(filters)} download="ausschreibungen.csv"
              style={{ padding: '4px 10px', borderRadius: 'var(--r)', border: '0.5px solid var(--border)', background: 'var(--white)', color: 'var(--text2)', fontSize: 11, textDecoration: 'none' }}>↓ CSV</a>
          </div>
        </div>
        {selected && (
          <DetailPanel tender={selected} onClose={() => { setSelected(null); setSelectedIdx(-1) }} onNav={handleNav} pos={`${selectedIdx + 1}/${tenders.length}`} />
        )}
      </div>
    </>
  )
}
