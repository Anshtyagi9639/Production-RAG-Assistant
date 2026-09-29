"use client"

import { useQueryClient } from "@tanstack/react-query"
import { CheckCircle2, CircleAlert, FileUp, Loader2 } from "lucide-react"
import { useRef, useState } from "react"

import { errorMessage } from "@/components/states"
import { Button } from "@/components/ui/button"
import { documentsApi } from "@/lib/api/endpoints"
import { queryKeys } from "@/lib/query-keys"
import { cn } from "@/lib/utils"

// Mirrors the backend's allow-list; the backend also checks magic bytes and size.
const ACCEPTED_EXTENSIONS = [".pdf", ".docx", ".txt", ".md"]

interface Upload {
  key: string
  name: string
  status: "uploading" | "done" | "error"
  message?: string
}

function extension(name: string): string {
  const dot = name.lastIndexOf(".")
  return dot === -1 ? "" : name.slice(dot).toLowerCase()
}

export function UploadDropzone({ workspaceId }: { workspaceId: string }) {
  const queryClient = useQueryClient()
  const inputRef = useRef<HTMLInputElement>(null)
  const [dragging, setDragging] = useState(false)
  const [uploads, setUploads] = useState<Upload[]>([])

  const update = (key: string, patch: Partial<Upload>) =>
    setUploads((current) => current.map((u) => (u.key === key ? { ...u, ...patch } : u)))

  const uploadFiles = async (files: File[]) => {
    const started = files.map((file) => ({ file, key: crypto.randomUUID() }))
    setUploads((current) => [
      ...started.map(({ file, key }) =>
        ACCEPTED_EXTENSIONS.includes(extension(file.name))
          ? { key, name: file.name, status: "uploading" as const }
          : {
              key,
              name: file.name,
              status: "error" as const,
              message: "Unsupported file type. Use PDF, DOCX, TXT or MD.",
            },
      ),
      ...current,
    ])
    for (const { file, key } of started) {
      if (!ACCEPTED_EXTENSIONS.includes(extension(file.name))) continue
      try {
        await documentsApi.upload(workspaceId, file)
        update(key, { status: "done", message: "Uploaded. Processing has started." })
      } catch (error) {
        update(key, { status: "error", message: errorMessage(error) })
      }
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
          "flex flex-col items-center justify-center gap-3 rounded-lg border border-dashed bg-card px-6 py-8 text-center transition-colors",
          dragging && "border-primary bg-accent",
        )}
      >
        <FileUp className="size-6 text-muted-foreground" aria-hidden />
        <div className="space-y-1">
          <p className="text-sm font-medium">Drag and drop files here</p>
          <p className="text-xs text-muted-foreground">PDF, DOCX, TXT or Markdown</p>
        </div>
        <Button variant="outline" size="sm" onClick={() => inputRef.current?.click()}>
          Choose files
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
        <div className="rounded-lg border bg-card">
          <div className="flex items-center justify-between border-b px-3 py-2">
            <p className="text-sm font-medium">Uploads</p>
            <Button
              variant="ghost"
              size="xs"
              onClick={() =>
                setUploads((current) => current.filter((u) => u.status === "uploading"))
              }
            >
              Clear finished
            </Button>
          </div>
          <ul aria-live="polite" className="divide-y">
            {uploads.map((upload) => (
              <li key={upload.key} className="flex items-start gap-2 px-3 py-2 text-sm">
                {upload.status === "uploading" && (
                  <Loader2
                    className="mt-0.5 size-4 shrink-0 animate-spin text-primary"
                    aria-hidden
                  />
                )}
                {upload.status === "done" && (
                  <CheckCircle2 className="mt-0.5 size-4 shrink-0 text-primary" aria-hidden />
                )}
                {upload.status === "error" && (
                  <CircleAlert className="mt-0.5 size-4 shrink-0 text-destructive" aria-hidden />
                )}
                <div className="min-w-0">
                  <p className="truncate font-medium">{upload.name}</p>
                  <p
                    className={cn(
                      "text-xs text-muted-foreground",
                      upload.status === "error" && "text-destructive",
                    )}
                  >
                    {upload.status === "uploading" ? "Uploading…" : upload.message}
                  </p>
                </div>
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  )
}
