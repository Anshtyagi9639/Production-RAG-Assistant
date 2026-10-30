import { AlertCircle } from "lucide-react"

import { errorMessage, errorReference } from "@/components/states"
import { Alert, AlertDescription } from "@/components/ui/alert"
import { ApiError } from "@/lib/api/client"

export function FormError({
  error,
  describe = errorMessage,
}: {
  error: unknown
  describe?: (error: unknown) => string
}) {
  if (!error) return null
  // A reference helps support find a server-side failure; user errors (4xx) don't need one.
  const reference =
    error instanceof ApiError && error.status >= 500 ? errorReference(error) : undefined
  return (
    <Alert variant="destructive">
      <AlertCircle aria-hidden />
      <AlertDescription>
        {describe(error)}
        {reference && (
          <span className="mt-1 block font-mono text-[11px] opacity-75">Reference {reference}</span>
        )}
      </AlertDescription>
    </Alert>
  )
}
