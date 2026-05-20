import * as Dialog from '@radix-ui/react-dialog'
import { X } from 'lucide-react'

interface Props {
  open: boolean
  onClose: () => void
  title: string
  children: React.ReactNode
  width?: number
}

export function Drawer({ open, onClose, title, children, width = 360 }: Props) {
  return (
    <Dialog.Root open={open} onOpenChange={(o) => !o && onClose()}>
      <Dialog.Portal>
        <Dialog.Overlay className="fixed inset-0 z-[100]" style={{ background: 'rgba(0,0,0,0.1)' }} />
        <Dialog.Content
          style={{ width }}
          className="fixed right-0 top-0 bottom-0 z-[101] flex flex-col outline-none"
          aria-describedby={undefined}
          onOpenAutoFocus={(e) => e.preventDefault()}
        >
          <div
            className="flex flex-col h-full"
            style={{ background: 'var(--color-surface)', borderLeft: '0.5px solid var(--color-border)', boxShadow: '-4px 0 20px rgba(0,0,0,.06)' }}
          >
            <div
              className="flex items-center justify-between px-[18px] py-[14px] shrink-0"
              style={{ borderBottom: '0.5px solid var(--color-border)' }}
            >
              <Dialog.Title className="text-sm font-semibold" style={{ color: 'var(--color-ink)' }}>{title}</Dialog.Title>
              <Dialog.Close asChild>
                <button
                  className="w-[26px] h-[26px] rounded-[5px] flex items-center justify-center"
                  style={{ border: '0.5px solid var(--color-border)', background: 'transparent', color: 'var(--color-ink2)' }}
                >
                  <X size={13} />
                </button>
              </Dialog.Close>
            </div>
            <div className="flex-1 overflow-y-auto px-[18px]">
              {children}
            </div>
          </div>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  )
}
