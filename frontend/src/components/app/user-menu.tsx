"use client"

import { ChevronsUpDown, LogOut } from "lucide-react"

import { useSignOut } from "@/components/app/use-sign-out"
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

export function initials(name: string): string {
  const parts = name.trim().split(/\s+/).filter(Boolean)
  const letters = parts.length > 1 ? [parts[0][0], parts.at(-1)![0]] : [parts[0]?.[0] ?? "?"]
  return letters.join("").toUpperCase()
}

export function Avatar({ name, className }: { name: string; className?: string }) {
  return (
    <span
      aria-hidden
      className={cn(
        "flex size-7 shrink-0 items-center justify-center rounded-full bg-primary/12 text-[11px] font-semibold text-accent-foreground",
        className,
      )}
    >
      {initials(name)}
    </span>
  )
}

/** The signed-in user, with sign out. `compact` shows only the avatar (mobile top bar and the
 * collapsed sidebar, where the menu opens to the given `side`). */
export function UserMenu({
  compact = false,
  side,
}: {
  compact?: boolean
  side?: "top" | "bottom" | "right"
}) {
  const { me } = useWorkspace()
  const signOut = useSignOut()

  return (
    <DropdownMenu>
      <DropdownMenuTrigger
        className={cn(
          "flex items-center gap-2.5 rounded-lg text-left transition-colors outline-none hover:bg-sidebar-accent focus-visible:ring-3 focus-visible:ring-ring/50 aria-expanded:bg-sidebar-accent",
          compact ? "p-1" : "w-full p-2",
        )}
        aria-label={`Account: ${me.user.full_name}`}
      >
        <Avatar name={me.user.full_name} />
        {!compact && (
          <>
            <span className="min-w-0 flex-1">
              <span className="block truncate text-sm font-medium">{me.user.full_name}</span>
              <span className="block truncate text-xs text-muted-foreground">{me.user.email}</span>
            </span>
            <ChevronsUpDown className="size-4 text-muted-foreground" aria-hidden />
          </>
        )}
      </DropdownMenuTrigger>
      <DropdownMenuContent
        align={compact ? "end" : "start"}
        side={side ?? (compact ? "bottom" : "top")}
        className="w-60"
      >
        <DropdownMenuLabel className="font-normal">
          <span className="block truncate text-sm font-medium text-foreground">
            {me.user.full_name}
          </span>
          <span className="block truncate text-xs text-muted-foreground">{me.user.email}</span>
        </DropdownMenuLabel>
        <DropdownMenuSeparator />
        <DropdownMenuItem onSelect={signOut}>
          <LogOut aria-hidden />
          Sign out
        </DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  )
}
