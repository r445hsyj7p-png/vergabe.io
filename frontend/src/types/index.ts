export interface TenderSource {
  source_id: string
  external_url: string | null
  platform_name: string | null
  scraped_at: string
}

export interface Lot {
  id: string
  lot_number: string | null
  title: string | null
  description: string | null
  value_min: number | null
  value_max: number | null
  cpv_codes: string[] | null
}

export interface Tender {
  id: string
  canonical_id: string
  title: string
  contracting_authority: string | null
  deadline: string | null
  publication_date: string | null
  value_min: number | null
  value_max: number | null
  currency: string
  cpv_codes: string[] | null
  it_category: string | null
  region: string | null
  country: string
  procedure_type: string | null
  tender_status: string
  source_url: string | null
  tag_status: 'interest' | 'ignore' | null
  sources: TenderSource[]
}

export interface TenderDetail extends Tender {
  description: string | null
  fulfillment_location: string | null
  authority_address: string | null
  authority_email: string | null
  authority_phone: string | null
  lots: Lot[]
  created_at: string
  updated_at: string
}

export interface TenderPage {
  items: Tender[]
  total: number
  page: number
  page_size: number
  has_more: boolean
}

export interface SearchProfile {
  id: string
  name: string
  keywords: string[] | null
  cpv_codes: string[] | null
  regions: string[] | null
  it_categories: string[] | null
  min_value: number | null
  deadline_days: number | null
  email: string | null
  is_active: boolean
  created_at: string
  updated_at: string
}

export interface Notification {
  id: string
  profile_id: string
  tender_id: string
  is_read: boolean
  notification_type: string
  triggered_at: string
  tender: Tender | null
  profile_name: string | null
}

export interface Source {
  id: string
  name: string
  slug: string
  source_type: string
  base_url: string | null
  interval_hours: number
  is_active: boolean
  status: 'ok' | 'warn' | 'error'
  last_run_at: string | null
  last_run_entries: number
}

export interface CrawlLog {
  id: string
  source_id: string | null
  level: 'info' | 'warn' | 'error'
  message: string
  entries_processed: number
  entries_new: number
  duration_ms: number | null
  created_at: string
}

export interface AdminStats {
  total_tenders: number
  tenders_today: number
  active_sources: number
  komunen_sources: number
  last_crawl_at: string | null
}

export interface KomunenSource {
  id: string
  ags: string | null
  name: string
  bundesland: string | null
  einwohner: number | null
  main_url: string | null
  vergabe_url: string | null
  discovery_confidence: number | null
  status: string
  last_verified_at: string | null
  last_scraped_at: string | null
}

export interface TenderFilters {
  q?: string
  cpv?: string
  region?: string
  auftraggeber?: string
  it_category?: string
  status?: string
  min_value?: number
  profile_id?: string
  tag_status?: string
  page?: number
  page_size?: number
}

export interface TenderSummary {
  tender_id: string
  summary_text: string
  provider: string
  model: string | null
  cost_cents: number
  created_at: string
}

export interface SummaryStatus {
  exists: boolean
  summary: TenderSummary | null
  provider_configured: string
}
