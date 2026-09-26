import React, { useEffect, useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis, Legend } from 'recharts';
import { AlertTriangle, ArrowLeft, ExternalLink, Lock } from 'lucide-react';
import { api } from '../../sylithe/api';
import { useAuth } from '../../context/AuthContext';
import { CATEGORY_LABEL, REGISTRY_LABEL, imageFor, num } from '../theme';
import { Eyebrow, GradeBadge } from '../components';

const RISK = { low: 'text-[#2F5D46]', medium: 'text-[#8A7D1F]', high: 'text-[#C2410C]', unknown: 'text-[#8E8B7E]' };

export default function ProjectPage() {
  const { id } = useParams();
  const { isAuthenticated } = useAuth();
  const [p, setP] = useState(null);
  const [error, setError] = useState(null);
  useEffect(() => { setP(null); api.project(id).then(setP).catch(setError); }, [id]);

  if (error) return <div className="mx-auto max-w-3xl px-5 py-24 text-center text-[#5B6152]">{String(error.message || error)}</div>;
  if (!p) return <div className="mx-auto max-w-7xl px-5 py-24"><div className="h-80 rounded-3xl bg-white/70 animate-pulse" /></div>;
  const r = p.rating;
  const years = [...new Set([...Object.keys(p.issuance_by_year || {}), ...Object.keys(p.retirement_by_year || {})])].filter((y) => y !== 'unknown').sort();
  const flow = years.map((y) => ({ year: y, Issued: p.issuance_by_year?.[y] || 0, Retired: p.retirement_by_year?.[y] || 0 }));

  return (
    <>
      <section className="relative text-white">
        <img src={imageFor(p.category)} alt="" className="absolute inset-0 w-full h-full object-cover object-bottom" />
        <div className="absolute inset-0 bg-gradient-to-t from-[#141810]/95 via-[#141810]/55 to-[#141810]/35" />
        <div className="relative mx-auto max-w-7xl px-5 lg:px-8 pt-14 pb-12">
          <Link to="/projects" className="inline-flex items-center gap-1.5 text-sm text-white/75 hover:text-white"><ArrowLeft className="w-4 h-4" /> All projects</Link>
          <div className="mt-10 flex flex-wrap items-end justify-between gap-6">
            <div className="max-w-4xl">
              <Eyebrow light>{CATEGORY_LABEL[p.category] || p.category} · {p.country} · {REGISTRY_LABEL[p.registry] || p.registry_name}</Eyebrow>
              <h1 className="font-display font-light text-4xl md:text-5xl leading-[1.1] mt-3">{p.name}</h1>
              <p className="mt-3 text-white/70 text-sm">{p.project_id} · Developer: {p.proponent || '—'} · Methodology: {(p.protocol || []).join(', ') || '—'}</p>
            </div>
            <div className="text-right">
              <div className="text-xs uppercase tracking-[0.18em] text-white/60 mb-2">Sylithe rating</div>
              <GradeBadge grade={r?.grade} provisional={r?.provisional} size="lg" />
            </div>
          </div>
        </div>
      </section>

      <section className="mx-auto max-w-7xl px-5 lg:px-8 py-12 grid lg:grid-cols-[2fr_1fr] gap-10">
        <div className="space-y-10">
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            {[['Credits issued', `${num(p.issued)} t`], ['Credits retired', `${num(p.retired)} t`],
              ['Retired share', p.retirement_ratio != null ? `${(p.retirement_ratio * 100).toFixed(0)}%` : '—'], ['Status', p.status]].map(([k, v]) => (
              <div key={k} className="rounded-2xl bg-white border border-[#E4DFD3] p-5">
                <div className="text-[11px] uppercase tracking-[0.16em] text-[#8E8B7E]">{k}</div>
                <div className={`font-display text-2xl mt-1 ${k === 'Status' ? 'capitalize' : ''}`}>{v}</div>
              </div>
            ))}
          </div>

          {r ? (
            <div>
              <h2 className="font-display text-3xl">Assessment</h2>
              {r.adjustment?.summary && <p className="mt-3 text-lg text-[#3A3D36] leading-relaxed">{r.adjustment.summary}</p>}
              <p className="mt-2 text-sm text-[#8E8B7E]">{r.methodology_version} · confidence {r.confidence}{r.provisional ? ' · provisional (no project documents analysed yet)' : ''}</p>
              {(r.anomalies || []).length > 0 && (
                <div className="mt-5 rounded-2xl bg-[#FFF6EC] border border-[#F3D2B0] p-5 space-y-2">
                  {r.anomalies.map((a) => <div key={a.key} className="flex gap-2 text-[15px] text-[#7A3E0E]"><AlertTriangle className="w-4 h-4 mt-1 shrink-0" />{a.text}</div>)}
                </div>
              )}
              <div className="mt-6 divide-y divide-[#E4DFD3] border-y border-[#E4DFD3]">
                {r.dimensions.map((d) => (
                  <details key={d.key} className="group py-4">
                    <summary className="flex items-center justify-between gap-4 cursor-pointer list-none">
                      <span className="font-display text-xl">{d.label}</span>
                      <span className="flex items-center gap-4">
                        <span className={`text-sm capitalize ${RISK[d.risk] || RISK.unknown}`}>{d.risk} risk</span>
                        <span className="w-24 h-1.5 rounded-full bg-[#EFEBE2] overflow-hidden hidden sm:block"><span className="block h-full bg-[#2F5D46]" style={{ width: `${d.score ?? 0}%` }} /></span>
                        <span className="w-8 text-right font-medium">{d.score ?? '—'}</span>
                      </span>
                    </summary>
                    <p className="mt-3 text-[#5B6152] leading-relaxed">{d.reason}</p>
                    {(d.evidence || []).length > 0 && (
                      <ul className="mt-2 space-y-1 text-sm text-[#5B6152]">
                        {d.evidence.slice(0, 4).map((e) => <li key={e.evidence_id}>• {e.supports} <span className="text-[#8E8B7E]">({e.source}{e.page ? `, p.${e.page}` : ''})</span></li>)}
                      </ul>
                    )}
                  </details>
                ))}
              </div>
              <p className="mt-4 text-xs text-[#8E8B7E]">{r.disclaimer}</p>
            </div>
          ) : (
            <div className="rounded-3xl bg-white border border-[#E4DFD3] p-8">
              <h2 className="font-display text-3xl">Not rated yet</h2>
              <p className="mt-3 text-[#5B6152]">Sylithe's rating agents haven't assessed this project yet. A rating covers additionality, baseline integrity, permanence, leakage, monitoring, verification, the developer's track record and more.</p>
              <Link to={isAuthenticated ? `/sylithe/project/${p.project_id}` : '/login'} className="mt-6 inline-flex items-center gap-2 rounded-full bg-[#1D2118] text-white px-5 py-2.5">
                {isAuthenticated ? 'Run the rating agents' : <><Lock className="w-4 h-4" /> Sign in to request a rating</>}
              </Link>
            </div>
          )}

          {flow.length > 0 && (
            <div>
              <h2 className="font-display text-3xl">Issuance & retirement</h2>
              <div className="mt-5 rounded-2xl bg-white border border-[#E4DFD3] p-5">
                <ResponsiveContainer width="100%" height={260}>
                  <BarChart data={flow}>
                    <CartesianGrid stroke="#EFEBE2" vertical={false} />
                    <XAxis dataKey="year" tick={{ fontSize: 12 }} /><YAxis tickFormatter={num} tick={{ fontSize: 12 }} width={50} />
                    <Tooltip formatter={(v) => `${Number(v).toLocaleString()} credits`} /><Legend wrapperStyle={{ fontSize: 12 }} />
                    <Bar isAnimationActive={false} dataKey="Issued" fill="#2F5D46" radius={[4, 4, 0, 0]} />
                    <Bar isAnimationActive={false} dataKey="Retired" fill="#C3B64C" radius={[4, 4, 0, 0]} />
                  </BarChart>
                </ResponsiveContainer>
              </div>
            </div>
          )}
        </div>

        <aside className="space-y-6">
          <div className="rounded-3xl bg-[#2F3A2A] text-white p-7">
            <h3 className="font-display text-2xl">Considering this project?</h3>
            <p className="mt-2 text-white/75 text-[15px]">Get the full evidence file: every source, page and quote behind the rating, plus analyst review.</p>
            <Link to={isAuthenticated ? `/sylithe/project/${p.project_id}` : '/signup'} className="mt-5 block text-center rounded-full bg-[#C3B64C] text-[#1D2118] py-3 font-medium">
              {isAuthenticated ? 'Open full assessment' : 'Create a free account'}
            </Link>
          </div>
          {p.developer && (
            <div className="rounded-3xl bg-white border border-[#E4DFD3] p-7">
              <Eyebrow>Developer</Eyebrow>
              <h3 className="font-display text-xl mt-1">{p.proponent}</h3>
              <dl className="mt-4 grid grid-cols-2 gap-4 text-sm">
                <div><dt className="text-[#8E8B7E]">Projects</dt><dd className="font-display text-2xl">{p.developer.projects}</dd></div>
                <div><dt className="text-[#8E8B7E]">Credits issued</dt><dd className="font-display text-2xl">{num(p.developer.total_issued)}</dd></div>
              </dl>
            </div>
          )}
          {p.project_url && (
            <a href={p.project_url} target="_blank" rel="noreferrer" className="flex items-center justify-between rounded-2xl bg-white border border-[#E4DFD3] px-6 py-4 text-[15px] hover:border-[#1D2118]">
              View on registry <ExternalLink className="w-4 h-4" />
            </a>
          )}
        </aside>
      </section>
    </>
  );
}
