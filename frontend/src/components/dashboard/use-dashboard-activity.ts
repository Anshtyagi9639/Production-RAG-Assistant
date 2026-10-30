"use client"

import { useQuery } from "@tanstack/react-query"

import { activityApi } from "@/lib/api/endpoints"
import type { ActivityEntry } from "@/lib/api/types"
import { queryKeys } from "@/lib/query-keys"

/** The longest range the dashboard charts (days). Shorter ranges are sliced from this. */
export const MAX_RANGE_DAYS = 30
const PAGE_SIZE = 100 // the API's maximum
const MAX_PAGES = 5

export interface DashboardActivity {
  entries: ActivityEntry[]
  /** True when older events in the range exist beyond the pages loaded (very busy workspace). */
  truncated: boolean
}

function startOfDay(date: Date): Date {
  return new Date(date.getFullYear(), date.getMonth(), date.getDate())
}

/** First moment of the `days`-day window ending today (local time). */
export function rangeStart(days: number, now: Date = new Date()): Date {
  const start = startOfDay(now)
  start.setDate(start.getDate() - (days - 1))
  return start
}

/**
 * Workspace activity for the last 30 days, newest first: one source for the dashboard's chart,
 * its run outcomes and its recent-activity list. Pages are read until the window is covered.
 */
export function useDashboardActivity(workspaceId: string) {
  return useQuery({
    // Under the workspace's "activity" prefix, so anything that refreshes activity refreshes this.
    queryKey: [...queryKeys.workspace(workspaceId), "activity", "dashboard", MAX_RANGE_DAYS],
    queryFn: async (): Promise<DashboardActivity> => {
      const since = rangeStart(MAX_RANGE_DAYS).getTime()
      const entries: ActivityEntry[] = []
      for (let page = 1; page <= MAX_PAGES; page++) {
        const result = await activityApi.list(workspaceId, page, PAGE_SIZE)
        entries.push(...result.items)
        const oldest = result.items.at(-1)
        const coveredWindow = !oldest || new Date(oldest.created_at).getTime() < since
        if (coveredWindow || page >= result.pages) return { entries, truncated: false }
      }
      return { entries, truncated: true }
    },
  })
}
