/// <reference types="vite/client" />
import axios from 'axios'
import type {
  TenderPage, TenderDetail, SearchProfile, Notification,
  Source, CrawlLog, AdminStats, KomunenSource, TenderFilters,
  SummaryStatus, TenderSummary,
} from '../types'

const BASE = import.meta.env.VITE_API_URL || '/api'

export const api = axios.create({ baseURL: BASE, timeout: 8000 })

api.interceptors.request.use((config) => {
  const token = sessionStorage.getItem('vergabe_token')
  if (token) config.headers.Authorization = `Bearer ${token}`
  return config
})

api.interceptors.response.use(
  (r) => r,
  (err) => {
    // Don't redirect on 401 for setup/auth endpoints themselves
    const url = err.config?.url ?? ''
    if (err.response?.status === 401 && !url.includes('/setup') && !url.includes('/auth/')) {
      sessionStorage.removeItem('vergabe_token')
      window.location.href = '/login'
    }
    return Promise.reject(err)
  }
)

export async function fetchSetupStatus() {
  const r = await api.get('/setup')
  return r.data as { setup_required: boolean }
}

export async function completeSetup(name: string, email: string, password: string) {
  await api.post('/setup', { name, email, password })
}

export async function login(email: string, password: string) {
  const r = await api.post('/auth/token', { email, password })
  return r.data as { access_token: string; token_type: string }
}

export async function fetchTenders(filters: TenderFilters) {
  const r = await api.get('/tenders', { params: filters })
  return r.data as TenderPage
}

export async function fetchTender(id: string) {
  const r = await api.get(`/tenders/${id}`)
  return r.data as TenderDetail
}

export async function setTag(tenderId: string, status: 'interest' | 'ignore') {
  await api.post(`/tenders/${tenderId}/tags`, { status })
}

export async function removeTag(tenderId: string) {
  await api.delete(`/tenders/${tenderId}/tags`)
}

export async function fetchProfiles() {
  const r = await api.get('/search-profiles')
  return r.data as SearchProfile[]
}

export async function createProfile(data: Partial<SearchProfile>) {
  const r = await api.post('/search-profiles', data)
  return r.data as SearchProfile
}

export async function updateProfile(id: string, data: Partial<SearchProfile>) {
  const r = await api.put(`/search-profiles/${id}`, data)
  return r.data as SearchProfile
}

export async function deleteProfile(id: string) {
  await api.delete(`/search-profiles/${id}`)
}

export async function fetchNotifications(unreadOnly = true) {
  const r = await api.get('/notifications', { params: { unread_only: unreadOnly } })
  return r.data as Notification[]
}

export async function markRead(id: string) {
  await api.patch(`/notifications/${id}/read`)
}

export async function markAllRead() {
  await api.post('/notifications/mark-all-read')
}

export async function fetchAdminStats() {
  const r = await api.get('/admin/stats')
  return r.data as AdminStats
}

export async function fetchSources() {
  const r = await api.get('/admin/sources')
  return r.data as Source[]
}

export async function triggerCrawl(sourceId: string) {
  const r = await api.post(`/admin/sources/${sourceId}/crawl`)
  return r.data
}

export async function fetchCrawlLogs(limit = 100) {
  const r = await api.get('/admin/crawl-logs', { params: { limit } })
  return r.data as CrawlLog[]
}

export async function fetchKomunenStats() {
  const r = await api.get('/admin/komunen/stats')
  return r.data
}

export async function fetchKomunenList(params: {
  status?: string; bundesland?: string; q?: string; page?: number; per_page?: number;
}) {
  const r = await api.get('/admin/komunen', { params })
  return r.data as { items: KomunenSource[]; total: number; page: number; per_page: number }
}

export async function fetchKomunenBundeslaender() {
  const r = await api.get('/admin/komunen/distinct-bundeslaender')
  return r.data as string[]
}

export async function fetchKomunenQueue() {
  const r = await api.get('/admin/komunen/queue')
  return r.data as KomunenSource[]
}

export async function updateKomunen(id: string, status: string) {
  await api.patch(`/admin/komunen/${id}`, null, { params: { status } })
}

export async function addKomunen(data: {
  name: string; bundesland?: string; einwohner?: number;
  main_url?: string; vergabe_url?: string; ags?: string;
}) {
  const r = await api.post('/admin/komunen', data)
  return r.data
}

export async function triggerDestatiSync() {
  const r = await api.post('/admin/komunen/sync-destatis')
  return r.data
}

export async function triggerWikidataSync() {
  const r = await api.post('/admin/komunen/sync-wikidata')
  return r.data
}

export async function triggerDiscovery() {
  const r = await api.post('/admin/komunen/run-discovery')
  return r.data
}

export async function fetchSummaryStatus(tenderId: string) {
  const r = await api.get(`/tenders/${tenderId}/summary`)
  return r.data as SummaryStatus
}

export async function generateSummary(tenderId: string) {
  const r = await api.post(`/tenders/${tenderId}/summary`)
  return r.data as TenderSummary
}

export async function deleteSummary(tenderId: string) {
  await api.delete(`/tenders/${tenderId}/summary`)
}

export async function downloadExport(filters: TenderFilters): Promise<void> {
  const params = new URLSearchParams()
  if (filters.q) params.set('q', filters.q)
  if (filters.status) params.set('status', filters.status)
  if (filters.it_category) params.set('it_category', filters.it_category)
  const r = await api.get(`/tenders/export?${params}`, { responseType: 'blob' })
  const url = URL.createObjectURL(r.data as Blob)
  const a = document.createElement('a')
  a.href = url
  a.download = 'ausschreibungen.csv'
  document.body.appendChild(a)
  a.click()
  document.body.removeChild(a)
  URL.revokeObjectURL(url)
}
