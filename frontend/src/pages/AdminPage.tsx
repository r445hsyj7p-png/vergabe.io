import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import {
  fetchAdminStats, fetchSources, triggerCrawl,
  fetchCrawlLogs, fetchKomunenStats, fetchKomunenQueue, updateKomunen,
  addKomunen, triggerDestatiSync, triggerWikidataSync, triggerDiscovery
} from '../api/client'
import { api } from '../api/client'
import { Topbar } from '../components/Topbar'
import type { TenderFilters, SearchProfile } from '../types'

const NAV = ['Dashboard', 'API-Quellen', 'Kommunen-Crawler', 'KI-Summaries', 'Aktivitätslog']

function StatCard({ label, value, sub, color }: { label: string; value: string | number; sub?: string; color?: string }) {
  return (
    <div style={{ background: 'var(--white)', border: '0.5px solid var(--border)', borderRadius: 'var(--r)', padding: '14px 16px' }}>
      <div style={{ fontSize: 11, color: 'var(--text3)', fontFamily: 'var(--mono)', letterSpacing: '.04em', marginBottom: 6 }}>{label}</div>
      <div style={{ fontSize: 26, fontWeight: 600, color: color || 'var(--text)', lineHeight: 1, marginBottom: 4 }}>{value}</div>
      {sub && <div style={{ fontSize: 11, color: 'var(--green)' }}>{sub}</div>}
    </div>
  )
}

function StatusDot({ status }: { status: string }) {
  const c = status === 'ok' ? 'var(--green)' : status === 'warn' ? 'var(--amber)' : 'var(--red)'
  const label = status === 'ok' ? 'OK' : status === 'warn' ? 'Warnung' : 'Fehler'
  return (
    <span style={{ display: 'inline-flex', alignItems: 'center', gap: 4, fontFamily: 'var(--mono)', fontSize: 10, padding: '2px 7px', borderRadius: 20, background: c + '20', color: c, border: `0.5px solid ${c}60` }}>
      <span style={{ width: 5, height: 5, borderRadius: '50%', background: c, display: 'inline-block' }} />
      {label}
    </span>
  )
}

function TableHead({ cols }: { cols: string[] }) {
  return (
    <thead>
      <tr style={{ background: 'var(--bg)' }}>
        {cols.map((c) => (
          <th key={c} style={{ padding: '8px 16px', textAlign: 'left', fontSize: 10, fontWeight: 600, color: 'var(--text3)', textTransform: 'uppercase', letterSpacing: '.05em', borderBottom: '0.5px solid var(--border)' }}>{c}</th>
        ))}
      </tr>
    </thead>
  )
}

function Btn({ onClick, children, variant = 'default' }: { onClick: () => void; children: React.ReactNode; variant?: 'default' | 'accent' }) {
  return (
    <button onClick={onClick} style={{
      padding: '3px 8px', borderRadius: 4, fontSize: 11, cursor: 'pointer',
      border: `0.5px solid ${variant === 'accent' ? 'var(--accent)' : 'var(--border)'}`,
      background: variant === 'accent' ? 'var(--accent-l)' : 'var(--white)',
      color: variant === 'accent' ? 'var(--accent)' : 'var(--text2)',
    }}>{children}</button>
  )
}

function Section({ title, sub, action, children }: { title: string; sub?: string; action?: React.ReactNode; children: React.ReactNode }) {
  return (
    <div style={{ background: 'var(--white)', border: '0.5px solid var(--border)', borderRadius: 'var(--r2)', overflow: 'hidden' }}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '14px 18px', borderBottom: '0.5px solid var(--border)' }}>
        <div>
          <div style={{ fontSize: 13, fontWeight: 600 }}>{title}</div>
          {sub && <div style={{ fontSize: 11, color: 'var(--text3)', marginTop: 2 }}>{sub}</div>}
        </div>
        {action}
      </div>
      {children}
    </div>
  )
}

