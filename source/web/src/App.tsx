import { useCallback, useEffect, useState } from 'react'
import { api, type ExtractResponse, type Health } from './api'
import { formatDate, formatPkr } from './format'
import { AskPanel } from './components/AskPanel'
import { BalanceCard } from './components/BalanceCard'
import { BatchPanel } from './components/BatchPanel'
import { Header, type Activity, type Tab } from './components/Header'
import { HomeHero } from './components/HomeHero'
import { BillImage, ResultsView } from './components/ResultsView'
import { SampleBills } from './components/SampleBills'
import { UploadPanel } from './components/UploadPanel'
import { CardHeader, ErrorBanner, Icon, Spinner, type IconName } from './components/ui'

const STEPS: { icon: IconName; title: string; text: string }[] = [
  { icon: 'image', title: 'Read', text: 'Every printed field is transcribed, including tilted photos and Urdu-labelled bills.' },
  { icon: 'shield', title: 'Check', text: 'Readings, subtotals and payable amounts are cross-checked; doubtful areas are re-read.' },
  { icon: 'chat', title: 'Explain', text: 'Ask anything. Numbers are calculated in code and explained in plain English.' },
]

export default function App() {
  const [health, setHealth] = useState<Health | null>(null)
  const [healthError, setHealthError] = useState(false)
  const [tab, setTab] = useState<Tab>('decode')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [result, setResult] = useState<ExtractResponse | null>(null)
  const [imageUrl, setImageUrl] = useState<string | null>(null)
  const [selectedSample, setSelectedSample] = useState<string | null>(null)
  const [answering, setAnswering] = useState(false)
  const [batchRunning, setBatchRunning] = useState(false)
  const onAnswering = useCallback((b: boolean) => setAnswering(b), [])
  const onBatchRunning = useCallback((b: boolean) => setBatchRunning(b), [])
  const activity: Activity = busy ? 'reading' : answering ? 'answering' : batchRunning ? 'batch' : 'idle'

  useEffect(() => {
    api.health().then(setHealth, () => setHealthError(true))
  }, [])

  /** Shared wrapper for both extraction paths: loading state, errors, results. */
  async function runExtraction(task: () => Promise<ExtractResponse>, image: string, sample: string | null) {
    setBusy(true)
    setError(null)
    setSelectedSample(sample)
    try {
      const response = await task()
      setResult(response)
      setImageUrl(image)
      window.scrollTo({ top: 0, behavior: 'smooth' })
    } catch (e) {
      setError((e as Error).message)
    } finally {
      setBusy(false)
    }
  }

  const extractSample = (name: string) => void runExtraction(() => api.extractSample(name), api.sampleUrl(name), name)

  return (
    <div className="min-h-screen p-0 xs:p-2 sm:p-6">
      <div className="mx-auto flex max-w-7xl flex-col gap-4 bg-shell p-3 xs:rounded-[28px] sm:gap-5 sm:rounded-[36px] sm:p-7">
        <Header health={health} healthError={healthError} tab={tab} onTab={setTab} askEnabled={result !== null} activity={activity} />

        {error && <ErrorBanner message={error} onClose={() => setError(null)} />}

        {/* Overview: choose a bill + extracted details */}
        <div className={tab === 'decode' ? 'flex flex-col gap-4' : 'hidden'}>
          <div className="grid gap-4 lg:grid-cols-[minmax(0,7fr)_minmax(0,5fr)]">
            {result ? (
              <BalanceCard key={result.bill_key} result={result} onAsk={() => setTab('ask')} />
            ) : (
              <HomeHero onBrowseSamples={() => document.getElementById('samples')?.scrollIntoView({ behavior: 'smooth' })} />
            )}
            <UploadPanel
              busy={busy}
              onExtract={(file) => void runExtraction(() => api.extract(file), URL.createObjectURL(file), null)}
            />
          </div>

          {busy && <LoadingState />}

          {result && !busy && (
            <div className="grid gap-4 lg:grid-cols-[minmax(0,4fr)_minmax(0,8fr)]">
              <div className="flex min-w-0 flex-col gap-4 lg:sticky lg:top-4 lg:self-start">
                <BillImage imageUrl={imageUrl} />
                <SampleBills busy={busy} selected={selectedSample} onExtract={extractSample} />
              </div>
              <ResultsView key={result.bill_key} result={result} />
            </div>
          )}

          {!result && !busy && (
            <>
              <SampleBills variant="gallery" busy={busy} selected={selectedSample} onExtract={extractSample} />
              <div className="grid gap-4 md:grid-cols-3">
                {STEPS.map((s, i) => (
                  <div key={s.title} className="card">
                    <CardHeader
                      icon={s.icon}
                      title={s.title}
                      aside={<span className="text-sm font-semibold text-muted">0{i + 1}</span>}
                    />
                    <p className="text-sm leading-relaxed text-muted">{s.text}</p>
                  </div>
                ))}
              </div>
            </>
          )}
        </div>

        {/* Ask: kept mounted so the Q&A history survives tab switches */}
        {result && (
          <div className={tab === 'ask' ? 'grid gap-4 lg:grid-cols-[minmax(0,4fr)_minmax(0,8fr)]' : 'hidden'}>
            <div className="flex min-w-0 flex-col gap-4">
              <div className="card">
                <p className="label">Payable within due date</p>
                <p className="amount text-3xl sm:text-4xl">{formatPkr(result.level1.payable_within_due_date)}</p>
                <p className="mt-1 text-sm text-muted">
                  {result.level1.provider ?? '—'} · {formatDate(result.level1.bill_month)}
                </p>
              </div>
              <div className="hidden lg:block">
                <BillImage imageUrl={imageUrl} />
              </div>
            </div>
            <AskPanel key={result.bill_key} billKey={result.bill_key} onBusyChange={onAnswering} />
          </div>
        )}

        <div className={tab === 'batch' ? '' : 'hidden'}>
          <BatchPanel onBusyChange={onBatchRunning} />
        </div>
      </div>
      <p className="px-4 py-4 text-center text-xs text-muted">Personal identifiers are never extracted or stored.</p>
    </div>
  )
}

/** Skeleton placeholders shown while a bill is being read. */
function LoadingState() {
  return (
    <div className="grid gap-4 lg:grid-cols-[minmax(0,4fr)_minmax(0,8fr)]" aria-busy="true" aria-live="polite">
      <div className="card flex flex-col gap-3">
        <div className="skeleton aspect-[3/4] w-full" />
      </div>
      <div className="flex min-w-0 flex-col gap-4">
        <div className="card flex items-center gap-3 text-sm font-medium">
          <Spinner className="h-5 w-5 shrink-0 text-forest" />
          <span>Reading the bill: transcribing fields, then cross-checking totals. Usually 10–30 seconds.</span>
        </div>
        <div className="grid gap-4 md:grid-cols-2">
          {[0, 1].map((i) => (
            <div key={i} className="card flex flex-col gap-3">
              <div className="flex items-center gap-3">
                <div className="skeleton h-10 w-10 rounded-full" />
                <div className="skeleton h-4 w-32" />
              </div>
              <div className="skeleton h-32 w-full" />
              <div className="skeleton h-4 w-3/4" />
            </div>
          ))}
        </div>
        <div className="card flex flex-col gap-3">
          <div className="flex items-center gap-2 text-sm text-muted">
            <Icon name="bars" className="h-4 w-4" /> Usage insights
          </div>
          <div className="skeleton h-48 w-full" />
        </div>
      </div>
    </div>
  )
}
