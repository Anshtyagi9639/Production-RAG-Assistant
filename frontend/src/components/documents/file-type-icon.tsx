import { FileCode2, FileText, FileType2, type LucideIcon } from "lucide-react"

import { type FileKind, fileKind } from "@/lib/format"
import { cn } from "@/lib/utils"

const ICONS: Record<FileKind, { icon: LucideIcon; tone: string }> = {
  pdf: { icon: FileText, tone: "bg-destructive/8 text-destructive" },
  docx: { icon: FileType2, tone: "bg-info/10 text-info" },
  markdown: { icon: FileCode2, tone: "bg-success/10 text-success" },
  text: { icon: FileText, tone: "bg-muted text-muted-foreground" },
  file: { icon: FileText, tone: "bg-muted text-muted-foreground" },
}

export function FileTypeIcon({
  filename,
  contentType,
  className,
}: {
  filename: string
  contentType?: string
  className?: string
}) {
  const { icon: Icon, tone } = ICONS[fileKind(filename, contentType)]
  return (
    <span
      className={cn("flex size-8 shrink-0 items-center justify-center rounded-md", tone, className)}
    >
      <Icon className="size-4" aria-hidden />
    </span>
  )
}
