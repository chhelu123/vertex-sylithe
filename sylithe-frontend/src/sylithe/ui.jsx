// Shared Sylithe UI primitives — evidence-first, data-dense, no decorative gradients.
import React, { createContext, useCallback, useContext, useEffect, useState } from 'react';
import { ExternalLink, FileText, Loader2, X, CheckCircle2, XCircle, CircleDashed, ShieldCheck, AlertTriangle } from 'lucide-react';
import { api } from './api';

export const cx = (...c) => c.filter(Boolean).join(' ');

export const fmt = (v, digits = 0) => {
  if (v === null || v === undefined || Number.isNaN(v)) return '—';
  if (typeof v !== 'number') return String(v);
  const abs = Math.abs(v);
  if (abs >= 1e9) return `${(v / 1e9).toFixed(2)}B`;
  if (abs >= 1e6) return `${(v / 1e6).toFixed(2)}M`;
  if (abs >= 1e4) return `${(v / 1e3).toFixed(1)}k`;
  return v.toLocaleString(undefined, { maximumFractionDigits: digits || (abs < 10 ? 2 : 0) });
};

export const fmtFull = (v) =>
  v === null || v === undefined ? '—' : Number(v).toLocaleString(undefined, { maximumFractionDigits: 2 });

// Card: divided header (title · subtitle · control), body, optional footer note.
export function Card({ title, subtitle, action, children, className, bodyClass, footer }) {
  return (
    <section className={cx('bg-white border border-[#E6E4DF] rounded-xl flex flex-col', className)}>
      {(title || action) && (
        <header className="flex items-start justify-between gap-3 px-6 pt-5 pb-4 border-b border-[#EEECE8]">
          <div className="min-w-0">
            {title && <h3 className="text-[17px] font-semibold text-slate-900 leading-snug">{title}</h3>}
            {subtitle && <p className="text-[13.5px] text-slate-500 mt-1">{subtitle}</p>}
          </div>
          {action}
        </header>
      )}
      <div className={cx('p-6 flex-1', bodyClass)}>{children}</div>
      {footer && <footer className="px-6 py-4 border-t border-[#EEECE8] text-[13.5px] leading-relaxed text-slate-500">{footer}</footer>}
    </section>
  );
}

// Section: a grey-header container that groups related cards.
export function Section({ title, action, children, className }) {
  return (
    <section className={cx('bg-white border border-[#E6E4DF] rounded-2xl overflow-hidden', className)}>
      <header className="flex items-center justify-between px-6 py-4 bg-[#F7F7F5] border-b border-[#E6E4DF]">
        <h2 className="text-[15px] font-semibold text-slate-900">{title}</h2>
        {action}
      </header>
      <div className="p-5 md:p-6">{children}</div>
    </section>
  );
}

// Distribution list: label, value + muted unit, share, thin progress bar; optional total row.
export function DistributionList({ items, unit = '', total, totalLabel, legend, format = fmtFull }) {
  const sum = total ?? items.reduce((a, x) => a + (x.value || 0), 0);
  return (
    <div>
      <ul className="space-y-5">
        {items.map((it) => {
          const pct = sum ? (it.value / sum) * 100 : 0;
          return (
            <li key={it.label} className="grid grid-cols-[1fr_auto] gap-x-6 items-end">
              <div className="min-w-0">
                <div className="text-[14.5px] font-semibold text-slate-800 truncate">{it.label}</div>
                <div className="mt-2 h-2.5 rounded-full bg-[#F0EFEC] overflow-hidden">
                  <div className="h-full rounded-full" style={{ width: `${Math.max(pct, 0.6)}%`, background: it.color }} />
                </div>
              </div>
              <div className="text-right leading-tight">
                <div className="text-[15px] font-semibold text-slate-900 tabular-nums">{format(it.value)}{unit && <span className="text-[12px] font-normal text-slate-400 ml-1">{unit}</span>}</div>
                <div className="text-[12.5px] text-slate-400 tabular-nums">{pct.toFixed(2)}%</div>
              </div>
            </li>
          );
        })}
      </ul>
      {(totalLabel || legend) && (
        <div className="mt-6 pt-5 border-t border-[#EEECE8] flex items-end justify-between gap-4">
          <div className="flex items-center gap-2 text-[14px] text-slate-700">
            <span className="w-4 h-4 rounded bg-[#E2E8F0]" />{legend || 'Values in'} {unit && <span className="text-slate-400">{unit}</span>}
          </div>
          <div className="text-right">
            <div className="text-[15px] font-semibold text-slate-900">Total {format(sum)}{unit && <span className="text-[12px] font-normal text-slate-400 ml-1">{unit}</span>}</div>
            {totalLabel && <div className="text-[12.5px] text-slate-400">{totalLabel}</div>}
          </div>
        </div>
      )}
    </div>
  );
}

