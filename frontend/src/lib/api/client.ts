import { accessToken } from "@/lib/session"
import type { ErrorBody } from "@/lib/api/types"

// Read as a literal so Next.js inlines it at build time. The only env var the frontend uses.
// Empty means the API is served from this site's own origin under /api (one Vercel project
// routes /api/* to the backend service); local development sets it to the backend's URL.
const API_URL = (process.env.NEXT_PUBLIC_API_URL ?? "").replace(/\/+$/, "")

export class ApiError extends Error {
  constructor(
    readonly status: number,
    readonly code: string,
    message: string,
    readonly details?: unknown,
    readonly retryAfterSeconds?: number,
    /** The backend's X-Request-ID: the same ID appears on every backend log line for the call. */
    readonly requestId?: string,
  ) {
    super(message)
    this.name = "ApiError"
  }
}

type QueryValue = string | number | undefined

interface RequestOptions {
  method?: "GET" | "POST" | "DELETE"
  json?: unknown
  form?: FormData
  query?: Record<string, QueryValue>
  /** Sent as X-Workspace-Id; the backend verifies membership for every tenant route. */
  workspaceId?: string
  signal?: AbortSignal
}

const FALLBACK_MESSAGES: Record<number, string> = {
  401: "Your session has expired. Please sign in again.",
  403: "You don't have permission to do that.",
  404: "Not found.",
  413: "The file is too large.",
  415: "This file type isn't supported.",
  429: "Too many requests. Please wait a moment and try again.",
}

async function toApiError(response: Response): Promise<ApiError> {
  const retryAfterHeader = response.headers.get("Retry-After")
  const retryAfter = retryAfterHeader ? Number.parseInt(retryAfterHeader, 10) : undefined
  let body: Partial<ErrorBody> = {}
  try {
    body = (await response.json()) as Partial<ErrorBody>
  } catch {
    // Non-JSON body (e.g. a proxy error page); fall back to a generic message.
  }
  const code = body.error?.code ?? `http_${response.status}`
  let message =
    body.error?.message ??
    FALLBACK_MESSAGES[response.status] ??
    "Something went wrong. Please try again."
  if (response.status === 429 && retryAfter) {
    message = `Too many requests. Try again in ${retryAfter} seconds.`
  }
  return new ApiError(
    response.status,
    code,
    message,
    body.error?.details,
    retryAfter,
    response.headers.get("X-Request-ID") ?? undefined,
  )
}

export async function apiRequest<T>(path: string, options: RequestOptions = {}): Promise<T> {
  // With no API_URL the path is relative and resolves against the page's own origin.
  const url = new URL(`${API_URL}/api${path}`, window.location.origin)
  for (const [key, value] of Object.entries(options.query ?? {})) {
    if (value !== undefined && value !== "") url.searchParams.set(key, String(value))
  }

  const headers = new Headers({ Accept: "application/json" })
  const token = accessToken.get()
  if (token) headers.set("Authorization", `Bearer ${token}`)
  if (options.workspaceId) headers.set("X-Workspace-Id", options.workspaceId)

  let body: BodyInit | undefined
  if (options.form) {
    body = options.form
  } else if (options.json !== undefined) {
    headers.set("Content-Type", "application/json")
    body = JSON.stringify(options.json)
  }

  let response: Response
  try {
    response = await fetch(url, {
      method: options.method ?? "GET",
      headers,
      body,
      signal: options.signal,
    })
  } catch (error) {
    if (error instanceof DOMException && error.name === "AbortError") throw error
    // fetch rejects when nothing answers at API_URL (backend stopped, wrong port) or when the
    // browser blocks the response (an origin missing from the backend's ALLOWED_ORIGINS).
    throw new ApiError(
      0,
      "network_error",
      `Can't reach the server at ${API_URL || window.location.origin}. Make sure the backend is running, then try again.`,
    )
  }

  if (response.status === 401 && token) {
    // Expired or invalid token: clearing it makes the route guard redirect to /login.
    accessToken.set(null)
  }
  if (!response.ok) throw await toApiError(response)
  if (response.status === 204) return undefined as T
  return (await response.json()) as T
}
