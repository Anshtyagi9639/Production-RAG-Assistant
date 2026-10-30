"use client"

import {
  Bot,
  ChevronRight,
  History,
  LayoutDashboard,
  Library,
  type LucideIcon,
  Menu,
  MessageSquareText,
  PanelLeftClose,
  PanelLeftOpen,
} from "lucide-react"
import Link from "next/link"
import { usePathname } from "next/navigation"
import { useEffect, useState } from "react"

import { BreadcrumbProvider, useBreadcrumbLeaf } from "@/components/app/breadcrumb"
import { UserMenu } from "@/components/app/user-menu"
import { useWorkspace } from "@/components/app/workspace-context"
import { WorkspaceSwitcher } from "@/components/app/workspace-switcher"
import { BrandMark, BrandName } from "@/components/brand"
import { Button } from "@/components/ui/button"
import { Sheet, SheetContent, SheetDescription, SheetTitle } from "@/components/ui/sheet"
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip"
import { persistedValue, usePersistedValue } from "@/lib/session"
import { cn } from "@/lib/utils"

interface NavItem {
  href: string
  label: string
  icon: LucideIcon
}

const NAV_GROUPS: { label: string; items: NavItem[] }[] = [
  {
    label: "Workspace",
    items: [
      { href: "/dashboard", label: "Dashboard", icon: LayoutDashboard },
      { href: "/knowledge", label: "Knowledge Base", icon: Library },
    ],
  },
  {
    label: "AI tools",
    items: [
      { href: "/assistant", label: "Assistant", icon: MessageSquareText },
      { href: "/agent", label: "Agent", icon: Bot },
    ],
  },
  {
    label: "Audit",
    items: [{ href: "/activity", label: "Activity", icon: History }],
  },
]

const ALL_ITEMS = NAV_GROUPS.flatMap((group) => group.items)

/** Pages that manage their own full-height, full-width layout. */
const FULL_BLEED = ["/assistant"]

/** Desktop only: the sidebar collapsed to icons. Remembered per browser. */
const sidebarCollapsed = persistedValue("copilot.sidebarCollapsed")
const TOGGLE_SHORTCUT = "b"

function isActive(pathname: string, href: string): boolean {
  return pathname === href || pathname.startsWith(`${href}/`)
}

function NavLink({
  item,
  active,
  collapsed,
  onNavigate,
}: {
  item: NavItem
  active: boolean
  collapsed: boolean
  onNavigate?: () => void
}) {
  const Icon = item.icon
  const link = (
    <Link
      href={item.href}
      onClick={onNavigate}
      aria-current={active ? "page" : undefined}
      // Collapsed, the visible label is gone: the accessible name stays on the link.
      aria-label={collapsed ? item.label : undefined}
      className={cn(
        "group/nav relative flex items-center gap-2.5 rounded-lg text-sm font-medium text-muted-foreground transition-colors outline-none hover:bg-sidebar-accent hover:text-foreground focus-visible:ring-3 focus-visible:ring-ring/50",
        collapsed ? "size-9 justify-center" : "px-2.5 py-1.5",
        active && "bg-card text-foreground shadow-xs ring-1 ring-border",
      )}
    >
      <Icon
        className={cn(
          "size-4 shrink-0 transition-colors",
          active ? "text-primary" : "text-muted-foreground group-hover/nav:text-foreground",
        )}
        aria-hidden
      />
      {!collapsed && item.label}
    </Link>
  )
  if (!collapsed) return link
  return (
    <Tooltip>
      <TooltipTrigger asChild>{link}</TooltipTrigger>
      <TooltipContent side="right" sideOffset={8}>
        {item.label}
      </TooltipContent>
    </Tooltip>
  )
}

function SidebarContent({
  collapsed = false,
  onNavigate,
}: {
  collapsed?: boolean
  onNavigate?: () => void
}) {
  const pathname = usePathname()

  return (
    <div className="flex h-full flex-col">
      <div
        className={cn(
          "flex h-14 shrink-0 items-center gap-2.5",
          collapsed ? "justify-center" : "px-4",
        )}
      >
        <Link
          href="/dashboard"
          onClick={onNavigate}
          aria-label={collapsed ? "Knowledge Copilot dashboard" : undefined}
          className="flex items-center gap-2.5 rounded-md outline-none focus-visible:ring-3 focus-visible:ring-ring/50"
        >
          <BrandMark />
          {!collapsed && <BrandName className="text-[0.9375rem]" />}
        </Link>
      </div>
      <div className={cn("pb-2", collapsed ? "flex justify-center" : "px-3")}>
        <WorkspaceSwitcher compact={collapsed} />
      </div>
      <nav
        aria-label="Main"
        className={cn(
          "flex-1 overflow-y-auto py-3",
          collapsed ? "flex flex-col items-center gap-3 px-2" : "space-y-5 px-3",
        )}
      >
        {NAV_GROUPS.map((group, index) => (
          <div
            key={group.label}
            className={cn("space-y-1", collapsed && "flex flex-col items-center")}
          >
            {collapsed ? (
              index > 0 && <span aria-hidden className="mb-2 block h-px w-6 bg-border" />
            ) : (
              <p className="px-2.5 pb-1 text-[11px] font-medium tracking-wide text-muted-foreground/80 uppercase">
                {group.label}
              </p>
            )}
            <ul className={cn("space-y-0.5", collapsed && "flex flex-col items-center gap-1")}>
              {group.items.map((item) => (
                <li key={item.href}>
                  <NavLink
                    item={item}
                    active={isActive(pathname, item.href)}
                    collapsed={collapsed}
                    onNavigate={onNavigate}
                  />
                </li>
              ))}
            </ul>
          </div>
        ))}
      </nav>
      <div className={cn("border-t p-2", collapsed && "flex justify-center")}>
        <UserMenu compact={collapsed} side={collapsed ? "right" : undefined} />
      </div>
    </div>
  )
}

