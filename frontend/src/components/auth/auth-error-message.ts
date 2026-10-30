import { errorMessage } from "@/components/states"
import { ApiError } from "@/lib/api/client"

/**
 * Messages for the sign-in and create-account forms. Server-side failures get a plain
 * "try again" message; internal details never reach the page (the API doesn't send any).
 */
export function authErrorMessage(error: unknown, action: "sign in" | "create your account") {
  if (!(error instanceof ApiError)) return errorMessage(error)
  // Server errors also show a request reference (FormError) for finding them in the logs.
  return userMessage(error, action)
}

function userMessage(error: ApiError, action: "sign in" | "create your account") {
  if (error.status === 401) return "Invalid email or password."
  if (error.status === 422) return "Please check the information you entered."
  // 503: a dependency (e.g. the database) is down; the API's message says it's temporary.
  if (error.status === 503) return error.message
  if (error.status >= 500) return `Unable to ${action} right now. Please try again.`
  // Network failures (status 0), 409 (email already registered), 429 (rate limited) and
  // others already carry a specific, user-facing message.
  return error.message
}
