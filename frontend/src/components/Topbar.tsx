import { useState } from 'react'
import { useNavigate, useLocation } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { fetchNotifications, fetchProfiles } from '../api/client'
import type { SearchProfile, TenderFilters } from '../types'
import { ProfileDrawer } from './ProfileDrawer'
import { NotifDrawer } from './NotifDrawer'

interface Props {
  filters: TenderFilters
  onFiltersChange: (f: TenderFilters) => void
  activeProfile: SearchProfile | null
  onProfileSelect: (p: SearchProfile | null) => void
}

export function Topbar({ filters, onFiltersChange, activeProfile, onProfileSelect }: Props) {
  const navigate = useNavigate()
  const location = useLocation()
  const isAdmin = location.pathname === '/admin'
  const [showProfileDD, setShowProfileDD] = useState(false)
  const [showProfileDrawer, setShowProfileDrawer] = useState(false)
  const [showNotifDrawer, setShowNotifDrawer] = useState(false)

  const { data: profiles = [] } = useQuery({ queryKey: ['profiles'], queryFn: fetchProfiles })
  const { data: notifications = [] } = useQuery({
    queryKey: ['notifications'],
    queryFn: () => fetchNotifications(true),
    refetchInterval: 60_000,
  })

  const unread = notifications.filter((n) => !n.is_read).length

  function handleProfileSelect(p: SearchProfile) {
    setShowProfileDD(false)
    onProfileSelect(p)
    const keywords = (p.keywords || []).join(', ')
    onFiltersChange({ ...filters, q: keywords, profile_id: p.id, page: 1 })
  }

  function logout() {
    localStorage.removeItem('vergabe_token')
    navigate('/login')
  }

  return (
    <>
      <div style={{
        display: 'flex', alignItems: 'center', gap: 10, padding: '0 16px',
        height: 48, background: 'var(--white)', borderBottom: '0.5px solid var(--border)',
        flexShrink: 0, position: 'relative', zIndex: 20,
      }}>
        {/* Logo */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginRight: 4, flexShrink: 0 }}>
          <div style={{ width: 6, height: 6, borderRadius: '50%', background: 'var(--accent)' }} />
          <span style={{ fontFamily: 'var(--mono)', fontSize: 13, fontWeight: 500 }}>vergabe.io</span>
        </div>

        {/* Nav tabs */}
        <div style={{ display: 'flex', gap: 2 }}>
          {[{ label: 'Ausschreibungen', path: '/' }, { label: 'Admin', path: '/admin' }].map(({ label, path }) => (
            <button key={path} onClick={() => navigate(path)} style={{
              padding: '5px 11px', borderRadius: 'var(--r)', fontSize: 12,
              border: `1px solid ${location.pathname === path ? '#c7d7fb' : 'transparent'}`,
              background: location.pathname === path ? 'var(--accent-l)' : 'transparent',
              color: location.pathname === path ? 'var(--accent)' : 'var(--text2)',
              fontWeight: location.pathname === path ? 500 : 400,
            }}>{label}</button>
          ))}
        </div>

        {/* Profile selector (search page only) */}
        {!isAdmin && (
          <div style={{ position: 'relative' }}>
            <button onClick={() => setShowProfileDD(!showProfileDD)} style={{
              display: 'flex', alignItems: 'center', gap: 6, padding: '5px 10px',
              borderRadius: 'var(--r)', border: '0.5px solid var(--border)',
              background: 'var(--white)', color: 'var(--text2)', fontSize: 12,
            }}>
              Suchprofil:&nbsp;
              <span style={{ color: 'var(--accent)', fontWeight: 500 }}>
                {activeProfile ? activeProfile.name : 'Kein Profil'}
              </span>
              <span style={{ fontSize: 10 }}>▾</span>
            </button>
            {showProfileDD && (
              <div style={{
                position: 'absolute', top: 36, left: 0, background: 'var(--white)',
                border: '0.5px solid var(--border)', borderRadius: 'var(--r)',
                boxShadow: 'var(--sh2)', minWidth: 250, zIndex: 50,
                padding: 6,
              }}>
                <div onClick={() => { setShowProfileDD(false); onProfileSelect(null); onFiltersChange({ ...filters, profile_id: undefined, q: undefined, page: 1 }) }}
                  style={{ padding: '7px 10px', borderRadius: 4, cursor: 'pointer', fontSize: 12.5, color: 'var(--text2)' }}
                  onMouseEnter={(e) => (e.currentTarget.style.background = 'var(--bg)')}
                  onMouseLeave={(e) => (e.currentTarget.style.background = 'transparent')}
                >Kein Profil</div>
                {profiles.map((p) => (
                  <div key={p.id} onClick={() => handleProfileSelect(p)}
                    style={{
                      padding: '7px 10px', borderRadius: 4, cursor: 'pointer', fontSize: 12.5,
                      background: activeProfile?.id === p.id ? 'var(--accent-l)' : 'transparent',
                      color: activeProfile?.id === p.id ? 'var(--accent)' : 'var(--text2)',
                    }}
                    onMouseEnter={(e) => { if (activeProfile?.id !== p.id) e.currentTarget.style.background = 'var(--bg)' }}
                    onMouseLeave={(e) => { if (activeProfile?.id !== p.id) e.currentTarget.style.background = 'transparent' }}
                  >
                    <div style={{ fontWeight: 500 }}>{p.name}</div>
                    <div style={{ fontSize: 11, color: 'var(--text3)' }}>{(p.keywords || []).slice(0, 3).join(', ')}</div>
                  </div>
                ))}
                <div style={{ height: 1, background: 'var(--border)', margin: '4px 0' }} />
                <div onClick={() => { setShowProfileDD(false); setShowProfileDrawer(true) }}
                  style={{ padding: '7px 10px', borderRadius: 4, cursor: 'pointer', fontSize: 12, color: 'var(--accent)', display: 'flex', alignItems: 'center', gap: 6 }}
                  onMouseEnter={(e) => (e.currentTarget.style.background = 'var(--accent-l)')}
                  onMouseLeave={(e) => (e.currentTarget.style.background = 'transparent')}
                >+ Neues Suchprofil</div>
              </div>
            )}
          </div>
        )}

        {/* Search input */}
        {!isAdmin && (
          <div style={{ flex: 1, position: 'relative', maxWidth: 700 }}>
            <span style={{ position: 'absolute', left: 10, top: '50%', transform: 'translateY(-50%)', color: 'var(--text3)', fontSize: 14, pointerEvents: 'none' }}>🔍</span>
            <input
              value={filters.q || ''}
              onChange={(e) => onFiltersChange({ ...filters, q: e.target.value, page: 1 })}
              placeholder="Suchbegriff, CPV-Code, Auftraggeber…"
              style={{
                width: '100%', background: 'var(--bg)', border: '0.5px solid var(--border)',
                borderRadius: 'var(--r)', color: 'var(--text)', fontSize: 12.5,
                padding: '7px 10px 7px 32px', outline: 'none',
              }}
            />
          </div>
        )}

        <div style={{ marginLeft: 'auto', display: 'flex', alignItems: 'center', gap: 8 }}>
          {/* Notifications */}
          <button onClick={() => setShowNotifDrawer(true)} style={{
            position: 'relative', display: 'flex', alignItems: 'center', gap: 5,
            padding: '6px 10px', borderRadius: 'var(--r)', border: '0.5px solid var(--border)',
            background: 'var(--white)', color: 'var(--text2)', fontSize: 12,
          }}>
            🔔 Benachrichtigungen
            {unread > 0 && (
              <span style={{
                position: 'absolute', top: -4, right: -4, background: 'var(--red)', color: 'white',
                fontSize: 9, width: 14, height: 14, borderRadius: '50%',
                display: 'flex', alignItems: 'center', justifyContent: 'center',
                border: '1.5px solid var(--white)', fontFamily: 'var(--mono)',
              }}>{unread}</span>
            )}
          </button>

          {/* Alerts button */}
          <button onClick={() => setShowProfileDrawer(true)} style={{
            display: 'flex', alignItems: 'center', gap: 5,
            padding: '6px 10px', borderRadius: 'var(--r)', border: '0.5px solid var(--border)',
            background: 'var(--white)', color: 'var(--text2)', fontSize: 12,
          }}>⏱ Alerts</button>

          {/* Logout */}
          <button onClick={logout} style={{
            padding: '6px 10px', borderRadius: 'var(--r)', border: '0.5px solid var(--border)',
            background: 'var(--white)', color: 'var(--text2)', fontSize: 12,
          }}>Abmelden</button>
        </div>
      </div>

      <ProfileDrawer open={showProfileDrawer} onClose={() => setShowProfileDrawer(false)} />
      <NotifDrawer open={showNotifDrawer} onClose={() => setShowNotifDrawer(false)} notifications={notifications} />
    </>
  )
}
