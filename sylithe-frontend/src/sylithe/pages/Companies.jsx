import React, { useEffect, useRef, useState } from 'react';
import { Link, useNavigate, useSearchParams } from 'react-router-dom';
import { Bot, Search } from 'lucide-react';
import { api } from '../api';
import { Card, Confidence, Empty, ErrorNote, Grade, JobProgress, Spinner, fmt, useJob, useLoad } from '../ui';

function ResearchPanel({ symbol, onDone }) {
  const [jobId, setJobId] = useState(null);
  const [err, setErr] = useState(null);
  const job = useJob(jobId, onDone);
  const started = useRef(null);
  useEffect(() => {
    if (started.current === symbol) return; // React dev mode runs effects twice — start the agents once
    started.current = symbol;
    setErr(null);
    api.researchCompany(symbol).then((r) => setJobId(r.job_id)).catch(setErr);
  }, [symbol]);
  if (err) return <ErrorNote error={err} />;
  if (!job) return <Spinner label={`Starting agents for ${symbol}…`} />;
  return <JobProgress job={job} title={`Researching ${symbol} — Document Discovery → XBRL → Narrative → Financial & Litigation → Rating`} />;
}

export default function Companies() {
  const nav = useNavigate();
  const [params, setParams] = useSearchParams();
  const [q, setQ] = useState('');
  const [search, setSearch] = useState(null);
  const [searching, setSearching] = useState(false);
  const researching = params.get('research');
  const list = useLoad(() => api.companies(''), []);

  useEffect(() => {
    if (q.trim().length < 2) { setSearch(null); return undefined; }
    const t = setTimeout(() => {
      setSearching(true);
      api.companies(q).then(setSearch).finally(() => setSearching(false));
    }, 300);
    return () => clearTimeout(t);
  }, [q]);

  const onDone = (job) => {
    list.reload();
    if (job.status === 'done' && job.result?.slug) nav(`/sylithe/company/${job.result.slug}`);
  };

  return (
    <div className="space-y-5">
      <div>
        <h1 className="text-xl font-semibold">Company Carbon Intelligence</h1>
        <p className="text-sm text-slate-500 max-w-3xl">
          Pick any NSE-listed company. Sylithe's agents find its BRSR and annual-report filings on NSE, read the exact
          XBRL-tagged emissions data, analyse the PDFs for targets, carbon credits, financials and climate litigation, and
          link every number to its source. No uploads needed.
        </p>
      </div>

      <Card title="Research a company">
        <div className="flex items-center gap-2 border border-slate-300 rounded-md px-3 py-2 bg-white focus-within:border-[#08292f]">
          <Search className="w-4 h-4 text-slate-400" />
          <input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Company name or NSE symbol, e.g. Tata Power, INFY, UltraTech Cement"
                 className="flex-1 text-sm outline-none" />
        </div>
        {searching && <Spinner label="Searching NSE listings…" />}
        {search && (
          <div className="mt-3 divide-y divide-slate-100 border border-slate-200 rounded-md">
            {(search.nse_matches || []).map((m) => (
              <div key={m.symbol} className="flex items-center justify-between px-3 py-2 text-sm">
                <div>
                  <div className="font-medium">{m.name}</div>
                  <div className="text-xs text-slate-500">NSE: {m.symbol} · ISIN {m.isin} · listed {m.listed_on}</div>
                </div>
                {m.tracked ? (
                  <span className="text-xs text-slate-500">Tracked</span>
                ) : (
                  <button onClick={() => setParams({ research: m.symbol })}
                          className="inline-flex items-center gap-1.5 text-xs bg-[#08292f] text-white px-2.5 py-1.5 rounded">
                    <Bot className="w-3.5 h-3.5" /> Run research agents
                  </button>
                )}
              </div>
            ))}
            {!search.nse_matches?.length && <div className="p-3 text-sm text-slate-500">No NSE-listed company matches “{q}”. Coverage is currently NSE-listed equities.</div>}
          </div>
        )}
        {researching && <div className="mt-4"><ResearchPanel symbol={researching} onDone={onDone} /></div>}
      </Card>

      <Card title="Tracked companies" subtitle="Latest reported BRSR period" bodyClass="p-0">
        {list.loading ? <Spinner /> : list.error ? <div className="p-4"><ErrorNote error={list.error} /></div> : list.data.companies.length === 0 ? (
          <div className="p-4"><Empty>No companies yet — search above and run the research agents.</Empty></div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-[13px]">
              <thead className="text-[11px] uppercase text-slate-500 bg-slate-50">
                <tr>
                  <th className="text-left px-4 py-2">Company</th>
                  <th className="text-left px-2">Industry</th>
                  <th className="text-right px-2">Scope 1+2 (tCO2e)</th>
                  <th className="text-right px-2">YoY</th>
                  <th className="text-right px-2">Renewable %</th>
                  <th className="text-right px-2">Intensity</th>
                  <th className="px-2">Confidence</th>
                  <th className="px-4">Rating</th>
                </tr>
              </thead>
              <tbody>
                {list.data.companies.map((c) => (
                  <tr key={c.slug} className="border-t border-slate-100 hover:bg-slate-50">
                    <td className="px-4 py-2"><Link to={`/sylithe/company/${c.slug}`} className="font-medium hover:underline">{c.name}</Link><div className="text-xs text-slate-400">{c.symbol} · {c.status}</div></td>
                    <td className="px-2 text-slate-600 max-w-[220px] truncate">{c.industry || '—'}</td>
                    <td className="px-2 text-right font-mono">{fmt(c.total_emissions?.current)}<div className="text-[10px] text-slate-400">{c.total_emissions?.period}</div></td>
                    <td className={`px-2 text-right font-mono ${c.total_emissions?.change_pct > 0 ? 'text-rose-600' : 'text-emerald-700'}`}>{c.total_emissions?.change_pct != null ? `${c.total_emissions.change_pct > 0 ? '+' : ''}${c.total_emissions.change_pct}%` : '—'}</td>
                    <td className="px-2 text-right font-mono">{c.renewable_pct?.current != null ? `${c.renewable_pct.current.toFixed(1)}%` : '—'}</td>
                    <td className="px-2 text-right font-mono">{fmt(c.emissions_intensity?.current)}<div className="text-[10px] text-slate-400 truncate max-w-[140px] ml-auto">{c.emissions_intensity?.unit}</div></td>
                    <td className="px-2 text-center"><Confidence level={c.rating?.confidence} /></td>
                    <td className="px-4 text-center"><Grade grade={c.rating?.grade} size="sm" /></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>
    </div>
  );
}
