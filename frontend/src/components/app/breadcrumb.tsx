"use client"

import { createContext, useContext, useEffect, useState } from "react"

/** Lets a page name the item it shows (e.g. a document) as the last breadcrumb. */
const BreadcrumbContext = createContext<((label: string | null) => void) | null>(null)
const LeafContext = createContext<string | null>(null)

export function BreadcrumbProvider({ children }: { children: React.ReactNode }) {
  const [leaf, setLeaf] = useState<string | null>(null)
  return (
    <BreadcrumbContext.Provider value={setLeaf}>
      <LeafContext.Provider value={leaf}>{children}</LeafContext.Provider>
    </BreadcrumbContext.Provider>
  )
}

export function useBreadcrumbLeaf(): string | null {
  return useContext(LeafContext)
}

/** Call from a page to show `label` after the section name; cleared when the page unmounts. */
export function useBreadcrumb(label: string | null | undefined) {
  const setLeaf = useContext(BreadcrumbContext)
  useEffect(() => {
    setLeaf?.(label ?? null)
    return () => setLeaf?.(null)
  }, [label, setLeaf])
}
