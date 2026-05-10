interface Props {
  open: boolean
  onClose: () => void
  title: string
  children: React.ReactNode
  width?: number
}

export function Drawer({ open, onClose, title, children, width = 360 }: Props) {
  return (
    <>
      {open && (
        <div
          onClick={onClose}
          style={{
            position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.1)',
            zIndex: 100,
          }}
        />
      )}
      <div style={{
        position: 'fixed', right: 0, top: 0, bottom: 0, width,
        background: 'var(--white)', borderLeft: '0.5px solid var(--border)',
        boxShadow: '-4px 0 20px rgba(0,0,0,.06)',
        zIndex: 101, display: 'flex', flexDirection: 'column',
        transform: open ? 'translateX(0)' : 'translateX(100%)',
        transition: 'transform .22s cubic-bezier(.4,0,.2,1)',
      }}>
        <div style={{
          display: 'flex', alignItems: 'center', justifyContent: 'space-between',
          padding: '14px 18px', borderBottom: '0.5px solid var(--border)', flexShrink: 0,
        }}>
          <span style={{ fontSize: 14, fontWeight: 600 }}>{title}</span>
          <button onClick={onClose} style={{
            width: 26, height: 26, borderRadius: 5, border: '0.5px solid var(--border)',
            background: 'transparent', color: 'var(--text2)', fontSize: 13,
            display: 'flex', alignItems: 'center', justifyContent: 'center',
          }}>✕</button>
        </div>
        <div style={{ flex: 1, overflowY: 'auto', padding: '0 18px' }}>
          {children}
        </div>
      </div>
    </>
  )
}
