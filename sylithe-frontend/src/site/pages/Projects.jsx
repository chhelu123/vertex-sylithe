import React, { useEffect, useState } from 'react';
import { Search } from 'lucide-react';
import { api } from '../../sylithe/api';
import { CATEGORY_LABEL, REGISTRY_LABEL, num } from '../theme';
import { Pill, ProjectCard, SectionTitle } from '../components';

const CATEGORIES = ['all', 'forest', 'agriculture', 'renewable-energy', 'energy-efficiency', 'ghg-management', 'fuel-switching', 'land-use', 'biomass-cdr'];

export default function Projects() {
  const [f, setF] = useState({ q: '', country: 'India', category: 'all', registry: 'all', rated: '', sort: 'issued', page: 1 });
  const [data, setData] = useState(null);
  const [facets, setFacets] = useState(null);
  const [error, setError] = useState(null);

  useEffect(() => { api.facets(f.country).then(setFacets).catch(() => {}); }, [f.country]);
  useEffect(() => {
    const t = setTimeout(() => {
      api.projects({ ...f, per_page: 24 }).then((d) => { setData(d); setError(d.message && !d.projects?.length ? d.message : null); }).catch(setError);
    }, 200);
    return () => clearTimeout(t);
  }, [f]);

  const set = (patch) => setF({ ...f, ...patch, page: 1 });
  const pages = data ? Math.max(1, Math.ceil(data.total / data.per_page)) : 1;

  return (
    <div className="mx-auto max-w-7xl px-5 lg:px-8 py-14">
      <SectionTitle eyebrow="Marketplace" title="Carbon projects, rated on evidence." intro="Every project listed on the Verra, Gold Standard, ACR, CAR, ART TREES, Isometric and Cercarbono registries, with issuance and retirement history. Projects rated by Sylithe show their grade." />

      <div className="mt-10 flex flex-col lg:flex-row gap-3 lg:items-center">
        <div className="flex items-center gap-2 rounded-full bg-white border border-[#E4DFD3] px-4 py-2.5 flex-1">
          <Search className="w-4 h-4 text-[#8E8B7E]" />
          <input value={f.q} onChange={(e) => set({ q: e.target.value })} placeholder="Search by project, ID or developer" className="flex-1 outline-none bg-transparent text-[15px]" />
        </div>
        <select value={f.country} onChange={(e) => set({ country: e.target.value })} className="rounded-full bg-white border border-[#E4DFD3] px-4 py-2.5 text-[15px]">
          <option value="all">All countries</option>
          {(facets?.countries || []).map((c) => <option key={c.value} value={c.value}>{c.value} ({c.count})</option>)}
        </select>
        <select value={f.registry} onChange={(e) => set({ registry: e.target.value })} className="rounded-full bg-white border border-[#E4DFD3] px-4 py-2.5 text-[15px]">
          <option value="all">All registries</option>
          {(facets?.registries || []).map((c) => <option key={c.value} value={c.value}>{REGISTRY_LABEL[c.value] || c.value}</option>)}
        </select>
        <select value={f.sort} onChange={(e) => set({ sort: e.target.value })} className="rounded-full bg-white border border-[#E4DFD3] px-4 py-2.5 text-[15px]">
          <option value="issued">Most credits issued</option><option value="retired">Most retired</option><option value="recent">Recently issued</option><option value="rating">Highest rated</option>
        </select>
      </div>
      <div className="mt-4 flex flex-wrap gap-2">
        {CATEGORIES.map((c) => <Pill key={c} active={f.category === c} onClick={() => set({ category: c })}>{c === 'all' ? 'All types' : CATEGORY_LABEL[c]}</Pill>)}
        <Pill active={f.rated === '1'} onClick={() => set({ rated: f.rated === '1' ? '' : '1' })}>Rated by Sylithe</Pill>
      </div>

      <div className="mt-8 text-sm text-[#5B6152]">{data ? `${num(data.total)} projects` : 'Loading projects…'}</div>
      {error && <div className="mt-4 rounded-xl bg-white border border-[#E4DFD3] p-5 text-[#5B6152]">{String(error.message || error)}</div>}
      <div className="mt-4 grid sm:grid-cols-2 lg:grid-cols-3 gap-6">
        {!data && Array.from({ length: 6 }).map((_, i) => <div key={i} className="rounded-2xl bg-white/70 border border-[#E4DFD3] h-[380px] animate-pulse" />)}
        {data?.projects.map((p) => <ProjectCard key={p.project_id} p={p} />)}
      </div>
      {data && data.projects.length === 0 && !error && <div className="mt-6 rounded-xl bg-white border border-[#E4DFD3] p-8 text-center text-[#5B6152]">No projects match these filters.</div>}

      {data && pages > 1 && (
        <div className="mt-10 flex items-center justify-center gap-3 text-sm">
          <button disabled={f.page <= 1} onClick={() => setF({ ...f, page: f.page - 1 })} className="rounded-full border border-[#1D2118] px-5 py-2 disabled:opacity-30">Previous</button>
          <span className="text-[#5B6152]">Page {f.page} of {pages}</span>
          <button disabled={f.page >= pages} onClick={() => setF({ ...f, page: f.page + 1 })} className="rounded-full border border-[#1D2118] px-5 py-2 disabled:opacity-30">Next</button>
        </div>
      )}
    </div>
  );
}