function Breadcrumbs() {
  const pathname = usePathname()
  const { workspace } = useWorkspace()
  const leaf = useBreadcrumbLeaf()
  const section = ALL_ITEMS.find((item) => isActive(pathname, item.href))
  const nested = section && pathname !== section.href

  return (
    <nav aria-label="Breadcrumb" className="min-w-0 flex-1">
      <ol className="flex min-w-0 items-center gap-1.5 text-sm">
        <li className="hidden min-w-0 shrink truncate text-muted-foreground sm:block">
          {workspace.name}
        </li>
        {section && (
          <>
            <li aria-hidden className="hidden text-muted-foreground/50 sm:block">
              <ChevronRight className="size-3.5" />
            </li>
            <li className="shrink-0">
              {nested ? (
                <Link
                  href={section.href}
                  className="text-muted-foreground transition-colors hover:text-foreground"
                >
                  {section.label}
                </Link>
              ) : (
                <span className="font-medium" aria-current="page">
                  {section.label}
                </span>
              )}
            </li>
          </>
        )}
        {nested && leaf && (
          <>
            <li aria-hidden className="text-muted-foreground/50">
              <ChevronRight className="size-3.5" />
            </li>
            <li className="min-w-0 truncate font-medium" aria-current="page">
              {leaf}
            </li>
          </>
        )}
      </ol>
    </nav>
  )
}

export function AppShell({ children }: { children: React.ReactNode }) {
  const [mobileOpen, setMobileOpen] = useState(false)
  const pathname = usePathname()
  const { workspace } = useWorkspace()
  const fullBleed = FULL_BLEED.some((href) => isActive(pathname, href))
  const collapsed = usePersistedValue(sidebarCollapsed) === "true"
  const toggleCollapsed = () => sidebarCollapsed.set(collapsed ? null : "true")

  // Ctrl+B / Cmd+B toggles the desktop sidebar, as in most editors and shadcn's sidebar.
  useEffect(() => {
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === TOGGLE_SHORTCUT && (event.metaKey || event.ctrlKey) && !event.altKey) {
        event.preventDefault()
        sidebarCollapsed.set(sidebarCollapsed.get() === "true" ? null : "true")
      }
    }
    window.addEventListener("keydown", onKeyDown)
    return () => window.removeEventListener("keydown", onKeyDown)
  }, [])

  const toggleLabel = collapsed ? "Expand sidebar" : "Collapse sidebar"

  return (
    <BreadcrumbProvider>
      <div
        className={cn(
          "min-h-svh bg-background lg:grid",
          collapsed ? "lg:grid-cols-[3.75rem_minmax(0,1fr)]" : "lg:grid-cols-[16rem_minmax(0,1fr)]",
        )}
      >
        <a
          href="#main"
          className="sr-only z-50 rounded-md bg-background px-3 py-2 focus:not-sr-only focus:fixed focus:top-2 focus:left-2"
        >
          Skip to content
        </a>

        <aside className="sticky top-0 hidden h-svh border-r bg-sidebar lg:block">
          <SidebarContent collapsed={collapsed} />
        </aside>

        <Sheet open={mobileOpen} onOpenChange={setMobileOpen}>
          <SheetContent side="left" className="w-72 bg-sidebar p-0">
            <SheetTitle className="sr-only">Navigation</SheetTitle>
            <SheetDescription className="sr-only">Pages and workspace switcher</SheetDescription>
            <SidebarContent onNavigate={() => setMobileOpen(false)} />
          </SheetContent>
        </Sheet>

        <div className="flex min-w-0 flex-col">
          <header className="sticky top-0 z-30 flex h-14 shrink-0 items-center gap-2 border-b bg-background/85 px-3 backdrop-blur supports-[backdrop-filter]:bg-background/70 sm:px-4 lg:px-6">
            <Button
              variant="ghost"
              size="icon"
              className="lg:hidden"
              onClick={() => setMobileOpen(true)}
              aria-label="Open navigation"
            >
              <Menu aria-hidden />
            </Button>
            <Tooltip>
              <TooltipTrigger asChild>
                <Button
                  variant="ghost"
                  size="icon-sm"
                  className="-ml-2 hidden text-muted-foreground lg:inline-flex"
                  onClick={toggleCollapsed}
                  aria-label={toggleLabel}
                  aria-keyshortcuts="Control+B Meta+B"
                >
                  {collapsed ? <PanelLeftOpen aria-hidden /> : <PanelLeftClose aria-hidden />}
                </Button>
              </TooltipTrigger>
              <TooltipContent side="bottom">{toggleLabel} (Ctrl+B)</TooltipContent>
            </Tooltip>
            <BrandMark className="size-6 lg:hidden [&_svg]:size-3.5" />
            <Breadcrumbs />
            <div className="lg:hidden">
              <UserMenu compact />
            </div>
          </header>

          {/* Keyed by workspace so page state (filters, open conversation) resets on switch. */}
          <main
            key={workspace.id}
            id="main"
            className={cn(
              "min-w-0 flex-1",
              !fullBleed && "mx-auto w-full max-w-6xl px-4 py-6 sm:px-6 lg:px-8 lg:py-8",
            )}
          >
            {children}
          </main>
        </div>
      </div>
    </BreadcrumbProvider>
  )
}
