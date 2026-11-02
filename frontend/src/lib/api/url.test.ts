// Run with `npm test` (compiled by tsc, executed by Node's built-in test runner).
import assert from "node:assert/strict"
import { describe, it } from "node:test"

import { buildApiUrl, resolveApiBase } from "./url"

const DEPLOYED = "https://production-rag-assistant.vercel.app"
const LOCAL_PAGE = "http://localhost:3000"

describe("resolveApiBase", () => {
  it("uses the page's own origin when no API URL is configured (Vercel Services)", () => {
    assert.equal(resolveApiBase(undefined, DEPLOYED), DEPLOYED)
    assert.equal(resolveApiBase("", DEPLOYED), DEPLOYED)
    assert.equal(resolveApiBase("   ", DEPLOYED), DEPLOYED)
  })

  it("ignores a loopback API URL on a deployed page", () => {
    for (const leaked of [
      "http://localhost:8000",
      "http://127.0.0.1:8000",
      "http://[::1]:8000",
      "http://api.localhost:8000",
    ]) {
      assert.equal(resolveApiBase(leaked, DEPLOYED), DEPLOYED, leaked)
    }
  })

  it("keeps the local backend URL during local development", () => {
    assert.equal(resolveApiBase("http://localhost:8000", LOCAL_PAGE), "http://localhost:8000")
    assert.equal(resolveApiBase("http://127.0.0.1:8000/", LOCAL_PAGE), "http://127.0.0.1:8000")
  })

  it("honours a real external API URL", () => {
    assert.equal(resolveApiBase("https://api.example.com/", DEPLOYED), "https://api.example.com")
  })

  it("drops a trailing /api so paths don't get it twice", () => {
    assert.equal(resolveApiBase("https://api.example.com/api", DEPLOYED), "https://api.example.com")
    assert.equal(
      resolveApiBase("https://api.example.com/api/", DEPLOYED),
      "https://api.example.com",
    )
  })

  it("falls back to the page origin for an unusable value", () => {
    assert.equal(resolveApiBase("http://", DEPLOYED), DEPLOYED)
  })
})

describe("buildApiUrl", () => {
  it("builds the production login URL on the deployment's own origin", () => {
    const base = resolveApiBase(undefined, DEPLOYED)

    assert.equal(buildApiUrl(base, "/auth/login").href, `${DEPLOYED}/api/auth/login`)
  })

  it("never builds a localhost login URL for a deployed page, even with a leaked value", () => {
    const base = resolveApiBase("http://localhost:8000", DEPLOYED)

    assert.equal(buildApiUrl(base, "/auth/login").href, `${DEPLOYED}/api/auth/login`)
  })

  it("builds the local login URL during development", () => {
    const base = resolveApiBase("http://127.0.0.1:8000", LOCAL_PAGE)

    assert.equal(buildApiUrl(base, "/auth/login").href, "http://127.0.0.1:8000/api/auth/login")
  })

  it("adds query parameters, skipping empty ones", () => {
    const url = buildApiUrl(DEPLOYED, "/documents", { page: 2, sort: "-created_at", status: "" })

    assert.equal(url.pathname, "/api/documents")
    assert.equal(url.search, "?page=2&sort=-created_at")
  })
})
