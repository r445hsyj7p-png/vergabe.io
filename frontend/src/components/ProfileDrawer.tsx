import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import * as Switch from '@radix-ui/react-switch'
import { Plus, Trash2 } from 'lucide-react'
import { fetchProfiles, createProfile, updateProfile, deleteProfile } from '../api/client'
import type { SearchProfile } from '../types'
import { Drawer } from './Drawer'

interface Props { open: boolean; onClose: () => void }

const emptyForm = { name: '', keywords: '', cpv_codes: '', deadline_days: '', min_value: '', email: '' }

export function ProfileDrawer({ open, onClose }: Props) {
  const qc = useQueryClient()
  const { data: profiles = [] } = useQuery({ queryKey: ['profiles'], queryFn: fetchProfiles })
  const [form, setForm] = useState(emptyForm)

  const createMut = useMutation({
    mutationFn: () => createProfile({
      name: form.name,
      keywords: form.keywords ? form.keywords.split(',').map((s) => s.trim()).filter(Boolean) : null,
      cpv_codes: form.cpv_codes ? form.cpv_codes.split(',').map((s) => s.trim()).filter(Boolean) : null,
      deadline_days: form.deadline_days ? parseInt(form.deadline_days) : null,
      min_value: form.min_value ? parseInt(form.min_value) * 100 : null,
      email: form.email || null,
      is_active: true,
    }),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['profiles'] }); setForm(emptyForm) },
  })

  const deleteMut = useMutation({
    mutationFn: (id: string) => deleteProfile(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['profiles'] }),
  })

  const toggleMut = useMutation({
    mutationFn: (p: SearchProfile) => updateProfile(p.id, { ...p, is_active: !p.is_active }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['profiles'] }),
  })

  function setField(key: string, value: string) {
    setForm((f) => ({ ...f, [key]: value }))
  }

  const fields: Array<{ label: string; key: keyof typeof emptyForm; placeholder: string }> = [
    { label: 'Name', key: 'name', placeholder: 'z.B. Cybersecurity DE' },
    { label: 'Stichwörter', key: 'keywords', placeholder: 'SOC, MDR, XDR, SIEM (kommagetrennt)' },
    { label: 'CPV-Codes', key: 'cpv_codes', placeholder: '72220000, 72200000' },
    { label: 'Deadline-Tage', key: 'deadline_days', placeholder: '30' },
    { label: 'Min. Volumen €', key: 'min_value', placeholder: '100000' },
    { label: 'Alert-E-Mail', key: 'email', placeholder: 'deine@email.de' },
  ]

  return (
    <Drawer open={open} onClose={onClose} title="Suchprofile & Alerts">
      {/* Create form */}
      <div className="py-[14px]" style={{ borderBottom: '0.5px solid var(--color-border)' }}>
        <div
          className="text-[10px] font-semibold uppercase tracking-wider mb-2.5"
          style={{ color: 'var(--color-ink3)' }}
        >
          Neues Profil
        </div>
        <div className="flex flex-col gap-2">
          {fields.map(({ label, key, placeholder }) => (
            <div key={key}>
              <label className="block text-[11px] font-medium mb-[3px]" style={{ color: 'var(--color-ink2)' }}>
                {label}
              </label>
              <input
                value={form[key]}
                onChange={(e) => setField(key, e.target.value)}
                placeholder={placeholder}
                className="w-full rounded-[5px] text-[12.5px] px-[9px] py-[6px] outline-none"
                style={{ background: 'var(--color-bg)', border: '0.5px solid var(--color-border)', color: 'var(--color-ink)' }}
              />
            </div>
          ))}
          <button
            onClick={() => createMut.mutate()}
            disabled={!form.name || createMut.isPending}
            className="self-start flex items-center gap-1.5 text-white rounded-md px-3 py-[7px] text-[12px] font-medium transition-opacity"
            style={{ background: 'var(--color-brand)', opacity: (!form.name || createMut.isPending) ? 0.5 : 1 }}
          >
            <Plus size={13} />
            {createMut.isPending ? 'Speichern…' : 'Profil & Alert speichern'}
          </button>
        </div>
      </div>

      {/* Existing profiles */}
      <div className="py-[14px]">
        <div
          className="text-[10px] font-semibold uppercase tracking-wider mb-2.5"
          style={{ color: 'var(--color-ink3)' }}
        >
          Aktive Profile
        </div>
        {profiles.map((p) => (
          <div
            key={p.id}
            className="flex items-center justify-between py-[9px]"
            style={{ borderBottom: '0.5px solid var(--color-border)' }}
          >
            <div>
              <div className="text-[12.5px] font-medium" style={{ color: 'var(--color-ink)' }}>{p.name}</div>
              <div className="font-mono text-[10px]" style={{ color: 'var(--color-ink3)' }}>
                {(p.keywords || []).slice(0, 3).join(', ')}{p.deadline_days ? ` · <${p.deadline_days}T` : ''}
              </div>
            </div>
            <div className="flex items-center gap-1.5">
              <Switch.Root
                checked={p.is_active}
                onCheckedChange={() => toggleMut.mutate(p)}
                className="relative inline-flex w-[30px] h-[17px] rounded-full cursor-pointer outline-none transition-colors"
                style={{ background: p.is_active ? 'var(--color-brand)' : 'var(--color-border2)' }}
              >
                <Switch.Thumb
                  className="block w-[13px] h-[13px] rounded-full bg-white shadow-sm transition-transform duration-200 translate-x-[2px] data-[state=checked]:translate-x-[15px]"
                  style={{ marginTop: 2 }}
                />
              </Switch.Root>
              <button
                onClick={() => deleteMut.mutate(p.id)}
                className="w-[22px] h-[22px] rounded flex items-center justify-center"
                style={{ border: '0.5px solid var(--color-border)', background: 'var(--color-surface)', color: 'var(--color-ink3)' }}
              >
                <Trash2 size={12} />
              </button>
            </div>
          </div>
        ))}
      </div>
    </Drawer>
  )
}
