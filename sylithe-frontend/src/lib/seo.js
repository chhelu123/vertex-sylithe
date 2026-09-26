// Shared SEO helpers.
//
// Two things crawlers reject silently and we kept getting wrong:
//   * og:image / schema image must be ABSOLUTE URLs — Vite gives us
//     bundled paths like "/assets/hero-CddmyV3r.png".
//   * schema.org datePublished / dateModified and article:published_time
//     must be ISO 8601 — our posts store display strings ("May 14, 2026").

export const SITE_ORIGIN = 'https://sylithe.com';

/** Turn a bundled/relative asset path into an absolute https:// URL. */
export function absoluteUrl(url) {
  if (!url) return url;
  if (/^https?:\/\//i.test(url)) return url;
  return `${SITE_ORIGIN}${url.startsWith('/') ? '' : '/'}${url}`;
}

/** Normalise a display date ("May 14, 2026") to ISO 8601 ("2026-05-14"). */
export function isoDate(value) {
  if (!value) return undefined;
  if (/^\d{4}-\d{2}-\d{2}/.test(value)) return value;
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return undefined;
  // Build from local parts — toISOString() would shift the day back in IST.
  const pad = (n) => String(n).padStart(2, '0');
  return `${parsed.getFullYear()}-${pad(parsed.getMonth() + 1)}-${pad(parsed.getDate())}`;
}
