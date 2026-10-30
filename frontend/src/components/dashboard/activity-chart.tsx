"use client"

import { BarChart3, Table2 } from "lucide-react"
import { useMemo, useState } from "react"

import { rangeStart } from "@/components/dashboard/use-dashboard-activity"
import { EmptyState } from "@/components/states"
import { Button } from "@/components/ui/button"
import type { ActivityEntry } from "@/lib/api/types"
import { formatNumber } from "@/lib/format"
import { cn } from "@/lib/utils"

/**
 * Daily workspace usage as stacked bars. Series colours are the first three slots of the
 * validated categorical palette, in fixed order (they follow the series, never its rank).
 * The aqua slot is under 3:1 against the surface, so values are always also reachable as text
 * (legend totals, tooltip, table view).
 */
export const SERIES = [
  { key: "documents", action: "document.uploaded", label: "Documents added", color: "#2a78d6" },
  { key: "questions", action: "chat.answered", label: "Questions answered", color: "#eb6834" },
  { key: "agent", action: "agent.run_started", label: "Agent runs", color: "#1baf7a" },
] as const

type SeriesKey = (typeof SERIES)[number]["key"]
type Day = { key: string; date: Date } & Record<SeriesKey, number>

const PLOT_HEIGHT = 168
const weekdayDay = new Intl.DateTimeFormat(undefined, { weekday: "short", day: "numeric" })
const monthDay = new Intl.DateTimeFormat(undefined, { month: "short", day: "numeric" })
const fullDay = new Intl.DateTimeFormat(undefined, {
  weekday: "long",
  month: "long",
  day: "numeric",
})

function dayKey(date: Date): string {
  return `${date.getFullYear()}-${date.getMonth() + 1}-${date.getDate()}`
}

export function bucketByDay(entries: ActivityEntry[], days: number, now = new Date()): Day[] {
  const start = rangeStart(days, now)
  const buckets: Day[] = Array.from({ length: days }, (_, index) => {
    const date = new Date(start)
    date.setDate(start.getDate() + index)
    return { key: dayKey(date), date, documents: 0, questions: 0, agent: 0 }
  })
  const byKey = new Map(buckets.map((bucket) => [bucket.key, bucket]))
  for (const entry of entries) {
    const series = SERIES.find((item) => item.action === entry.action)
    if (!series) continue
    const bucket = byKey.get(dayKey(new Date(entry.created_at)))
    if (bucket) bucket[series.key] += 1
  }
  return buckets
}

/** A round axis maximum (1, 2, 5 × 10ⁿ) at or above the tallest bar. */
function niceMax(value: number): number {
  if (value <= 4) return 4
  const magnitude = 10 ** Math.floor(Math.log10(value))
  const step = [1, 2, 5, 10].find((m) => m * magnitude >= value) ?? 10
  return step * magnitude
}

function total(day: Day): number {
  return SERIES.reduce((sum, series) => sum + day[series.key], 0)
}

function Legend({ days }: { days: Day[] }) {
  return (
    <ul className="flex flex-wrap gap-x-5 gap-y-2" aria-label="Totals in this range">
      {SERIES.map((series) => (
        <li key={series.key} className="flex items-center gap-2 text-sm">
          <span
            aria-hidden
            className="size-2.5 rounded-[3px]"
            style={{ backgroundColor: series.color }}
          />
          <span className="text-muted-foreground">{series.label}</span>
          <span className="font-semibold tabular-nums">
            {formatNumber(days.reduce((sum, day) => sum + day[series.key], 0))}
          </span>
        </li>
      ))}
    </ul>
  )
}

function DayTooltip({ day }: { day: Day }) {
  return (
    <div className="pointer-events-none w-44 rounded-lg border bg-popover p-2.5 text-popover-foreground shadow-md">
      <p className="mb-1.5 text-xs font-medium">{fullDay.format(day.date)}</p>
      <ul className="space-y-1">
        {SERIES.map((series) => (
          <li key={series.key} className="flex items-center gap-2 text-xs">
            <span
              aria-hidden
              className="h-0.5 w-3 rounded-full"
              style={{ backgroundColor: series.color }}
            />
            <span className="flex-1 text-muted-foreground">{series.label}</span>
            <span className="font-semibold text-foreground tabular-nums">
              {formatNumber(day[series.key])}
            </span>
          </li>
        ))}
      </ul>
    </div>
  )
}

