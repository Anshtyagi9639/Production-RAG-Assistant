"use client"

import { useMutation, useQueryClient } from "@tanstack/react-query"
import { Loader2, Trash2 } from "lucide-react"
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
  AlertDialogTrigger,
} from "@/components/ui/alert-dialog"
import { Button } from "@/components/ui/button"
import { documentsApi } from "@/lib/api/endpoints"
import type { Document } from "@/lib/api/types"
import { queryKeys } from "@/lib/query-keys"

export function DeleteDocumentDialog({
  workspaceId,
  document,
  onDeleted,
  showLabel = false,
}: {
  workspaceId: string
  document: Pick<Document, "id" | "filename">
  onDeleted?: () => void
  showLabel?: boolean
}) {
  const queryClient = useQueryClient()
  const [open, setOpen] = useState(false)
  const remove = useMutation({
    mutationFn: () => documentsApi.remove(workspaceId, document.id),
    onSuccess: async () => {
      setOpen(false)
      toast.success(`Deleted ${document.filename}`)
      onDeleted?.()
      queryClient.removeQueries({ queryKey: queryKeys.document(workspaceId, document.id) })
      await queryClient.invalidateQueries({ queryKey: queryKeys.workspace(workspaceId) })
    },
  })

  return (
    <AlertDialog
      open={open}
      onOpenChange={(next) => {
        if (!remove.isPending) setOpen(next)
        if (!next) remove.reset()
      }}
    >
      <AlertDialogTrigger asChild>
        <Button
          variant={showLabel ? "destructive" : "ghost"}
          size={showLabel ? "default" : "icon-sm"}
          aria-label={showLabel ? undefined : `Delete ${document.filename}`}
        >
          <Trash2 aria-hidden />
          {showLabel && "Delete"}
        </Button>
      </AlertDialogTrigger>
      <AlertDialogContent>
        <AlertDialogHeader>
          <AlertDialogTitle>Delete {document.filename}?</AlertDialogTitle>
          <AlertDialogDescription>
            The file, its indexed passages and its search vectors are removed. Answers can no longer
            cite it. This can&apos;t be undone.
          </AlertDialogDescription>
        </AlertDialogHeader>
        <FormError error={remove.error} />
        <AlertDialogFooter>
          <AlertDialogCancel disabled={remove.isPending}>Cancel</AlertDialogCancel>
          <Button variant="destructive" onClick={() => remove.mutate()} disabled={remove.isPending}>
            {remove.isPending && <Loader2 className="animate-spin" aria-hidden />}
            Delete document
          </Button>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  )
}
