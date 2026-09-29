"use client"

import { useQuery } from "@tanstack/react-query"
import { Building2 } from "lucide-react"
import { useState } from "react"

import { AppShell } from "@/components/app/app-shell"
import { AuthGuard } from "@/components/app/auth-guard"
import { CreateWorkspaceDialog } from "@/components/app/create-workspace-dialog"
import { useSignOut } from "@/components/app/use-sign-out"
import { WorkspaceProvider } from "@/components/app/workspace-context"
import { EmptyState, ErrorState, FullPageSpinner } from "@/components/states"
import { Button } from "@/components/ui/button"
import { authApi } from "@/lib/api/endpoints"
import { queryKeys } from "@/lib/query-keys"

function NoWorkspace() {
  const [open, setOpen] = useState(false)
  return (
    <main className="flex min-h-svh items-center justify-center p-4">
      <EmptyState
        className="w-full max-w-md"
        icon={Building2}
        title="You're not in a workspace yet"
        description="Create one to start uploading documents, or ask a workspace owner to add you."
        action={<Button onClick={() => setOpen(true)}>Create workspace</Button>}
      />
      <CreateWorkspaceDialog open={open} onOpenChange={setOpen} />
    </main>
  )
}

function Session({ children }: { children: React.ReactNode }) {
  const me = useQuery({ queryKey: queryKeys.me, queryFn: authApi.me })
  const signOut = useSignOut()

  if (me.isPending) return <FullPageSpinner label="Loading your workspace…" />
  if (me.isError) {
    return (
      <main className="flex min-h-svh flex-col items-center justify-center gap-3 p-4">
        <ErrorState
          className="w-full max-w-md"
          title="Couldn't load your account"
          error={me.error}
          onRetry={() => me.refetch()}
        />
        <Button variant="ghost" onClick={signOut}>
          Sign out
        </Button>
      </main>
    )
  }
  return (
    <WorkspaceProvider me={me.data}>
      {(hasWorkspace) => (hasWorkspace ? <AppShell>{children}</AppShell> : <NoWorkspace />)}
    </WorkspaceProvider>
  )
}

export default function AppLayout({ children }: { children: React.ReactNode }) {
  return (
    <AuthGuard>
      <Session>{children}</Session>
    </AuthGuard>
  )
}
