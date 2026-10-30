import { cn } from "@/lib/utils"

export function PageHeader({
  className,
  title,
  description,
  badge,
  actions,
  documentTitle,
}: {
  title: string
  description?: React.ReactNode
  badge?: React.ReactNode
  actions?: React.ReactNode
  /** The browser tab title, when it should differ from the heading. */
  documentTitle?: string
  className?: string
}) {
  return (
    <header
      className={cn(
        "mb-6 flex flex-col gap-4 sm:mb-8 sm:flex-row sm:items-end sm:justify-between",
        className,
      )}
    >
      <title>{`${documentTitle ?? title} · Knowledge Copilot`}</title>
      <div className="min-w-0 space-y-1.5">
        <div className="flex flex-wrap items-center gap-2.5">
          <h1 className="text-2xl font-semibold tracking-tight text-balance break-words">
            {title}
          </h1>
          {badge}
        </div>
        {description && (
          <p className="max-w-2xl text-sm leading-relaxed text-muted-foreground">{description}</p>
        )}
      </div>
      {actions && <div className="flex shrink-0 flex-wrap items-center gap-2">{actions}</div>}
    </header>
  )
}
