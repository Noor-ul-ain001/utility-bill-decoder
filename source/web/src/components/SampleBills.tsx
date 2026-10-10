import { useEffect, useState } from 'react'
import { api, type Sample } from '../api'
import { CardHeader, Icon, Spinner } from './ui'

interface Props {
  busy: boolean
  selected: string | null
  onExtract: (name: string) => void
  /** "gallery" = thumbnail grid for the home page, "list" = compact list beside results. */
  variant?: 'gallery' | 'list'
}

const PROVIDER_LABEL: Record<string, string> = { KESC: 'K-Electric', LESCO: 'LESCO', IESCO: 'IESCO' }

function describe(sample: Sample) {
  const stem = sample.name.replace(/\.[^.]+$/, '')
  const prefix = stem.split('_')[0]
  return { stem, provider: PROVIDER_LABEL[prefix] ?? prefix }
}

/** Sample bills from train/bills and test/bills. */
export function SampleBills({ busy, selected, onExtract, variant = 'list' }: Props) {
  const [samples, setSamples] = useState<Sample[] | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    api.samples().then(setSamples, (e: Error) => setError(e.message))
  }, [])

  const header = (
    <CardHeader
      icon="receipt"
      title="Sample bills"
      aside={samples && <span className="pill">{samples.length} available</span>}
    />
  )

  const status = (
    <>
      {error && <p className="text-sm font-medium text-down">{error}</p>}
      {!samples && !error && (
        <p className="flex items-center gap-2 text-sm text-muted">
          <Spinner /> Loading samples…
        </p>
      )}
      {samples?.length === 0 && <p className="text-sm text-muted">No sample bills found on the server.</p>}
    </>
  )

  if (variant === 'gallery') {
    return (
      <div id="samples" className="card scroll-mt-6">
        {header}
        {status}
        <ul className="grid grid-cols-1 gap-3 xs:grid-cols-2 sm:grid-cols-3 lg:grid-cols-5">
          {samples?.map((s) => {
            const { stem, provider } = describe(s)
            const active = selected === s.name
            return (
              <li key={`${s.dataset}-${s.name}`}>
                <button
                  disabled={busy}
                  onClick={() => onExtract(s.name)}
                  className={`group w-full rounded-[22px] p-2 text-left transition hover:-translate-y-0.5 hover:bg-shell disabled:hover:translate-y-0 ${
                    active ? 'bg-lime-pale ring-2 ring-lime' : ''
                  }`}
                >
                  <div className="relative aspect-[16/10] overflow-hidden rounded-2xl border border-line bg-shell xs:aspect-[4/5]">
                    <img
                      src={api.sampleUrl(s.name)}
                      alt={`${stem} bill preview`}
                      loading="lazy"
                      className="h-full w-full object-cover object-top transition duration-300 group-hover:scale-105"
                    />
                    <span className="absolute left-2 top-2 rounded-full bg-white/90 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide">
                      {s.dataset === 'train' ? 'Training' : 'Test'}
                    </span>
                    <span
                      className={`absolute bottom-2 right-2 grid h-9 w-9 place-items-center rounded-full bg-lime text-forest shadow transition ${
                        busy && active ? '' : 'group-hover:rotate-45'
                      }`}
                    >
                      {busy && active ? <Spinner className="h-4 w-4" /> : <Icon name="arrow" className="h-4 w-4" />}
                    </span>
                  </div>
                  <p className="mt-2 px-1 text-sm font-semibold">{stem}</p>
                  <p className="px-1 text-xs text-muted">{provider}</p>
                </button>
              </li>
            )
          })}
        </ul>
      </div>
    )
  }

  return (
    <div className="card flex h-full flex-col">
      {header}
      {status}
      <ul className="-mx-2 flex max-h-[26rem] flex-col overflow-y-auto">
        {samples?.map((s) => {
          const { stem, provider } = describe(s)
          const active = selected === s.name
          return (
            <li key={`${s.dataset}-${s.name}`} className="border-b border-line last:border-b-0">
              <button
                disabled={busy}
                onClick={() => onExtract(s.name)}
                className={`my-1 flex w-full items-center gap-3 rounded-2xl px-2 py-2.5 text-left transition ${
                  active ? 'bg-lime-pale ring-1 ring-lime' : 'hover:bg-shell'
                }`}
              >
                <img
                  src={api.sampleUrl(s.name)}
                  alt=""
                  loading="lazy"
                  className="h-11 w-11 rounded-full border border-line bg-white object-cover object-top"
                />
                <span className="min-w-0 flex-1">
                  <span className="block truncate text-sm font-semibold">{stem}</span>
                  <span className="text-xs text-muted">
                    {provider} · {s.dataset === 'train' ? 'Training' : 'Test'} bill
                  </span>
                </span>
                {busy && active ? (
                  <Spinner className="h-5 w-5 text-forest" />
                ) : (
                  <span className="grid h-8 w-8 place-items-center rounded-full bg-lime text-forest">
                    <Icon name="arrow" className="h-4 w-4" />
                  </span>
                )}
              </button>
            </li>
          )
        })}
      </ul>
    </div>
  )
}