function Dashboard() {
  const { data: stats } = useQuery({ queryKey: ['admin-stats'], queryFn: fetchAdminStats, refetchInterval: 30_000 })
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4,1fr)', gap: 10 }}>
        <StatCard label="Gesamt aktiv" value={stats?.total_tenders ?? '—'} sub={`+${stats?.tenders_today ?? 0} heute`} />
        <StatCard label="Heute neu" value={stats?.tenders_today ?? '—'} color="var(--green)" />
        <StatCard label="Aktive Quellen" value={stats?.active_sources ?? '—'} />
        <StatCard label="Kommunen-Quellen" value={stats?.komunen_sources ?? '—'} color="var(--accent)" />
      </div>
      {stats?.last_crawl_at && (
        <div style={{ fontSize: 11, color: 'var(--text3)' }}>
          Letzter Crawl: {new Date(stats.last_crawl_at).toLocaleString('de-DE')}
        </div>
      )}
    </div>
  )
}

function SourcesTable() {
  const qc = useQueryClient()
  const { data: sources = [] } = useQuery({ queryKey: ['sources'], queryFn: fetchSources })
  const crawlMut = useMutation({
    mutationFn: (id: string) => triggerCrawl(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['sources'] }),
  })

  return (
    <Section title="API-Quellen & Scraper" sub="Alle aktiven Datenquellen" action={
      <div style={{ fontSize: 11, color: 'var(--text3)' }}>{sources.length} Quellen</div>
    }>
      <table style={{ width: '100%', borderCollapse: 'collapse' }}>
        <TableHead cols={['Quelle', 'Typ', 'Intervall', 'Letzter Lauf', 'Status', 'Einträge', '']} />
        <tbody>
          {sources.map((s) => (
            <tr key={s.id} style={{ borderBottom: '0.5px solid var(--border)' }}>
              <td style={{ padding: '10px 16px', fontSize: 12, fontWeight: 500, color: 'var(--text)' }}>{s.name}</td>
              <td style={{ padding: '10px 16px', fontSize: 11, fontFamily: 'var(--mono)', color: 'var(--text2)' }}>
                <span style={{ padding: '2px 6px', borderRadius: 4, background: s.source_type === 'api' ? 'var(--accent-l)' : 'var(--gray-tag)', color: s.source_type === 'api' ? 'var(--accent)' : 'var(--text2)', border: '0.5px solid var(--border)', fontSize: 10 }}>
                  {s.source_type.toUpperCase()}
                </span>
              </td>
              <td style={{ padding: '10px 16px', fontSize: 11, color: 'var(--text2)' }}>alle {s.interval_hours}h</td>
              <td style={{ padding: '10px 16px', fontSize: 11, color: 'var(--text2)' }}>
                {s.last_run_at ? new Date(s.last_run_at).toLocaleString('de-DE') : '—'}
              </td>
              <td style={{ padding: '10px 16px' }}><StatusDot status={s.status} /></td>
              <td style={{ padding: '10px 16px', fontSize: 11, fontFamily: 'var(--mono)', color: 'var(--text2)' }}>{s.last_run_entries}</td>
              <td style={{ padding: '10px 16px' }}>
                <Btn variant="accent" onClick={() => crawlMut.mutate(s.id)}>Crawlen</Btn>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </Section>
  )
}

function KomunenPanel() {
  const qc = useQueryClient()
  const { data: stats } = useQuery({ queryKey: ['komunen-stats'], queryFn: fetchKomunenStats })
  const { data: queue = [] } = useQuery({ queryKey: ['komunen-queue'], queryFn: fetchKomunenQueue })
  const updateMut = useMutation({
    mutationFn: ({ id, status }: { id: string; status: string }) => updateKomunen(id, status),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['komunen-queue'] }); qc.invalidateQueries({ queryKey: ['komunen-stats'] }) },
  })
  const [form, setForm] = useState({ name: '', bundesland: '', main_url: '', vergabe_url: '', ags: '' })
  const addMut = useMutation({
    mutationFn: () => addKomunen({ name: form.name, bundesland: form.bundesland || undefined, main_url: form.main_url || undefined, vergabe_url: form.vergabe_url || undefined, ags: form.ags || undefined }),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['komunen-stats'] }); setForm({ name: '', bundesland: '', main_url: '', vergabe_url: '', ags: '' }) },
  })
  const [syncMsg, setSyncMsg] = useState('')
  async function runSync(fn: () => Promise<any>, label: string) {
    setSyncMsg(`${label} gestartet…`)
    try { const r = await fn(); setSyncMsg(r.message || 'Gestartet') }
    catch { setSyncMsg('Fehler beim Starten') }
    setTimeout(() => setSyncMsg(''), 4000)
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
      {/* Stats */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4,1fr)', gap: 10 }}>
        <StatCard label="Gemeinden gesamt" value={stats?.total ?? '—'} />
        <StatCard label="Verifiziert" value={stats?.verified ?? '—'} color="var(--green)" />
        <StatCard label="Kurations-Queue" value={stats?.pending_review ?? '—'} color="var(--amber)" />
        <StatCard label="Mit Vergabe-URL" value={stats?.with_vergabe_url ?? '—'} color="var(--accent)" />
      </div>

      {/* Automation controls */}
      <Section title="Automatisierung" sub="Kommunen automatisch entdecken und prüfen">
        <div style={{ padding: '14px 18px', display: 'flex', flexDirection: 'column', gap: 12 }}>
          {syncMsg && <div style={{ fontSize: 12, color: 'var(--green)', padding: '6px 10px', background: 'var(--green-l)', borderRadius: 'var(--r)' }}>{syncMsg}</div>}
          <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
            <Btn variant="accent" onClick={() => runSync(triggerDestatiSync, 'Destatis-Sync')}>🗺 Destatis-Sync (alle ~10.000 Gemeinden)</Btn>
            <Btn variant="accent" onClick={() => runSync(triggerWikidataSync, 'Wikidata')}>🔗 Wikidata URLs auflösen</Btn>
            <Btn variant="accent" onClick={() => runSync(triggerDiscovery, 'URL-Verify + Discovery')}>🔍 URL-Verify + Discovery</Btn>
          </div>
          <div style={{ fontSize: 11, color: 'var(--text3)', lineHeight: 1.5 }}>
            <strong style={{ color: 'var(--text2)' }}>Automatischer Ablauf:</strong> Destatis-Sync quartalsweise → Wikidata-URLs wöchentlich → URL-Verify + Discovery täglich 03:00 → Kurations-Queue für Grenzfälle.
          </div>
        </div>
      </Section>

      {/* Manual add */}
      <Section title="Gemeinde manuell hinzufügen" sub="Direkt in die Crawler-Queue eintragen">
        <div style={{ padding: '14px 18px', display: 'flex', flexDirection: 'column', gap: 8 }}>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8 }}>
            {[
              { label: 'Name *', key: 'name', placeholder: 'z.B. Stadt Marl' },
              { label: 'Bundesland', key: 'bundesland', placeholder: 'z.B. Nordrhein-Westfalen' },
              { label: 'Haupt-URL', key: 'main_url', placeholder: 'https://www.marl.de' },
              { label: 'Vergabe-URL (optional)', key: 'vergabe_url', placeholder: 'https://www.marl.de/vergabe' },
            ].map(({ label, key, placeholder }) => (
              <div key={key}>
                <div style={{ fontSize: 11, color: 'var(--text2)', fontWeight: 500, marginBottom: 3 }}>{label}</div>
                <input
                  value={(form as any)[key]}
                  onChange={(e) => setForm({ ...form, [key]: e.target.value })}
                  placeholder={placeholder}
                  style={{ width: '100%', background: 'var(--bg)', border: '0.5px solid var(--border)', borderRadius: 'var(--r)', fontSize: 12, padding: '5px 8px', outline: 'none', color: 'var(--text)' }}
                />
              </div>
            ))}
          </div>
          <div style={{ fontSize: 11, color: 'var(--text3)' }}>
            Ohne Vergabe-URL wird die URL automatisch per Discovery gesucht (täglich 03:00).
          </div>
          <Btn variant="accent" onClick={() => addMut.mutate()}>+ Gemeinde hinzufügen</Btn>
        </div>
      </Section>

      {/* Queue */}
      <Section title="Kurations-Queue" sub="Grenzfälle mit niedrigem Konfidenz-Score" action={
        <div style={{ fontSize: 11, color: 'var(--text3)' }}>{queue.length} offen</div>
      }>
        {queue.length === 0 ? (
          <div style={{ padding: '20px', textAlign: 'center', color: 'var(--text3)', fontSize: 13 }}>Queue leer — alle Einträge geprüft.</div>
        ) : (
          <table style={{ width: '100%', borderCollapse: 'collapse' }}>
            <TableHead cols={['Name', 'Bundesland', 'URL', 'Score', 'Status', '']} />
            <tbody>
              {queue.map((k) => (
                <tr key={k.id} style={{ borderBottom: '0.5px solid var(--border)' }}>
                  <td style={{ padding: '10px 16px', fontSize: 12, fontWeight: 500 }}>{k.name}</td>
                  <td style={{ padding: '10px 16px', fontSize: 11, color: 'var(--text2)' }}>{k.bundesland}</td>
                  <td style={{ padding: '10px 16px', fontSize: 11 }}>
                    {k.vergabe_url ? <a href={k.vergabe_url} target="_blank" rel="noopener" style={{ color: 'var(--accent)', fontFamily: 'var(--mono)', fontSize: 10 }}>{k.vergabe_url.substring(0, 40)}…</a> : '—'}
                  </td>
                  <td style={{ padding: '10px 16px', fontFamily: 'var(--mono)', fontSize: 11, color: 'var(--text2)' }}>
                    {k.discovery_confidence != null ? (k.discovery_confidence * 100).toFixed(0) + '%' : '—'}
                  </td>
                  <td style={{ padding: '10px 16px' }}><StatusDot status={k.status === 'verified' ? 'ok' : k.status === 'excluded' ? 'error' : 'warn'} /></td>
                  <td style={{ padding: '10px 16px' }}>
                    <div style={{ display: 'flex', gap: 4 }}>
                      <Btn variant="accent" onClick={() => updateMut.mutate({ id: k.id, status: 'verified' })}>Verified</Btn>
                      <Btn onClick={() => updateMut.mutate({ id: k.id, status: 'excluded' })}>Exclude</Btn>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </Section>
    </div>
  )
}

function ActivityLog() {
  const { data: logs = [] } = useQuery({ queryKey: ['crawl-logs'], queryFn: () => fetchCrawlLogs(100), refetchInterval: 15_000 })
  const dotColor = (level: string) => level === 'error' ? 'var(--red)' : level === 'warn' ? 'var(--amber)' : 'var(--green)'
  return (
    <Section title="Aktivitätslog" sub="Letzte 100 Crawl-Ereignisse">
      <div>
        {logs.map((log) => (
          <div key={log.id} style={{ display: 'flex', alignItems: 'flex-start', gap: 10, padding: '8px 16px', borderBottom: '0.5px solid var(--border)', fontSize: 11.5 }}>
            <span style={{ fontFamily: 'var(--mono)', fontSize: 10, color: 'var(--text3)', whiteSpace: 'nowrap', marginTop: 1, minWidth: 130 }}>
              {new Date(log.created_at).toLocaleString('de-DE')}
            </span>
            <span style={{ width: 6, height: 6, borderRadius: '50%', background: dotColor(log.level), marginTop: 4, flexShrink: 0 }} />
            <span style={{ color: 'var(--text2)', lineHeight: 1.4 }}>{log.message}</span>
            {log.entries_new > 0 && (
              <span style={{ marginLeft: 'auto', fontFamily: 'var(--mono)', fontSize: 10, color: 'var(--green)', whiteSpace: 'nowrap' }}>+{log.entries_new} neu</span>
            )}
          </div>
        ))}
        {logs.length === 0 && (
          <div style={{ padding: 20, textAlign: 'center', color: 'var(--text3)' }}>Keine Logs vorhanden.</div>
        )}
      </div>
    </Section>
  )
}



function SummaryStats() {
  const { data } = useQuery({
    queryKey: ['summary-stats'],
    queryFn: async () => { const r = await api.get('/admin/summaries/stats'); return r.data },
    refetchInterval: 60_000,
  })
  const providerLabels: Record<string, string> = { anthropic: 'Claude Haiku', ollama: 'Ollama (lokal)', openai: 'GPT-4o mini' }
  return (
    <Section title="KI-Zusammenfassungen" sub="On-demand generiert · pro Ausschreibung einmal gecacht">
      <div style={{ padding: '14px 18px', display: 'flex', flexDirection: 'column', gap: 12 }}>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3,1fr)', gap: 10 }}>
          <div className="a-stat"><div className="a-stat-val">{data?.total_summaries ?? '—'}</div><div className="a-stat-label">Generierte Summaries</div></div>
          <div className="a-stat"><div className="a-stat-val" style={{ fontSize: 18 }}>{data ? `${data.total_cost_eur.toFixed(3)} €` : '—'}</div><div className="a-stat-label">Gesamtkosten</div></div>
          <div className="a-stat"><div className="a-stat-val" style={{ fontSize: 18 }}>{data?.total_summaries ? `${((data.total_cost_cents / data.total_summaries) / 100).toFixed(4)} €` : '—'}</div><div className="a-stat-label">Ø pro Summary</div></div>
        </div>
        {data?.by_provider?.length > 0 && (
          <div>
            <div style={{ fontSize: 11, color: 'var(--text3)', marginBottom: 6 }}>Nach Provider</div>
            {data.by_provider.map((p: any) => (
              <div key={p.provider} style={{ display: 'flex', justifyContent: 'space-between', padding: '5px 0', borderBottom: '0.5px solid var(--border)', fontSize: 12 }}>
                <span style={{ color: 'var(--text)' }}>{providerLabels[p.provider] || p.provider}</span>
                <span style={{ color: 'var(--text2)', fontFamily: 'var(--mono)' }}>{p.count}× · {p.cost_cents === 0 ? 'kostenfrei' : `${(p.cost_cents/100).toFixed(3)} €`}</span>
              </div>
            ))}
          </div>
        )}
        {data?.total_summaries === 0 && (
          <div style={{ fontSize: 12, color: 'var(--text3)' }}>
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
      <div style={{ display: 'flex', flex: 1, minHeight: 0, overflow: 'hidden' }}>
        {/* Left nav */}
        <div style={{ width: 180, flexShrink: 0, background: 'var(--white)', borderRight: '0.5px solid var(--border)', padding: '14px 10px', display: 'flex', flexDirection: 'column', gap: 2 }}>
          <div style={{ fontSize: 10, fontWeight: 600, color: 'var(--text3)', textTransform: 'uppercase', letterSpacing: '.06em', padding: '8px 10px 4px' }}>Admin</div>
          {NAV.map((n) => (
            <button key={n} onClick={() => setActiveNav(n)} style={{
              display: 'flex', alignItems: 'center', padding: '7px 10px', borderRadius: 'var(--r)',
              fontSize: 13, textAlign: 'left', border: 'none', cursor: 'pointer',
              background: activeNav === n ? 'var(--accent-l)' : 'transparent',
              color: activeNav === n ? 'var(--accent)' : 'var(--text2)',
              fontWeight: activeNav === n ? 500 : 400,
            }}>{n}</button>
          ))}
        </div>

        {/* Content */}
        <div style={{ flex: 1, overflowY: 'auto', padding: 24, display: 'flex', flexDirection: 'column', gap: 20 }}>
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
