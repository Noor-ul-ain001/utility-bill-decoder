import { useEffect, useState } from 'react'
import type { ExtractResponse, LabeledLine } from '../api'
import { formatDate, formatNumber, formatPkr } from '../format'
import { ChargesTable } from './ChargesTable'
import { UsageInsights } from './UsageInsights'
import { ValidationList } from './ValidationList'
import { CardHeader, Icon, Row } from './ui'

/** Use the labelled lines when the backend sent them, else fall back to Level 1 entries. */
function linesOrFallback(labeled: LabeledLine[], plain: { type: string; amount: number }[]): LabeledLine[] {
  return labeled.length > 0 ? labeled : plain.map((p) => ({ label: '', ...p }))
}

/** Donut of charges vs taxes around the current bill (like the reference "Spending" card). */
function BillSplit({ result }: { result: ExtractResponse }) {
  const l1 = result.level1
  const charges = l1.total_charges ?? l1.charges.reduce((s, c) => s + c.amount, 0)
  const taxes = l1.total_taxes ?? l1.taxes.reduce((s, t) => s + t.amount, 0)
  const whole = Math.max(charges, 0) + Math.max(taxes, 0)
  const taxShare = whole > 0 ? Math.max(taxes, 0) / whole : 0

  const r = 54
  const circumference = 2 * Math.PI * r
  const gap = 6
  const taxLen = Math.max(circumference * taxShare - gap, 0)
  const chargeLen = Math.max(circumference * (1 - taxShare) - gap, 0)

  return (
    <div className="card flex flex-col">
      <CardHeader icon="pie" title="Where it goes" aside={<span className="pill">{formatDate(l1.bill_month)}</span>} />
      <div className="relative mx-auto my-2 h-36 w-36 xs:h-44 xs:w-44">
        <svg viewBox="0 0 128 128" className="h-full w-full -rotate-90">
          <circle cx="64" cy="64" r={r} fill="none" stroke="#ececea" strokeWidth="12" />
          {whole > 0 && (
            <>
              <circle
                cx="64" cy="64" r={r} fill="none" stroke="#b7ec7c" strokeWidth="12" strokeLinecap="round"
                strokeDasharray={`${chargeLen} ${circumference}`}
              />
              <circle
                cx="64" cy="64" r={r} fill="none" stroke="#1f3d17" strokeWidth="12" strokeLinecap="round"
                strokeDasharray={`${taxLen} ${circumference}`}
                strokeDashoffset={-(circumference * (1 - taxShare))}
              />
            </>
          )}
        </svg>
        <div className="absolute inset-0 flex flex-col items-center justify-center text-center">
          <span className="text-xs text-muted">Current bill · PKR</span>
          <span className="amount text-2xl xs:text-3xl">
            {l1.current_bill !== null ? Math.round(l1.current_bill).toLocaleString('en-PK') : '—'}
          </span>
          {whole > 0 && <span className="text-xs font-semibold text-down">{(taxShare * 100).toFixed(1)}% tax</span>}
        </div>
      </div>
      <div className="mt-auto grid grid-cols-1 gap-x-4 gap-y-2 pt-4 text-sm sm:grid-cols-2">
        <span className="flex items-center gap-2">
          <span className="h-2.5 w-2.5 rounded-full bg-lime" /> Charges <b className="ml-auto tabular-nums">{formatPkr(charges)}</b>
        </span>
        <span className="flex items-center gap-2">
          <span className="h-2.5 w-2.5 rounded-full bg-forest" /> Taxes <b className="ml-auto tabular-nums">{formatPkr(taxes)}</b>
        </span>
        <span className="flex items-center gap-2 text-muted">
          <span className="h-2.5 w-2.5 rounded-full bg-line" /> Arrears <span className="ml-auto tabular-nums">{formatPkr(l1.arrears)}</span>
        </span>
        <span className="flex items-center gap-2 text-muted">
          <span className="h-2.5 w-2.5 rounded-full bg-line" /> Late total{' '}
          <span className="ml-auto tabular-nums">{formatPkr(l1.payable_after_due_date)}</span>
        </span>
      </div>
    </div>
  )
}

