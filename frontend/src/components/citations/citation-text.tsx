import type { Source } from "@/lib/api/types"
import { formatLocation } from "@/lib/format"
import { cn } from "@/lib/utils"

// Inline tokens: **bold**, `code` and [n] citations.
const INLINE = /(\*\*[^*\n]+\*\*|`[^`\n]+`|\[\d+\])/g
const BULLET = /^\s*[-*•]\s+/
const NUMBERED = /^\s*\d+[.)]\s+/
const HEADING = /^\s{0,3}#{1,4}\s+/

function isChip(node: React.ReactNode): node is React.ReactElement {
  return (
    typeof node === "object" &&
    node !== null &&
    "props" in node &&
    (node.props as Record<string, unknown>)["data-citation"] !== undefined
  )
}

type Block =
  | { kind: "paragraph"; lines: string[] }
  | { kind: "heading"; text: string }
  | { kind: "list"; ordered: boolean; items: string[] }

/** Split answer text into paragraphs, headings and lists (the subset models actually use). */
function toBlocks(text: string): Block[] {
  const blocks: Block[] = []
  for (const raw of text.replace(/\r\n/g, "\n").split("\n")) {
    const line = raw.trimEnd()
    const last = blocks.at(-1)
    if (!line.trim()) {
      blocks.push({ kind: "paragraph", lines: [] })
      continue
    }
    if (HEADING.test(line)) {
      blocks.push({ kind: "heading", text: line.replace(HEADING, "") })
      continue
    }
    const ordered = NUMBERED.test(line)
    if (ordered || BULLET.test(line)) {
      const item = line.replace(ordered ? NUMBERED : BULLET, "")
      if (last?.kind === "list" && last.ordered === ordered) last.items.push(item)
      else blocks.push({ kind: "list", ordered, items: [item] })
      continue
    }
    if (last?.kind === "paragraph") last.lines.push(line)
    else blocks.push({ kind: "paragraph", lines: [line] })
  }
  return blocks.filter((block) => block.kind !== "paragraph" || block.lines.length > 0)
}

/**
 * Renders an answer: light formatting (paragraphs, headings, lists, bold, code) with [n]
 * markers that match a returned source turned into citation buttons. Markers without a
 * matching source stay plain text rather than linking to nothing. No HTML is interpreted.
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

  // Keeps a run of citation chips together with the punctuation right after it, so a "." never
  // wraps onto its own line after a chip.
  const inline = (value: string, keyPrefix: string): React.ReactNode[] => {
    const nodes = renderParts(value, keyPrefix)
    const out: React.ReactNode[] = []
    for (let i = 0; i < nodes.length; i++) {
      if (!isChip(nodes[i])) {
        out.push(nodes[i])
        continue
      }
      const group: React.ReactNode[] = [nodes[i]]
      // Adjacent chips ("[1][2]") are separated by empty strings after the split.
      while (i + 2 < nodes.length && nodes[i + 1] === "" && isChip(nodes[i + 2])) {
        group.push(nodes[i + 2])
        i += 2
      }
      const next = nodes[i + 1]
      if (typeof next === "string") {
        const punctuation = /^[.,;:!?)\]]+/.exec(next)?.[0] ?? ""
        group.push(punctuation)
        nodes[i + 1] = next.slice(punctuation.length)
      }
      out.push(
        <span key={`${keyPrefix}-g${i}`} className="whitespace-nowrap">
          {group}
        </span>,
      )
    }
    return out
  }

  const renderParts = (value: string, keyPrefix: string): React.ReactNode[] =>
    value.split(INLINE).map((part, position) => {
      const key = `${keyPrefix}-${position}`
      if (part.startsWith("**") && part.endsWith("**") && part.length > 4) {
        return (
          <strong key={key} className="font-semibold">
            {part.slice(2, -2)}
          </strong>
        )
      }
      if (part.startsWith("`") && part.endsWith("`") && part.length > 2) {
        return (
          <code key={key} className="rounded bg-muted px-1 py-0.5 font-mono text-[0.85em]">
            {part.slice(1, -1)}
          </code>
        )
      }
      const citation = /^\[(\d+)\]$/.exec(part)
      const source = citation ? byIndex.get(Number(citation[1])) : undefined
      if (citation && source) {
        const index = Number(citation[1])
        return (
          <button
            key={key}
            data-citation=""
            type="button"
            onClick={() => onCite(index)}
            aria-label={`Source ${index}: ${source.filename}, ${formatLocation(source.page, source.chunk_index)}`}
            className={cn(
              "mx-0.5 inline-flex h-[1.15rem] min-w-[1.15rem] items-center justify-center rounded-md border border-primary/20 bg-accent px-1 align-[0.1em] text-[10.5px] leading-none font-semibold text-accent-foreground tabular-nums transition-colors hover:border-primary/50 hover:bg-primary hover:text-primary-foreground focus-visible:ring-3 focus-visible:ring-ring/50 focus-visible:outline-none",
              activeIndex === index && "border-primary bg-primary text-primary-foreground",
            )}
          >
            {index}
          </button>
        )
      }
      return part
    })

  return (
    <div className="space-y-3 text-[0.9375rem] leading-relaxed text-foreground">
      {toBlocks(text).map((block, position) => {
        const key = `b${position}`
        if (block.kind === "heading") {
          return (
            <p key={key} className="pt-1 font-semibold">
              {inline(block.text, key)}
            </p>
          )
        }
        if (block.kind === "list") {
          const List = block.ordered ? "ol" : "ul"
          return (
            <List
              key={key}
              className={cn(
                "space-y-1.5 pl-5 marker:text-muted-foreground",
                block.ordered ? "list-decimal" : "list-disc",
              )}
            >
              {block.items.map((item, index) => (
                <li key={index} className="pl-1">
                  {inline(item, `${key}-${index}`)}
                </li>
              ))}
            </List>
          )
        }
        return (
          <p key={key}>
            {block.lines.map((line, index) => (
              <span key={index}>
                {index > 0 && <br />}
                {inline(line, `${key}-${index}`)}
              </span>
            ))}
          </p>
        )
      })}
    </div>
  )
}
