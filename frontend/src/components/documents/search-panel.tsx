"use client"

import { useMutation } from "@tanstack/react-query"
import { Loader2, Search, SearchX, Sparkles } from "lucide-react"
import Link from "next/link"
import { useState } from "react"

import { FileTypeIcon } from "@/components/documents/file-type-icon"
import { EmptyState, ErrorState, ListSkeleton } from "@/components/states"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { searchApi } from "@/lib/api/endpoints"
import { cleanSnippet, formatLocation, formatScore } from "@/lib/format"

/** Cosine similarity as a small meter, with the exact value for those who want it. */
function Relevance({ score }: { score: number }) {
  const width = `${Math.max(8, Math.min(100, score * 100))}%`
  return (
    <span
      className="flex items-center gap-2 text-xs text-muted-foreground"
      title={`Similarity ${formatScore(score)}`}
    >
      <span className="h-1.5 w-14 overflow-hidden rounded-full bg-muted" aria-hidden>
        <span className="block h-full rounded-full bg-primary/70" style={{ width }} />
      </span>
      <span className="tabular-nums">{formatScore(score)}</span>
    </span>
  )
}

export function SearchPanel({ workspaceId }: { workspaceId: string }) {
  const [query, setQuery] = useState("")
  const search = useMutation({
    mutationFn: (text: string) => searchApi.search(workspaceId, { query: text }),
  })

  return (
    <div className="space-y-5">
      <form
        role="search"
        className="flex flex-col gap-2 sm:flex-row"
        onSubmit={(event) => {
          event.preventDefault()
          if (query.trim()) search.mutate(query.trim())
        }}
      >
        <div className="relative flex-1">
          <Search
            className="pointer-events-none absolute top-1/2 left-3 size-4 -translate-y-1/2 text-muted-foreground"
            aria-hidden
          />
          <Input
            id="search-query"
            aria-label="Search by meaning"
            placeholder="Describe what you're looking for, e.g. how long refunds take"
            value={query}
            maxLength={1000}
            className="h-10 pl-9"
            onChange={(event) => setQuery(event.target.value)}
          />
        </div>
        <Button
          type="submit"
          size="lg"
          className="h-10"
          disabled={search.isPending || !query.trim()}
        >
          {search.isPending ? (
            <Loader2 className="animate-spin" aria-hidden />
          ) : (
            <Sparkles aria-hidden />
          )}
          Search
        </Button>
      </form>

      <div aria-live="polite">
        {search.isIdle && (
          <p className="text-sm text-muted-foreground">
            Semantic search finds passages that match the meaning of your query, not just its
            keywords. Only documents that finished processing are searchable.
          </p>
        )}
        {search.isPending && <ListSkeleton rows={3} label="Searching" />}
        {search.isError && (
          <ErrorState
            title="Search failed"
            error={search.error}
            onRetry={() => search.mutate(search.variables)}
          />
        )}
        {search.isSuccess && search.data.results.length === 0 && (
          <EmptyState
            icon={SearchX}
            title="No relevant passages"
            description="Nothing in this workspace passed the relevance threshold. Try other wording."
          />
        )}
        {search.isSuccess && search.data.results.length > 0 && (
          <div className="space-y-3">
            <p className="text-xs text-muted-foreground">
              {search.data.results.length}{" "}
              {search.data.results.length === 1 ? "passage" : "passages"}, most relevant first
            </p>
            <ol className="space-y-2.5">
              {search.data.results.map((result) => (
                <li
                  key={`${result.document_id}-${result.chunk_index}`}
                  className="rounded-xl border bg-card p-4 shadow-xs"
                >
                  <div className="mb-2 flex items-center gap-3">
                    <FileTypeIcon filename={result.filename} className="size-7" />
                    <div className="min-w-0 flex-1">
                      <Link
                        href={`/knowledge/${result.document_id}`}
                        className="block truncate text-sm font-medium hover:underline"
                      >
                        {result.filename}
                      </Link>
                      <p className="text-xs text-muted-foreground">
                        {formatLocation(result.page, result.chunk_index)}
                      </p>
                    </div>
                    <Relevance score={result.score} />
                  </div>
                  <p className="text-sm leading-relaxed text-muted-foreground">
                    {cleanSnippet(result.snippet)}
                  </p>
                </li>
              ))}
            </ol>
          </div>
        )}
      </div>
    </div>
  )
}
