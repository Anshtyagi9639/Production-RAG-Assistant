"use client"

import { useQueryClient } from "@tanstack/react-query"
import { CheckCircle2, CircleAlert, CloudUpload, X } from "lucide-react"
import Link from "next/link"
import { useImperativeHandle, useRef, useState } from "react"
import { toast } from "sonner"

import { FileTypeIcon } from "@/components/documents/file-type-icon"
import { ProcessingStatus } from "@/components/documents/processing-status"
import { errorMessage } from "@/components/states"
import { Button } from "@/components/ui/button"
import { documentsApi } from "@/lib/api/endpoints"
import { formatBytes } from "@/lib/format"
import { queryKeys } from "@/lib/query-keys"
import { cn } from "@/lib/utils"

// Mirrors the backend's allow-list; the backend also checks magic bytes and size.
const ACCEPTED_EXTENSIONS = [".pdf", ".docx", ".txt", ".md"]

interface Upload {
  key: string
  name: string
  size: number
  status: "uploading" | "done" | "error"
  /** Fraction of the file sent (0-1); undefined until the browser reports any. */
  progress?: number
  message?: string
  documentId?: string
}

export interface UploadDropzoneHandle {
  /** Open the file picker (used by the page's Upload button). */
  openPicker: () => void
}

/** Byte progress while the file is sent; indeterminate before the first report and while the
 * server finishes (stores the file and queues it) after the last byte. */
function UploadProgressBar({ name, progress }: { name: string; progress?: number }) {
  const sending = progress !== undefined && progress < 1
  const percent = Math.round((progress ?? 0) * 100)
  return (
    <div className="flex items-center gap-2">
      <div
        className="h-1.5 flex-1 overflow-hidden rounded-full bg-muted"
        role="progressbar"
        aria-label={`Uploading ${name}`}
        aria-valuemin={0}
        aria-valuemax={100}
        aria-valuenow={sending ? percent : undefined}
      >
        {sending ? (
          <div
            className="h-full rounded-full bg-primary transition-[width] duration-200 ease-out"
            style={{ width: `${percent}%` }}
          />
        ) : (
          <div className="h-full w-1/3 animate-[upload_1.2s_ease-in-out_infinite] rounded-full bg-primary" />
        )}
      </div>
      <span className="w-16 shrink-0 text-right text-xs text-muted-foreground tabular-nums">
        {sending ? `${percent}%` : progress === undefined ? "Starting…" : "Finishing…"}
      </span>
    </div>
  )
}

function extension(name: string): string {
  const dot = name.lastIndexOf(".")
  return dot === -1 ? "" : name.slice(dot).toLowerCase()
}

