# Sylithe — Frontend

React 19 + Vite + Tailwind + Recharts front end for **Sylithe**, the evidence-backed carbon intelligence platform.

- `src/site/` — public website: home, project marketplace, public project pages, rating methodology, company intelligence, due-diligence process, about
- `src/sylithe/` — platform (`/sylithe`, login required): Overview · Company Intelligence (incl. emissions pathway) · Carbon Calculator · Project Ratings · Compare · AI Research Agent · Methodology

```bash
npm install
VITE_API_URL=http://localhost:5001 npm run dev   # http://localhost:5173
npm run build                                    # sitemap → vite build → prerender
```

Full documentation, agent workflows and architecture: see the main repository
[vertex-sylithe](https://github.com/chhelu123/vertex-sylithe#readme).