function Readings({ result }: { result: ExtractResponse }) {
  const l1 = result.level1
  return (
    <div className="card">
      <CardHeader icon="meter" title="Readings" aside={<span className="pill">{formatNumber(l1.units_consumed)} units</span>} />
      <Row label="Previous reading" value={formatNumber(l1.previous_reading)} />
      <Row label="Current reading" value={formatNumber(l1.current_reading)} />
      <Row label="Units consumed" value={formatNumber(l1.units_consumed)} />
      <Row label="Sanctioned load" value={formatNumber(l1.sanctioned_load_kw, ' kW')} />
      <Row label="Reading date" value={formatDate(l1.reading_date)} />
      <Row label="Issue date" value={formatDate(l1.issue_date)} />
      <Row label="Due date" value={formatDate(l1.due_date)} />
    </div>
  )
}

function RawJson({ data }: { data: unknown }) {
  const [open, setOpen] = useState(false)
  return (
    <div className="card">
      <button onClick={() => setOpen(!open)} className="flex w-full items-center justify-between" aria-expanded={open}>
        <span className="flex items-center gap-3">
          <span className="icon-chip">
            <Icon name="code" className="h-4.5 w-4.5" />
          </span>
          <span className="text-lg font-semibold">Raw Level 1 JSON</span>
        </span>
        <span className={`icon-chip transition ${open ? 'rotate-90' : ''}`}>
          <Icon name="chevron" className="h-4 w-4" />
        </span>
      </button>
      {open && (
        <pre className="mt-5 max-h-96 overflow-auto rounded-2xl bg-shell p-4 font-mono text-xs leading-relaxed">
          {JSON.stringify(data, null, 2)}
        </pre>
      )}
    </div>
  )
}

/** Bill image card shown to the left of the results; click to view it full size. */
export function BillImage({ imageUrl }: { imageUrl: string | null }) {
  const [open, setOpen] = useState(false)

  useEffect(() => {
    if (!open) return
    const onKey = (e: KeyboardEvent) => e.key === 'Escape' && setOpen(false)
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [open])

  if (!imageUrl) {
    return (
      <div className="card">
        <p className="text-sm text-muted">Image preview unavailable.</p>
      </div>
    )
  }
  return (
    <>
      <button
        onClick={() => setOpen(true)}
        className="card group relative block w-full overflow-hidden p-3 text-left"
        aria-label="View the bill full size"
      >
        <img src={imageUrl} alt="Bill being decoded" className="w-full rounded-[20px] object-contain" />
        <span className="absolute bottom-6 right-6 inline-flex items-center gap-1.5 rounded-full bg-forest px-3.5 py-2 text-xs font-semibold text-lime opacity-90 shadow transition group-hover:opacity-100">
          <Icon name="image" className="h-3.5 w-3.5" /> View full size
        </span>
      </button>
      {open && (
        <div
          role="dialog"
          aria-modal="true"
          aria-label="Bill image"
          onClick={() => setOpen(false)}
          className="fixed inset-0 z-50 flex cursor-zoom-out items-start justify-center overflow-auto bg-ink/70 p-4 backdrop-blur-sm sm:p-10"
        >
          <img src={imageUrl} alt="Bill, full size" className="max-w-full rounded-2xl bg-white shadow-2xl" />
          <button
            onClick={() => setOpen(false)}
            className="fixed right-5 top-5 grid h-11 w-11 place-items-center rounded-full bg-card text-ink shadow"
            aria-label="Close"
          >
            <Icon name="close" className="h-4 w-4" />
          </button>
        </div>
      )}
    </>
  )
}

/** Extracted details: split, readings, usage insights, charges, taxes, checks and raw JSON. */
export function ResultsView({ result }: { result: ExtractResponse }) {
  const l1 = result.level1
  return (
    <div className="rise grid gap-4 md:grid-cols-2">
      <BillSplit result={result} />
      <Readings result={result} />
      <div className="md:col-span-2">
        <UsageInsights usage={result.usage} />
      </div>
      <ChargesTable
        title="Charges"
        icon="bolt"
        lines={linesOrFallback(result.charge_lines, l1.charges)}
        total={l1.total_charges}
        emptyText="No individual charge lines are printed on this bill."
      />
      <ChargesTable
        title="Taxes & duties"
        icon="receipt"
        lines={linesOrFallback(result.tax_lines, l1.taxes)}
        total={l1.total_taxes}
        emptyText="This bill prints only a combined tax amount (shown as the total)."
      />
      <div className="md:col-span-2">
        <ValidationList checks={result.validation} />
      </div>
      <div className="md:col-span-2">
        <RawJson data={l1} />
      </div>
    </div>
  )
}
