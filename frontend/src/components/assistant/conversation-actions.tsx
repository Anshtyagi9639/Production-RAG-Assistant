"use client"

import { useMutation, useQueryClient } from "@tanstack/react-query"
import { Loader2, MoreHorizontal, Pencil, Trash2 } from "lucide-react"
import { useState } from "react"
import { toast } from "sonner"

import { FormError } from "@/components/auth/form-error"
import {
  AlertDialog,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog"
import { Button } from "@/components/ui/button"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import { Input } from "@/components/ui/input"
import { chatApi } from "@/lib/api/endpoints"
import type { ConversationSummary } from "@/lib/api/types"
import { queryKeys } from "@/lib/query-keys"

/** Rename / delete menu for one conversation in the history list. */
export function ConversationActions({
  workspaceId,
  conversation,
  onDeleted,
}: {
  workspaceId: string
  conversation: ConversationSummary
  /** Called after deletion, e.g. to leave the conversation if it was open. */
  onDeleted: () => void
}) {
  const queryClient = useQueryClient()
  const [dialog, setDialog] = useState<"rename" | "delete" | null>(null)
  const [title, setTitle] = useState(conversation.title)

  const refresh = () =>
    queryClient.invalidateQueries({ queryKey: queryKeys.workspace(workspaceId) })
  const rename = useMutation({
    mutationFn: () => chatApi.renameConversation(workspaceId, conversation.id, title),
    onSuccess: async () => {
      setDialog(null)
      await refresh()
    },
  })
  const remove = useMutation({
    mutationFn: () => chatApi.deleteConversation(workspaceId, conversation.id),
    onSuccess: async () => {
      setDialog(null)
      toast.success("Conversation deleted")
      onDeleted()
      queryClient.removeQueries({ queryKey: queryKeys.conversation(workspaceId, conversation.id) })
      await refresh()
    },
  })
  const busy = rename.isPending || remove.isPending

  return (
    <>
      <DropdownMenu>
        <DropdownMenuTrigger asChild>
          <Button
            variant="ghost"
            size="icon-xs"
            className="text-muted-foreground opacity-0 group-focus-within/conversation:opacity-100 group-hover/conversation:opacity-100 aria-expanded:opacity-100 max-lg:opacity-100"
            aria-label={`Actions for ${conversation.title}`}
          >
            <MoreHorizontal aria-hidden />
          </Button>
        </DropdownMenuTrigger>
        <DropdownMenuContent align="end" className="w-40">
          <DropdownMenuItem
            onSelect={() => {
              setTitle(conversation.title)
              rename.reset()
              setDialog("rename")
            }}
          >
            <Pencil aria-hidden />
            Rename
          </DropdownMenuItem>
          <DropdownMenuItem
            variant="destructive"
            onSelect={() => {
              remove.reset()
              setDialog("delete")
            }}
          >
            <Trash2 aria-hidden />
            Delete
          </DropdownMenuItem>
        </DropdownMenuContent>
      </DropdownMenu>

      <Dialog open={dialog === "rename"} onOpenChange={(open) => !busy && !open && setDialog(null)}>
        <DialogContent className="sm:max-w-md">
          <form
            onSubmit={(event) => {
              event.preventDefault()
              if (title.trim()) rename.mutate()
            }}
            className="space-y-4"
          >
            <DialogHeader>
              <DialogTitle>Rename conversation</DialogTitle>
              <DialogDescription>Only you can see your conversations.</DialogDescription>
            </DialogHeader>
            <Input
              aria-label="Conversation title"
              value={title}
              maxLength={200}
              autoFocus
              onChange={(event) => setTitle(event.target.value)}
            />
            <FormError error={rename.error} />
            <DialogFooter>
              <Button
                type="button"
                variant="outline"
                onClick={() => setDialog(null)}
                disabled={busy}
              >
                Cancel
              </Button>
              <Button type="submit" disabled={busy || !title.trim()}>
                {rename.isPending && <Loader2 className="animate-spin" aria-hidden />}
                Save
              </Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>

      <AlertDialog
        open={dialog === "delete"}
        onOpenChange={(open) => !busy && !open && setDialog(null)}
      >
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Delete this conversation?</AlertDialogTitle>
            <AlertDialogDescription>
              &ldquo;{conversation.title}&rdquo; and all its messages are removed, and their token
              usage no longer counts toward the workspace totals. This can&apos;t be undone.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <FormError error={remove.error} />
          <AlertDialogFooter>
            <AlertDialogCancel disabled={busy}>Cancel</AlertDialogCancel>
            <Button variant="destructive" onClick={() => remove.mutate()} disabled={busy}>
              {remove.isPending && <Loader2 className="animate-spin" aria-hidden />}
              Delete conversation
            </Button>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </>
  )
}
