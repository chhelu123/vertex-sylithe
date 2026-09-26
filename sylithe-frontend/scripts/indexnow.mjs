// Submit all sitemap URLs to IndexNow (Bing, Yandex, etc.) in one call.
// Run AFTER deploy so the key file is live:  node scripts/indexnow.mjs
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';

const KEY = '0b852bc6c24c8b81697ab9890e171807';
const HOST = 'sylithe.com';
const __dir = dirname(fileURLToPath(import.meta.url));

const xml = readFileSync(join(__dir, '..', 'public', 'sitemap.xml'), 'utf8');
const urlList = [...xml.matchAll(/<loc>([^<]+)<\/loc>/g)].map((m) => m[1].trim());

if (!urlList.length) { console.error('No URLs found in sitemap.xml'); process.exit(1); }

const res = await fetch('https://api.indexnow.org/indexnow', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json; charset=utf-8' },
  body: JSON.stringify({
    host: HOST,
    key: KEY,
    keyLocation: `https://${HOST}/${KEY}.txt`,
    urlList,
  }),
});

console.log(`Submitted ${urlList.length} URLs to IndexNow → HTTP ${res.status} ${res.statusText}`);
if (res.status === 200 || res.status === 202) console.log('✓ Accepted. Bing will re-crawl shortly.');
else console.log('Response:', await res.text());
