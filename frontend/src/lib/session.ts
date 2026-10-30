"use client"

import { useSyncExternalStore } from "react"

/** A string persisted in localStorage that components can subscribe to. */
export interface PersistedValue {
  get: () => string | null
  set: (value: string | null) => void
  subscribe: (listener: () => void) => () => void
}

export function persistedValue(key: string): PersistedValue {
  const listeners = new Set<() => void>()

  const get = () => {
    try {
      return window.localStorage.getItem(key)
    } catch {
      return null
    }
  }

  const set = (value: string | null) => {
    try {
      if (value === null) window.localStorage.removeItem(key)
      else window.localStorage.setItem(key, value)
    } catch {
      // Storage unavailable (private mode, blocked): the value just won't persist.
    }
    listeners.forEach((listener) => listener())
  }

  const subscribe = (listener: () => void) => {
    listeners.add(listener)
    // Keep tabs in sync: signing out in one tab signs out the others.
    const onStorage = (event: StorageEvent) => {
      if (event.key === key) listener()
    }
    window.addEventListener("storage", onStorage)
    return () => {
      listeners.delete(listener)
      window.removeEventListener("storage", onStorage)
    }
  }

  return { get, set, subscribe }
}

/** The JWT access token. Sent as `Authorization: Bearer`. */
export const accessToken = persistedValue("copilot.accessToken")

/** The workspace the user last selected. Sent as `X-Workspace-Id`. */
export const selectedWorkspace = persistedValue("copilot.workspaceId")

export function usePersistedValue(value: PersistedValue): string | null {
  return useSyncExternalStore(value.subscribe, value.get, () => null)
}

const noopSubscribe = () => () => {}

/** False during server rendering and hydration, true afterwards. */
export function useIsClient(): boolean {
  return useSyncExternalStore(
    noopSubscribe,
    () => true,
    () => false,
  )
}