function Bars({ days }: { days: Day[] }) {
  const [active, setActive] = useState<number | null>(null)
  const max = niceMax(Math.max(...days.map(total)))
  // Label every day for a week; thin out longer ranges so labels never collide.
  const labelEvery = days.length <= 7 ? 1 : days.length <= 14 ? 2 : 5
  const format = days.length <= 7 ? weekdayDay : monthDay

  return (
    <div className="flex gap-2">
      {/* Recessive y-axis: three ticks on the same scale as the gridlines. */}
      <div
        aria-hidden
        className="flex w-6 shrink-0 flex-col justify-between text-right text-[11px] text-muted-foreground tabular-nums"
        style={{ height: PLOT_HEIGHT }}
      >
        <span className="-translate-y-1/2">{max}</span>
        <span>{max / 2}</span>
        <span className="translate-y-1/2">0</span>
      </div>
      <div className="min-w-0 flex-1">
        <div className="relative" style={{ height: PLOT_HEIGHT }}>
          <div aria-hidden className="absolute inset-0 flex flex-col justify-between">
            <span className="border-t border-dashed border-border" />
            <span className="border-t border-dashed border-border" />
            <span className="border-t border-border" />
          </div>
          <ol
            className="relative flex h-full items-end gap-[2px] sm:gap-1"
            onPointerLeave={() => setActive(null)}
          >
            {days.map((day, index) => {
              const dayTotal = total(day)
              const segments = SERIES.filter((series) => day[series.key] > 0)
              const label = `${fullDay.format(day.date)}: ${SERIES.map(
                (series) => `${day[series.key]} ${series.label.toLowerCase()}`,
              ).join(", ")}`
              return (
                <li
                  key={day.key}
                  tabIndex={0}
                  aria-label={label}
                  onPointerEnter={() => setActive(index)}
                  onFocus={() => setActive(index)}
                  onBlur={() => setActive(null)}
                  // The whole column is the hit target, not just the painted bar.
                  className={cn(
                    "group/bar relative flex h-full min-w-0 flex-1 flex-col justify-end rounded-sm outline-none focus-visible:ring-2 focus-visible:ring-ring/60",
                    active === index && "bg-muted/70",
                  )}
                >
                  {dayTotal > 0 && (
                    <div
                      className="mx-auto flex w-full max-w-7 flex-col-reverse gap-[2px]"
                      style={{ height: `${(dayTotal / max) * 100}%` }}
                    >
                      {segments.map((series, position) => (
                        <span
                          key={series.key}
                          className={cn(
                            "min-h-[2px] transition-opacity",
                            position === segments.length - 1 && "rounded-t-[4px]",
                            active !== null && active !== index && "opacity-60",
                          )}
                          style={{ backgroundColor: series.color, flexGrow: day[series.key] }}
                        />
                      ))}
                    </div>
                  )}
                  {active === index && (
                    <div
                      className={cn(
                        "absolute bottom-full z-10 mb-2",
                        index < days.length / 2 ? "left-0" : "right-0",
                      )}
                    >
                      <DayTooltip day={day} />
                    </div>
                  )}
                </li>
              )
            })}
          </ol>
        </div>
        <div aria-hidden className="mt-2 flex gap-[2px] sm:gap-1">
          {days.map((day, index) => (
            <span
              key={day.key}
              // The outermost labels align inward so they never spill past the plot.
              className={cn(
                "min-w-0 flex-1 overflow-visible text-[11px] whitespace-nowrap text-muted-foreground",
                index === days.length - 1
                  ? "text-right"
                  : index === 0
                    ? "text-left"
                    : "text-center",
              )}
            >
              {(days.length - 1 - index) % labelEvery === 0 ? format.format(day.date) : ""}
            </span>
          ))}
        </div>
      </div>
    </div>
  )
}

function DataTable({ days }: { days: Day[] }) {
  const rows = [...days].reverse()
  return (
    <div className="max-h-72 overflow-auto rounded-lg border">
      <table className="w-full text-sm">
        <caption className="sr-only">Daily activity</caption>
        <thead className="sticky top-0 bg-muted text-xs text-muted-foreground">
          <tr>
            <th scope="col" className="px-3 py-2 text-left font-medium">
              Day
            </th>
            {SERIES.map((series) => (
              <th key={series.key} scope="col" className="px-3 py-2 text-right font-medium">
                {series.label}
              </th>
            ))}
          </tr>
        </thead>
        <tbody className="divide-y divide-border/60">
          {rows.map((day) => (
            <tr key={day.key}>
              <th scope="row" className="px-3 py-1.5 text-left font-normal whitespace-nowrap">
                {fullDay.format(day.date)}
              </th>
              {SERIES.map((series) => (
                <td key={series.key} className="px-3 py-1.5 text-right tabular-nums">
                  {formatNumber(day[series.key])}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

/** Daily usage for the selected range, as a chart or a table. */
export function ActivityChart({ entries, days }: { entries: ActivityEntry[]; days: number }) {
  const [view, setView] = useState<"chart" | "table">("chart")
  const buckets = useMemo(() => bucketByDay(entries, days), [entries, days])
  const empty = buckets.every((day) => total(day) === 0)

  if (empty) {
    return (
      <EmptyState
        icon={BarChart3}
        title={`No activity in the last ${days} days`}
        description="Each upload, answered question and agent run adds to this chart, so you can see how the workspace is used."
        className="py-10"
      />
    )
  }

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <Legend days={buckets} />
        <Button
          variant="ghost"
          size="sm"
          className="text-muted-foreground"
          onClick={() => setView(view === "chart" ? "table" : "chart")}
          aria-pressed={view === "table"}
        >
          {view === "chart" ? <Table2 aria-hidden /> : <BarChart3 aria-hidden />}
          {view === "chart" ? "Show table" : "Show chart"}
        </Button>
      </div>
      {view === "chart" ? <Bars days={buckets} /> : <DataTable days={buckets} />}
    </div>
  )
}
