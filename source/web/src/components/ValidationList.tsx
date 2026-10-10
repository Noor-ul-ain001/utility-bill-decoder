import type { ValidationCheck } from '../api'
import { CardHeader, Icon } from './ui'

/** Consistency checks with pass/fail indicators (styled like the reference "Transactions" list). */
export function ValidationList({ checks }: { checks: ValidationCheck[] }) {
  const passed = checks.filter((c) => c.passed).length
  return (
    <div className="card">
      <CardHeader
        icon="shield"
        title="Consistency checks"
        aside={
          <span className={`pill ${passed === checks.length ? 'text-up' : 'text-warn'}`}>
            {passed}/{checks.length} passed
          </span>
        }
      />
      {checks.length === 0 && <p className="text-sm text-muted">Not enough values were printed to run any check.</p>}
      <ul className="flex flex-col">
        {checks.map((c) => (
          <li
            key={c.check}
            className={`flex flex-wrap items-center gap-x-3 gap-y-1 border-b border-line py-3 last:border-b-0 ${
              c.passed ? '' : '-mx-3 rounded-2xl border border-warn/30 bg-[#fff6f1] px-3'
            }`}
          >
            <span
              className={`grid h-9 w-9 shrink-0 place-items-center rounded-full ${
                c.passed ? 'bg-lime text-forest' : 'border border-line bg-card text-down'
              }`}
              aria-label={c.passed ? 'passed' : 'failed'}
            >
              <Icon name={c.passed ? 'check' : 'close'} className="h-4 w-4" />
            </span>
            <span className="min-w-0 flex-1">
              <span className="block text-sm font-semibold">{c.check}</span>
              <span className={`block text-xs ${c.passed ? 'text-muted' : 'text-warn'}`}>{c.detail}</span>
            </span>
            <span className={`text-sm font-semibold ${c.passed ? 'text-up' : 'text-down'}`}>
              {c.passed ? 'Passed' : 'Check'}
            </span>
          </li>
        ))}
      </ul>
    </div>
  )
}
