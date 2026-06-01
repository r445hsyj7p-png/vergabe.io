import { useState, useEffect, useRef } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { LayoutDashboard, Database, Globe, Brain, ScrollText, Play, Check, X, PlayCircle, Loader2 } from 'lucide-react'
import {
  fetchAdminStats, fetchSources, triggerCrawl,
  fetchCrawlLogs, fetchKomunenStats, fetchKomunenQueue, updateKomunen,
  addKomunen, triggerDestatiSync, triggerWikidataSync, triggerDiscovery,
  fetchKomunenList, fetchKomunenBundeslaender,
  fetchCrawlerLive, triggerAllCrawlers,
} from '../api/client'
import type { CrawlerLiveEntry } from '../api/client'
import { api } from '../api/client'
import { Topbar } from '../components/Topbar'
import type { TenderFilters, SearchProfile } from '../types'

const NAV = [
  { id: 'Dashboard', label: 'Dashboard', icon: LayoutDashboard },
  { id: 'API-Quellen', label: 'API-Quellen', icon: Database },
  { id: 'Kommunen-Crawler', label: 'Kommunen-Crawler', icon: Globe },
  { id: 'KI-Summaries', label: 'KI-Summaries', icon: Brain },
  { id: 'Aktivitätslog', label: 'Aktivitätslog', icon: ScrollText },
]

function StatCard({ label, value, sub, color }: { label: string; value: string | number; sub?: string; color?: string }) {
  return (
    <div
      className="rounded px-4 py-[14px]"
      style={{ background: 'var(--color-surface)', border: '0.5px solid var(--color-border)' }}
    >
      <div
        className="font-mono text-[11px] tracking-[0.04em] mb-1.5"
        style={{ color: 'var(--color-ink3)' }}
      >
        {label}
      </div>
      <div
        className="text-[26px] font-semibold leading-none mb-1"
        style={{ color: color || 'var(--color-ink)' }}
      >
        {value}
      </div>
      {sub && <div className="text-[11px]" style={{ color: 'var(--color-emerald)' }}>{sub}</div>}
    </div>
  )
}

function StatusDot({ status }: { status: string }) {
  const c = status === 'ok' ? 'var(--color-emerald)' : status === 'warn' ? 'var(--color-amber)' : 'var(--color-rose)'
  const label = status === 'ok' ? 'OK' : status === 'warn' ? 'Warnung' : 'Fehler'
  return (
    <span
      className="inline-flex items-center gap-1 font-mono text-[10px] px-[7px] py-[2px] rounded-full"
      style={{ background: `${c}20`, color: c, border: `0.5px solid ${c}60` }}
    >
      <span className="w-[5px] h-[5px] rounded-full inline-block" style={{ background: c }} />
      {label}
    </span>
  )
}

function TableHead({ cols }: { cols: string[] }) {
  return (
    <thead>
      <tr style={{ background: 'var(--color-bg)' }}>
        {cols.map((c) => (
          <th
            key={c}
            className="px-4 py-2 text-left text-[10px] font-semibold uppercase tracking-[0.05em]"
            style={{ color: 'var(--color-ink3)', borderBottom: '0.5px solid var(--color-border)' }}
          >
            {c}
          </th>
        ))}
      </tr>
    </thead>
  )
}

function Btn({ onClick, children, variant = 'default', disabled = false }: {
  onClick: () => void
  children: React.ReactNode
  variant?: 'default' | 'accent'
  disabled?: boolean
}) {
  return (
    <button
      onClick={onClick}
      disabled={disabled}
      className="px-2 py-[3px] rounded text-[11px] cursor-pointer disabled:opacity-40 disabled:cursor-default"
      style={{
        border: `0.5px solid ${variant === 'accent' ? 'var(--color-brand)' : 'var(--color-border)'}`,
        background: variant === 'accent' ? 'var(--color-brand-light)' : 'var(--color-surface)',
        color: variant === 'accent' ? 'var(--color-brand)' : 'var(--color-ink2)',
      }}
    >
      {children}
    </button>
  )
}

