"use client"

import Link from "next/link"
import { useEffect, useRef } from "react"

import { Badge } from "@/components/ui/badge"
import type { Source } from "@/lib/api/types"
import { formatLocation, formatScore } from "@/lib/format"
import { cn } from "@/lib/utils"

/** Retrieved passages an answer was grounded on, numbered to match its [n] citations. */
export function SourcesList({
  sources,
  activeIndex,
}: {
  sources: Source[]
  activeIndex?: number | null
}) {
  const activeRef = useRef<HTMLLIElement>(null)
  useEffect(() => {
    activeRef.current?.scrollIntoView({ block: "nearest", behavior: "smooth" })
  }, [activeIndex])

  return (
    <ol className="space-y-3">
      {sources.map((source) => (
        <li
          key={source.index}
          ref={source.index === activeIndex ? activeRef : undefined}
          className={cn(
            "space-y-2 rounded-lg border bg-card p-3 transition-colors",
            source.index === activeIndex && "border-primary ring-3 ring-ring/20",
          )}
        >
          <div className="flex items-start gap-2">
            <span className="flex size-5 shrink-0 items-center justify-center rounded border text-[11px] font-medium text-primary tabular-nums">
              {source.index}
            </span>
            <div className="min-w-0 flex-1">
              <Link
                href={`/knowledge/${source.document_id}`}
                className="block truncate text-sm font-medium hover:underline"
              >
                {source.filename}
              </Link>
              <p className="text-xs text-muted-foreground">
                {formatLocation(source.page, source.chunk_index)}
              </p>
            </div>
            <Badge variant="outline" className="tabular-nums">
              {formatScore(source.score)}
            </Badge>
          </div>
          <p className="text-xs leading-relaxed text-muted-foreground">{source.snippet}</p>
        </li>
      ))}
    </ol>
  )
}
