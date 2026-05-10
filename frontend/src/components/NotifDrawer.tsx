import { useMutation, useQueryClient } from '@tanstack/react-query'
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
  const readMut = useMutation({ mutationFn: (id: string) => markRead(id), onSuccess: () => qc.invalidateQueries({ queryKey: ['notifications'] }) })
  const readAllMut = useMutation({ mutationFn: markAllRead, onSuccess: () => qc.invalidateQueries({ queryKey: ['notifications'] }) })

  const unread = notifications.filter((n) => !n.is_read)
  const read = notifications.filter((n) => n.is_read)

  function typeColor(type: string) {
    if (type.includes('deadline')) return 'var(--amber)'
    return 'var(--accent)'
  }

  function typeLabel(type: string) {
    if (type.includes('deadline')) return 'Deadline-Warnung'
    return 'Neuer Treffer'
  }

  return (
    <Drawer open={open} onClose={onClose} title="Benachrichtigungen">
      {unread.length > 0 && (
        <div style={{ padding: '14px 0', borderBottom: '0.5px solid var(--border)' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 10 }}>
            <span style={{ fontSize: 10, fontWeight: 600, color: 'var(--text3)', textTransform: 'uppercase', letterSpacing: '.05em' }}>
              Ungelesen — aktive Suchprofile
            </span>
            <button onClick={() => readAllMut.mutate()} style={{ fontSize: 11, color: 'var(--accent)', background: 'none', border: 'none' }}>Alle lesen</button>
          </div>
          {unread.map((n) => (
            <div key={n.id} onClick={() => readMut.mutate(n.id)} style={{
              display: 'flex', gap: 9, padding: '9px 0', borderBottom: '0.5px solid var(--border)',
              cursor: 'pointer',
            }}>
              <div style={{ width: 6, height: 6, borderRadius: '50%', background: typeColor(n.notification_type), marginTop: 4, flexShrink: 0 }} />
              <div>
                <div style={{ fontSize: 12, color: 'var(--text)', fontWeight: 500, lineHeight: 1.4 }}>
                  <strong>{typeLabel(n.notification_type)}</strong>
                  {n.profile_name && <span style={{ fontWeight: 400, color: 'var(--text2)' }}> — {n.profile_name}</span>}
                </div>
                {n.tender && (
                  <div style={{ fontSize: 11, color: 'var(--text2)', marginTop: 2 }}>{n.tender.title.substring(0, 70)}{n.tender.title.length > 70 ? '…' : ''}</div>
                )}
                <div style={{ fontSize: 10, color: 'var(--text3)', fontFamily: 'var(--mono)', marginTop: 3 }}>
                  {new Date(n.triggered_at).toLocaleString('de-DE')}
                </div>
              </div>
            </div>
          ))}
        </div>
      )}

      {read.length > 0 && (
        <div style={{ padding: '14px 0' }}>
          <div style={{ fontSize: 10, fontWeight: 600, color: 'var(--text3)', textTransform: 'uppercase', letterSpacing: '.05em', marginBottom: 10 }}>Gelesen</div>
          {read.slice(0, 10).map((n) => (
            <div key={n.id} style={{ display: 'flex', gap: 9, padding: '9px 0', borderBottom: '0.5px solid var(--border)' }}>
              <div style={{ width: 6, height: 6, borderRadius: '50%', background: 'var(--border2)', marginTop: 4, flexShrink: 0 }} />
              <div>
                <div style={{ fontSize: 12, color: 'var(--text2)' }}>{typeLabel(n.notification_type)} — {n.profile_name}</div>
                {n.tender && <div style={{ fontSize: 11, color: 'var(--text3)', marginTop: 2 }}>{n.tender.title.substring(0, 60)}…</div>}
                <div style={{ fontSize: 10, color: 'var(--text3)', fontFamily: 'var(--mono)', marginTop: 3 }}>{new Date(n.triggered_at).toLocaleString('de-DE')}</div>
              </div>
            </div>
          ))}
        </div>
      )}

      {notifications.length === 0 && (
        <div style={{ padding: '40px 0', textAlign: 'center', color: 'var(--text3)', fontSize: 13 }}>
          Keine Benachrichtigungen.
        </div>
      )}

      <div style={{ padding: '14px 0', fontSize: 11, color: 'var(--text3)', lineHeight: 1.5 }}>
        Benachrichtigungen werden nur für <strong style={{ color: 'var(--text2)' }}>aktive Suchprofile</strong> ausgelöst.
      </div>
    </Drawer>
  )
}
