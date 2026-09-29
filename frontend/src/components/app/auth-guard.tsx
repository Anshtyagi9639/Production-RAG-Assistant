"use client"

import { usePathname, useRouter } from "next/navigation"
import { useEffect } from "react"

import { FullPageSpinner } from "@/components/states"
import { accessToken, useIsClient, usePersistedValue } from "@/lib/session"

/** Sends signed-out users (no token, or a token the API rejected with 401) to /login. */
export function AuthGuard({ children }: { children: React.ReactNode }) {
  const isClient = useIsClient()
  const token = usePersistedValue(accessToken)
  const router = useRouter()
  const pathname = usePathname()

  useEffect(() => {
    if (isClient && !token) router.replace(`/login?next=${encodeURIComponent(pathname)}`)
  }, [isClient, token, router, pathname])

  if (!isClient || !token) return <FullPageSpinner label="Checking your session…" />
  return children
}