function Section({ title, sub, action, children }: {
  title: string
  sub?: string
  action?: React.ReactNode
  children: React.ReactNode
}) {
  return (
    <div
      className="overflow-hidden rounded-lg"
      style={{ background: 'var(--color-surface)', border: '0.5px solid var(--color-border)' }}
    >
      <div
        className="flex items-center justify-between px-[18px] py-[14px]"
        style={{ borderBottom: '0.5px solid var(--color-border)' }}
      >
        <div>
          <div className="text-[13px] font-semibold" style={{ color: 'var(--color-ink)' }}>{title}</div>
          {sub && <div className="text-[11px] mt-0.5" style={{ color: 'var(--color-ink3)' }}>{sub}</div>}
        </div>
        {action}
      </div>
      {children}
    </div>
  )
}

function Dashboard() {
  const { data: stats } = useQuery({
    queryKey: ['admin-stats'],
    queryFn: fetchAdminStats,
    refetchInterval: 30_000,
  })
  return (
    <div className="flex flex-col gap-4">
      <div className="grid grid-cols-4 gap-2.5">
        <StatCard label="Gesamt aktiv" value={stats?.total_tenders ?? '—'} sub={`+${stats?.tenders_today ?? 0} heute`} />
        <StatCard label="Heute neu" value={stats?.tenders_today ?? '—'} color="var(--color-emerald)" />
        <StatCard label="Aktive Quellen" value={stats?.active_sources ?? '—'} />
        <StatCard label="Kommunen-Quellen" value={stats?.komunen_sources ?? '—'} color="var(--color-brand)" />
      </div>
      {stats?.last_crawl_at && (
        <div className="text-[11px]" style={{ color: 'var(--color-ink3)' }}>
          Letzter Crawl: {new Date(stats.last_crawl_at).toLocaleString('de-DE')}
        </div>
      )}
    </div>
  )
}

function ElapsedTimer({ startedAt }: { startedAt: string }) {
  const [elapsed, setElapsed] = useState(0)
  useEffect(() => {
    const t0 = new Date(startedAt).getTime()
    const iv = setInterval(() => setElapsed(Math.floor((Date.now() - t0) / 1000)), 500)
    return () => clearInterval(iv)
  }, [startedAt])
  const m = Math.floor(elapsed / 60)
  const s = elapsed % 60
  return <span className="font-mono text-[11px]" style={{ color: 'var(--color-brand)' }}>{m > 0 ? `${m}m ` : ''}{s}s</span>
}

