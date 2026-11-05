"use client"

import { useQuery } from "@tanstack/react-query"
import { Check, ChevronDown, FileText, Library, Lock } from "lucide-react"

import { FileTypeIcon } from "@/components/documents/file-type-icon"
import { Button } from "@/components/ui/button"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import { documentsApi } from "@/lib/api/endpoints"
import type { ScopeDocument } from "@/lib/api/types"
import { queryKeys } from "@/lib/query-keys"

// Ready documents offered in the picker. Enough for the menu; larger workspaces would need
// a searchable picker.
const PICKER_LIMIT = 100

/**
 * Which documents answers come from. Chosen before the first question of a conversation; after
 * that the conversation keeps it (the API rejects changes), so it is shown read-only.
 */
export function ScopePicker({
  workspaceId,
  selected,
  onSelect,
  locked,
}: {
  workspaceId: string
  /** The chosen document for a new conversation (null: all documents). */
  selected: ScopeDocument | null
  onSelect: (document: ScopeDocument | null) => void
  /** An existing conversation's scope: shown, not editable. undefined for a new conversation. */
  locked?: ScopeDocument[] | null
}) {
  const params = { page: 1, pageSize: PICKER_LIMIT, sort: "filename", status: "COMPLETED" } as const
  const documents = useQuery({
    queryKey: queryKeys.documents(workspaceId, params),
    queryFn: () => documentsApi.list(workspaceId, params),
    enabled: locked === undefined,
  })

  if (locked !== undefined) {
    return (
      <p className="flex min-w-0 items-center gap-1.5 text-xs text-muted-foreground">
        <Lock className="size-3 shrink-0" aria-hidden />
        <span className="shrink-0">Answers only from</span>
        {locked === null ? (
          <span className="font-medium text-foreground">all documents</span>
        ) : (
          <span className="truncate font-medium text-foreground">
            {locked.map((item) => item.filename).join(", ")}
          </span>
        )}
      </p>
    )
  }

  return (
    <div className="flex min-w-0 items-center gap-2 text-xs text-muted-foreground">
      <span className="shrink-0">Answer from</span>
      <DropdownMenu>
        <DropdownMenuTrigger asChild>
          <Button variant="outline" size="xs" className="min-w-0 bg-card">
            {selected ? (
              <FileTypeIcon
                filename={selected.filename}
                className="size-4 rounded [&_svg]:size-2.5"
              />
            ) : (
              <Library aria-hidden />
            )}
            <span className="truncate">{selected ? selected.filename : "All documents"}</span>
            <ChevronDown aria-hidden />
          </Button>
        </DropdownMenuTrigger>
        <DropdownMenuContent align="start" className="max-h-80 w-72 overflow-y-auto">
          <DropdownMenuItem onSelect={() => onSelect(null)}>
            <Library aria-hidden />
            <span className="flex-1">All documents</span>
            {selected === null && <Check aria-hidden />}
          </DropdownMenuItem>
          <DropdownMenuSeparator />
          <DropdownMenuLabel className="text-xs font-normal text-muted-foreground">
            Only one document
          </DropdownMenuLabel>
          {documents.isPending && (
            <p className="px-2 py-1.5 text-xs text-muted-foreground">Loading documents…</p>
          )}
          {documents.isSuccess && documents.data.items.length === 0 && (
            <p className="px-2 py-1.5 text-xs text-muted-foreground">No ready documents yet.</p>
          )}
          {documents.data?.items.map((document) => (
            <DropdownMenuItem
              key={document.id}
              onSelect={() => onSelect({ document_id: document.id, filename: document.filename })}
            >
              <FileText aria-hidden />
              <span className="min-w-0 flex-1 truncate">{document.filename}</span>
              {selected?.document_id === document.id && <Check aria-hidden />}
            </DropdownMenuItem>
          ))}
        </DropdownMenuContent>
      </DropdownMenu>
      <span className="hidden truncate sm:inline">
        {selected ? "Other documents are ignored." : "Searches every ready document."}
      </span>
    </div>
  )
}
