import type { ReactNode } from 'react'

/** Small inline spinner used inside buttons and loading states. */
export function Spinner({ className = 'h-4 w-4' }: { className?: string }) {
  return (
    <svg className={`animate-spin ${className}`} viewBox="0 0 24 24" fill="none" aria-hidden="true">
      <circle cx="12" cy="12" r="10" stroke="currentColor" strokeOpacity="0.25" strokeWidth="3" />
      <path d="M22 12a10 10 0 0 0-10-10" stroke="currentColor" strokeWidth="3" strokeLinecap="round" />
    </svg>
  )
}

/** Friendly, dismissible error banner (styled like the reference's highlighted transaction). */
export function ErrorBanner({ message, onClose }: { message: string; onClose?: () => void }) {
  return (
    <div role="alert" className="flex items-start gap-3 rounded-2xl border border-down/25 bg-down-soft px-4 py-3 text-sm">
      <span className="grid h-7 w-7 shrink-0 place-items-center rounded-full bg-down text-xs font-bold text-white">!</span>
      <p className="flex-1 font-medium text-ink">{message}</p>
      {onClose && (
        <button onClick={onClose} className="icon-chip h-8 w-8" aria-label="Dismiss error">
          <Icon name="close" className="h-3.5 w-3.5" />
        </button>
      )}
    </div>
  )
}

/** Card heading: round icon chip, title and an optional element on the right. */
export function CardHeader({ icon, title, aside }: { icon: IconName; title: string; aside?: ReactNode }) {
  return (
    <div className="mb-4 flex flex-wrap items-center justify-between gap-x-3 gap-y-2 sm:mb-5">
      <div className="flex min-w-0 items-center gap-2.5 sm:gap-3">
        <span className="icon-chip h-9 w-9 sm:h-10 sm:w-10">
          <Icon name={icon} className="h-4.5 w-4.5" />
        </span>
        <h3 className="min-w-0 text-base font-semibold sm:text-lg">{title}</h3>
      </div>
      {aside}
    </div>
  )
}

/** Key/value row used inside cards. */
export function Row({ label, value }: { label: string; value: ReactNode }) {
  return (
    <div className="flex flex-wrap items-baseline justify-between gap-x-4 gap-y-0.5 border-b border-line py-3 last:border-b-0">
      <span className="text-sm text-muted">{label}</span>
      <span className="text-sm font-semibold tabular-nums">{value}</span>
    </div>
  )
}

export type IconName =
  | 'bolt' | 'upload' | 'arrow' | 'close' | 'check' | 'copy' | 'receipt' | 'pie' | 'bars'
  | 'shield' | 'meter' | 'chat' | 'folder' | 'download' | 'image' | 'history' | 'code' | 'chevron'

const PATHS: Record<IconName, ReactNode> = {
  bolt: <path d="M13 2 4 14h7l-1 8 9-12h-7z" />,
  upload: <path d="M12 16V4m0 0-4 4m4-4 4 4M4 16v2a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-2" />,
  arrow: <path d="M7 17 17 7M8 7h9v9" />,
  close: <path d="M6 6l12 12M18 6 6 18" />,
  check: <path d="m5 12 5 5 9-10" />,
  copy: <path d="M9 9h10v10H9zM5 15V5h10" />,
  receipt: <path d="M6 3h12v18l-3-2-3 2-3-2-3 2zM9 8h6M9 12h6M9 16h3" />,
  pie: <path d="M12 3a9 9 0 1 0 9 9h-9zM15 3.5A9 9 0 0 1 20.5 9H15z" />,
  bars: <path d="M4 20V10M10 20V4M16 20v-7M22 20H2" />,
  shield: <path d="M12 3 4 6v6c0 4.5 3.4 8.3 8 9 4.6-.7 8-4.5 8-9V6zM9 12l2 2 4-4" />,
  meter: <path d="M12 14l4-4M4 18a9 9 0 1 1 16 0z" />,
  chat: <path d="M4 5h16v11H9l-5 4z" />,
  folder: <path d="M3 6h7l2 2h9v11H3z" />,
  download: <path d="M12 4v12m0 0-4-4m4 4 4-4M4 20h16" />,
  image: <path d="M4 5h16v14H4zM4 16l5-5 4 4 3-3 4 4M15 9h.01" />,
  history: <path d="M3 12a9 9 0 1 0 3-6.7L3 8M3 3v5h5M12 7v5l3 3" />,
  code: <path d="m8 8-4 4 4 4M16 8l4 4-4 4" />,
  chevron: <path d="m9 6 6 6-6 6" />,
}

export function Icon({ name, className = 'h-5 w-5' }: { name: IconName; className?: string }) {
  return (
    <svg
      viewBox="0 0 24 24"
      className={className}
      fill="none"
      stroke="currentColor"
      strokeWidth="1.8"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
    >
      {PATHS[name]}
    </svg>
  )
}
