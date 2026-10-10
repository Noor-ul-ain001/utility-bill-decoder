import { Icon, type IconName } from './ui'

const HIGHLIGHTS: { icon: IconName; value: string; label: string }[] = [
  { icon: 'receipt', value: '18', label: 'fields extracted' },
  { icon: 'shield', value: '6', label: 'consistency checks' },
  { icon: 'bars', value: '13', label: 'months of usage' },
]

/** Welcome card shown before any bill is decoded (takes the place of the balance card). */
export function HomeHero({ onBrowseSamples }: { onBrowseSamples: () => void }) {
  return (
    <div className="card flex h-full flex-col justify-between gap-6 sm:gap-8">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <span className="inline-flex items-center gap-2 rounded-full bg-shell px-3 py-1.5 text-xs font-semibold">
          <span className="h-2 w-2 rounded-full bg-up" /> AI bill reader
        </span>
        <div className="flex rounded-full bg-shell p-1 text-xs font-semibold text-muted xs:text-sm">
          {['KE', 'LESCO', 'IESCO'].map((p) => (
            <span key={p} className="whitespace-nowrap rounded-full px-2 py-1 xs:px-3.5">
              {p}
            </span>
          ))}
        </div>
      </div>

      <div>
        <h2 className="max-w-xl text-[1.7rem] font-light leading-[1.1] tracking-tight xs:text-4xl sm:text-5xl">
          Understand every line of your <span className="font-semibold">electricity bill</span>.
        </h2>
        <p className="mt-3 max-w-lg text-sm text-muted sm:mt-4 sm:text-base">
          Upload a K-Electric, LESCO or IESCO bill. Every charge and tax is extracted, the totals are cross-checked,
          and your questions are answered in plain English.
        </p>
      </div>

      <div className="flex flex-wrap items-end justify-between gap-4">
        <div className="grid w-full grid-cols-1 gap-2 xs:grid-cols-3 sm:w-auto sm:max-w-md sm:flex-1">
          {HIGHLIGHTS.map((h) => (
            <div key={h.label} className="rounded-2xl bg-shell px-3 py-3">
              <Icon name={h.icon} className="h-4 w-4 text-muted" />
              <p className="amount mt-2 text-2xl">{h.value}</p>
              <p className="text-xs text-muted">{h.label}</p>
            </div>
          ))}
        </div>
        <button
          onClick={onBrowseSamples}
          className="group flex w-full items-center justify-between gap-3 rounded-full bg-forest py-2 pl-5 pr-2 sm:w-auto text-sm font-semibold text-lime transition hover:bg-forest-dark"
        >
          Try a sample bill
          <span className="grid h-10 w-10 place-items-center rounded-full bg-lime text-forest transition group-hover:rotate-45">
            <Icon name="arrow" className="h-4 w-4" />
          </span>
        </button>
      </div>
    </div>
  )
}
