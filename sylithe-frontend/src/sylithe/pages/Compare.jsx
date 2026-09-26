import React, { useState } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import { api } from '../api';
import { Card, Confidence, Disclaimer, Empty, ErrorNote, Grade, Risk, ScoreBar, Spinner, fmt, useLoad } from '../ui';

export default function Compare() {
  const [params, setParams] = useSearchParams();
  const ids = (params.get('ids') || '').split(',').filter(Boolean);
  const [add, setAdd] = useState('');
  const { data, error, loading } = useLoad(() => (ids.length ? api.compare(ids) : Promise.resolve(null)), [ids.join(',')]);

  const addId = () => { if (add.trim()) { setParams({ ids: [...ids, add.trim().toUpperCase()].slice(0, 5).join(',') }); setAdd(''); } };
  const remove = (id) => setParams({ ids: ids.filter((x) => x !== id).join(',') });

  return (
    <div className="space-y-4">
      <div>
        <h1 className="text-xl font-semibold">Compare projects</h1>
        <p className="text-sm text-slate-500">Side-by-side evidence strength and documented risk per dimension. Select projects on the <Link to="/sylithe/projects" className="underline">Project Ratings</Link> page or add IDs here.</p>
      </div>
      <div className="flex gap-2 max-w-md">
        <input value={add} onChange={(e) => setAdd(e.target.value)} onKeyDown={(e) => e.key === 'Enter' && addId()} placeholder="Project ID, e.g. VCS1566 or GLD12019" className="flex-1 border border-slate-300 rounded px-2.5 py-1.5 text-sm" />
        <button onClick={addId} className="text-sm bg-[#08292f] text-white px-3 rounded">Add</button>
      </div>
      {!ids.length ? <Empty>Add at least two projects to compare.</Empty> : loading ? <Spinner /> : error ? <ErrorNote error={error} /> : (
        <Card bodyClass="p-0">
          <div className="overflow-x-auto">
            <table className="w-full text-[13px] min-w-[720px]">
              <thead>
                <tr className="bg-slate-50 align-top">
                  <th className="text-left px-4 py-3 w-48 text-[11px] uppercase text-slate-500">Dimension</th>
                  {data.projects.map((p) => (
                    <th key={p.project_id} className="text-left px-3 py-3 font-normal">
                      <Link to={`/sylithe/project/${p.project_id}`} className="font-semibold hover:underline line-clamp-2">{p.name}</Link>
                      <div className="text-[11px] text-slate-500">{p.project_id} · {p.category} · {p.country}</div>
                      <div className="flex items-center gap-2 mt-1.5"><Grade grade={p.rating?.grade} size="sm" /><Confidence level={p.rating?.confidence} />
                        <button onClick={() => remove(p.project_id)} className="text-[11px] text-slate-400 hover:text-rose-600 ml-auto">remove</button></div>
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                <tr className="border-t border-slate-100"><td className="px-4 py-2 text-slate-500">Credits issued / retired</td>
                  {data.projects.map((p) => <td key={p.project_id} className="px-3 font-mono">{fmt(p.issued)} / {fmt(p.retired)}</td>)}</tr>
                <tr className="border-t border-slate-100"><td className="px-4 py-2 text-slate-500">Methodology</td>
                  {data.projects.map((p) => <td key={p.project_id} className="px-3 font-mono text-xs">{(p.protocol || []).join(', ') || '—'}</td>)}</tr>
                {data.dimensions.map((dim) => (
                  <tr key={dim.key} className="border-t border-slate-100 align-top">
                    <td className="px-4 py-2.5 font-medium text-slate-700">{dim.label}</td>
                    {data.projects.map((p) => {
                      const d = p.rating?.dimensions?.find((x) => x.key === dim.key);
                      if (!d) return <td key={p.project_id} className="px-3 py-2.5 text-slate-400 text-xs">not rated</td>;
                      return (
                        <td key={p.project_id} className="px-3 py-2.5">
                          <div className="flex items-center justify-between gap-2 mb-1"><Risk risk={d.risk} /><span className="font-mono">{d.score ?? '—'}</span></div>
                          <ScoreBar score={d.score} />
                          <div className="text-[11px] text-slate-500 mt-1 line-clamp-3" title={d.reason}>{d.reason}</div>
                          <div className="mt-1"><Confidence level={d.confidence} /></div>
                        </td>
                      );
                    })}
                  </tr>
                ))}
                <tr className="border-t border-slate-100 align-top"><td className="px-4 py-2 text-slate-500">Anomalies</td>
                  {data.projects.map((p) => <td key={p.project_id} className="px-3 py-2 text-xs text-slate-600">{(p.rating?.anomalies || []).map((a) => a.text).join(' · ') || 'none detected'}</td>)}</tr>
              </tbody>
            </table>
          </div>
        </Card>
      )}
      {data && <Disclaimer>{data.language_note} {data.disclaimer}</Disclaimer>}
    </div>
  );
}
