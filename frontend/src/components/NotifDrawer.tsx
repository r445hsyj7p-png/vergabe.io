import { useMutation, useQueryClient } from '@tanstack/react-query'
import { Bell, CheckCheck } from 'lucide-react'
import { markRead, markAllRead } from '../api/client'
import type { Notification } from '../types'
import { Drawer } from './Drawer'

interface Props {
  open: boolean
  onClose: () => void
  notifications: Notification[]
}

export function NotifDrawer({ open, onClose, notifications }: Props) {
  const qc = useQueryClient()
  const readMut = useMutation({
    mutationFn: (id: string) => markRead(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['notifications'] }),
  })
  const readAllMut = useMutation({
    mutationFn: markAllRead,
    onSuccess: () => qc.invalidateQueries({ queryKey: ['notifications'] }),
  })

  const unread = notifications.filter((n) => !n.is_read)
  const read = notifications.filter((n) => n.is_read)

  function typeColor(type: string) {
    if (type.includes('deadline')) return 'var(--color-amber)'
    return 'var(--color-brand)'
  }

  function typeLabel(type: string) {
    if (type.includes('deadline')) return 'Deadline-Warnung'
    return 'Neuer Treffer'
  }

  return (
    <Drawer open={open} onClose={onClose} title="Benachrichtigungen">
      {unread.length > 0 && (
        <div className="py-[14px]" style={{ borderBottom: '0.5px solid var(--color-border)' }}>
          <div className="flex justify-between items-center mb-2.5">
            <span
              className="text-[10px] font-semibold uppercase tracking-wider"
              style={{ color: 'var(--color-ink3)' }}
            >
              Ungelesen — aktive Suchprofile
            </span>
            <button
              onClick={() => readAllMut.mutate()}
              className="flex items-center gap-1 text-[11px]"
              style={{ background: 'none', border: 'none', color: 'var(--color-brand)' }}
            >
              <CheckCheck size={12} />
              Alle lesen
            </button>
          </div>
          {unread.map((n) => (
            <div
              key={n.id}
              onClick={() => readMut.mutate(n.id)}
              className="flex gap-[9px] py-[9px] cursor-pointer"
              style={{ borderBottom: '0.5px solid var(--color-border)' }}
            >
              <div
                className="w-1.5 h-1.5 rounded-full mt-1 shrink-0"
                style={{ background: typeColor(n.notification_type) }}
              />
              <div>
                <div className="text-[12px] font-medium leading-snug" style={{ color: 'var(--color-ink)' }}>
                  <strong>{typeLabel(n.notification_type)}</strong>
                  {n.profile_name && (
                    <span className="font-normal" style={{ color: 'var(--color-ink2)' }}> — {n.profile_name}</span>
                  )}
                </div>
                {n.tender && (
                  <div className="text-[11px] mt-0.5" style={{ color: 'var(--color-ink2)' }}>
                    {n.tender.title.substring(0, 70)}{n.tender.title.length > 70 ? '…' : ''}
                  </div>
                )}
                <div className="font-mono text-[10px] mt-[3px]" style={{ color: 'var(--color-ink3)' }}>
                  {new Date(n.triggered_at).toLocaleString('de-DE')}
                </div>
              </div>
            </div>
          ))}
        </div>
      )}

      {read.length > 0 && (
        <div className="py-[14px]">
          <div
            className="text-[10px] font-semibold uppercase tracking-wider mb-2.5"
            style={{ color: 'var(--color-ink3)' }}
          >
            Gelesen
          </div>
          {read.slice(0, 10).map((n) => (
            <div
              key={n.id}
              className="flex gap-[9px] py-[9px]"
              style={{ borderBottom: '0.5px solid var(--color-border)' }}
            >
              <div className="w-1.5 h-1.5 rounded-full mt-1 shrink-0" style={{ background: 'var(--color-border2)' }} />
              <div>
                <div className="text-[12px]" style={{ color: 'var(--color-ink2)' }}>
                  {typeLabel(n.notification_type)} — {n.profile_name}
                </div>
                {n.tender && (
                  <div className="text-[11px] mt-0.5" style={{ color: 'var(--color-ink3)' }}>
                    {n.tender.title.substring(0, 60)}…
                  </div>
                )}
                <div className="font-mono text-[10px] mt-[3px]" style={{ color: 'var(--color-ink3)' }}>
                  {new Date(n.triggered_at).toLocaleString('de-DE')}
                </div>
              </div>
            </div>
          ))}
        </div>
      )}

      {notifications.length === 0 && (
        <div className="py-10 text-center text-[13px] flex flex-col items-center gap-3" style={{ color: 'var(--color-ink3)' }}>
          <Bell size={24} />
          Keine Benachrichtigungen.
        </div>
      )}

      <div className="py-[14px] text-[11px] leading-relaxed" style={{ color: 'var(--color-ink3)' }}>
        Benachrichtigungen werden nur für{' '}
        <strong style={{ color: 'var(--color-ink2)' }}>aktive Suchprofile</strong> ausgelöst.
      </div>
    </Drawer>
  )
}
