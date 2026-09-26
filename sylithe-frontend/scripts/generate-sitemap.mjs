// Auto-generate public/sitemap.xml from the public site's static routes.
// Runs before `vite build`; prerender.js then renders every URL listed here.
import { writeFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';

const __dir = dirname(fileURLToPath(import.meta.url));
const ROOT = join(__dir, '..');
const BASE = 'https://sylithe.com';
const today = new Date().toISOString().slice(0, 10);

// Public routes (must match the routes under <SiteLayout> in src/App.jsx).
const STATIC_ROUTES = [
  '/', '/projects', '/ratings', '/companies', '/how-it-works', '/about',
  '/terms-of-service', '/privacy-policy',
];

const xml =
  `<?xml version="1.0" encoding="UTF-8"?>\n` +
  `<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n` +
  STATIC_ROUTES.map((u) => `  <url>\n    <loc>${BASE}${u}</loc>\n    <lastmod>${today}</lastmod>\n  </url>`).join('\n') +
  `\n</urlset>\n`;

writeFileSync(join(ROOT, 'public/sitemap.xml'), xml);
console.log(`[sitemap] Wrote ${STATIC_ROUTES.length} URLs to public/sitemap.xml`);
