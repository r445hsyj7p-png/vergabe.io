import { useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { useQuery, keepPreviousData } from '@tanstack/react-query'
import { fetchTenders, downloadExport } from '../api/client'
import type { Tender, TenderFilters } from '../types'
import { Topbar } from '../components/Topbar'
import { FilterSidebar } from '../components/filters/FilterSidebar'
import { TenderList } from '../components/TenderList'
import { DetailPanel } from '../components/detail/DetailPanel'

function filtersToParams(f: TenderFilters): Record<string, string> {
  const p: Record<string, string> = {}
  if (f.q) p.q = f.q
  if (f.cpv) p.cpv = f.cpv
  if (f.region) p.region = f.region
  if (f.auftraggeber) p.auftraggeber = f.auftraggeber
  if (f.it_category) p.it_category = f.it_category
  if (f.status && f.status !== 'open') p.status = f.status
  if (f.min_value) p.min_value = String(f.min_value)
  if (f.profile_id) p.profile_id = f.profile_id
  if (f.tag_status) p.tag_status = f.tag_status
  if (f.page && f.page > 1) p.page = String(f.page)
  if (f.page_size && f.page_size !== 25) p.page_size = String(f.page_size)
  return p
}

function filtersFromParams(params: URLSearchParams): TenderFilters {
  return {
    q: params.get('q') ?? undefined,
    cpv: params.get('cpv') ?? undefined,
    region: params.get('region') ?? undefined,
    auftraggeber: params.get('auftraggeber') ?? undefined,
    it_category: params.get('it_category') ?? undefined,
    status: params.get('status') ?? 'open',
    min_value: params.get('min_value') ? Number(params.get('min_value')) : undefined,
    profile_id: params.get('profile_id') ?? undefined,
    tag_status: params.get('tag_status') ?? undefined,
    page: params.get('page') ? Number(params.get('page')) : 1,
    page_size: params.get('page_size') ? Number(params.get('page_size')) : 25,
  }
}

export function SearchPage() {
  const [searchParams, setSearchParams] = useSearchParams()
  const [selected, setSelected] = useState<Tender | null>(null)
  const [selectedIdx, setSelectedIdx] = useState<number>(-1)

  const filters = filtersFromParams(searchParams)
  const setFilters = (f: TenderFilters) => setSearchParams(filtersToParams(f), { replace: true })

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
            <button
              onClick={() => downloadExport(filters)}
              className="px-[10px] py-1 rounded text-[11px]"
              style={{ border: '0.5px solid var(--color-border)', background: 'var(--color-surface)', color: 'var(--color-ink2)', cursor: 'pointer' }}
            >
              ↓ CSV
            </button>
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
