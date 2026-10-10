/**
 * Typed client for the FastAPI backend (source/api.py).
 * The frontend never talks to an LLM directly; every model call happens in Python.
 */

export const API_BASE: string = (import.meta.env.VITE_API_URL as string | undefined) ?? 'http://localhost:8000'

export type Provider = 'KE' | 'LESCO' | 'IESCO'
export type ChargeType =
  | 'energy'
  | 'fixed'
  | 'fpa'
  | 'quarterly_adjustment'
  | 'surcharge'
  | 'meter_rent'
  | 'subsidy'
  | 'other'
export type TaxType = 'gst' | 'electricity_duty' | 'income_tax' | 'municipal_tax' | 'other_tax'

/** Level 1 JSON exactly as defined in GUIDE section 5.1. */
export interface Level1 {
  provider: Provider | null
  tariff: string | null
  sanctioned_load_kw: number | null
  bill_month: string | null
  reading_date: string | null
  issue_date: string | null
  due_date: string | null
  previous_reading: number | null
  current_reading: number | null
  units_consumed: number | null
  charges: { type: ChargeType; amount: number }[]
  total_charges: number | null
  taxes: { type: TaxType; amount: number }[]
  total_taxes: number | null
  current_bill: number | null
  arrears: number | null
  payable_within_due_date: number | null
  payable_after_due_date: number | null
}

/** A charge or tax line with the label printed on the bill (for display only). */
export interface LabeledLine {
  label: string
  type: string
  amount: number
}

export interface HistoryPoint {
  month: string
  units: number | null
  bill_amount: number | null
  payment: number | null
}

export interface ValidationCheck {
  check: string
  passed: boolean
  detail: string
}

export interface MonthUnits {
  month: string
  units: number
}

export interface Change {
  from: number
  to: number
  difference: number
  percent_change: number | null
}

/** Usage statistics computed in Python (calculator.usage_insights). */
export interface UsageInsights {
  points: (MonthUnits & { is_current: boolean })[]
  current: MonthUnits | null
  previous: MonthUnits | null
  change_vs_previous: Change | null
  average_units: number | null
  average_months: number
  highest: MonthUnits | null
  lowest: MonthUnits | null
  change_vs_average: Change | null
}

export interface ExtractResponse {
  bill_key: string
  level1: Level1
  validation: ValidationCheck[]
  charge_lines: LabeledLine[]
  tax_lines: LabeledLine[]
  history: HistoryPoint[]
  usage: UsageInsights
}

export interface Health {
  model: string
  provider: string
  api_key_set: boolean
}

export interface Sample {
  name: string
  dataset: 'train' | 'test'
  url: string
}

export interface BatchBill {
  bill_id: string
  ok: boolean
  error: string | null
  from_cache: boolean
  checks_passed: number
  checks_total: number
  provider: Provider | null
  payable_within_due_date: number | null
}

export interface BatchResponse {
  processed: number
  warnings: number
  failures: number
  failed_bills: string[]
  bills: BatchBill[]
}

/** A batch preset (test or training data) and whether its folders exist. */
export interface Dataset {
  name: 'test' | 'train'
  bills_dir: string
  csv_dir: string
  bill_count: number
  available: boolean
}

/** Error carrying the backend's readable message. */
export class ApiError extends Error {
  readonly status: number
  constructor(status: number, message: string) {
    super(message)
    this.status = status
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response
  try {
    response = await fetch(`${API_BASE}${path}`, init)
  } catch {
    throw new ApiError(0, `Cannot reach the backend at ${API_BASE}. Is it running?`)
  }
  if (!response.ok) {
    let message = `Request failed (${response.status})`
    try {
      const body = (await response.json()) as { detail?: unknown }
      if (typeof body.detail === 'string') message = body.detail
    } catch {
      /* keep the generic message */
    }
    throw new ApiError(response.status, message)
  }
  return (await response.json()) as T
}

const json = (body: unknown): RequestInit => ({
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify(body),
})

export const api = {
  health: () => request<Health>('/api/health'),
  samples: () => request<Sample[]>('/api/samples'),
  datasets: () => request<Dataset[]>('/api/datasets'),
  sampleUrl: (name: string) => `${API_BASE}/api/samples/${encodeURIComponent(name)}`,
  extract: (file: File) => {
    const form = new FormData()
    form.append('file', file)
    return request<ExtractResponse>('/api/extract', { method: 'POST', body: form })
  },
  extractSample: (name: string) => request<ExtractResponse>('/api/extract-sample', json({ name })),
  ask: (bill_key: string, question: string) => request<{ answer: string }>('/api/ask', json({ bill_key, question })),
  batch: (bills_dir: string, csv_dir: string) => request<BatchResponse>('/api/batch', json({ bills_dir, csv_dir })),
  downloadUrl: (level: 'level1' | 'level2') => `${API_BASE}/api/download/${level}`,
}
