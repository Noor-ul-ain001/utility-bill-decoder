import type { Change, MonthUnits, UsageInsights as Usage } from '../api'
import { formatDate, formatNumber } from '../format'
import { CardHeader, Icon } from './ui'

/** Axis label: three-letter month, plus the year on the first bar and every January. */
function axisLabel(month: string, index: number): { name: string; year: string | null } {
  const [name, year] = formatDate(month).split(' ')
  const showYear = index === 0 || month.endsWith('-01')
  return { name, year: showYear ? `’${year?.slice(2) ?? ''}` : null }
}

function Delta({ change, unit = 'units' }: { change: Change | null; unit?: string }) {
  if (!change) return <span className="text-xs text-muted">No comparison available</span>
  const up = change.difference > 0
  const flat = change.difference === 0
  return (
    <span className={`text-xs font-semibold ${flat ? 'text-muted' : up ? 'text-down' : 'text-up'}`}>
      {flat ? '±' : up ? '▲ +' : '▼ '}
      {formatNumber(change.difference)} {unit}
      {change.percent_change !== null && ` (${up ? '+' : ''}${formatNumber(change.percent_change)}%)`}
    </span>
  )
}

function Tile({
  label,
  value,
  sub,
  accent = false,
}: {
  label: string
  value: string
  sub: React.ReactNode
  accent?: boolean
}) {
  return (
    <div className={`flex flex-col justify-between rounded-[22px] p-4 ${accent ? 'bg-lime text-forest' : 'bg-shell'}`}>
      <p className={`text-xs font-medium ${accent ? 'text-forest/70' : 'text-muted'}`}>{label}</p>
      <p className="amount mt-1 text-3xl">{value}</p>
      <div className="mt-1">{sub}</div>
    </div>
  )
}

function monthText(m: MonthUnits | null): string {
  return m ? formatDate(m.month) : 'Not shown'
}

/**
 * Monthly units graph plus the key usage figures: current vs previous month,
 * highest and lowest month, and the average. All numbers come from the backend.
 */
