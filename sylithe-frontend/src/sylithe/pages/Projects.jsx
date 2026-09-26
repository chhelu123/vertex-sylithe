import React, { useEffect, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { Database, GitCompareArrows } from 'lucide-react';
import { api } from '../api';
import { Card, Confidence, Disclaimer, Empty, ErrorNote, Grade, JobProgress, Spinner, fmt, useJob, useLoad } from '../ui';

const REG = { verra: 'Verra', 'gold-standard': 'Gold Standard', 'american-carbon-registry': 'ACR', 'climate-action-reserve': 'CAR', 'art-trees': 'ART', isometric: 'Isometric', cercarbono: 'Cercarbono' };

function LoadRegistry({ onDone }) {
  const [jobId, setJobId] = useState(null);
  const [err, setErr] = useState(null);
  const job = useJob(jobId, onDone);
  return (
    <Card title="Registry data not loaded">
      <p className="text-sm text-slate-600 mb-3">Load CarbonPlan's OffsetsDB (Verra, Gold Standard, ACR, CAR, ART TREES, Isometric, Cercarbono — projects plus every issuance and retirement). Admin only.</p>
      <button onClick={() => api.refreshRegistry().then((r) => setJobId(r.job_id)).catch(setErr)} className="inline-flex items-center gap-1.5 text-sm bg-[#08292f] text-white px-3 py-1.5 rounded-md">
        <Database className="w-4 h-4" /> Load registry data
      </button>
      <div className="mt-3"><ErrorNote error={err} /></div>
      {job && <JobProgress job={job} title="Ingesting OffsetsDB" />}
    </Card>
  );
}

export default function Projects() {
  const nav = useNavigate();
  const meta = useLoad(() => api.registryMeta(), []);
  const [f, setF] = useState({ q: '', country: 'India', category: 'all', registry: 'all', rated: '', sort: 'issued', page: 1 });
  const [data, setData] = useState(null);
  const [err, setErr] = useState(null);
  const [selected, setSelected] = useState([]);
  const facets = useLoad(() => api.facets(f.country), [f.country]);

  useEffect(() => {
    if (!meta.data?.loaded) return undefined;
    const t = setTimeout(() => {
      api.projects({ ...f, per_page: 25 }).then((d) => { setData(d); setErr(null); }).catch(setErr);
    }, 200);
    return () => clearTimeout(t);
  }, [f, meta.data]);

  if (meta.loading) return <Spinner />;
  if (!meta.data?.loaded) return <LoadRegistry onDone={() => meta.reload()} />;
  const set = (k) => (e) => setF({ ...f, [k]: e.target.value, page: 1 });
  const toggle = (id) => setSelected((s) => (s.includes(id) ? s.filter((x) => x !== id) : s.length < 5 ? [...s, id] : s));
  const pages = data ? Math.ceil(data.total / data.per_page) : 1;

  return (
    <div className="space-y-4">
      <div className="flex items-end justify-between gap-4 flex-wrap">
        <div>
          <h1 className="text-xl font-semibold">Carbon Project Ratings</h1>
          <p className="text-sm text-slate-500 max-w-3xl">Explainable AI due diligence on {fmt(meta.data.projects)} registry projects. Open a project and run the rating agents — every dimension links to its evidence.</p>
        </div>
        <button disabled={selected.length < 2} onClick={() => nav(`/sylithe/compare?ids=${selected.join(',')}`)}
                className="inline-flex items-center gap-1.5 text-sm bg-[#08292f] text-white px-3 py-1.5 rounded-md disabled:opacity-40">
          <GitCompareArrows className="w-4 h-4" /> Compare {selected.length || ''}
        </button>
      </div>

      <Card bodyClass="p-3">
        <div className="grid grid-cols-2 md:grid-cols-6 gap-2 text-sm">
          <input value={f.q} onChange={set('q')} placeholder="Name, ID or developer" className="col-span-2 border border-slate-300 rounded px-2.5 py-1.5" />
          <select value={f.country} onChange={set('country')} className="border border-slate-300 rounded px-2 py-1.5">
            <option value="all">All countries</option>
            {(facets.data?.countries || []).map((c) => <option key={c.value} value={c.value}>{c.value} ({c.count})</option>)}
          </select>
          <select value={f.category} onChange={set('category')} className="border border-slate-300 rounded px-2 py-1.5">
            <option value="all">All categories</option>
            {(facets.data?.categories || []).map((c) => <option key={c.value} value={c.value}>{c.value} ({c.count})</option>)}
          </select>
          <select value={f.registry} onChange={set('registry')} className="border border-slate-300 rounded px-2 py-1.5">
            <option value="all">All registries</option>
            {(facets.data?.registries || []).map((c) => <option key={c.value} value={c.value}>{REG[c.value] || c.value} ({c.count})</option>)}
          </select>
          <div className="flex gap-2">
            <select value={f.sort} onChange={set('sort')} className="flex-1 border border-slate-300 rounded px-2 py-1.5">
              <option value="issued">Most issued</option><option value="retired">Most retired</option><option value="recent">Recent issuance</option><option value="rating">Rating score</option><option value="name">Name</option>
            </select>
            <label className="flex items-center gap-1 text-xs text-slate-600 whitespace-nowrap"><input type="checkbox" checked={f.rated === '1'} onChange={(e) => setF({ ...f, rated: e.target.checked ? '1' : '', page: 1 })} /> Rated</label>
          </div>
        </div>
      </Card>

      <ErrorNote error={err} />
      <Card bodyClass="p-0" title={data ? `${fmt(data.total)} projects` : 'Projects'} subtitle="Select up to 5 to compare">
        {!data ? <Spinner /> : data.projects.length === 0 ? <div className="p-4"><Empty>No projects match these filters.</Empty></div> : (
          <div className="overflow-x-auto">
            <table className="w-full text-[13px]">
              <thead className="text-[11px] uppercase text-slate-500 bg-slate-50">
                <tr><th className="w-8" /><th className="text-left px-2 py-2">Project</th><th className="text-left px-2">Registry</th><th className="text-left px-2">Category</th><th className="text-left px-2">Methodology</th><th className="text-right px-2">Issued</th><th className="text-right px-2">Retired</th><th className="px-2">Confidence</th><th className="px-3">Rating</th></tr>
              </thead>
              <tbody>
                {data.projects.map((p) => (
                  <tr key={p.project_id} className="border-t border-slate-100 hover:bg-slate-50">
                    <td className="text-center"><input type="checkbox" checked={selected.includes(p.project_id)} onChange={() => toggle(p.project_id)} /></td>
                    <td className="px-2 py-2 max-w-[360px]"><Link to={`/sylithe/project/${p.project_id}`} className="font-medium hover:underline line-clamp-1">{p.name}</Link>
                      <div className="text-[11px] text-slate-400 truncate">{p.project_id} · {p.country} · {p.proponent || '—'}</div></td>
                    <td className="px-2">{REG[p.registry] || p.registry}</td>
                    <td className="px-2 text-slate-600">{p.category}</td>
                    <td className="px-2 text-xs font-mono text-slate-600">{(p.protocol || []).join(', ') || '—'}</td>
                    <td className="px-2 text-right font-mono">{fmt(p.issued)}</td>
                    <td className="px-2 text-right font-mono">{fmt(p.retired)}</td>
                    <td className="px-2 text-center"><Confidence level={p.latest_rating?.confidence} /></td>
                    <td className="px-3 text-center"><Grade grade={p.latest_rating?.grade} size="sm" /></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
        {data && pages > 1 && (
          <div className="flex items-center justify-end gap-2 px-4 py-2 border-t border-slate-100 text-xs">
            <button disabled={f.page <= 1} onClick={() => setF({ ...f, page: f.page - 1 })} className="px-2 py-1 border rounded disabled:opacity-40">Prev</button>
            <span>Page {f.page} / {pages}</span>
            <button disabled={f.page >= pages} onClick={() => setF({ ...f, page: f.page + 1 })} className="px-2 py-1 border rounded disabled:opacity-40">Next</button>
          </div>
        )}
      </Card>
      <Disclaimer>Registry data: {meta.data.citation} (snapshot {String(meta.data.generated_at).slice(0, 10)}). Sylithe ratings are analytical assessments, not registry certification.</Disclaimer>
    </div>
  );
}