function CrawlerRow({ entry, onStart }: { entry: CrawlerLiveEntry; onStart: () => void }) {
  const isRunning = entry.running
  const hasError = !!entry.run_error || entry.last_log_level === 'warn' || entry.last_log_level === 'error'
  const logOk = entry.last_log_level === 'info'

  const statusLabel = isRunning ? 'Läuft…' : entry.status === 'ok' ? 'OK' : entry.status === 'warn' ? 'Warnung' : entry.status === 'error' ? 'Fehler' : '—'
  const statusColor = isRunning
    ? 'var(--color-brand)'
    : entry.status === 'ok' ? 'var(--color-emerald)'
    : entry.status === 'warn' ? 'var(--color-amber)'
    : entry.status === 'error' ? 'var(--color-rose)'
    : 'var(--color-ink3)'

  return (
    <tr style={{ borderBottom: '0.5px solid var(--color-border)' }}>
      {/* Name */}
      <td className="px-4 py-3 text-[12px] font-medium" style={{ color: 'var(--color-ink)' }}>
        {entry.name}
      </td>

      {/* Typ */}
      <td className="px-4 py-3">
        <span
          className="px-[6px] py-[2px] rounded font-mono text-[10px]"
          style={{
            background: entry.source_type === 'api' ? 'var(--color-brand-light)' : 'var(--color-chip)',
            color: entry.source_type === 'api' ? 'var(--color-brand)' : 'var(--color-ink2)',
            border: '0.5px solid var(--color-border)',
          }}
        >
          {entry.source_type.toUpperCase()}
        </span>
      </td>

      {/* Intervall */}
      <td className="px-4 py-3 text-[11px]" style={{ color: 'var(--color-ink3)' }}>
        alle {entry.interval_hours}h
      </td>

      {/* Status */}
      <td className="px-4 py-3">
        <span
          className="inline-flex items-center gap-1.5 font-mono text-[10px] px-[7px] py-[2px] rounded-full"
          style={{ background: `${statusColor}20`, color: statusColor, border: `0.5px solid ${statusColor}60` }}
        >
          {isRunning
            ? <Loader2 size={9} className="animate-spin" />
            : <span className="w-[5px] h-[5px] rounded-full inline-block" style={{ background: statusColor }} />
          }
          {statusLabel}
        </span>
      </td>

      {/* Progress / Letzter Lauf */}
      <td className="px-4 py-3 text-[11px]" style={{ color: 'var(--color-ink2)' }}>
        {isRunning && entry.started_at ? (
          <div className="flex flex-col gap-0.5">
            <ElapsedTimer startedAt={entry.started_at} />
            <span style={{ color: 'var(--color-ink3)' }}>
              {entry.run_processed ?? 0} geprüft · {entry.run_new ?? 0} neu
            </span>
          </div>
        ) : entry.last_log_at ? (
          <div className="flex flex-col gap-0.5">
            <span>{new Date(entry.last_log_at).toLocaleString('de-DE', { day: '2-digit', month: '2-digit', hour: '2-digit', minute: '2-digit' })}</span>
            <span style={{ color: hasError ? 'var(--color-amber)' : 'var(--color-ink3)' }}>
              {entry.last_log_processed ?? 0} geprüft · {entry.last_log_new ?? 0} neu
            </span>
          </div>
        ) : (
          <span style={{ color: 'var(--color-ink3)' }}>—</span>
        )}
      </td>

      {/* Letzte Meldung */}
      <td className="px-4 py-3 text-[11px] max-w-[280px]" style={{ color: 'var(--color-ink3)' }}>
        {entry.run_error ? (
          <span className="text-[10px]" style={{ color: 'var(--color-rose)' }} title={entry.run_error}>
            {entry.run_error.slice(0, 80)}{entry.run_error.length > 80 ? '…' : ''}
          </span>
        ) : entry.last_log_message ? (
          <span className="text-[10px]" title={entry.last_log_message}>
            {entry.last_log_message.slice(0, 80)}{entry.last_log_message.length > 80 ? '…' : ''}
          </span>
        ) : null}
      </td>

      {/* Starten */}
      <td className="px-4 py-3">
        <Btn variant="accent" disabled={isRunning} onClick={onStart}>
          <span className="flex items-center gap-1">
            {isRunning ? <Loader2 size={10} className="animate-spin" /> : <Play size={10} />}
            {isRunning ? 'Läuft' : 'Starten'}
          </span>
        </Btn>
      </td>
    </tr>
  )
}

function SourcesTable() {
  const qc = useQueryClient()
  const anyRunningRef = useRef(false)

  const { data: entries = [] } = useQuery({
    queryKey: ['crawlers-live'],
    queryFn: fetchCrawlerLive,
    refetchInterval: (query) => {
      const data = query.state.data as CrawlerLiveEntry[] | undefined
      return data?.some((e) => e.running) ? 1500 : 8000
    },
  })

  const crawlMut = useMutation({
    mutationFn: (id: string) => triggerCrawl(id),
    onSuccess: () => setTimeout(() => qc.invalidateQueries({ queryKey: ['crawlers-live'] }), 300),
  })

  const runAllMut = useMutation({
    mutationFn: triggerAllCrawlers,
    onSuccess: () => setTimeout(() => qc.invalidateQueries({ queryKey: ['crawlers-live'] }), 300),
  })

  const anyRunning = entries.some((e) => e.running)
  anyRunningRef.current = anyRunning

  return (
    <Section
      title="API-Quellen & Scraper"
      sub="Live-Status aller Crawler"
      action={
        <Btn variant="accent" disabled={anyRunning} onClick={() => runAllMut.mutate()}>
          <span className="flex items-center gap-1.5">
            <PlayCircle size={12} />
            Alle starten
          </span>
        </Btn>
      }
    >
      <table className="w-full border-collapse">
        <TableHead cols={['Quelle', 'Typ', 'Intervall', 'Status', 'Lauf / Ergebnis', 'Meldung', '']} />
        <tbody>
          {entries.map((e) => (
            <CrawlerRow
              key={e.id}
              entry={e}
              onStart={() => crawlMut.mutate(e.id)}
            />
          ))}
        </tbody>
      </table>
      {anyRunning && (
        <div
          className="px-4 py-2 text-[11px] flex items-center gap-2"
          style={{ borderTop: '0.5px solid var(--color-border)', color: 'var(--color-brand)' }}
        >
          <Loader2 size={11} className="animate-spin" />
          Live-Update aktiv · alle 1,5s
        </div>
      )}
    </Section>
  )
}

