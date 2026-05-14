import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { fetchProfiles, createProfile, updateProfile, deleteProfile } from '../api/client'
import type { SearchProfile } from '../types'
import { Drawer } from './Drawer'

interface Props { open: boolean; onClose: () => void }

const empty = { name: '', keywords: '', cpv_codes: '', deadline_days: '', min_value: '', email: '', is_active: true }

export function ProfileDrawer({ open, onClose }: Props) {
  const qc = useQueryClient()
  const { data: profiles = [] } = useQuery({ queryKey: ['profiles'], queryFn: fetchProfiles })
  const [form, setForm] = useState(empty)

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
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['profiles'] }); setForm(empty) },
  })

  const deleteMut = useMutation({
    mutationFn: (id: string) => deleteProfile(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['profiles'] }),
  })

  const toggleMut = useMutation({
    mutationFn: (p: SearchProfile) => updateProfile(p.id, { ...p, is_active: !p.is_active }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['profiles'] }),
  })

  const F = (key: string) => ({
    value: (form as any)[key],
    onChange: (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>) => setForm({ ...form, [key]: e.target.value }),
  })

  return (
    <Drawer open={open} onClose={onClose} title="Suchprofile & Alerts">
      {/* Create form */}
      <div style={{ padding: '14px 0', borderBottom: '0.5px solid var(--border)' }}>
        <div style={{ fontSize: 10, fontWeight: 600, color: 'var(--text3)', textTransform: 'uppercase', letterSpacing: '.05em', marginBottom: 10 }}>Neues Profil</div>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
          {[
            { label: 'Name', key: 'name', placeholder: 'z.B. Cybersecurity DE' },
            { label: 'Stichwörter', key: 'keywords', placeholder: 'SOC, MDR, XDR, SIEM (kommagetrennt)' },
            { label: 'CPV-Codes', key: 'cpv_codes', placeholder: '72220000, 72200000' },
            { label: 'Deadline-Tage', key: 'deadline_days', placeholder: '30' },
            { label: 'Min. Volumen €', key: 'min_value', placeholder: '100000' },
            { label: 'Alert-E-Mail', key: 'email', placeholder: 'deine@email.de' },
          ].map(({ label, key, placeholder }) => (
            <div key={key}>
              <label style={{ fontSize: 11, color: 'var(--text2)', fontWeight: 500, display: 'block', marginBottom: 3 }}>{label}</label>
              <input {...F(key)} placeholder={placeholder} style={{
                width: '100%', background: 'var(--bg)', border: '0.5px solid var(--border)',
                borderRadius: 5, color: 'var(--text)', fontSize: 12.5, padding: '6px 9px', outline: 'none',
              }} />
            </div>
          ))}
          <button onClick={() => createMut.mutate()} disabled={!form.name} style={{
            background: 'var(--accent)', color: 'white', border: 'none',
            borderRadius: 'var(--r)', padding: '7px 12px', fontSize: 12, fontWeight: 500,
            alignSelf: 'flex-start', opacity: !form.name ? 0.5 : 1,
          }}>Profil & Alert speichern</button>
        </div>
      </div>

      {/* Existing profiles */}
      <div style={{ padding: '14px 0' }}>
        <div style={{ fontSize: 10, fontWeight: 600, color: 'var(--text3)', textTransform: 'uppercase', letterSpacing: '.05em', marginBottom: 10 }}>Aktive Profile</div>
        {profiles.map((p) => (
          <div key={p.id} style={{
            display: 'flex', alignItems: 'center', justifyContent: 'space-between',
            padding: '9px 0', borderBottom: '0.5px solid var(--border)',
          }}>
            <div>
              <div style={{ fontSize: 12.5, fontWeight: 500, color: 'var(--text)' }}>{p.name}</div>
              <div style={{ fontSize: 10, color: 'var(--text3)', fontFamily: 'var(--mono)' }}>
                {(p.keywords || []).slice(0, 3).join(', ')}{p.deadline_days ? ` · <${p.deadline_days}T` : ''}
              </div>
            </div>
            <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
              <label style={{ position: 'relative', width: 30, height: 17, cursor: 'pointer' }}>
                <input type="checkbox" checked={p.is_active} onChange={() => toggleMut.mutate(p)}
                  style={{ opacity: 0, width: 0, height: 0 }} />
                <span style={{
                  position: 'absolute', inset: 0, borderRadius: 17,
                  background: p.is_active ? 'var(--accent)' : 'var(--border2)',
                  transition: 'background .2s',
                }} />
                <span style={{
                  position: 'absolute', top: 2, left: p.is_active ? 15 : 2,
                  width: 13, height: 13, background: 'white', borderRadius: '50%',
                  transition: 'left .2s', boxShadow: '0 1px 2px rgba(0,0,0,.2)',
                }} />
              </label>
              <button onClick={() => deleteMut.mutate(p.id)} style={{
                width: 22, height: 22, borderRadius: 4, border: '0.5px solid var(--border)',
                background: 'var(--white)', color: 'var(--text3)', fontSize: 12, display: 'flex', alignItems: 'center', justifyContent: 'center',
              }}>✕</button>
            </div>
          </div>
        ))}
      </div>
    </Drawer>
  )
}
