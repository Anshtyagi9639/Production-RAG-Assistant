"use client"

import { useQueryClient } from "@tanstack/react-query"
import { useCallback } from "react"

import { accessToken } from "@/lib/session"

/** Clears the token (the route guard then redirects to /login) and all cached data. */
export function useSignOut(): () => void {
  const queryClient = useQueryClient()
  return useCallback(() => {
    accessToken.set(null)
    queryClient.clear()
  }, [queryClient])
}
