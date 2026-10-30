import { ArrowLeft, FileQuestion } from "lucide-react"
import Link from "next/link"

import { BrandMark, BrandName } from "@/components/brand"
import { Button } from "@/components/ui/button"

export default function NotFound() {
  return (
    <main className="flex min-h-svh flex-col items-center justify-center gap-6 p-6 text-center">
      <title>Page not found · Knowledge Copilot</title>
      <div className="flex items-center gap-2.5">
        <BrandMark />
        <BrandName />
      </div>
      <span className="flex size-12 items-center justify-center rounded-2xl border bg-card shadow-xs">
        <FileQuestion className="size-5 text-muted-foreground" aria-hidden />
      </span>
      <div className="space-y-2">
        <p className="font-mono text-xs text-muted-foreground">404</p>
        <h1 className="text-2xl font-semibold tracking-tight">Page not found</h1>
        <p className="max-w-sm text-sm text-muted-foreground">
          The page you&apos;re looking for doesn&apos;t exist or has moved.
        </p>
      </div>
      <Button asChild>
        <Link href="/dashboard">
          <ArrowLeft aria-hidden />
          Back to dashboard
        </Link>
      </Button>
    </main>
  )
}
