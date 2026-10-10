import { useRef, useState, type DragEvent } from 'react'
import { Icon, Spinner } from './ui'

interface Props {
  busy: boolean
  onExtract: (file: File) => void
}

const ACCEPTED = ['image/png', 'image/jpeg']

/** Lime highlight card: drag-and-drop (or browse) a bill image, preview it, decode it. */
export function UploadPanel({ busy, onExtract }: Props) {
  const inputRef = useRef<HTMLInputElement>(null)
  const [file, setFile] = useState<File | null>(null)
  const [preview, setPreview] = useState<string | null>(null)
  const [dragging, setDragging] = useState(false)
  const [error, setError] = useState<string | null>(null)

  function choose(next: File | undefined) {
    if (!next) return
    if (!ACCEPTED.includes(next.type)) {
      setError('Please choose a PNG or JPG image of the bill.')
      return
    }
    setError(null)
    setFile(next)
    setPreview((old) => {
      if (old) URL.revokeObjectURL(old)
      return URL.createObjectURL(next)
    })
  }

  function onDrop(event: DragEvent<HTMLDivElement>) {
    event.preventDefault()
    setDragging(false)
    choose(event.dataTransfer.files[0])
  }

  return (
    <div className="relative flex h-full min-w-0 flex-col overflow-hidden rounded-[22px] bg-lime p-4 sm:rounded-[28px] sm:p-6">
      {/* Decorative sparkle, echoing the reference card */}
      <svg viewBox="0 0 100 100" className="pointer-events-none absolute -right-6 -top-6 h-40 w-40 text-white/25" aria-hidden="true">
        <path d="M50 0c4 30 16 42 50 50-34 8-46 20-50 50-4-30-16-42-50-50C34 42 46 30 50 0z" fill="currentColor" />
      </svg>

      <div className="relative flex items-center justify-between">
        <button
          type="button"
          onClick={() => inputRef.current?.click()}
          disabled={busy}
          className="group inline-flex items-center gap-2 rounded-full bg-forest py-1.5 pl-4 pr-1.5 text-xs font-semibold tracking-wider text-lime transition hover:bg-forest-dark disabled:opacity-60"
        >
          UPLOAD A BILL
          <span className="grid h-6 w-6 place-items-center rounded-full bg-lime text-forest transition group-hover:-translate-y-0.5">
            <Icon name="upload" className="h-3.5 w-3.5" />
          </span>
        </button>
      </div>

      <p className="relative mt-5 text-sm font-medium text-forest/80">Scan, screenshot or photo · PNG or JPG</p>

      <div
        role="button"
        tabIndex={0}
        aria-label="Choose a bill image"
        onClick={() => inputRef.current?.click()}
        onKeyDown={(e) => (e.key === 'Enter' || e.key === ' ') && inputRef.current?.click()}
        onDragOver={(e) => {
          e.preventDefault()
          setDragging(true)
        }}
        onDragLeave={() => setDragging(false)}
        onDrop={onDrop}
        className={`relative mt-3 flex min-h-36 flex-1 sm:min-h-44 cursor-pointer items-center justify-center gap-4 rounded-2xl border-2 border-dashed p-4 transition ${
          dragging ? 'border-forest bg-white/60' : 'border-forest/25 bg-white/35 hover:bg-white/50'
        }`}
      >
        {preview ? (
          <img src={preview} alt="Selected bill preview" className="max-h-48 rounded-xl object-contain shadow" />
        ) : (
          <div className="text-center text-forest">
            <Icon name="image" className="mx-auto h-8 w-8" />
            <p className="mt-2 text-sm font-semibold sm:text-base">Drop the bill image here</p>
            <p className="text-xs text-forest/70 sm:text-sm">or tap to browse</p>
          </div>
        )}
        <input
          ref={inputRef}
          type="file"
          accept=".png,.jpg,.jpeg"
          className="hidden"
          onChange={(e) => choose(e.target.files?.[0])}
        />
      </div>

      {error && <p className="relative mt-2 text-sm font-semibold text-down">{error}</p>}

      <div className="relative mt-4 grid grid-cols-1 gap-2 xs:grid-cols-[minmax(0,1fr)_auto] xs:gap-3">
        <div className="min-w-0 rounded-2xl bg-white/45 px-4 py-2.5">
          <p className="text-xs font-medium text-forest/70">Selected file</p>
          <p className="truncate text-sm font-semibold text-forest">{file ? file.name : 'None yet'}</p>
        </div>
        <button className="btn-primary h-full py-3 xs:px-6" disabled={!file || busy} onClick={() => file && onExtract(file)}>
          {busy ? <Spinner /> : <Icon name="arrow" className="h-4 w-4" />}
          {busy ? 'Reading…' : 'Decode'}
        </button>
      </div>
    </div>
  )
}
