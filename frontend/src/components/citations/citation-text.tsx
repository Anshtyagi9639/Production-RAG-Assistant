import type { Source } from "@/lib/api/types"
import { formatLocation } from "@/lib/format"
import { cn } from "@/lib/utils"

const CITATION = /\[(\d+)\]/g

/**
 * Renders answer text, turning [n] markers that match a returned source into buttons.
 * Markers without a matching source are left as plain text rather than linked to nothing.
 */
export function CitationText({
  text,
  sources,
  activeIndex,
  onCite,
}: {
  text: string
  sources: Source[]
  activeIndex?: number | null
  onCite: (index: number) => void
}) {
  const byIndex = new Map(sources.map((source) => [source.index, source]))
  const parts: React.ReactNode[] = []
  let last = 0
  for (const match of text.matchAll(CITATION)) {
    const index = Number(match[1])
    const source = byIndex.get(index)
    if (!source) continue
    parts.push(text.slice(last, match.index))
    parts.push(
      <button
        key={`${match.index}-${index}`}
        type="button"
        onClick={() => onCite(index)}
        aria-label={`Source ${index}: ${source.filename}, ${formatLocation(source.page, source.chunk_index)}`}
        className={cn(
          "mx-0.5 inline-flex h-5 min-w-5 items-center justify-center rounded border bg-card px-1 align-text-top text-[11px] font-medium text-primary tabular-nums transition-colors hover:bg-accent focus-visible:ring-3 focus-visible:ring-ring/50 focus-visible:outline-none",
          activeIndex === index && "border-primary bg-accent",
        )}
      >
        {index}
      </button>,
    )
    last = match.index + match[0].length
  }
  parts.push(text.slice(last))
  return <p className="text-sm leading-relaxed whitespace-pre-wrap">{parts}</p>
}
