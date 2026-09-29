"use client"

import { keepPreviousData, useQuery } from "@tanstack/react-query"
import { History } from "lucide-react"
import { useState } from "react"

import { ActivityList } from "@/components/activity/activity-list"
import { useWorkspace } from "@/components/app/workspace-context"
import { PageHeader } from "@/components/page-header"
import { Pagination } from "@/components/pagination"
import { EmptyState, ErrorState, ListSkeleton } from "@/components/states"
import { Card, CardContent } from "@/components/ui/card"
import { activityApi } from "@/lib/api/endpoints"
import { queryKeys } from "@/lib/query-keys"

const PAGE_SIZE = 25

export default function ActivityPage() {
  const { workspace } = useWorkspace()
  const [page, setPage] = useState(1)
  const activity = useQuery({
    queryKey: queryKeys.activity(workspace.id, page, PAGE_SIZE),
    queryFn: () => activityApi.list(workspace.id, page, PAGE_SIZE),
    placeholderData: keepPreviousData,
  })

  return (
    <>
      <PageHeader
        title="Activity"
        description="Everything that happened in this workspace, newest first."
      />
      <Card>
        <CardContent>
          {activity.isPending && <ListSkeleton rows={8} label="Loading activity" />}
          {activity.isError && (
            <ErrorState
              title="Couldn't load activity"
              error={activity.error}
              onRetry={() => activity.refetch()}
            />
          )}
          {activity.isSuccess && activity.data.items.length === 0 && (
            <EmptyState
              icon={History}
              title="No activity yet"
              description="Uploads, deletions, questions and agent runs are recorded here."
            />
          )}
          {activity.isSuccess && activity.data.items.length > 0 && (
            <>
              <ActivityList entries={activity.data.items} />
              <Pagination page={page} pages={activity.data.pages} onPageChange={setPage} />
            </>
          )}
        </CardContent>
      </Card>
    </>
  )
}
