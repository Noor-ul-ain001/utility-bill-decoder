import { useEffect, useState, type FormEvent } from 'react'
import { api } from '../api'
import { CardHeader, ErrorBanner, Icon, Spinner } from './ui'

interface Props {
  billKey: string
  /** Reports when a question is being answered (drives the header's agent status). */
  onBusyChange?: (busy: boolean) => void
}

interface QA {
  question: string
  answer: string
}

interface Suggestion {
  /** Short chip text. */
  label: string
  /** Full question sent to the backend. */
  question: string
}

/** The 12 questions from the competition's level2.csv (asked for every test bill). */
const TEST_QUESTIONS: Suggestion[] = [
  { label: 'Do I have a solar (net-metered) connection?', question: 'Is this a net-metered (solar) connection or a standard connection? How did you tell?' },
  { label: 'Which month did I use the most electricity?', question: 'Which month in the last 12 months had the highest units consumed?' },
  { label: 'How much fuel adjustment am I paying?', question: 'How much fuel adjustment am I being charged (shown as FPA or FCA on the bill), and for which month?' },
  { label: 'What extra do I pay if I pay late?', question: "If I don't pay on time, what late payment surcharges will be added?" },
  { label: 'Am I using more than this month last year?', question: 'Am I consuming more units than in the same month last year?' },
  { label: 'What is my average monthly usage?', question: 'What are my average monthly units consumed, and how does this month compare?' },
  { label: 'How much more do I use in summer than winter?', question: 'How many more units do I consume in summer (June-August) than in winter (December-February)?' },
  { label: 'Have I paid all my past bills?', question: 'Looking at the payments for the 12 months shown on the bill, have I been paying every bill?' },
  { label: 'Is my usage going up or down lately?', question: 'Have my units consumed gone up or down over the last 3 months?' },
  { label: 'How many units will I use next month?', question: 'Based on the 12 months trend, how many units should I expect to consume next month?' },
  { label: 'How much should I save each month for bills?', question: 'If I wanted to spread my electricity cost evenly across the year, how much should I set aside each month?' },
  { label: 'What will my bill be if I use the same as last month?', question: 'If I consume the same units as last month, what would my bill be roughly?' },
]

const MORE_QUESTIONS: Suggestion[] = [
  { label: 'How much of my bill is taxes?', question: 'How much of my bill is taxes?' },
  { label: 'How many months went above 200 units?', question: 'How many months in my history went above 200 units?' },
  { label: 'How much am I paying per unit?', question: 'What is my effective cost per unit?' },
]

const SUGGESTION_GROUPS: { title: string; items: Suggestion[] }[] = [
  { title: 'Common questions', items: TEST_QUESTIONS },
  { title: 'More ideas', items: MORE_QUESTIONS },
]

/** Free-form questions about the decoded bill, with a running Q&A history. */
export function AskPanel({ billKey, onBusyChange }: Props) {
  const [question, setQuestion] = useState('')
  const [history, setHistory] = useState<QA[]>([])
  const [pending, setPending] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const busy = pending !== null

  useEffect(() => onBusyChange?.(busy), [busy, onBusyChange])

  async function ask(text: string) {
    const q = text.trim()
    if (!q || busy) return
    setPending(q)
    setError(null)
    try {
      const { answer } = await api.ask(billKey, q)
      setHistory((h) => [{ question: q, answer }, ...h])
      setQuestion('')
    } catch (e) {
      setError((e as Error).message)
    } finally {
      setPending(null)
    }
  }

  function onSubmit(event: FormEvent) {
    event.preventDefault()
    void ask(question)
  }

  return (
    <div className="card">
      <CardHeader icon="chat" title="Ask about this bill" aside={<span className="pill">{history.length} answered</span>} />

      <form onSubmit={onSubmit} className="flex flex-col gap-2 xs:flex-row">
        <input
          className="input flex-1"
          placeholder="e.g. Why is this bill higher than last month?"
          value={question}
          onChange={(e) => setQuestion(e.target.value)}
          disabled={busy}
          aria-label="Question about this bill"
        />
        <button type="submit" className="btn-primary" disabled={busy || !question.trim()}>
          {busy ? <Spinner /> : <Icon name="arrow" className="h-4 w-4" />}
          Ask
        </button>
      </form>

      {SUGGESTION_GROUPS.map((group) => (
        <div key={group.title} className="mt-4">
          <p className="mb-2 text-xs font-semibold uppercase tracking-wider text-muted">{group.title}</p>
          <div className="flex flex-wrap gap-2">
            {group.items.map((s) => (
              <button
                key={s.question}
                onClick={() => void ask(s.question)}
                disabled={busy}
                title={s.question}
                className="rounded-full border border-line bg-card px-3.5 py-1.5 text-xs font-semibold transition hover:border-lime hover:bg-lime-pale disabled:opacity-50"
              >
                {s.label}
              </button>
            ))}
          </div>
        </div>
      ))}

      {error && (
        <div className="mt-4">
          <ErrorBanner message={error} onClose={() => setError(null)} />
        </div>
      )}

      <ul className="mt-6 flex flex-col gap-3">
        {pending && (
          <li className="rounded-[22px] bg-shell p-4">
            <p className="text-sm font-semibold">{pending}</p>
            <p className="mt-2 flex items-center gap-2 text-sm text-muted">
              <Spinner className="h-4 w-4 text-forest" /> Working it out from your bill…
            </p>
          </li>
        )}
        {history.map((qa, i) => (
          <li key={`${i}-${qa.question}`} className="rounded-[22px] bg-shell p-3 xs:p-4">
            <p className="flex items-center gap-2 text-sm font-semibold">
              <span className="grid h-6 w-6 shrink-0 place-items-center rounded-full bg-forest text-[10px] text-lime">Q</span>
              {qa.question}
            </p>
            <p className="mt-2 whitespace-pre-line text-sm xs:pl-8 leading-relaxed text-ink/85">{qa.answer}</p>
          </li>
        ))}
        {!pending && history.length === 0 && (
          <li className="rounded-[22px] border border-dashed border-line p-6 text-center text-sm text-muted">
            Pick a suggestion or type your own question. Numbers are calculated in code, not guessed.
          </li>
        )}
      </ul>
    </div>
  )
}
