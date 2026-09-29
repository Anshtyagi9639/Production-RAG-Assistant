import { AlertCircle } from "lucide-react"

import { Alert, AlertDescription } from "@/components/ui/alert"
import { errorMessage } from "@/components/states"

export function FormError({ error }: { error: unknown }) {
  if (!error) return null
  return (
    <Alert variant="destructive">
      <AlertCircle aria-hidden />
      <AlertDescription>{errorMessage(error)}</AlertDescription>
    </Alert>
  )
}
