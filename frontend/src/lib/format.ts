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
