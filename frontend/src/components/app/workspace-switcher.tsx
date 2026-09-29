"use client"

import { Check, ChevronsUpDown, Plus } from "lucide-react"
import { useState } from "react"

import { CreateWorkspaceDialog } from "@/components/app/create-workspace-dialog"
import { useWorkspace } from "@/components/app/workspace-context"
import { Button } from "@/components/ui/button"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"

export function WorkspaceSwitcher() {
  const { me, workspace, selectWorkspace } = useWorkspace()
  const [creating, setCreating] = useState(false)

  return (
    <>
      <DropdownMenu>
        <DropdownMenuTrigger asChild>
          <Button
            variant="outline"
            className="h-auto w-full justify-between px-3 py-2 text-left"
            aria-label={`Workspace: ${workspace.name}. Switch workspace`}
          >
            <span className="min-w-0">
              <span className="block truncate text-sm font-medium">{workspace.name}</span>
              <span className="block text-xs text-muted-foreground capitalize">
                {workspace.role}
              </span>
            </span>
            <ChevronsUpDown className="text-muted-foreground" aria-hidden />
          </Button>
        </DropdownMenuTrigger>
        <DropdownMenuContent align="start" className="w-(--radix-dropdown-menu-trigger-width)">
          <DropdownMenuLabel>Workspaces</DropdownMenuLabel>
          {me.workspaces.map((item) => (
            <DropdownMenuItem key={item.id} onSelect={() => selectWorkspace(item.id)}>
              <span className="min-w-0 flex-1 truncate">{item.name}</span>
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
