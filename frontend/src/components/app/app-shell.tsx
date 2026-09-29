"use client"

import {
  BookOpenText,
  Bot,
  History,
  LayoutDashboard,
  Library,
  LogOut,
  Menu,
  MessageSquareText,
} from "lucide-react"
import Link from "next/link"
import { usePathname } from "next/navigation"
import { useState } from "react"

import { useSignOut } from "@/components/app/use-sign-out"
import { useWorkspace } from "@/components/app/workspace-context"
import { WorkspaceSwitcher } from "@/components/app/workspace-switcher"
import { Button } from "@/components/ui/button"
import { Sheet, SheetContent, SheetDescription, SheetTitle } from "@/components/ui/sheet"
import { cn } from "@/lib/utils"

const NAV_ITEMS = [
  { href: "/dashboard", label: "Dashboard", icon: LayoutDashboard },
  { href: "/knowledge", label: "Knowledge Base", icon: Library },
  { href: "/assistant", label: "Assistant", icon: MessageSquareText },
  { href: "/agent", label: "Agent", icon: Bot },
  { href: "/activity", label: "Activity", icon: History },
] as const

function Brand() {
  return (
    <Link href="/dashboard" className="flex items-center gap-2 px-1 font-semibold">
      <span className="flex size-7 items-center justify-center rounded-md bg-primary text-primary-foreground">
        <BookOpenText className="size-4" aria-hidden />
      </span>
      Knowledge Copilot
    </Link>
  )
}

function SidebarContent({ onNavigate }: { onNavigate?: () => void }) {
  const pathname = usePathname()
  const { me } = useWorkspace()
  const signOut = useSignOut()

  return (
    <div className="flex h-full flex-col gap-4 p-3">
      <Brand />
      <WorkspaceSwitcher />
      <nav aria-label="Main" className="flex-1">
        <ul className="space-y-1">
          {NAV_ITEMS.map(({ href, label, icon: Icon }) => {
            const active = pathname === href || pathname.startsWith(`${href}/`)
            return (
              <li key={href}>
                <Link
                  href={href}
                  onClick={onNavigate}
                  aria-current={active ? "page" : undefined}
                  className={cn(
                    "flex items-center gap-2.5 rounded-md px-2.5 py-2 text-sm font-medium text-muted-foreground transition-colors hover:bg-muted hover:text-foreground focus-visible:ring-3 focus-visible:ring-ring/50 focus-visible:outline-none",
                    active && "bg-accent text-accent-foreground hover:bg-accent",
                  )}
                >
                  <Icon className="size-4" aria-hidden />
                  {label}
                </Link>
              </li>
            )
          })}
        </ul>
      </nav>
      <div className="flex items-center gap-2 border-t pt-3">
        <div className="min-w-0 flex-1">
          <p className="truncate text-sm font-medium">{me.user.full_name}</p>
          <p className="truncate text-xs text-muted-foreground">{me.user.email}</p>
        </div>
        <Button variant="ghost" size="icon-sm" onClick={signOut} aria-label="Sign out">
          <LogOut aria-hidden />
        </Button>
      </div>
    </div>
  )
}

export function AppShell({ children }: { children: React.ReactNode }) {
  const [mobileOpen, setMobileOpen] = useState(false)
  const { workspace } = useWorkspace()

  return (
    <div className="min-h-svh lg:grid lg:grid-cols-[15rem_1fr]">
      <a
        href="#main"
        className="sr-only z-50 rounded-md bg-background px-3 py-2 focus:not-sr-only focus:fixed focus:top-2 focus:left-2"
      >
        Skip to content
      </a>

      <aside className="sticky top-0 hidden h-svh border-r bg-card lg:block">
        <SidebarContent />
      </aside>

      <header className="sticky top-0 z-30 flex items-center gap-2 border-b bg-card px-3 py-2 lg:hidden">
        <Button
          variant="ghost"
          size="icon"
          onClick={() => setMobileOpen(true)}
          aria-label="Open navigation"
        >
          <Menu aria-hidden />
        </Button>
        <Brand />
      </header>
      <Sheet open={mobileOpen} onOpenChange={setMobileOpen}>
        <SheetContent side="left" className="w-72 p-0">
          <SheetTitle className="sr-only">Navigation</SheetTitle>
          <SheetDescription className="sr-only">Pages and workspace switcher</SheetDescription>
          <SidebarContent onNavigate={() => setMobileOpen(false)} />
        </SheetContent>
      </Sheet>

      {/* Keyed by workspace so page state (filters, open conversation) resets on switch. */}
      <main key={workspace.id} id="main" className="min-w-0 px-4 py-6 sm:px-6 lg:px-8">
        {children}
      </main>
    </div>
  )
}