export function UsageInsights({ usage }: { usage: Usage }) {
  const points = usage.points
  if (points.length === 0) {
    return (
      <div className="card">
        <CardHeader icon="history" title="Usage insights" />
        <p className="rounded-2xl bg-shell px-4 py-3 text-sm text-muted">
          This bill does not print a usage history, so monthly comparisons are not available.
        </p>
      </div>
    )
  }

  const max = Math.max(...points.map((p) => Math.abs(p.units)), usage.average_units ?? 0, 1)
  const avgPct = usage.average_units !== null ? (usage.average_units / max) * 100 : null

  return (
    <div className="card">
      <CardHeader
        icon="bars"
        title="Usage insights"
        aside={<span className="pill">{points.length} months of history</span>}
      />

      <div className="grid gap-6 xl:grid-cols-[minmax(0,3fr)_minmax(0,2fr)]">
        {/* Monthly units graph */}
        <div className="min-w-0">
          <div className="mb-2 flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-muted">
            <span className="flex items-center gap-1.5">
              <span className="h-2.5 w-2.5 rounded-full bg-lime" /> Previous months
            </span>
            <span className="flex items-center gap-1.5">
              <span className="h-2.5 w-2.5 rounded-full bg-forest" /> This bill
            </span>
            {avgPct !== null && (
              <span className="flex items-center gap-1.5">
                <span className="w-4 border-t-2 border-dashed border-warn" /> Average
              </span>
            )}
          </div>
          {/* Scrolls sideways on narrow screens instead of squashing the bars together. */}
          <div className="-mx-1 overflow-x-auto px-1 pb-1">
          <div className="min-w-[26rem]">
          <div className="relative flex h-56 items-end gap-1.5 border-b border-line pb-px sm:h-64" role="img"
            aria-label={`Monthly units for ${points.length} months`}>
            {avgPct !== null && (
              <div
                className="pointer-events-none absolute inset-x-0 z-10 border-t-2 border-dashed border-warn"
                style={{ bottom: `calc(${avgPct}% * 0.82)` }}
              >
                <span className="absolute -top-5 right-0 rounded-full bg-card px-1.5 text-[10px] font-semibold text-warn">
                  avg {formatNumber(usage.average_units)}
                </span>
              </div>
            )}
            {points.map((p) => {
              const isHigh = usage.highest?.month === p.month
              const isLow = usage.lowest?.month === p.month
              return (
                <div key={p.month} className="group relative flex h-full min-w-0 flex-1 flex-col items-center justify-end">
                  <span
                    className={`mb-1 text-[10px] font-semibold tabular-nums ${
                      p.is_current ? 'text-forest' : 'text-muted'
                    }`}
                  >
                    {formatNumber(p.units)}
                  </span>
                  <div
                    className={`w-full max-w-9 rounded-t-xl rounded-b-md transition group-hover:opacity-80 ${
                      p.is_current ? 'bg-forest' : 'bg-lime'
                    } ${isHigh || isLow ? 'ring-2 ring-offset-2 ' + (isHigh ? 'ring-down/50' : 'ring-up/60') : ''}`}
                    style={{ height: `calc(${Math.max((Math.abs(p.units) / max) * 100, 2)}% * 0.82)` }}
                    title={`${formatDate(p.month)}: ${formatNumber(p.units)} units`}
                  />
                </div>
              )
            })}
          </div>
          <div className="mt-1.5 flex gap-1.5">
            {points.map((p, i) => {
              const label = axisLabel(p.month, i)
              return (
                <span key={p.month} className="min-w-0 flex-1 text-center leading-tight">
                  <span className={`block text-[10px] ${p.is_current ? 'font-bold text-forest' : 'text-muted'}`}>
                    {label.name}
                  </span>
                  <span className="block h-3 text-[9px] font-semibold text-muted/80">{label.year}</span>
                </span>
              )
            })}
          </div>
          </div>
          </div>
        </div>

        {/* Key figures */}
        <div className="grid grid-cols-1 gap-3 xs:grid-cols-2">
          <Tile
            accent
            label={`This bill · ${monthText(usage.current)}`}
            value={usage.current ? `${formatNumber(usage.current.units)}` : '—'}
            sub={
              <span className="text-xs font-medium text-forest/80">
                vs {usage.previous ? `${formatNumber(usage.previous.units)} in ${formatDate(usage.previous.month)}` : 'no previous month'}
              </span>
            }
          />
          <Tile
            label="Change vs previous month"
            value={usage.change_vs_previous ? `${usage.change_vs_previous.difference > 0 ? '+' : ''}${formatNumber(usage.change_vs_previous.difference)}` : '—'}
            sub={<Delta change={usage.change_vs_previous} />}
          />
          <Tile
            label="Highest month"
            value={usage.highest ? formatNumber(usage.highest.units) : '—'}
            sub={
              <span className="flex items-center gap-1 text-xs font-semibold text-down">
                <Icon name="arrow" className="h-3 w-3" /> {monthText(usage.highest)}
              </span>
            }
          />
          <Tile
            label="Lowest month"
            value={usage.lowest ? formatNumber(usage.lowest.units) : '—'}
            sub={
              <span className="flex items-center gap-1 text-xs font-semibold text-up">
                <Icon name="arrow" className="h-3 w-3 rotate-90" /> {monthText(usage.lowest)}
              </span>
            }
          />
          <div className="rounded-[22px] bg-forest p-4 text-lime xs:col-span-2">
            <div className="flex flex-wrap items-end justify-between gap-3">
              <div>
                <p className="text-xs font-medium text-lime/70">
                  Average monthly units · previous {usage.average_months} month{usage.average_months === 1 ? '' : 's'}
                </p>
                <p className="amount mt-1 text-4xl">{formatNumber(usage.average_units)}</p>
              </div>
              <div className="text-xs xs:text-right">
                <p className="text-lime/70">This bill vs average</p>
                {usage.change_vs_average ? (
                  <p className="font-semibold">
                    {usage.change_vs_average.difference > 0 ? '+' : ''}
                    {formatNumber(usage.change_vs_average.difference)} units
                    {usage.change_vs_average.percent_change !== null &&
                      ` (${usage.change_vs_average.difference > 0 ? '+' : ''}${formatNumber(usage.change_vs_average.percent_change)}%)`}
                  </p>
                ) : (
                  <p>—</p>
                )}
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
