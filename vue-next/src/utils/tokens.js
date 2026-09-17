/**
 * Read a design token declared in src/style.css at runtime.
 *
 * Canvas 2D, Three.js and SVG presentation attributes cannot resolve
 * `var(--token)` themselves, so anything drawing outside plain CSS must go
 * through here. That keeps a single source of truth for the palette: change
 * the `--brand-*` block in style.css and the canvas follows.
 *
 * @param {string} name  Token name without the leading dashes, e.g. 'brand-500'.
 * @param {number} alpha Opacity from 0 to 1.
 * @returns {string} An `rgba(r, g, b, a)` string usable anywhere.
 */
export function token(name, alpha = 1) {
  const fallback = `rgba(255, 255, 255, ${alpha})`
  if (typeof window === 'undefined' || !document?.documentElement) return fallback

  const raw = getComputedStyle(document.documentElement)
    .getPropertyValue(`--${name}`)
    .trim()
  if (!raw) return fallback

  const [r, g, b] = raw.split(/[\s,]+/)
  if (r === undefined || g === undefined || b === undefined) return fallback
  return `rgba(${r}, ${g}, ${b}, ${alpha})`
}

/**
 * Same token as an opaque `rgb()` string, for APIs that reject alpha
 * (notably `new THREE.Color(...)`).
 */
export function tokenRgb(name) {
  const raw = typeof window !== 'undefined' && document?.documentElement
    ? getComputedStyle(document.documentElement).getPropertyValue(`--${name}`).trim()
    : ''
  if (!raw) return 'rgb(255, 255, 255)'
  const [r, g, b] = raw.split(/[\s,]+/)
  return `rgb(${r}, ${g}, ${b})`
}