// Info grid: "Project Information"-style header row of metric cells + optional footer row.
export function InfoGrid({ title, badge, cells, footerCells }) {
  return (
    <section className="bg-white border border-[#E6E4DF] rounded-2xl overflow-hidden">
      {title && (
        <header className="flex items-center justify-between px-7 py-5 bg-[#F7F7F5] border-b border-[#E6E4DF]">
          <h2 className="text-[19px] font-semibold text-slate-900">{title}</h2>
          {badge}
        </header>
      )}
      <div className="grid grid-cols-2 lg:grid-flow-col lg:auto-cols-fr divide-x divide-y lg:divide-y-0 divide-[#EEECE8]">
        {cells.map((c) => (
          <div key={c.label} className="px-7 py-6 min-w-0">
            <div className="flex items-center gap-2 text-[11.5px] font-semibold uppercase tracking-[0.14em] text-slate-500">
              {c.dot && <span className="w-2 h-2 rounded-full" style={{ background: c.dot }} />}{c.label}
            </div>
            <div className={cx('mt-2.5 font-semibold tracking-tight text-slate-900',
              typeof c.value === 'string' && c.value.length > 7 && !/^[\d.,$%kMB\s—-]+$/.test(c.value)
                ? 'text-[21px] leading-tight line-clamp-2' : 'text-[30px] leading-none truncate')}>
              {c.value ?? '—'}{c.unit && <span className="text-[16px] font-normal text-slate-400 ml-1.5">{c.unit}</span>}
            </div>
            {(c.sub || c.subNote) && (
              <div className="mt-5 pt-4 border-t border-dotted border-slate-300">
                {c.sub && <div className="text-[14px] font-semibold text-slate-800">{c.sub}</div>}
                {c.subNote && <div className="text-[13px] text-slate-400 mt-0.5">{c.subNote}</div>}
              </div>
            )}
          </div>
        ))}
      </div>
      {footerCells && (
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 px-7 py-5 border-t border-[#EEECE8]">
          {footerCells.map((c) => (
            <div key={c.label} className="min-w-0">
              <div className="text-[11.5px] font-semibold uppercase tracking-[0.14em] text-slate-400">{c.label}</div>
              <div className="text-[15px] font-medium text-slate-900 mt-1 truncate" title={typeof c.value === 'string' ? c.value : undefined}>{c.value ?? '—'}</div>
            </div>
          ))}
        </div>
      )}
    </section>
  );
}

export function StatusPill({ children }) {
  return <span className="inline-flex items-center gap-1.5 rounded-full bg-[#F1F0ED] px-3 py-1 text-[13px] font-medium text-slate-700"><span className="w-1.5 h-1.5 rounded-full bg-slate-400" />{children}</span>;
}

// Tabs with an underline on the active tab.
export function Tabs({ tabs, value, onChange }) {
  return (
    <div className="flex gap-7 border-b border-[#E6E4DF] overflow-x-auto">
      {tabs.map(([k, label]) => (
        <button key={k} onClick={() => onChange(k)}
                className={cx('pb-3 -mb-px text-[15px] whitespace-nowrap border-b-2 transition-colors',
                  value === k ? 'border-[#2F8F4E] text-slate-900 font-semibold' : 'border-transparent text-slate-400 hover:text-slate-600')}>
          {label}
        </button>
      ))}
    </div>
  );
}

export function YearSelect({ value, options, onChange }) {
  return (
    <select value={value} onChange={(e) => onChange(e.target.value)} className="border border-[#E0DED9] rounded-lg px-3 py-1.5 text-[14px] bg-white text-slate-800">
      {options.map((o) => <option key={o} value={o}>{o}</option>)}
    </select>
  );
}

// ---------------- Shared chart styling (recharts)
export const CHART_COLORS = ['#2F5D46', '#3A7CA5', '#C3A13B', '#E07A2F', '#7F8A6E', '#8B5E83', '#1F2937', '#5FA8A0'];
export const chartAxis = { tick: { fontSize: 12, fill: '#64748B' }, axisLine: false, tickLine: false };
export const chartGrid = { stroke: '#E2E8F0', strokeDasharray: '3 4', vertical: false };
export const chartTooltip = {
  contentStyle: { borderRadius: 10, border: '1px solid #E2E8F0', boxShadow: '0 8px 24px -8px rgba(15,23,42,0.18)', fontSize: 12, padding: '8px 12px' },
  labelStyle: { color: '#0F172A', fontWeight: 600, marginBottom: 4 },
  cursor: { stroke: '#CBD5E1', strokeDasharray: '3 3' },
};
export const chartDot = (color) => ({ r: 4.5, fill: '#fff', stroke: color, strokeWidth: 2.5 });
export const chartActiveDot = (color) => ({ r: 6, fill: color, stroke: '#fff', strokeWidth: 2 });
export const chartLegend = { iconType: 'circle', iconSize: 8, wrapperStyle: { fontSize: 12, paddingTop: 8, color: '#475569' } };

const CONF = {
  High: 'bg-emerald-50 text-emerald-700 border-emerald-200',
  Medium: 'bg-amber-50 text-amber-700 border-amber-200',
  Low: 'bg-rose-50 text-rose-700 border-rose-200',
};
export function Confidence({ level }) {
  if (!level) return <span className="text-[11px] text-slate-400">—</span>;
  return (
    <span className={cx('inline-flex items-center gap-1 px-1.5 py-0.5 text-[11px] font-medium border rounded', CONF[level])}>
      <span className={cx('w-1.5 h-1.5 rounded-full', level === 'High' ? 'bg-emerald-500' : level === 'Medium' ? 'bg-amber-500' : 'bg-rose-500')} />
      {level}
    </span>
  );
}

// Spec §52 data states
const STATE = {
  Reported: 'text-slate-700 bg-slate-100',
  Calculated: 'text-sky-700 bg-sky-50',
  Estimated: 'text-violet-700 bg-violet-50',
  'Model estimate': 'text-violet-700 bg-violet-50',
  Inference: 'text-orange-700 bg-orange-50',
  'Data not found': 'text-slate-400 bg-slate-50',
};
export function DataState({ state }) {
  if (!state) return null;
  const short = state === 'Data not found' ? 'No data' : state;
  return (
    <span title={state} className={cx('shrink-0 whitespace-nowrap px-1.5 py-0.5 text-[10px] font-medium rounded-md', STATE[state] || STATE.Reported)}>
      {short}
    </span>
  );
}

// One palette for project (AAA–D) and company (A–E) grades: greens = strongest, olive/mustard = middle, orange/red = weakest.
const GRADE_BG = {
  AAA: '#2F5D46', AA: '#3E7358', A: '#4F8A6B', BBB: '#6F8A5E', BB: '#8E9A55', B: '#B39A3A',
  C: '#D9822F', D: '#C2410C', E: '#B42318',
};
export function Grade({ grade, size = 'md', provisional }) {
  const s = size === 'lg' ? 'text-3xl px-4 py-2 min-w-[76px] rounded-xl' : size === 'sm' ? 'text-[11px] px-2 py-0.5 min-w-[34px] rounded-md' : 'text-sm px-2.5 py-1 min-w-[46px] rounded-lg';
  const bg = GRADE_BG[grade];
  return (
    <span className={cx('inline-flex flex-col items-center justify-center font-semibold tracking-wide', s, bg ? 'text-white' : 'bg-slate-100 text-slate-500')}
          style={bg ? { background: bg } : undefined}>
      {grade || 'N/R'}
      {provisional && size === 'lg' && <span className="text-[9px] font-medium tracking-widest uppercase opacity-90">provisional</span>}
    </span>
  );
}

export function Risk({ risk }) {
  const c = { low: 'text-emerald-700 bg-emerald-50', medium: 'text-amber-700 bg-amber-50', high: 'text-rose-700 bg-rose-50', unknown: 'text-slate-500 bg-slate-100' };
  return <span className={cx('px-1.5 py-0.5 text-[11px] font-semibold rounded capitalize', c[risk] || c.unknown)}>{risk || 'unknown'} risk</span>;
}

export function ScoreBar({ score }) {
  if (score === null || score === undefined) return <div className="h-1.5 rounded bg-slate-100" />;
  const color = score >= 70 ? 'bg-emerald-500' : score >= 50 ? 'bg-lime-500' : score >= 35 ? 'bg-amber-500' : 'bg-rose-500';
  return (
    <div className="h-1.5 rounded bg-slate-100 overflow-hidden">
      <div className={cx('h-full', color)} style={{ width: `${Math.max(2, Math.min(100, score))}%` }} />
    </div>
  );
}

export function Spinner({ label }) {
  return (
    <div className="flex items-center gap-2 text-sm text-slate-500 py-6 justify-center">
      <Loader2 className="w-4 h-4 animate-spin" /> {label || 'Loading…'}
    </div>
  );
}

export function ErrorNote({ error }) {
  if (!error) return null;
  return (
    <div className="flex items-start gap-2 text-sm text-rose-700 bg-rose-50 border border-rose-200 rounded p-3">
      <AlertTriangle className="w-4 h-4 mt-0.5 shrink-0" /> <span>{String(error.message || error)}</span>
    </div>
  );
}

export function Empty({ children }) {
  return <div className="text-sm text-slate-500 border border-dashed border-slate-300 rounded-lg p-6 text-center">{children}</div>;
}

export function Disclaimer({ children }) {
  return (
    <div className="flex items-start gap-2 text-xs text-slate-600 bg-slate-50 border border-slate-200 rounded p-2.5">
      <ShieldCheck className="w-4 h-4 text-slate-500 shrink-0" /> <span>{children}</span>
    </div>
  );
}

// ---------------- Evidence drawer (spec §29: view source → page → highlighted evidence)
const EvidenceCtx = createContext(() => {});
export const useEvidence = () => useContext(EvidenceCtx);

export function EvidenceProvider({ children }) {
  const [state, setState] = useState(null); // {id} | {inline}
  const open = useCallback((idOrObj) => setState(typeof idOrObj === 'string' ? { id: idOrObj } : { inline: idOrObj }), []);
  return (
    <EvidenceCtx.Provider value={open}>
      {children}
      {state && <EvidenceDrawer state={state} onClose={() => setState(null)} />}
    </EvidenceCtx.Provider>
  );
}

function EvidenceDrawer({ state, onClose }) {
  const [ev, setEv] = useState(state.inline || null);
  const [err, setErr] = useState(null);
  useEffect(() => {
    if (state.id) api.evidence(state.id).then(setEv).catch(setErr);
  }, [state.id]);
  const pdfLink = ev?.url && ev?.page ? `${ev.url}#page=${ev.page}` : ev?.url;
  return (
    <div className="fixed inset-0 z-[80] flex justify-end" onClick={onClose}>
      <div className="absolute inset-0 bg-slate-900/30" />
      <aside className="relative w-full max-w-md h-full bg-white shadow-xl border-l border-slate-200 overflow-y-auto" onClick={(e) => e.stopPropagation()}>
        <div className="flex items-center justify-between px-4 py-3 border-b border-slate-200">
          <div className="flex items-center gap-2 text-sm font-semibold text-slate-800"><FileText className="w-4 h-4" /> Evidence</div>
          <button onClick={onClose} className="p-1 rounded hover:bg-slate-100" aria-label="Close"><X className="w-4 h-4" /></button>
        </div>
        <div className="p-4 space-y-4 text-sm">
          <ErrorNote error={err} />
          {!ev && !err && <Spinner />}
          {ev && (
            <>
              <div>
                <div className="text-[11px] uppercase tracking-wide text-slate-500 mb-1">Claim</div>
                <div className="font-medium text-slate-900">{ev.claim}</div>
              </div>
              <div className="flex flex-wrap gap-2 items-center">
                <DataState state={ev.label} />
                <Confidence level={ev.confidence} />
                {ev.verified !== undefined && (
                  <span className={cx('inline-flex items-center gap-1 text-[11px]', ev.verified ? 'text-emerald-700' : 'text-rose-600')}>
                    {ev.verified ? <CheckCircle2 className="w-3.5 h-3.5" /> : <XCircle className="w-3.5 h-3.5" />}
                    {ev.verified ? 'Quote verified against source' : 'Quote not verified'}
                  </span>
                )}
              </div>
              {ev.quote && (
                <div>
                  <div className="text-[11px] uppercase tracking-wide text-slate-500 mb-1">Source excerpt{ev.page ? ` · page ${ev.page}` : ''}</div>
                  <blockquote className="border-l-4 border-yellow-400 bg-yellow-50 px-3 py-2 font-mono text-[12px] text-slate-800 whitespace-pre-wrap break-words">
                    {ev.quote}
                  </blockquote>
                </div>
              )}
              <dl className="grid grid-cols-3 gap-y-2 text-[13px]">
                <dt className="text-slate-500">Source</dt><dd className="col-span-2 text-slate-800">{ev.source_title}</dd>
                {ev.period && (<><dt className="text-slate-500">Period</dt><dd className="col-span-2">{ev.period}</dd></>)}
                {ev.value !== undefined && ev.value !== null && (<><dt className="text-slate-500">Value</dt><dd className="col-span-2 font-mono">{fmtFull(ev.value)} {ev.unit}</dd></>)}
                <dt className="text-slate-500">Method</dt><dd className="col-span-2">{ev.extraction_method}{ev.agent ? ` · ${ev.agent}` : ''}</dd>
                {ev.retrieved_at && (<><dt className="text-slate-500">Retrieved</dt><dd className="col-span-2">{new Date(ev.retrieved_at).toLocaleString()}</dd></>)}
              </dl>
              {pdfLink && (
                <a href={pdfLink} target="_blank" rel="noreferrer" className="inline-flex items-center gap-1.5 text-sm font-medium text-[#08292f] underline">
                  Open source{ev.page ? ` at page ${ev.page}` : ''} <ExternalLink className="w-3.5 h-3.5" />
                </a>
              )}
            </>
          )}
        </div>
      </aside>
    </div>
  );
}

export function EvidenceLink({ id, children, className }) {
  const open = useEvidence();
  if (!id) return null;
  return (
    <button onClick={() => open(id)} className={cx('inline-flex items-center gap-1 text-[11px] text-[#08292f] hover:underline', className)}>
      <FileText className="w-3 h-3" /> {children || 'Evidence'}
    </button>
  );
}

// Numbered source chips: "Sources  p.37  XBRL  3" — one tidy line instead of repeated "source" links.
export function SourceChips({ sources, label = 'Sources', max = 4 }) {
  const open = useEvidence();
  const list = (sources || []).filter((x) => x && (x.evidence_id || typeof x === 'string')).slice(0, max);
  if (!list.length) return null;
  return (
    <div className="flex items-center gap-1.5 flex-wrap">
      <span className="text-[11px] text-slate-400 inline-flex items-center gap-1"><FileText className="w-3 h-3" />{label}</span>
      {list.map((x, i) => {
        const id = typeof x === 'string' ? x : x.evidence_id;
        const text = typeof x === 'string' ? i + 1 : x.page ? `p.${x.page}` : x.title && /xbrl/i.test(x.title) ? 'XBRL' : i + 1;
        return (
          <button key={`${id}-${i}`} onClick={() => open(id)} title={typeof x === 'string' ? 'Open evidence' : x.title}
                  className="px-1.5 py-0.5 rounded-md bg-slate-100 hover:bg-[#08292f] hover:text-white text-[11px] font-medium text-slate-600 transition-colors">
            {text}
          </button>
        );
      })}
    </div>
  );
}

// ---------------- Agent job progress (polls /api/jobs/:id)
export function useJob(jobId, onDone) {
  const [job, setJob] = useState(null);
  useEffect(() => {
    if (!jobId) return undefined;
    let alive = true;
    let timer;
    const tick = async () => {
      try {
        const j = await api.job(jobId);
        if (!alive) return;
        setJob(j);
        if (j.status === 'running') timer = setTimeout(tick, 2500);
        else onDone?.(j);
      } catch {
        timer = setTimeout(tick, 5000);
      }
    };
    tick();
    return () => { alive = false; clearTimeout(timer); };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [jobId]);
  return job;
}

export function JobProgress({ job, title = 'AI agents working' }) {
  if (!job) return null;
  return (
    <div className="border border-slate-200 rounded-lg bg-white">
      <div className="flex items-center justify-between px-4 py-2.5 border-b border-slate-100">
        <div className="text-sm font-semibold text-slate-800 flex items-center gap-2">
          {job.status === 'running' && <Loader2 className="w-4 h-4 animate-spin text-[#08292f]" />}
          {title}
        </div>
        <div className="text-[11px] text-slate-500 font-mono">
          {job.status} · est. ${Number(job.cost_usd || 0).toFixed(4)}
        </div>
      </div>
      <ol className="px-4 py-3 space-y-2">
        {(job.steps || []).map((s) => (
          <li key={s.key} className="flex items-start gap-2 text-[13px]">
            {s.status === 'done' ? <CheckCircle2 className="w-4 h-4 text-emerald-600 mt-0.5 shrink-0" />
              : s.status === 'failed' ? <XCircle className="w-4 h-4 text-rose-600 mt-0.5 shrink-0" />
              : <CircleDashed className="w-4 h-4 text-slate-400 animate-spin mt-0.5 shrink-0" />}
            <div>
              <div className="text-slate-800">{s.label}</div>
              {s.detail && <div className="text-xs text-slate-500">{s.detail}</div>}
            </div>
          </li>
        ))}
      </ol>
      {job.error && <div className="px-4 pb-3"><ErrorNote error={job.error} /></div>}
    </div>
  );
}

export function useLoad(fn, deps) {
  const [data, setData] = useState(null);
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(true);
  const load = useCallback(() => {
    setLoading(true);
    setError(null);
    return fn().then(setData).catch(setError).finally(() => setLoading(false));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps);
  useEffect(() => { load(); }, [load]);
  return { data, error, loading, reload: load, setData };
}
