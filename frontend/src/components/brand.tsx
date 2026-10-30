import { BookOpenText } from "lucide-react"

import { cn } from "@/lib/utils"

/** The product mark: an open book on the accent colour. */
export function BrandMark({ className }: { className?: string }) {
  return (
    <span
      className={cn(
        "flex size-7 shrink-0 items-center justify-center rounded-lg bg-primary text-primary-foreground shadow-xs",
        className,
      )}
    >
      <BookOpenText className="size-4" aria-hidden />
    </span>
  )
}

export function BrandName({ className }: { className?: string }) {
  return <span className={cn("font-semibold tracking-tight", className)}>Knowledge Copilot</span>
}
