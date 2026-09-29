"use client"

import { useMutation } from "@tanstack/react-query"
import { Loader2, Search, SearchX } from "lucide-react"
import Link from "next/link"
import { useState } from "react"

import { EmptyState, ErrorState, ListSkeleton } from "@/components/states"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { searchApi } from "@/lib/api/endpoints"
import { formatLocation, formatScore } from "@/lib/format"

export function SearchPanel({ workspaceId }: { workspaceId: string }) {
  const [query, setQuery] = useState("")
  const search = useMutation({
    mutationFn: (text: string) => searchApi.search(workspaceId, { query: text }),
  })

  return (
    <div className="space-y-4">
      <form
        role="search"
        className="flex flex-col gap-2 sm:flex-row sm:items-end"
        onSubmit={(event) => {
          event.preventDefault()
          if (query.trim()) search.mutate(query.trim())
        }}
      >
        <div className="flex-1 space-y-1.5">
          <Label htmlFor="search-query">Search by meaning</Label>
          <Input
            id="search-query"
            placeholder="e.g. How long do refunds take?"
            value={query}
            maxLength={1000}
            onChange={(event) => setQuery(event.target.value)}
          />
        </div>
        <Button type="submit" disabled={search.isPending || !query.trim()}>
          {search.isPending ? (
            <Loader2 className="animate-spin" aria-hidden />
          ) : (
            <Search aria-hidden />
          )}
          Search
        </Button>
      </form>

      <div aria-live="polite">
        {search.isIdle && (
          <p className="text-sm text-muted-foreground">
            Search finds passages that match the meaning of your query, not just its keywords. Only
            documents that finished processing are searchable.
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
          <ol className="space-y-3">
            {search.data.results.map((result) => (
              <li
                key={`${result.document_id}-${result.chunk_index}`}
                className="space-y-2 rounded-lg border bg-card p-4"
              >
                <div className="flex flex-wrap items-center gap-x-3 gap-y-1 text-sm">
                  <Link
                    href={`/knowledge/${result.document_id}`}
                    className="font-medium hover:underline"
                  >
                    {result.filename}
                  </Link>
                  <span className="text-muted-foreground">
                    {formatLocation(result.page, result.chunk_index)}
                  </span>
                  <Badge variant="outline" className="ml-auto tabular-nums">
                    Score {formatScore(result.score)}
                  </Badge>
                </div>
                <p className="text-sm leading-relaxed text-muted-foreground">{result.snippet}</p>
              </li>
            ))}
          </ol>
        )}
      </div>
    </div>
  )
}
