"use client"

import { useCallback, useSyncExternalStore } from "react"

import { DARK_QUERY, THEME_STORAGE_KEY as STORAGE_KEY } from "@/lib/theme-script"

export type ThemePreference = "light" | "dark" | "system"

function read(): ThemePreference {
  try {
    const value = localStorage.getItem(STORAGE_KEY)
    return value === "light" || value === "dark" ? value : "system"
  } catch {
    return "system"
  }
}

function apply(preference: ThemePreference) {
  const dark = preference === "dark" || (preference === "system" && matchMedia(DARK_QUERY).matches)
  document.documentElement.classList.toggle("dark", dark)
}

const listeners = new Set<() => void>()

function subscribe(listener: () => void) {
  listeners.add(listener)
  // Following the system: repaint when the OS switches between light and dark.
  const media = matchMedia(DARK_QUERY)
  const onSystemChange = () => {
    if (read() === "system") apply("system")
  }
  media.addEventListener("change", onSystemChange)
  return () => {
    listeners.delete(listener)
    media.removeEventListener("change", onSystemChange)
  }
}

/** The stored theme preference and a setter that applies it immediately. */
export function useTheme(): [ThemePreference, (preference: ThemePreference) => void] {
  const preference = useSyncExternalStore(subscribe, read, () => "system" as const)
  const setPreference = useCallback((next: ThemePreference) => {
    try {
      if (next === "system") localStorage.removeItem(STORAGE_KEY)
      else localStorage.setItem(STORAGE_KEY, next)
    } catch {
      // Storage blocked (private mode): the choice still applies until the page reloads.
    }
    apply(next)
    for (const listener of listeners) listener()
  }, [])
  return [preference, setPreference]
}
