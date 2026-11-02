// URL resolution for API calls, kept free of browser globals so it can be unit tested.

export type QueryValue = string | number | undefined

const LOOPBACK_HOSTS = new Set(["localhost", "127.0.0.1", "[::1]"])

function isLoopback(hostname: string): boolean {
  return LOOPBACK_HOSTS.has(hostname) || hostname.endsWith(".localhost")
}

/**
 * Where API requests go: `configured` (NEXT_PUBLIC_API_URL) or, when it's empty, the page's
 * own origin, which is how a Vercel deployment serves the API (`/api/*` routes to the backend).
 *
 * A loopback URL is only honoured on a page that is itself served from this machine. A
 * deployed build that picked up a local value (e.g. http://localhost:8000) would otherwise send
 * every visitor's requests to their own computer. A trailing `/api` is dropped because paths
 * already start with it.
 */
export function resolveApiBase(configured: string | undefined, pageOrigin: string): string {
  const value = (configured ?? "")
    .trim()
    .replace(/\/+$/, "")
    .replace(/\/api$/, "")
  if (!value) return pageOrigin
  let url: URL
  try {
    url = new URL(value, pageOrigin)
  } catch {
    return pageOrigin
  }
  if (isLoopback(url.hostname) && !isLoopback(new URL(pageOrigin).hostname)) return pageOrigin
  return url.href.replace(/\/+$/, "")
}

/** The full URL for an API path such as `/auth/login`. */
export function buildApiUrl(
  base: string,
  path: string,
  query: Record<string, QueryValue> = {},
): URL {
  const url = new URL(`${base}/api${path}`)
  for (const [key, value] of Object.entries(query)) {
    if (value !== undefined && value !== "") url.searchParams.set(key, String(value))
  }
  return url
}
