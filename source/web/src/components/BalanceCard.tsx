import { useState } from 'react'
import type { ExtractResponse } from '../api'
import { formatDate, formatNumber, formatPkr } from '../format'
import { Icon, type IconName } from './ui'

interface Props {
  result: ExtractResponse
  onAsk: () => void
}

const PROVIDERS = ['KE', 'LESCO', 'IESCO'] as const

function MiniTile({ icon, label, value, tone }: { icon: IconName; label: string; value: string; tone?: 'up' | 'down' }) {
  return (
    <div className="rounded-2xl bg-shell px-3.5 py-3">
      <p className="flex items-center gap-1.5 text-xs text-muted">
        <Icon name={icon} className="h-3.5 w-3.5" /> {label}
      </p>
      <p
        className={`mt-1 truncate text-base font-semibold tabular-nums ${
          tone === 'down' ? 'text-down' : tone === 'up' ? 'text-up' : ''
        }`}
        title={value}
      >
        {value}
      </p>
    </div>
  )
}

/** Headline card (like "Active Balance" in the reference): the amount payable within the due date. */
export function BalanceCard({ result, onAsk }: Props) {
  const [copied, setCopied] = useState(false)
  const l1 = result.level1

  async function copyJson() {
    try {
      await navigator.clipboard.writeText(JSON.stringify(l1))
      setCopied(true)
      setTimeout(() => setCopied(false), 1500)
    } catch {
      setCopied(false)
    }
  }

  const late =
    l1.payable_after_due_date != null && l1.payable_within_due_date != null
      ? l1.payable_after_due_date - l1.payable_within_due_date
      : null
  const passed = result.validation.filter((c) => c.passed).length

  // Explain why the payable amount can differ from the current bill: arrears and, on
  // LESCO / IESCO bills, the fuel adjustment (FPA) printed outside the current bill.
  const fpa = l1.charges.filter((c) => c.type === 'fpa').reduce((s, c) => s + c.amount, 0)
  const arrears = l1.arrears ?? 0
  let breakdown: string | null = null
  if (l1.current_bill !== null && l1.payable_within_due_date !== null) {
    const near = (a: number, b: number) => Math.abs(a - b) <= 1
    const base = l1.current_bill + arrears
    const parts = [`current bill ${formatPkr(l1.current_bill)}`]
    if (arrears) parts.push(`arrears ${formatPkr(arrears)}`)
    if (fpa && !near(base, l1.payable_within_due_date) && near(base + fpa, l1.payable_within_due_date)) {
      parts.push(`fuel adjustment (FPA) ${formatPkr(fpa)} billed separately`)
    }
    if (parts.length > 1) breakdown = `= ${parts.join(' + ')}`
  }

  return (
    <div className="card rise flex h-full flex-col justify-between gap-6">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div className="no-scrollbar flex max-w-full overflow-x-auto rounded-full bg-shell p-1" aria-label={`Provider: ${l1.provider ?? 'unknown'}`}>
          {PROVIDERS.map((p) => (
            <span
              key={p}
              className={`whitespace-nowrap rounded-full px-2 py-1.5 text-xs font-semibold xs:px-4 xs:text-sm ${
                l1.provider === p ? 'bg-card text-ink shadow-sm' : 'text-muted'
              }`}
            >
              {p}
            </span>
          ))}
        </div>
        <div className="sm:text-right">
          <p className="text-xs text-muted">Bill month · Tariff</p>
          <p className="text-base font-semibold sm:text-lg">
            {formatDate(l1.bill_month)} · {l1.tariff ?? '—'}
          </p>
        </div>
      </div>

      <div>
        <p className="label flex flex-wrap items-center gap-2">
          Payable within due date
          <span className={`pill ${passed === result.validation.length ? 'text-up' : 'text-warn'}`}>
            <Icon name="shield" className="h-3 w-3" /> {passed}/{result.validation.length} checks
          </span>
        </p>
        <p className="amount mt-1 text-3xl xs:text-4xl sm:text-6xl">{formatPkr(l1.payable_within_due_date)}</p>
        {breakdown && <p className="mt-1 text-sm font-medium text-ink/70">{breakdown}</p>}
        <p className="mt-2 text-sm text-muted">
          Due {formatDate(l1.due_date)}
          {late !== null && late > 0 && (
            <>
              {' · '}
              <span className="font-semibold text-down">+{formatPkr(late)} if paid late</span>
            </>
          )}
        </p>
      </div>

      <div className="grid grid-cols-1 gap-2 xs:grid-cols-2 sm:grid-cols-4">
        <MiniTile icon="bolt" label="Units used" value={formatNumber(l1.units_consumed)} />
        <MiniTile icon="receipt" label="Current bill" value={formatPkr(l1.current_bill)} />
        <MiniTile
          icon="history"
          label="Arrears"
          value={formatPkr(l1.arrears)}
          tone={l1.arrears !== null && l1.arrears < 0 ? 'up' : undefined}
        />
        <MiniTile icon="meter" label="After due date" value={formatPkr(l1.payable_after_due_date)} tone="down" />
      </div>

      <div className="flex items-center justify-between gap-4">
        <div className="flex w-full flex-col gap-2 xs:w-auto xs:flex-row xs:flex-wrap">
          <button className="btn-primary" onClick={onAsk}>
            <Icon name="chat" className="h-4 w-4" /> Ask about this bill
          </button>
          <button className="btn-outline" onClick={copyJson}>
            <Icon name={copied ? 'check' : 'copy'} className="h-4 w-4" /> {copied ? 'Copied' : 'Copy JSON'}
          </button>
        </div>
        <button
          onClick={onAsk}
          aria-label="Ask about this bill"
          className="hidden h-14 w-14 shrink-0 place-items-center rounded-full bg-lime sm:grid text-forest transition hover:rotate-45"
        >
          <Icon name="arrow" className="h-6 w-6" />
        </button>
      </div>
    </div>
  )
}
