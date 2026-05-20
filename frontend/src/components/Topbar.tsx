import { useState } from 'react'
import { useNavigate, useLocation } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { Search, Bell, Settings, LogOut, ChevronDown } from 'lucide-react'
import { fetchNotifications, fetchProfiles } from '../api/client'
import type { SearchProfile, TenderFilters } from '../types'
import { ProfileDrawer } from './ProfileDrawer'
import { NotifDrawer } from './NotifDrawer'
import { cn } from '@/lib/utils'

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

  const navItems = [
    { label: 'Ausschreibungen', path: '/' },
    { label: 'Admin', path: '/admin' },
  ]

  return (
    <>
      <div
        className="flex items-center gap-2.5 px-4 h-12 shrink-0 relative z-20"
        style={{ background: 'var(--color-surface)', borderBottom: '0.5px solid var(--color-border)' }}
      >
        {/* Logo */}
        <div className="flex items-center gap-1.5 mr-1 shrink-0">
          <div className="w-1.5 h-1.5 rounded-full" style={{ background: 'var(--color-brand)' }} />
          <span className="font-mono text-[13px] font-medium" style={{ color: 'var(--color-ink)' }}>vergabe.io</span>
        </div>

        {/* Nav tabs */}
        <div className="flex gap-[2px]">
          {navItems.map(({ label, path }) => {
            const active = location.pathname === path
            return (
              <button
                key={path}
                onClick={() => navigate(path)}
                className={cn('px-[11px] py-[5px] rounded text-[12px] transition-colors')}
                style={{
                  border: `1px solid ${active ? '#c7d7fb' : 'transparent'}`,
                  background: active ? 'var(--color-brand-light)' : 'transparent',
                  color: active ? 'var(--color-brand)' : 'var(--color-ink2)',
                  fontWeight: active ? 500 : 400,
                }}
              >
                {label}
              </button>
            )
          })}
        </div>

        {/* Profile selector (search page only) */}
        {!isAdmin && (
          <div className="relative">
            <button
              onClick={() => setShowProfileDD(!showProfileDD)}
              className="flex items-center gap-1.5 px-[10px] py-[5px] rounded text-[12px]"
              style={{ border: '0.5px solid var(--color-border)', background: 'var(--color-surface)', color: 'var(--color-ink2)' }}
            >
              Suchprofil:&nbsp;
              <span className="font-medium" style={{ color: 'var(--color-brand)' }}>
                {activeProfile ? activeProfile.name : 'Kein Profil'}
              </span>
              <ChevronDown size={12} />
            </button>
            {showProfileDD && (
              <div
                className="absolute top-9 left-0 rounded p-1.5 min-w-[250px] z-50"
                style={{ background: 'var(--color-surface)', border: '0.5px solid var(--color-border)', boxShadow: '0 4px 16px rgba(0,0,0,.08)' }}
              >
                <div
                  onClick={() => {
                    setShowProfileDD(false)
                    onProfileSelect(null)
                    onFiltersChange({ ...filters, profile_id: undefined, q: undefined, page: 1 })
                  }}
                  className="px-[10px] py-[7px] rounded cursor-pointer text-[12.5px]"
                  style={{ color: 'var(--color-ink2)' }}
                  onMouseEnter={(e) => { e.currentTarget.style.background = 'var(--color-bg)' }}
                  onMouseLeave={(e) => { e.currentTarget.style.background = 'transparent' }}
                >
                  Kein Profil
                </div>
                {profiles.map((p) => (
                  <div
                    key={p.id}
                    onClick={() => handleProfileSelect(p)}
                    className="px-[10px] py-[7px] rounded cursor-pointer text-[12.5px]"
                    style={{
                      background: activeProfile?.id === p.id ? 'var(--color-brand-light)' : 'transparent',
                      color: activeProfile?.id === p.id ? 'var(--color-brand)' : 'var(--color-ink2)',
                    }}
                    onMouseEnter={(e) => { if (activeProfile?.id !== p.id) e.currentTarget.style.background = 'var(--color-bg)' }}
                    onMouseLeave={(e) => { if (activeProfile?.id !== p.id) e.currentTarget.style.background = 'transparent' }}
                  >
                    <div className="font-medium">{p.name}</div>
                    <div className="text-[11px]" style={{ color: 'var(--color-ink3)' }}>
                      {(p.keywords || []).slice(0, 3).join(', ')}
                    </div>
                  </div>
                ))}
                <div className="h-px mx-0 my-1" style={{ background: 'var(--color-border)' }} />
                <div
                  onClick={() => { setShowProfileDD(false); setShowProfileDrawer(true) }}
                  className="px-[10px] py-[7px] rounded cursor-pointer text-[12px] flex items-center gap-1.5"
                  style={{ color: 'var(--color-brand)' }}
                  onMouseEnter={(e) => { e.currentTarget.style.background = 'var(--color-brand-light)' }}
                  onMouseLeave={(e) => { e.currentTarget.style.background = 'transparent' }}
                >
                  + Neues Suchprofil
                </div>
              </div>
            )}
          </div>
        )}

        {/* Search input */}
        {!isAdmin && (
          <div className="flex-1 relative max-w-[700px]">
            <Search
              size={14}
              className="absolute left-[10px] top-1/2 -translate-y-1/2 pointer-events-none"
              style={{ color: 'var(--color-ink3)' }}
            />
            <input
              value={filters.q || ''}
              onChange={(e) => onFiltersChange({ ...filters, q: e.target.value, page: 1 })}
              placeholder="Suchbegriff, CPV-Code, Auftraggeber…"
              className="w-full pl-8 pr-[10px] py-[7px] rounded text-[12.5px] outline-none"
              style={{ background: 'var(--color-bg)', border: '0.5px solid var(--color-border)', color: 'var(--color-ink)' }}
            />
          </div>
        )}

        <div className="ml-auto flex items-center gap-2">
          {/* Notifications */}
          <button
            onClick={() => setShowNotifDrawer(true)}
            className="relative flex items-center gap-[5px] px-[10px] py-[6px] rounded text-[12px]"
            style={{ border: '0.5px solid var(--color-border)', background: 'var(--color-surface)', color: 'var(--color-ink2)' }}
          >
            <Bell size={13} />
            Benachrichtigungen
            {unread > 0 && (
              <span
                className="absolute -top-1 -right-1 flex items-center justify-center font-mono text-[9px] text-white w-[14px] h-[14px] rounded-full"
                style={{ background: 'var(--color-rose)', border: '1.5px solid var(--color-surface)' }}
              >
                {unread}
              </span>
            )}
          </button>

          {/* Alerts / Profile button */}
          <button
            onClick={() => setShowProfileDrawer(true)}
            className="flex items-center gap-[5px] px-[10px] py-[6px] rounded text-[12px]"
            style={{ border: '0.5px solid var(--color-border)', background: 'var(--color-surface)', color: 'var(--color-ink2)' }}
          >
            <Settings size={13} />
            Alerts
          </button>

          {/* Logout */}
          <button
            onClick={logout}
            className="flex items-center gap-[5px] px-[10px] py-[6px] rounded text-[12px]"
            style={{ border: '0.5px solid var(--color-border)', background: 'var(--color-surface)', color: 'var(--color-ink2)' }}
          >
            <LogOut size={13} />
            Abmelden
          </button>
        </div>
      </div>

      <ProfileDrawer open={showProfileDrawer} onClose={() => setShowProfileDrawer(false)} />
      <NotifDrawer open={showNotifDrawer} onClose={() => setShowNotifDrawer(false)} notifications={notifications} />
    </>
  )
}
