import fs from 'fs';
import path from 'path';
import chromium from '@sparticuz/chromium';
import puppeteer from 'puppeteer-core';
import express from 'express';
import { fileURLToPath } from 'url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

const PORT = 4173;
const DIST_DIR = path.resolve(__dirname, 'dist');
const SITEMAP_PATH = path.join(DIST_DIR, 'sitemap.xml');

const LOCAL_CHROME_PATHS = [
  '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
  '/Applications/Chromium.app/Contents/MacOS/Chromium',
  '/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge',
];

async function getBrowserLaunchOptions() {
  if (process.env.PUPPETEER_EXECUTABLE_PATH) {
    return {
      executablePath: process.env.PUPPETEER_EXECUTABLE_PATH,
      headless: 'new',
      args: ['--no-sandbox', '--disable-setuid-sandbox'],
    };
  }

  const localChrome = LOCAL_CHROME_PATHS.find((browserPath) => fs.existsSync(browserPath));
  if (localChrome) {
    return {
      executablePath: localChrome,
      headless: 'new',
      args: ['--no-sandbox', '--disable-setuid-sandbox'],
    };
  }

  return {
    executablePath: await chromium.executablePath(),
    headless: chromium.headless,
    args: chromium.args,
    defaultViewport: chromium.defaultViewport,
  };
}

function writeFallbackRoutes(routes) {
  const html = fs.readFileSync(path.join(DIST_DIR, 'index.html'), 'utf-8');

  for (const route of routes) {
    if (route === '/' || route === '') continue;

    const routeDir = path.join(DIST_DIR, route.substring(1));
    if (!fs.existsSync(routeDir)) fs.mkdirSync(routeDir, { recursive: true });
    fs.writeFileSync(path.join(routeDir, 'index.html'), html);
  }
}

// ─── Static server ────────────────────────────────────────────────────────────
const app = express();
app.use(express.static(DIST_DIR));
app.get('/*splat', (_req, res) => {
  res.sendFile(path.join(DIST_DIR, 'index.html'));
});

const server = app.listen(PORT, async () => {
  console.log(`[prerender] Server running on http://localhost:${PORT}`);

  try {
    if (!fs.existsSync(SITEMAP_PATH)) {
      throw new Error(`Sitemap not found at ${SITEMAP_PATH}. Run 'vite build' first.`);
    }

    const sitemapContent = fs.readFileSync(SITEMAP_PATH, 'utf-8');
    const urlMatches = [...sitemapContent.matchAll(/<loc>(.*?)<\/loc>/g)];
    const routes = urlMatches.map(match => new URL(match[1]).pathname);

    console.log(`[prerender] Found ${routes.length} routes to prerender.`);

    let browser;
    try {
      browser = await puppeteer.launch(await getBrowserLaunchOptions());
    } catch (error) {
      console.warn(`[prerender] Browser prerender unavailable: ${error.message}`);
      writeFallbackRoutes(routes);
      server.close();
      console.log('[prerender] Wrote fallback route files from the Vite build.');
      process.exit(0);
    }

    for (const route of routes) {
      console.log(`[prerender] Rendering: ${route}`);
      const url = `http://localhost:${PORT}${route}`;
      const page = await browser.newPage();

      await page.goto(url, { waitUntil: 'networkidle0', timeout: 30000 });
      await new Promise(r => setTimeout(r, 1200)); // Let Helmet flush

      let html = await page.evaluate(() => '<!DOCTYPE html>\n' + document.documentElement.outerHTML);

      // ── Deduplicate <link rel="canonical"> ──────────────────────────────
      const canonicalMatches = [...html.matchAll(/<link[^>]+rel="canonical"[^>]*>/g)];
      if (canonicalMatches.length > 1) {
        const last = canonicalMatches[canonicalMatches.length - 1][0];
        html = html.replace(/<link[^>]+rel="canonical"[^>]*>/g, '');
        html = html.replace('</head>', `  ${last}\n</head>`);
      }

      // ── Deduplicate key meta tags ────────────────────────────────────────
      const metaTagsToDedupe = [
        /(<meta[^>]+name="description"[^>]*>)/g,
        /(<meta[^>]+name="keywords"[^>]*>)/g,
        /(<meta[^>]+property="og:title"[^>]*>)/g,
        /(<meta[^>]+property="og:description"[^>]*>)/g,
        /(<meta[^>]+property="og:url"[^>]*>)/g,
        /(<meta[^>]+property="og:image"[^>]*>)/g,
        /(<meta[^>]+name="twitter:title"[^>]*>)/g,
        /(<meta[^>]+name="twitter:description"[^>]*>)/g,
        /(<meta[^>]+name="twitter:image"[^>]*>)/g,
        /(<meta[^>]+name="robots"[^>]*>)/g,
      ];

      for (const regex of metaTagsToDedupe) {
        const matches = [...html.matchAll(regex)];
        if (matches.length > 1) {
          const last = matches[matches.length - 1][0];
          html = html.replace(regex, '');
          html = html.replace('</head>', `  ${last}\n</head>`);
        }
      }

      // ── Deduplicate <title> tags ─────────────────────────────────────────
      const titleMatches = [...html.matchAll(/<title>(.*?)<\/title>/gs)];
      if (titleMatches.length > 1) {
        const first = titleMatches[0][0];
        html = html.replace(/<title>.*?<\/title>/gs, '');
        html = html.replace('</head>', `  ${first}\n</head>`);
      }

      // ── Write file ───────────────────────────────────────────────────────
      let filePath;
      if (route === '/' || route === '') {
        filePath = path.join(DIST_DIR, 'index.html');
      } else {
        const routeDir = path.join(DIST_DIR, route.substring(1));
        if (!fs.existsSync(routeDir)) fs.mkdirSync(routeDir, { recursive: true });
        filePath = path.join(routeDir, 'index.html');
      }

      fs.writeFileSync(filePath, html);
      console.log(`[prerender] ✅ Saved: ${filePath}`);
      await page.close();
    }

    await browser.close();
    server.close();
    console.log('[prerender] 🎉 All pages prerendered successfully!');
    process.exit(0);

  } catch (error) {
    console.error('[prerender] ❌ Error:', error.message);
    server.close();
    process.exit(1);
  }
});
