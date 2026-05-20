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

  const totalPages = Math.ceil((data?.total || 0) / (filters.page_size || 25))

  return (
    <>
      <Topbar
        filters={filters}
        onFiltersChange={setFilters}
        activeProfile={activeProfile}
        onProfileSelect={setActiveProfile}
      />
      <div className="flex flex-1 min-h-0 overflow-hidden">
        <FilterSidebar filters={filters} onChange={setFilters} />
        <div className="flex-1 flex flex-col min-w-0 overflow-hidden">
          {/* Column headers */}
          <div
            className="grid px-[18px] py-[7px] shrink-0 text-[11px] font-medium uppercase tracking-[0.04em]"
            style={{
              gridTemplateColumns: '86px 1fr 90px',
              background: 'var(--color-surface)',
              borderBottom: '0.5px solid var(--color-border)',
              color: 'var(--color-ink3)',
            }}
          >
            <div>Frist</div>
            <div className="pl-[10px]">Titel</div>
            <div className="text-right">Region</div>
          </div>

          {isLoading && (
            <div className="flex-1 flex items-center justify-center" style={{ color: 'var(--color-ink3)' }}>
              Lädt…
            </div>
          )}
          {!isLoading && tenders.length === 0 && (
            <div className="flex-1 flex items-center justify-center text-[13px]" style={{ color: 'var(--color-ink3)' }}>
              Keine Ausschreibungen gefunden.
            </div>
          )}
          {!isLoading && tenders.length > 0 && (
            <TenderList tenders={tenders} selectedId={selected?.id || null} onSelect={handleSelect} />
          )}

          {/* Footer / pagination */}
          <div
            className="flex items-center gap-2.5 px-[18px] py-[5px] text-[11px] shrink-0"
            style={{ background: 'var(--color-surface)', borderTop: '0.5px solid var(--color-border)', color: 'var(--color-ink3)' }}
          >
            <div className="w-[5px] h-[5px] rounded-full" style={{ background: 'var(--color-emerald)' }} />
            <span>
              {data?.total || 0} Ausschreibungen{filters.q ? ` für „${filters.q}"` : ''}
            </span>
            <span style={{ color: 'var(--color-border2)' }}>·</span>
            <span>Seite {filters.page || 1} von {totalPages}</span>
            <div className="ml-auto flex gap-[3px]">
              <button
                onClick={() => setFilters({ ...filters, page: Math.max(1, (filters.page || 1) - 1) })}
                disabled={(filters.page || 1) <= 1}
                className="w-7 h-7 rounded flex items-center justify-center text-[11px] cursor-pointer"
                style={{
                  border: '0.5px solid var(--color-border)',
                  background: 'var(--color-surface)',
                  color: 'var(--color-ink2)',
                  opacity: (filters.page || 1) <= 1 ? 0.4 : 1,
                }}
              >
                ‹
              </button>
              <button
                onClick={() => setFilters({ ...filters, page: (filters.page || 1) + 1 })}
                disabled={!data?.has_more}
                className="w-7 h-7 rounded flex items-center justify-center text-[11px] cursor-pointer"
                style={{
                  border: '0.5px solid var(--color-border)',
                  background: 'var(--color-surface)',
                  color: 'var(--color-ink2)',
                  opacity: !data?.has_more ? 0.4 : 1,
                }}
              >
                ›
              </button>
            </div>
            <a
              href={exportUrl(filters)}
              download="ausschreibungen.csv"
              className="px-[10px] py-1 rounded no-underline text-[11px]"
              style={{ border: '0.5px solid var(--color-border)', background: 'var(--color-surface)', color: 'var(--color-ink2)' }}
            >
              ↓ CSV
            </a>
          </div>
        </div>
        {selected && (
          <DetailPanel
            tender={selected}
            onClose={() => { setSelected(null); setSelectedIdx(-1) }}
            onNav={handleNav}
            pos={`${selectedIdx + 1}/${tenders.length}`}
          />
        )}
      </div>
    </>
  )
}
