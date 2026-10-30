"use client"

import Link from "next/link"
import { useEffect, useRef } from "react"

import { FileTypeIcon } from "@/components/documents/file-type-icon"
import type { Source } from "@/lib/api/types"
import { cleanSnippet, formatLocation, formatScore } from "@/lib/format"
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
    <ol className="space-y-2.5">
      {sources.map((source) => {
        const active = source.index === activeIndex
        return (
          <li
            key={source.index}
            ref={active ? activeRef : undefined}
            className={cn(
              "rounded-xl border bg-card p-3.5 transition-colors",
              active ? "border-primary/60 shadow-sm ring-3 ring-ring/15" : "shadow-xs",
            )}
          >
            <div className="mb-2 flex items-start gap-2.5">
              <span
                className={cn(
                  "flex size-5 shrink-0 items-center justify-center rounded-md border border-primary/20 bg-accent text-[10.5px] font-semibold text-accent-foreground tabular-nums",
                  active && "border-primary bg-primary text-primary-foreground",
                )}
              >
                {source.index}
              </span>
              <div className="min-w-0 flex-1">
                <Link
                  href={`/knowledge/${source.document_id}`}
                  className="flex items-center gap-1.5 text-sm font-medium hover:underline"
                >
                  <FileTypeIcon
                    filename={source.filename}
                    className="size-5 rounded [&_svg]:size-3"
                  />
                  <span className="truncate">{source.filename}</span>
                </Link>
                <p className="mt-0.5 text-xs text-muted-foreground">
                  {formatLocation(source.page, source.chunk_index)} · relevance{" "}
                  <span className="tabular-nums">{formatScore(source.score)}</span>
                </p>
              </div>
            </div>
            <blockquote className="border-l-2 border-primary/25 pl-3 text-xs leading-relaxed text-muted-foreground">
              {cleanSnippet(source.snippet)}
            </blockquote>
          </li>
        )
      })}
    </ol>
  )
}
