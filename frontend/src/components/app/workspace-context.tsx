"use client"

import { createContext, useContext, useEffect } from "react"

import type { Me, Workspace } from "@/lib/api/types"
import { selectedWorkspace, usePersistedValue } from "@/lib/session"

interface WorkspaceContextValue {
  me: Me
  workspace: Workspace
  selectWorkspace: (id: string) => void
}

const WorkspaceContext = createContext<WorkspaceContextValue | null>(null)

export function WorkspaceProvider({
  me,
  children,
}: {
  me: Me
  children: (hasWorkspace: boolean) => React.ReactNode
}) {
  const storedId = usePersistedValue(selectedWorkspace)
  // Fall back to the first workspace if nothing is stored or the stored one is no longer ours.
  const workspace = me.workspaces.find((w) => w.id === storedId) ?? me.workspaces[0]

  useEffect(() => {
    if (workspace && workspace.id !== storedId) selectedWorkspace.set(workspace.id)
  }, [workspace, storedId])

  if (!workspace) return children(false)

  return (
    <WorkspaceContext.Provider value={{ me, workspace, selectWorkspace: selectedWorkspace.set }}>
      {children(true)}
    </WorkspaceContext.Provider>
  )
}

export function useWorkspace(): WorkspaceContextValue {
  const value = useContext(WorkspaceContext)
  if (!value) throw new Error("useWorkspace must be used inside WorkspaceProvider")
  return value
}
