import axios from 'axios'
import type {
  TenderPage, TenderDetail, SearchProfile, Notification,
  Source, CrawlLog, AdminStats, KomunenSource, TenderFilters
} from '../types'

const BASE = import.meta.env.VITE_API_URL || '/api'

export const api = axios.create({ baseURL: BASE })

// Auth interceptor
api.interceptors.request.use((config) => {
  const token = localStorage.getItem('vergabe_token')
  if (token) config.headers.Authorization = `Bearer ${token}`
  return config
})

api.interceptors.response.use(
  (r) => r,
  (err) => {
    if (err.response?.status === 401) {
      localStorage.removeItem('vergabe_token')
      window.location.href = '/login'
    }
    return Promise.reject(err)
  }
)

export async function login(password: string) {
  const r = await api.post('/auth/token', { password })
  return r.data as { access_token: string; token_type: string }
}

// Tenders
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

// Search profiles
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

// Notifications
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

// Admin
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

export async function fetchKomunenQueue() {
  const r = await api.get('/admin/komunen/queue')
  return r.data as KomunenSource[]
}

export async function updateKomunen(id: string, status: string) {
  await api.patch(`/admin/komunen/${id}`, null, { params: { status } })
}

export function exportUrl(filters: TenderFilters) {
  const params = new URLSearchParams()
  if (filters.q) params.set('q', filters.q)
  if (filters.status) params.set('status', filters.status)
  if (filters.it_category) params.set('it_category', filters.it_category)
  return `${BASE}/tenders/export?${params}`
}

// Komunen manual add + sync triggers
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

// Summary
export async function fetchSummaryStatus(tenderId: string) {
  const r = await api.get(`/tenders/${tenderId}/summary`)
  return r.data as import('../types').SummaryStatus
}

export async function generateSummary(tenderId: string) {
  const r = await api.post(`/tenders/${tenderId}/summary`)
  return r.data as import('../types').TenderSummary
}

export async function deleteSummary(tenderId: string) {
  await api.delete(`/tenders/${tenderId}/summary`)
}
