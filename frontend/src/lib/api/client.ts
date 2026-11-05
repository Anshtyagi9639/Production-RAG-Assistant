import { accessToken } from "@/lib/session"
import type { ErrorBody } from "@/lib/api/types"
import { buildApiUrl, type QueryValue, resolveApiBase } from "@/lib/api/url"

// Read as a literal so Next.js inlines it at build time. The only env var the frontend uses.
// Empty means the API is served from this site's own origin under /api (one Vercel project
// routes /api/* to the backend service); local development sets it to the backend's URL.
const API_URL = process.env.NEXT_PUBLIC_API_URL

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

interface RequestOptions {
  method?: "GET" | "POST" | "PATCH" | "DELETE"
  json?: unknown
  form?: FormData
  query?: Record<string, QueryValue>
  /** Sent as X-Workspace-Id; the backend verifies membership for every tenant route. */
  workspaceId?: string
  signal?: AbortSignal
  /** Called with the fraction of the request body sent (0-1); used for file uploads. */
  onUploadProgress?: UploadProgress
}

export type UploadProgress = (fraction: number) => void

/**
 * fetch() can't report upload progress, so requests that need it go through XMLHttpRequest.
 * The result is wrapped in a Response so callers handle both transports the same way; like
 * fetch, it rejects only when no response arrives.
 */
function sendWithProgress(
  url: URL | string,
  init: { method: string; headers?: Headers; body?: BodyInit; signal?: AbortSignal },
  onProgress: UploadProgress,
): Promise<Response> {
  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest()
    xhr.open(init.method, url)
    init.headers?.forEach((value, name) => xhr.setRequestHeader(name, value))
    xhr.upload.onprogress = (event) => {
      if (event.lengthComputable && event.total > 0) onProgress(event.loaded / event.total)
    }
    xhr.onload = () => {
      const headers = new Headers()
      for (const line of xhr
        .getAllResponseHeaders()
        .trim()
        .split(/[\r\n]+/)) {
        const separator = line.indexOf(":")
        if (separator > 0)
          headers.append(line.slice(0, separator), line.slice(separator + 1).trim())
      }
      const empty = xhr.status === 204 || xhr.status === 205 || xhr.status === 304
      resolve(new Response(empty ? null : xhr.responseText, { status: xhr.status, headers }))
    }
    xhr.onerror = () => reject(new TypeError("Network request failed"))
    xhr.onabort = () => reject(new DOMException("The upload was cancelled.", "AbortError"))
    init.signal?.addEventListener("abort", () => xhr.abort(), { once: true })
    xhr.send(init.body as XMLHttpRequestBodyInit | null | undefined)
  })
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
  const base = resolveApiBase(API_URL, window.location.origin)
  const url = buildApiUrl(base, path, options.query)

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
    const init = { method: options.method ?? "GET", headers, body, signal: options.signal }
    response = options.onUploadProgress
      ? await sendWithProgress(url, init, options.onUploadProgress)
      : await fetch(url, init)
  } catch (error) {
    if (error instanceof DOMException && error.name === "AbortError") throw error
    // fetch rejects when nothing answers at API_URL (backend stopped, wrong port) or when the
    // browser blocks the response (an origin missing from the backend's ALLOWED_ORIGINS).
    throw new ApiError(
      0,
      "network_error",
      `Can't reach the server at ${base}. Make sure the backend is running, then try again.`,
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

/**
 * POST a file to a presigned storage URL. No auth headers: the signed fields are the
 * permission, and they only allow this one key, type and size until they expire.
 */
export async function uploadToBucket(
  url: string,
  fields: Record<string, string>,
  file: File,
  onProgress?: UploadProgress,
): Promise<void> {
  const form = new FormData()
  for (const [name, value] of Object.entries(fields)) form.append(name, value)
  // The bucket ignores fields after the file, so it goes last.
  form.append("file", file)

  let response: Response
  try {
    const init = { method: "POST", body: form }
    response = onProgress ? await sendWithProgress(url, init, onProgress) : await fetch(url, init)
  } catch {
    // Also how a bucket without a CORS rule for this site shows up in the browser.
    throw new ApiError(
      0,
      "storage_unreachable",
      "The file couldn't be sent to storage. Check your connection and try again.",
    )
  }
  if (!response.ok) {
    // S3 answers with XML; its 403 here means the upload expired or the file changed size.
    throw new ApiError(
      response.status,
      "storage_rejected",
      "Storage refused the file. Upload it again.",
    )
  }
}
