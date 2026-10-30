"use client"

import { Check, ChevronsUpDown, Plus } from "lucide-react"
import { useState } from "react"

import { CreateWorkspaceDialog } from "@/components/app/create-workspace-dialog"
import { useWorkspace } from "@/components/app/workspace-context"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import { cn } from "@/lib/utils"

function WorkspaceInitial({ name, className }: { name: string; className?: string }) {
  return (
    <span
      aria-hidden
      className={cn(
        "flex size-7 shrink-0 items-center justify-center rounded-md border bg-card text-xs font-semibold text-foreground shadow-xs",
        className,
      )}
    >
      {name.trim()[0]?.toUpperCase() ?? "W"}
    </span>
  )
}

/** `compact` shows only the workspace initial (collapsed sidebar). */
export function WorkspaceSwitcher({ compact = false }: { compact?: boolean }) {
  const { me, workspace, selectWorkspace } = useWorkspace()
  const [creating, setCreating] = useState(false)

  return (
    <>
      <DropdownMenu>
        <DropdownMenuTrigger
          className={cn(
            "flex items-center gap-2.5 rounded-lg text-left transition-colors outline-none hover:bg-muted focus-visible:ring-3 focus-visible:ring-ring/50 aria-expanded:bg-muted",
            compact ? "p-1" : "w-full border bg-card p-2 shadow-xs",
          )}
          aria-label={`Workspace: ${workspace.name}. Switch workspace`}
        >
          <WorkspaceInitial name={workspace.name} />
          {!compact && (
            <>
              <span className="min-w-0 flex-1">
                <span className="block truncate text-sm font-medium">{workspace.name}</span>
                <span className="block text-xs text-muted-foreground capitalize">
                  {workspace.role}
                </span>
              </span>
              <ChevronsUpDown className="size-4 text-muted-foreground" aria-hidden />
            </>
          )}
        </DropdownMenuTrigger>
        <DropdownMenuContent
          align="start"
          side={compact ? "right" : "bottom"}
          className={cn("min-w-56", !compact && "w-(--radix-dropdown-menu-trigger-width)")}
        >
          <DropdownMenuLabel className="text-xs font-medium text-muted-foreground">
            Workspaces
          </DropdownMenuLabel>
          {me.workspaces.map((item) => (
            <DropdownMenuItem key={item.id} onSelect={() => selectWorkspace(item.id)}>
              <WorkspaceInitial name={item.name} className="size-6 text-[11px] shadow-none" />
              <span className="min-w-0 flex-1">
                <span className="block truncate">{item.name}</span>
                <span className="block text-xs text-muted-foreground capitalize">{item.role}</span>
              </span>
              {item.id === workspace.id && <Check aria-label="Current workspace" />}
            </DropdownMenuItem>
          ))}
          <DropdownMenuSeparator />
          <DropdownMenuItem onSelect={() => setCreating(true)}>
            <Plus aria-hidden />
            Create workspace
          </DropdownMenuItem>
        </DropdownMenuContent>
      </DropdownMenu>
      <CreateWorkspaceDialog open={creating} onOpenChange={setCreating} />
    </>
  )
}
