// Shared by the root layout (a server component) and the client-side theme hook.

export const THEME_STORAGE_KEY = "copilot-theme"
export const DARK_QUERY = "(prefers-color-scheme: dark)"

/**
 * Runs before first paint (inlined in the root layout) so a dark page never flashes light.
 * Mirrors `apply` in lib/theme.ts; it must not depend on anything outside itself.
 */
export const THEME_INIT_SCRIPT = `(function(){try{var p=localStorage.getItem("${THEME_STORAGE_KEY}");var d=p==="dark"||(p!=="light"&&matchMedia("${DARK_QUERY}").matches);document.documentElement.classList.toggle("dark",d)}catch(e){}})()`
