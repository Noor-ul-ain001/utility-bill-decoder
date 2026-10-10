import type { LabeledLine } from '../api'
import { formatPkr, humanizeType } from '../format'
import { CardHeader, type IconName } from './ui'

interface Props {
  title: string
  icon: IconName
  lines: LabeledLine[]
  total: number | null
  emptyText: string
}

/**
 * Charge or tax lines as printed, each with its type and a bar showing its share
 * of the printed subtotal (styled like the reference "Earning" card).
 */
export function ChargesTable({ title, icon, lines, total, emptyText }: Props) {
  const base = Math.max(Math.abs(total ?? 0), ...lines.map((l) => Math.abs(l.amount)), 1)
  const largest = lines.reduce((best, l, i) => (l.amount > (lines[best]?.amount ?? -Infinity) ? i : best), 0)

  return (
    <div className="card">
      <CardHeader
        icon={icon}
        title={title}
        aside={
          <span className="flex flex-col xs:items-end">
            <span className="text-xs text-muted">Printed total</span>
            <span className="text-base font-semibold tabular-nums">{formatPkr(total)}</span>
            <span className="mt-1 h-1 w-full rounded-full bg-warn" />
          </span>
        }
      />

      {lines.length === 0 ? (
        <p className="rounded-2xl bg-shell px-4 py-3 text-sm text-muted">{emptyText}</p>
      ) : (
        <ul className="flex flex-col gap-4">
          {lines.map((line, i) => {
            const share = (Math.abs(line.amount) / base) * 100
            const highlight = i === largest && line.amount > 0
            return (
              <li key={`${line.type}-${i}`}>
                <div className="mb-1.5 flex flex-wrap items-baseline justify-between gap-x-3 gap-y-0.5 text-sm">
                  <span className="min-w-0">
                    <span className={highlight ? 'font-semibold' : 'text-muted'}>{line.label || humanizeType(line.type)}</span>
                    <span className="ml-2 rounded-full bg-shell px-2 py-0.5 text-[11px] font-semibold text-muted">
                      {humanizeType(line.type)}
                    </span>
                  </span>
                  <span className={`shrink-0 tabular-nums ${line.amount < 0 ? 'font-semibold text-up' : 'text-muted'}`}>
                    {formatPkr(line.amount)}
                  </span>
                </div>
                <div className="relative h-2.5 rounded-full bg-line">
                  <div
                    className={`h-2.5 rounded-full ${line.amount < 0 ? 'bg-up/60' : highlight ? 'bg-lime' : 'bg-[#d5d5d2]'}`}
                    style={{ width: `${Math.max(share, 2)}%` }}
                  />
                  {highlight && total ? (
                    <span
                      className="absolute top-1/2 -translate-y-1/2 rounded-full bg-forest px-2 py-0.5 text-[10px] font-semibold text-lime"
                      style={{ left: `min(calc(${share}% - 1.5rem), calc(100% - 2.75rem))` }}
                    >
                      {Math.round((line.amount / total) * 100)}%
                    </span>
                  ) : null}
                </div>
              </li>
            )
          })}
        </ul>
      )}
    </div>
  )
}