function KomunenPanel() {
  const qc = useQueryClient()
  const { data: stats } = useQuery({ queryKey: ['komunen-stats'], queryFn: fetchKomunenStats })
  const { data: queue = [] } = useQuery({ queryKey: ['komunen-queue'], queryFn: fetchKomunenQueue })
  const updateMut = useMutation({
    mutationFn: ({ id, status }: { id: string; status: string }) => updateKomunen(id, status),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['komunen-queue'] })
      qc.invalidateQueries({ queryKey: ['komunen-stats'] })
    },
  })
  const [form, setForm] = useState({ name: '', bundesland: '', main_url: '', vergabe_url: '', ags: '' })
  const addMut = useMutation({
    mutationFn: () => addKomunen({
      name: form.name,
      bundesland: form.bundesland || undefined,
      main_url: form.main_url || undefined,
      vergabe_url: form.vergabe_url || undefined,
      ags: form.ags || undefined,
    }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['komunen-stats'] })
      setForm({ name: '', bundesland: '', main_url: '', vergabe_url: '', ags: '' })
    },
  })
  const [syncMsg, setSyncMsg] = useState('')

  async function runSync(fn: () => Promise<{ message?: string }>, label: string) {
    setSyncMsg(`${label} gestartet…`)
    try {
      const r = await fn()
      setSyncMsg(r.message || 'Gestartet')
    } catch {
      setSyncMsg('Fehler beim Starten')
    }
    setTimeout(() => setSyncMsg(''), 4000)
  }

  const komunenStats = stats as { total?: number; verified?: number; pending_review?: number; with_vergabe_url?: number } | undefined

  const addFormFields: Array<{ label: string; key: keyof typeof form; placeholder: string }> = [
    { label: 'Name *', key: 'name', placeholder: 'z.B. Stadt Marl' },
    { label: 'Bundesland', key: 'bundesland', placeholder: 'z.B. Nordrhein-Westfalen' },
    { label: 'Haupt-URL', key: 'main_url', placeholder: 'https://www.marl.de' },
    { label: 'Vergabe-URL (optional)', key: 'vergabe_url', placeholder: 'https://www.marl.de/vergabe' },
  ]

  return (
    <div className="flex flex-col gap-4">
      {/* Stats */}
      <div className="grid grid-cols-4 gap-2.5">
        <StatCard label="Gemeinden gesamt" value={komunenStats?.total ?? '—'} />
        <StatCard label="Verifiziert" value={komunenStats?.verified ?? '—'} color="var(--color-emerald)" />
        <StatCard label="Kurations-Queue" value={komunenStats?.pending_review ?? '—'} color="var(--color-amber)" />
        <StatCard label="Mit Vergabe-URL" value={komunenStats?.with_vergabe_url ?? '—'} color="var(--color-brand)" />
      </div>

      {/* Automation controls */}
      <Section title="Automatisierung" sub="Kommunen automatisch entdecken und prüfen">
        <div className="px-[18px] py-[14px] flex flex-col gap-3">
          {syncMsg && (
            <div
              className="text-[12px] px-[10px] py-1.5 rounded"
              style={{ color: 'var(--color-emerald)', background: 'var(--color-emerald-light)' }}
            >
              {syncMsg}
            </div>
          )}
          <div className="flex gap-2 flex-wrap">
            <Btn variant="accent" onClick={() => runSync(triggerDestatiSync, 'Destatis-Sync')}>
              Destatis-Sync (alle ~10.000 Gemeinden)
            </Btn>
            <Btn variant="accent" onClick={() => runSync(triggerWikidataSync, 'Wikidata')}>
              Wikidata URLs auflösen
            </Btn>
            <Btn variant="accent" onClick={() => runSync(triggerDiscovery, 'URL-Verify + Discovery')}>
              URL-Verify + Discovery
            </Btn>
          </div>
          <div className="text-[11px] leading-relaxed" style={{ color: 'var(--color-ink3)' }}>
            <strong style={{ color: 'var(--color-ink2)' }}>Automatischer Ablauf:</strong> Destatis-Sync quartalsweise → Wikidata-URLs wöchentlich → URL-Verify + Discovery täglich 03:00 → Kurations-Queue für Grenzfälle.
          </div>
        </div>
      </Section>

      {/* Manual add */}
      <Section title="Gemeinde manuell hinzufügen" sub="Direkt in die Crawler-Queue eintragen">
        <div className="px-[18px] py-[14px] flex flex-col gap-2">
          <div className="grid grid-cols-2 gap-2">
            {addFormFields.map(({ label, key, placeholder }) => (
              <div key={key}>
                <div className="text-[11px] font-medium mb-[3px]" style={{ color: 'var(--color-ink2)' }}>{label}</div>
                <input
                  value={form[key]}
                  onChange={(e) => setForm({ ...form, [key]: e.target.value })}
                  placeholder={placeholder}
                  className="w-full rounded text-[12px] px-2 py-[5px] outline-none"
                  style={{ background: 'var(--color-bg)', border: '0.5px solid var(--color-border)', color: 'var(--color-ink)' }}
                />
              </div>
            ))}
          </div>
          <div className="text-[11px]" style={{ color: 'var(--color-ink3)' }}>
            Ohne Vergabe-URL wird die URL automatisch per Discovery gesucht (täglich 03:00).
          </div>
          <Btn variant="accent" onClick={() => addMut.mutate()}>+ Gemeinde hinzufügen</Btn>
        </div>
      </Section>

      {/* Queue */}
      <Section
        title="Kurations-Queue"
        sub="Grenzfälle mit niedrigem Konfidenz-Score"
        action={<div className="text-[11px]" style={{ color: 'var(--color-ink3)' }}>{queue.length} offen</div>}
      >
        {queue.length === 0 ? (
          <div className="p-5 text-center text-[13px]" style={{ color: 'var(--color-ink3)' }}>
            Queue leer — alle Einträge geprüft.
          </div>
        ) : (
          <table className="w-full border-collapse">
            <TableHead cols={['Name', 'Bundesland', 'URL', 'Score', 'Status', '']} />
            <tbody>
              {queue.map((k) => (
                <tr key={k.id} style={{ borderBottom: '0.5px solid var(--color-border)' }}>
                  <td className="px-4 py-2.5 text-[12px] font-medium" style={{ color: 'var(--color-ink)' }}>{k.name}</td>
                  <td className="px-4 py-2.5 text-[11px]" style={{ color: 'var(--color-ink2)' }}>{k.bundesland}</td>
                  <td className="px-4 py-2.5 text-[11px]">
                    {k.vergabe_url ? (
                      <a
                        href={k.vergabe_url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="font-mono text-[10px]"
                        style={{ color: 'var(--color-brand)' }}
                      >
                        {k.vergabe_url.substring(0, 40)}…
                      </a>
                    ) : '—'}
                  </td>
                  <td className="px-4 py-2.5 font-mono text-[11px]" style={{ color: 'var(--color-ink2)' }}>
                    {k.discovery_confidence != null ? (k.discovery_confidence * 100).toFixed(0) + '%' : '—'}
                  </td>
                  <td className="px-4 py-2.5">
                    <StatusDot status={k.status === 'verified' ? 'ok' : k.status === 'excluded' ? 'error' : 'warn'} />
                  </td>
                  <td className="px-4 py-2.5">
                    <div className="flex gap-1">
                      <Btn variant="accent" onClick={() => updateMut.mutate({ id: k.id, status: 'verified' })}>
                        <span className="flex items-center gap-1"><Check size={10} /> Verified</span>
                      </Btn>
                      <Btn onClick={() => updateMut.mutate({ id: k.id, status: 'excluded' })}>
                        <span className="flex items-center gap-1"><X size={10} /> Exclude</span>
                      </Btn>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </Section>

      {/* Alle Gemeinden */}
      <AllKomunenTable invalidateStats={() => qc.invalidateQueries({ queryKey: ['komunen-stats'] })} />
    </div>
  )
}

function AllKomunenTable({ invalidateStats }: { invalidateStats: () => void }) {
  const qc = useQueryClient()
  const [statusFilter, setStatusFilter] = useState('')
  const [bundeslandFilter, setBundeslandFilter] = useState('')
  const [search, setSearch] = useState('')
  const [page, setPage] = useState(1)
  const PER_PAGE = 50

  const { data: bundeslaender = [] } = useQuery({
    queryKey: ['komunen-bundeslaender'],
    queryFn: fetchKomunenBundeslaender,
  })

  const { data, isFetching } = useQuery({
    queryKey: ['komunen-list', statusFilter, bundeslandFilter, search, page],
    queryFn: () => fetchKomunenList({
      status: statusFilter || undefined,
      bundesland: bundeslandFilter || undefined,
      q: search || undefined,
      page,
      per_page: PER_PAGE,
    }),
    placeholderData: (prev) => prev,
  })

  const updateMut = useMutation({
    mutationFn: ({ id, status }: { id: string; status: string }) => updateKomunen(id, status),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['komunen-list'] })
      invalidateStats()
    },
  })

  const items = data?.items ?? []
  const total = data?.total ?? 0
  const totalPages = Math.ceil(total / PER_PAGE)

  function resetPage() { setPage(1) }

  const STATUS_LABELS: Record<string, string> = {
    auto: 'Auto',
    verified: 'Verifiziert',
    excluded: 'Ausgeschlossen',
    pending_review: 'Prüfen',
  }

  return (
    <Section
      title="Alle Gemeinden"
      sub={`${total} Einträge gesamt`}
      action={
        isFetching ? (
          <span className="text-[11px]" style={{ color: 'var(--color-ink3)' }}>Lädt…</span>
        ) : null
      }
    >
      {/* Filters */}
      <div className="px-4 py-3 flex gap-2 flex-wrap" style={{ borderBottom: '0.5px solid var(--color-border)' }}>
        <input
          value={search}
          onChange={(e) => { setSearch(e.target.value); resetPage() }}
          placeholder="Suche Name / URL…"
          className="rounded text-[12px] px-2 py-[4px] outline-none min-w-[160px]"
          style={{ background: 'var(--color-bg)', border: '0.5px solid var(--color-border)', color: 'var(--color-ink)' }}
        />
        <select
          value={statusFilter}
          onChange={(e) => { setStatusFilter(e.target.value); resetPage() }}
          className="rounded text-[12px] px-2 py-[4px] outline-none"
          style={{ background: 'var(--color-bg)', border: '0.5px solid var(--color-border)', color: 'var(--color-ink)' }}
        >
          <option value="">Alle Status</option>
          <option value="auto">Auto</option>
          <option value="verified">Verifiziert</option>
          <option value="pending_review">Prüfen</option>
          <option value="excluded">Ausgeschlossen</option>
        </select>
        <select
          value={bundeslandFilter}
          onChange={(e) => { setBundeslandFilter(e.target.value); resetPage() }}
          className="rounded text-[12px] px-2 py-[4px] outline-none"
          style={{ background: 'var(--color-bg)', border: '0.5px solid var(--color-border)', color: 'var(--color-ink)' }}
        >
          <option value="">Alle Bundesländer</option>
          {bundeslaender.map((bl) => <option key={bl} value={bl}>{bl}</option>)}
        </select>
      </div>

      {/* Table */}
      {items.length === 0 ? (
        <div className="p-5 text-center text-[13px]" style={{ color: 'var(--color-ink3)' }}>
          Keine Einträge gefunden.
        </div>
      ) : (
        <table className="w-full border-collapse">
          <TableHead cols={['Name', 'Bundesland', 'Ew.', 'Vergabe-URL', 'Status', '']} />
          <tbody>
            {items.map((k) => (
              <tr key={k.id} style={{ borderBottom: '0.5px solid var(--color-border)' }}>
                <td className="px-4 py-2 text-[12px] font-medium" style={{ color: 'var(--color-ink)' }}>{k.name}</td>
                <td className="px-4 py-2 text-[11px]" style={{ color: 'var(--color-ink2)' }}>{k.bundesland ?? '—'}</td>
                <td className="px-4 py-2 font-mono text-[11px]" style={{ color: 'var(--color-ink3)' }}>
                  {k.einwohner ? k.einwohner.toLocaleString('de-DE') : '—'}
                </td>
                <td className="px-4 py-2 text-[11px] max-w-[200px] truncate">
                  {k.vergabe_url ? (
                    <a href={k.vergabe_url} target="_blank" rel="noopener noreferrer"
                      className="font-mono text-[10px]" style={{ color: 'var(--color-brand)' }}>
                      {k.vergabe_url.replace(/^https?:\/\//, '').substring(0, 35)}
                    </a>
                  ) : '—'}
                </td>
                <td className="px-4 py-2">
                  <span
                    className="text-[10px] font-medium px-1.5 py-0.5 rounded"
                    style={{
                      background: k.status === 'verified' ? 'var(--color-emerald-light)' :
                        k.status === 'excluded' ? 'var(--color-rose-light)' :
                          k.status === 'pending_review' ? 'var(--color-amber-light)' : 'var(--color-border)',
                      color: k.status === 'verified' ? 'var(--color-emerald)' :
                        k.status === 'excluded' ? 'var(--color-rose)' :
                          k.status === 'pending_review' ? 'var(--color-amber)' : 'var(--color-ink2)',
                    }}
                  >
                    {STATUS_LABELS[k.status] ?? k.status}
                  </span>
                </td>
                <td className="px-4 py-2">
                  <div className="flex gap-1">
                    {k.status !== 'verified' && (
                      <Btn variant="accent" onClick={() => updateMut.mutate({ id: k.id, status: 'verified' })}>
                        <Check size={10} />
                      </Btn>
                    )}
                    {k.status !== 'excluded' && (
                      <Btn onClick={() => updateMut.mutate({ id: k.id, status: 'excluded' })}>
                        <X size={10} />
                      </Btn>
                    )}
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}

      {/* Pagination */}
      {totalPages > 1 && (
        <div className="px-4 py-3 flex items-center gap-3" style={{ borderTop: '0.5px solid var(--color-border)' }}>
          <span className="text-[11px]" style={{ color: 'var(--color-ink3)' }}>
            Seite {page} / {totalPages} ({total} gesamt)
          </span>
          <div className="flex gap-1 ml-auto">
            <Btn onClick={() => setPage((p) => Math.max(1, p - 1))} disabled={page === 1}>
              ← Zurück
            </Btn>
            <Btn onClick={() => setPage((p) => Math.min(totalPages, p + 1))} disabled={page === totalPages}>
              Weiter →
            </Btn>
          </div>
        </div>
      )}
    </Section>
  )
}

function ActivityLog() {
  const { data: logs = [] } = useQuery({
    queryKey: ['crawl-logs'],
    queryFn: () => fetchCrawlLogs(100),
    refetchInterval: 15_000,
  })

  function dotColor(level: string) {
    if (level === 'error') return 'var(--color-rose)'
    if (level === 'warn') return 'var(--color-amber)'
    return 'var(--color-emerald)'
  }

  return (
    <Section title="Aktivitätslog" sub="Letzte 100 Crawl-Ereignisse">
      <div>
        {logs.map((log) => (
          <div
            key={log.id}
            className="flex items-start gap-2.5 px-4 py-2 text-[11.5px]"
            style={{ borderBottom: '0.5px solid var(--color-border)' }}
          >
            <span
              className="font-mono text-[10px] whitespace-nowrap mt-[1px] min-w-[130px]"
              style={{ color: 'var(--color-ink3)' }}
            >
              {new Date(log.created_at).toLocaleString('de-DE')}
            </span>
            <span
              className="w-1.5 h-1.5 rounded-full mt-1 shrink-0"
              style={{ background: dotColor(log.level) }}
            />
            <span className="leading-snug" style={{ color: 'var(--color-ink2)' }}>{log.message}</span>
            {log.entries_new > 0 && (
              <span className="ml-auto font-mono text-[10px] whitespace-nowrap" style={{ color: 'var(--color-emerald)' }}>
                +{log.entries_new} neu
              </span>
            )}
          </div>
        ))}
        {logs.length === 0 && (
          <div className="p-5 text-center" style={{ color: 'var(--color-ink3)' }}>Keine Logs vorhanden.</div>
        )}
      </div>
    </Section>
  )
}

interface SummaryStatsData {
  total_summaries: number
  total_cost_eur: number
  total_cost_cents: number
  by_provider: Array<{ provider: string; count: number; cost_cents: number }>
}

function SummaryStats() {
  const { data } = useQuery<SummaryStatsData>({
    queryKey: ['summary-stats'],
    queryFn: async () => {
      const r = await api.get('/admin/summaries/stats')
      return r.data as SummaryStatsData
    },
    refetchInterval: 60_000,
  })

  const providerLabels: Record<string, string> = {
    anthropic: 'Claude Haiku',
    ollama: 'Ollama (lokal)',
    openai: 'GPT-4o mini',
  }

  return (
    <Section title="KI-Zusammenfassungen" sub="On-demand generiert · pro Ausschreibung einmal gecacht">
      <div className="px-[18px] py-[14px] flex flex-col gap-3">
        <div className="grid grid-cols-3 gap-2.5">
          <StatCard label="Generierte Summaries" value={data?.total_summaries ?? '—'} />
          <StatCard
            label="Gesamtkosten"
            value={data ? `${data.total_cost_eur.toFixed(3)} €` : '—'}
          />
          <StatCard
            label="Ø pro Summary"
            value={data?.total_summaries
              ? `${((data.total_cost_cents / data.total_summaries) / 100).toFixed(4)} €`
              : '—'
            }
          />
        </div>
        {data?.by_provider && data.by_provider.length > 0 && (
          <div>
            <div className="text-[11px] mb-1.5" style={{ color: 'var(--color-ink3)' }}>Nach Provider</div>
            {data.by_provider.map((p) => (
              <div
                key={p.provider}
                className="flex justify-between py-[5px] text-[12px]"
                style={{ borderBottom: '0.5px solid var(--color-border)' }}
              >
                <span style={{ color: 'var(--color-ink)' }}>{providerLabels[p.provider] || p.provider}</span>
                <span className="font-mono" style={{ color: 'var(--color-ink2)' }}>
                  {p.count}× · {p.cost_cents === 0 ? 'kostenfrei' : `${(p.cost_cents / 100).toFixed(3)} €`}
                </span>
              </div>
            ))}
          </div>
        )}
        {data?.total_summaries === 0 && (
          <div className="text-[12px]" style={{ color: 'var(--color-ink3)' }}>
            Noch keine Summaries generiert. Klicke im Detail-Panel einer Ausschreibung auf „KI-Zusammenfassung erstellen".
          </div>
        )}
      </div>
    </Section>
  )
}

export function AdminPage() {
  const [activeNav, setActiveNav] = useState('Dashboard')
  const [filters] = useState<TenderFilters>({})
  const [activeProfile] = useState<SearchProfile | null>(null)

  return (
    <>
      <Topbar
        filters={filters}
        onFiltersChange={() => {}}
        activeProfile={activeProfile}
        onProfileSelect={() => {}}
      />
      <div className="flex flex-1 min-h-0 overflow-hidden">
        {/* Left nav */}
        <div
          className="w-[180px] shrink-0 flex flex-col gap-[2px] py-[14px] px-[10px]"
          style={{ background: 'var(--color-surface)', borderRight: '0.5px solid var(--color-border)' }}
        >
          <div
            className="text-[10px] font-semibold uppercase tracking-[0.06em] px-[10px] pb-1 pt-2"
            style={{ color: 'var(--color-ink3)' }}
          >
            Admin
          </div>
          {NAV.map(({ id, label, icon: Icon }) => (
            <button
              key={id}
              onClick={() => setActiveNav(id)}
              className="flex items-center gap-2 px-[10px] py-[7px] rounded text-[13px] text-left cursor-pointer"
              style={{
                border: 'none',
                background: activeNav === id ? 'var(--color-brand-light)' : 'transparent',
                color: activeNav === id ? 'var(--color-brand)' : 'var(--color-ink2)',
                fontWeight: activeNav === id ? 500 : 400,
              }}
            >
              <Icon size={14} />
              {label}
            </button>
          ))}
        </div>

        {/* Content */}
        <div className="flex-1 overflow-y-auto p-6 flex flex-col gap-5">
          {activeNav === 'Dashboard' && <Dashboard />}
          {activeNav === 'API-Quellen' && <SourcesTable />}
          {activeNav === 'Kommunen-Crawler' && <KomunenPanel />}
          {activeNav === 'KI-Summaries' && <SummaryStats />}
          {activeNav === 'Aktivitätslog' && <ActivityLog />}
        </div>
      </div>
    </>
  )
}
