"use client"

import { useRouter, useSearchParams } from "next/navigation"
import { useEffect } from "react"

import { accessToken, usePersistedValue } from "@/lib/session"

/** Where to go after signing in: `?next=` if it is a same-site path, else the dashboard. */
export function useAfterSignInPath(): string {
  const next = useSearchParams().get("next")
  return next && next.startsWith("/") && !next.startsWith("//") ? next : "/dashboard"
}

/** Auth pages bounce users who already have a token. */
export function useSignedInRedirect(): void {
  const token = usePersistedValue(accessToken)
  const router = useRouter()
  const target = useAfterSignInPath()
  useEffect(() => {
    if (token) router.replace(target)
  }, [token, router, target])
}
