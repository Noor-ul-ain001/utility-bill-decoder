/** Display helpers shared by the components. */

const pkr = new Intl.NumberFormat('en-PK', { minimumFractionDigits: 0, maximumFractionDigits: 2 })

/** "PKR 3,430.24", or an em dash for missing values. */
export function formatPkr(value: number | null | undefined): string {
  if (value === null || value === undefined) return '—'
  return `PKR ${pkr.format(value)}`
}

export function formatNumber(value: number | null | undefined, suffix = ''): string {
  if (value === null || value === undefined) return '—'
  return `${pkr.format(value)}${suffix}`
}

const MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']

/** "2026-04" → "Apr 2026", "2026-04-21" → "21 Apr 2026". */
export function formatDate(value: string | null | undefined): string {
  if (!value) return '—'
  const [y, m, d] = value.split('-')
  const month = MONTHS[Number(m) - 1]
  if (!month) return value
  return d ? `${Number(d)} ${month} ${y}` : `${month} ${y}`
}

/** "quarterly_adjustment" → "Quarterly adjustment". */
export function humanizeType(type: string): string {
  const special: Record<string, string> = { fpa: 'FPA', gst: 'GST' }
  if (special[type]) return special[type]
  const text = type.replace(/_/g, ' ')
  return text.charAt(0).toUpperCase() + text.slice(1)
}
