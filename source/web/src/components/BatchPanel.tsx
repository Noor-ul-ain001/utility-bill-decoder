import { useEffect, useState, type FormEvent } from 'react'
import { api, type BatchResponse, type Dataset } from '../api'
import { formatPkr } from '../format'
import { CardHeader, ErrorBanner, Icon, Spinner } from './ui'

const PRESET_LABEL: Record<Dataset['name'], string> = { test: 'Test data', train: 'Training data' }

/** "75" -> "1:15" */
function clock(seconds: number): string {
  return `${Math.floor(seconds / 60)}:${String(seconds % 60).padStart(2, '0')}`
}

/** Run the full CLI pipeline over a folder of bills and download both CSVs. */
export function BatchPanel({ onBusyChange }: { onBusyChange?: (busy: boolean) => void }) {
  const [datasets, setDatasets] = useState<Dataset[] | null>(null)
  const [billsDir, setBillsDir] = useState('test/bills')
  const [csvDir, setCsvDir] = useState('test/csv')
  const [busy, setBusy] = useState(false)
  const [elapsed, setElapsed] = useState(0)
  const [result, setResult] = useState<BatchResponse | null>(null)
  const [error, setError] = useState<string | null>(null)

  // Load presets and pre-select the first one whose folders exist.
  useEffect(() => {
    api.datasets().then(
      (list) => {
        setDatasets(list)
        const first = list.find((d) => d.available)
        if (first) {
          setBillsDir(first.bills_dir)
          setCsvDir(first.csv_dir)
        }
      },
      () => setDatasets([]),
    )
  }, [])

  useEffect(() => onBusyChange?.(busy), [busy, onBusyChange])

  // Elapsed-time counter while a batch is running.
  useEffect(() => {
    if (!busy) return
    setElapsed(0)
    const timer = setInterval(() => setElapsed((s) => s + 1), 1000)
    return () => clearInterval(timer)
  }, [busy])

  async function run(event: FormEvent) {
    event.preventDefault()
    setBusy(true)
    setError(null)
    setResult(null)
    try {
      setResult(await api.batch(billsDir, csvDir))
    } catch (e) {
      setError((e as Error).message)
    } finally {
      setBusy(false)
    }
  }

  const activePreset = datasets?.find((d) => d.bills_dir === billsDir && d.csv_dir === csvDir)

  return (
    <div className="flex flex-col gap-4">
      <div className="grid gap-4 lg:grid-cols-[minmax(0,3fr)_minmax(0,2fr)]">
        <div className="card">
          <CardHeader icon="folder" title="Batch run" aside={<span className="pill">CLI pipeline</span>} />

          <p className="mb-2 text-sm font-medium text-muted">Dataset</p>
          <div className="mb-5 grid grid-cols-1 gap-2 xs:grid-cols-2">
            {(datasets ?? []).map((d) => {
              const active = activePreset?.name === d.name
              return (
                <button
                  key={d.name}
                  type="button"
                  disabled={busy || !d.available}
                  onClick={() => {
                    setBillsDir(d.bills_dir)
                    setCsvDir(d.csv_dir)
                  }}
                  className={`flex min-w-0 items-center gap-3 rounded-2xl border px-3 py-3 text-left transition disabled:opacity-50 ${
                    active ? 'border-lime bg-lime-pale' : 'border-line hover:bg-shell'
                  }`}
                >
                  <span
                    className={`grid h-9 w-9 shrink-0 place-items-center rounded-full ${
                      active ? 'bg-lime text-forest' : 'bg-shell text-muted'
                    }`}
                  >
                    <Icon name={active ? 'check' : 'folder'} className="h-4 w-4" />
                  </span>
                  <span className="min-w-0">
                    <span className="block text-sm font-semibold">{PRESET_LABEL[d.name]}</span>
                    <span className="block text-xs text-muted">
                      {d.available ? `${d.bill_count} bills · ${d.bills_dir}` : 'Not available yet'}
                    </span>
                  </span>
                </button>
              )
            })}
            {datasets === null && (
              <p className="flex items-center gap-2 text-sm text-muted">
                <Spinner /> Looking for datasets…
              </p>
            )}
          </div>

          <form onSubmit={run} className="flex flex-col gap-4">
            <details className="group rounded-2xl bg-shell px-4 py-3">
              <summary className="flex list-none items-center justify-between text-sm font-medium">
                Custom folders
                <Icon name="chevron" className="h-4 w-4 transition group-open:rotate-90" />
              </summary>
              <div className="mt-3 grid gap-3 sm:grid-cols-2">
                <label className="flex min-w-0 flex-col gap-1.5 text-xs font-medium text-muted">
                  Bills folder
                  <input className="input bg-card text-ink" value={billsDir} onChange={(e) => setBillsDir(e.target.value)} disabled={busy} />
                </label>
                <label className="flex min-w-0 flex-col gap-1.5 text-xs font-medium text-muted">
                  CSV templates folder
                  <input className="input bg-card text-ink" value={csvDir} onChange={(e) => setCsvDir(e.target.value)} disabled={busy} />
                </label>
              </div>
            </details>

            <div className="flex flex-col gap-3 sm:flex-row sm:items-center">
              <button type="submit" className="btn-primary w-full sm:w-auto" disabled={busy || !billsDir || !csvDir}>
                {busy ? <Spinner /> : <Icon name="bolt" className="h-4 w-4" />}
                {busy ? `Running… ${clock(elapsed)}` : 'Run batch'}
              </button>
              <p className="text-xs text-muted">
                {busy
                  ? 'Reading bills and answering questions. Cached bills are instant; new ones take about a minute each on the free tier.'
                  : 'Writes output/level1.csv and output/level2.csv, exactly like the CLI.'}
              </p>
            </div>
          </form>

          {error && (
            <div className="mt-4">
              <ErrorBanner message={error} onClose={() => setError(null)} />
            </div>
          )}
        </div>

        <div className="flex flex-col justify-between gap-4 rounded-[22px] bg-lime p-4 text-forest sm:rounded-[28px] sm:p-6">
          <div>
            <p className="text-sm font-semibold">Last run</p>
            <p className="text-xs text-forest/70">{result ? `${billsDir} → output/` : 'No batch run yet'}</p>
          </div>
          <div className="grid grid-cols-1 gap-2 xs:grid-cols-3">
            <Stat label="Processed" value={result?.processed} />
            <Stat label="Warnings" value={result?.warnings} />
            <Stat label="Failures" value={result?.failures} />
          </div>
          <div className="grid grid-cols-1 gap-2 xs:grid-cols-2">
            {(['level1', 'level2'] as const).map((level) => (
              <a
                key={level}
                className={`btn-primary ${result ? '' : 'pointer-events-none opacity-50'}`}
                href={api.downloadUrl(level)}
                download
                aria-disabled={!result}
              >
                <Icon name="download" className="h-4 w-4" /> {level}.csv
              </a>
            ))}
          </div>
        </div>
      </div>

      {result && result.bills.length > 0 && (
        <div className="card rise">
          <CardHeader icon="receipt" title="Bills in this run" aside={<span className="pill">{result.bills.length} bills</span>} />
          <ul className="flex flex-col">
            {result.bills.map((b) => (
              <li key={b.bill_id} className="flex flex-wrap items-center gap-x-3 gap-y-1 border-b border-line py-3 last:border-b-0">
                <span
                  className={`grid h-9 w-9 shrink-0 place-items-center rounded-full ${
                    b.ok ? 'bg-lime text-forest' : 'border border-line text-down'
                  }`}
                >
                  <Icon name={b.ok ? 'check' : 'close'} className="h-4 w-4" />
                </span>
                <span className="min-w-0 flex-1">
                  <span className="block text-sm font-semibold">{b.bill_id}</span>
                  <span className={`block text-xs ${b.ok ? 'text-muted' : 'text-down'}`}>
                    {b.ok
                      ? `${b.provider ?? '—'} · ${b.checks_passed}/${b.checks_total} checks · ${b.from_cache ? 'cached' : 'read now'}`
                      : b.error}
                  </span>
                </span>
                <span className="text-sm font-semibold tabular-nums">{formatPkr(b.payable_within_due_date)}</span>
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  )
}

function Stat({ label, value }: { label: string; value: number | undefined }) {
  return (
    <div className="rounded-2xl bg-white/45 px-3 py-3">
      <p className="text-xs font-medium text-forest/70">{label}</p>
      <p className="amount text-3xl">{value ?? '—'}</p>
    </div>
  )
}
