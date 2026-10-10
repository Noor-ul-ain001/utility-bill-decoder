import type { Health } from '../api'
import { Icon } from './ui'

export type Tab = 'decode' | 'ask' | 'batch'

/** What the agent is doing right now; shown as a live status pill in the header. */
export type Activity = 'idle' | 'reading' | 'answering' | 'batch'

const ACTIVITY_LABEL: Record<Exclude<Activity, 'idle'>, string> = {
  reading: 'Reading bill…',
  answering: 'Answering…',
  batch: 'Running batch…',
}

const TABS: { id: Tab; label: string }[] = [
  { id: 'decode', label: 'Overview' },
  { id: 'ask', label: 'Ask' },
  { id: 'batch', label: 'Batch run' },
]

interface Props {
  health: Health | null
  healthError: boolean
  tab: Tab
  onTab: (tab: Tab) => void
  askEnabled: boolean
  activity: Activity
}

/** Top bar: brand, centred pill tabs, model + API-key status from /api/health. */
export function Header({ health, healthError, tab, onTab, askEnabled, activity }: Props) {
  // Status priority: unreachable backend > missing key > current work > ready.
  let status: { text: string; tone: 'ok' | 'busy' | 'bad' }
  if (healthError) status = { text: 'Agent offline', tone: 'bad' }
  else if (health && !health.api_key_set) status = { text: 'Setup needed', tone: 'bad' }
  else if (activity !== 'idle') status = { text: ACTIVITY_LABEL[activity], tone: 'busy' }
  else if (!health) status = { text: 'Connecting…', tone: 'busy' }
  else status = { text: 'Agent ready', tone: 'ok' }

  return (
    <header className="flex flex-wrap items-center justify-between gap-x-4 gap-y-3">
      <div className="flex min-w-0 flex-1 items-center gap-2.5 sm:gap-3 md:flex-none">
        <span className="grid h-9 w-9 shrink-0 place-items-center rounded-full bg-lime text-forest sm:h-11 sm:w-11">
          <Icon name="bolt" className="h-4 w-4 sm:h-5 sm:w-5" />
        </span>
        <div className="min-w-0">
          <h1 className="text-lg font-medium leading-tight xs:text-xl sm:text-2xl">Utility Bill Decoder</h1>
          <p className="hidden text-xs text-muted xs:block">K-Electric · LESCO · IESCO bills, explained</p>
        </div>
      </div>

      <nav
        className="no-scrollbar order-3 -mx-1 flex w-full gap-1 overflow-x-auto px-1 md:order-none md:mx-0 md:w-auto md:justify-center md:px-0"
        aria-label="Views"
      >
        {TABS.map((t) => {
          const disabled = t.id === 'ask' && !askEnabled
          return (
            <button
              key={t.id}
              disabled={disabled}
              onClick={() => onTab(t.id)}
              title={disabled ? 'Decode a bill first' : undefined}
              aria-current={tab === t.id ? 'page' : undefined}
              className={`flex-1 whitespace-nowrap rounded-full px-2.5 py-2 text-xs font-medium xs:px-3 xs:text-sm transition disabled:opacity-40 md:flex-none md:px-5 ${
                tab === t.id ? 'bg-lime text-forest' : 'bg-card/60 text-muted hover:text-ink md:bg-transparent'
              }`}
            >
              {t.label}
            </button>
          )
        })}
      </nav>

      <div
        role="status"
        aria-live="polite"
        title={health ? `Model: ${health.model}` : undefined}
        className={`inline-flex items-center gap-2 rounded-full px-3 py-2 text-xs font-semibold transition-colors ${
          status.tone === 'busy' ? 'bg-forest text-lime' : status.tone === 'bad' ? 'bg-down-soft text-down' : 'bg-card'
        }`}
      >
        <span className="relative flex h-2.5 w-2.5 shrink-0">
          {status.tone !== 'bad' && (
            <span
              className={`absolute inline-flex h-full w-full animate-ping rounded-full opacity-60 ${
                status.tone === 'busy' ? 'bg-lime' : 'bg-up [animation-duration:2.5s]'
              }`}
            />
          )}
          <span
            className={`relative inline-flex h-2.5 w-2.5 rounded-full ${
              status.tone === 'busy' ? 'bg-lime' : status.tone === 'bad' ? 'bg-down' : 'bg-up'
            }`}
          />
        </span>
        <span className="hidden xs:inline">{status.text}</span>
      </div>
    </header>
  )
}
