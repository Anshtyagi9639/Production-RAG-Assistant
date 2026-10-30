const dateTime = new Intl.DateTimeFormat(undefined, { dateStyle: "medium", timeStyle: "short" })
const number = new Intl.NumberFormat()

export function formatDateTime(iso: string): string {
  return dateTime.format(new Date(iso))
}

export function formatNumber(value: number): string {
  return number.format(value)
}

export function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
}

export function formatDuration(ms: number): string {
  return ms < 1000 ? `${Math.round(ms)} ms` : `${(ms / 1000).toFixed(1)} s`
}

/** Cosine similarity, shown with two decimals. */
export function formatScore(score: number): string {
  return score.toFixed(2)
}

/** Where a passage sits: "Page 3 · Passage 8", or just "Passage 8" for files without pages. */
export function formatLocation(page: number | null, chunkIndex: number): string {
  const passage = `Passage ${chunkIndex + 1}`
  return page === null ? passage : `Page ${page} · ${passage}`
}

const relative = new Intl.RelativeTimeFormat(undefined, { numeric: "auto" })
const timeOnly = new Intl.DateTimeFormat(undefined, { timeStyle: "short" })
const dayLabel = new Intl.DateTimeFormat(undefined, {
  weekday: "long",
  month: "long",
  day: "numeric",
})
const shortDate = new Intl.DateTimeFormat(undefined, { month: "short", day: "numeric" })

/** "just now", "5 minutes ago", "yesterday"; falls back to a short date after a week. */
export function formatRelative(iso: string, now: Date = new Date()): string {
  const seconds = Math.round((new Date(iso).getTime() - now.getTime()) / 1000)
  const abs = Math.abs(seconds)
  if (abs < 45) return "just now"
  if (abs < 3600) return relative.format(Math.round(seconds / 60), "minute")
  if (abs < 86_400) return relative.format(Math.round(seconds / 3600), "hour")
  if (abs < 7 * 86_400) return relative.format(Math.round(seconds / 86_400), "day")
  return shortDate.format(new Date(iso))
}

/** "1 passage", "3 passages". */
export function plural(count: number, word: string, pluralWord = `${word}s`): string {
  return `${formatNumber(count)} ${count === 1 ? word : pluralWord}`
}

export function formatTime(iso: string): string {
  return timeOnly.format(new Date(iso))
}

/** Heading for a group of events on one calendar day: "Today", "Yesterday" or the date. */
export function formatDayGroup(iso: string, now: Date = new Date()): string {
  const day = new Date(iso)
  const startOf = (d: Date) => new Date(d.getFullYear(), d.getMonth(), d.getDate()).getTime()
  const days = Math.round((startOf(now) - startOf(day)) / 86_400_000)
  if (days === 0) return "Today"
  if (days === 1) return "Yesterday"
  return dayLabel.format(day)
}

export type FileKind = "pdf" | "docx" | "markdown" | "text" | "file"

export function fileKind(filename: string, contentType?: string): FileKind {
  const name = filename.toLowerCase()
  if (name.endsWith(".pdf") || contentType === "application/pdf") return "pdf"
  if (name.endsWith(".docx") || contentType?.includes("wordprocessingml")) return "docx"
  if (name.endsWith(".md") || contentType === "text/markdown") return "markdown"
  if (name.endsWith(".txt") || contentType?.startsWith("text/")) return "text"
  return "file"
}

export const FILE_KIND_LABELS: Record<FileKind, string> = {
  pdf: "PDF",
  docx: "Word",
  markdown: "Markdown",
  text: "Text",
  file: "File",
}

/** Passage text for display: Markdown syntax from the source file removed, whitespace collapsed. */
export function cleanSnippet(text: string): string {
  return text
    .replace(/^\s{0,3}#{1,6}\s+/gm, "")
    .replace(/\*\*(.+?)\*\*/g, "$1")
    .replace(/^\s*[-*+]\s+/gm, "")
    .replace(/\s+/g, " ")
    .trim()
}