export function UploadDropzone({
  workspaceId,
  compact = false,
  ref,
}: {
  workspaceId: string
  /** A slim bar instead of the large drop area (when the workspace already has documents). */
  compact?: boolean
  ref?: React.Ref<UploadDropzoneHandle>
}) {
  const queryClient = useQueryClient()
  const inputRef = useRef<HTMLInputElement>(null)
  const [dragging, setDragging] = useState(false)
  const [uploads, setUploads] = useState<Upload[]>([])

  useImperativeHandle(ref, () => ({ openPicker: () => inputRef.current?.click() }), [])

  const update = (key: string, patch: Partial<Upload>) =>
    setUploads((current) => current.map((u) => (u.key === key ? { ...u, ...patch } : u)))

  const uploadFiles = async (files: File[]) => {
    if (files.length === 0) return
    const started = files.map((file) => ({ file, key: crypto.randomUUID() }))
    setUploads((current) => [
      ...started.map(({ file, key }) =>
        ACCEPTED_EXTENSIONS.includes(extension(file.name))
          ? { key, name: file.name, size: file.size, status: "uploading" as const }
          : {
              key,
              name: file.name,
              size: file.size,
              status: "error" as const,
              message: "Unsupported file type. Use PDF, DOCX, TXT or Markdown.",
            },
      ),
      ...current,
    ])
    let uploaded = 0
    for (const { file, key } of started) {
      if (!ACCEPTED_EXTENSIONS.includes(extension(file.name))) continue
      try {
        const created = await documentsApi.upload(workspaceId, file, (progress) =>
          update(key, { progress }),
        )
        uploaded += 1
        update(key, {
          status: "done",
          message: "Uploaded. Processing has started.",
          documentId: created.id,
        })
      } catch (error) {
        update(key, { status: "error", message: errorMessage(error) })
      }
    }
    if (uploaded > 0) {
      toast.success(uploaded === 1 ? "Document uploaded" : `${uploaded} documents uploaded`, {
        description: "Processing has started. Status updates automatically.",
      })
    }
    await queryClient.invalidateQueries({ queryKey: queryKeys.workspace(workspaceId) })
  }

  return (
    <div className="space-y-3">
      <div
        onDragOver={(event) => {
          event.preventDefault()
          setDragging(true)
        }}
        onDragLeave={() => setDragging(false)}
        onDrop={(event) => {
          event.preventDefault()
          setDragging(false)
          void uploadFiles(Array.from(event.dataTransfer.files))
        }}
        className={cn(
          "flex rounded-xl border border-dashed bg-card transition-colors",
          compact
            ? "flex-col items-start gap-3 px-4 py-3 sm:flex-row sm:items-center"
            : "flex-col items-center justify-center gap-3 px-6 py-10 text-center",
          dragging && "border-primary bg-accent/60",
        )}
      >
        <span
          className={cn(
            "flex shrink-0 items-center justify-center rounded-lg border bg-background shadow-xs",
            compact ? "size-9" : "size-11",
          )}
        >
          <CloudUpload className={cn("text-primary", compact ? "size-4" : "size-5")} aria-hidden />
        </span>
        <div className={cn("space-y-0.5", compact && "flex-1")}>
          <p className="text-sm font-medium">
            {dragging ? "Drop to upload" : "Drop files here, or browse"}
          </p>
          <p className="text-xs text-muted-foreground">
            PDF, Word (.docx), TXT or Markdown. Files are processed and indexed automatically.
          </p>
        </div>
        <Button variant="outline" size="sm" onClick={() => inputRef.current?.click()}>
          Browse files
        </Button>
        <input
          ref={inputRef}
          type="file"
          multiple
          accept={ACCEPTED_EXTENSIONS.join(",")}
          className="sr-only"
          tabIndex={-1}
          aria-hidden
          onChange={(event) => {
            const files = Array.from(event.target.files ?? [])
            event.target.value = ""
            void uploadFiles(files)
          }}
        />
      </div>

      {uploads.length > 0 && (
        <section aria-label="Uploads" className="rounded-xl border bg-card shadow-xs">
          <div className="flex items-center justify-between border-b px-4 py-2.5">
            <p className="text-sm font-medium">Uploads</p>
            <Button
              variant="ghost"
              size="xs"
              onClick={() =>
                setUploads((current) => current.filter((u) => u.status === "uploading"))
              }
            >
              <X aria-hidden />
              Clear finished
            </Button>
          </div>
          <ul aria-live="polite" className="divide-y">
            {uploads.map((upload) => (
              <li key={upload.key} className="flex items-center gap-3 px-4 py-2.5 text-sm">
                <FileTypeIcon filename={upload.name} />
                <div className="min-w-0 flex-1 space-y-1">
                  <div className="flex items-center gap-2">
                    <p className="min-w-0 flex-1 truncate font-medium">{upload.name}</p>
                    <span className="shrink-0 text-xs text-muted-foreground tabular-nums">
                      {formatBytes(upload.size)}
                    </span>
                  </div>
                  {upload.status === "uploading" ? (
                    <UploadProgressBar name={upload.name} progress={upload.progress} />
                  ) : upload.documentId ? (
                    <ProcessingStatus workspaceId={workspaceId} documentId={upload.documentId} />
                  ) : (
                    <p
                      className={cn(
                        "flex items-center gap-1 text-xs",
                        upload.status === "error" ? "text-destructive" : "text-success",
                      )}
                    >
                      {upload.status === "error" ? (
                        <CircleAlert className="size-3.5 shrink-0" aria-hidden />
                      ) : (
                        <CheckCircle2 className="size-3.5 shrink-0" aria-hidden />
                      )}
                      {upload.message}
                      {upload.documentId && (
                        <Link
                          href={`/knowledge/${upload.documentId}`}
                          className="ml-1 font-medium text-primary underline-offset-2 hover:underline"
                        >
                          View
                        </Link>
                      )}
                    </p>
                  )}
                </div>
              </li>
            ))}
          </ul>
        </section>
      )}
    </div>
  )
}
