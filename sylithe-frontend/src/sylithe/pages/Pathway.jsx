// Emissions pathway & carbon suggestion: how much the company emits, how much it should emit,
// the gap, how to close it, and matching carbon projects for residual emissions.
import React from 'react';
import { Link } from 'react-router-dom';
import { CartesianGrid, ComposedChart, Legend, Line, ResponsiveContainer, Scatter, Tooltip, XAxis, YAxis } from 'recharts';
import { CheckCircle2, ExternalLink, TrendingDown, TriangleAlert } from 'lucide-react';
import { Card, Empty, EvidenceLink, Grade, fmt, fmtFull, cx } from '../ui';

function Stat({ label, value, sub, tone }) {
  return (
    <div className="border border-slate-200 rounded-lg px-3.5 py-3 bg-white">
      <div className="text-[11px] uppercase tracking-wider text-slate-500">{label}</div>
      <div className={cx('text-lg font-mono font-semibold mt-0.5', tone)}>{value}</div>
      {sub && <div className="text-[11px] text-slate-500 mt-0.5">{sub}</div>}
    </div>
  );
}

function SbtiBadge({ sbti }) {
  const s = sbti?.status || 'Not on SBTi dashboard';
  const tone = /validated/i.test(s) ? 'bg-emerald-50 text-emerald-700 border-emerald-200'
    : /removed/i.test(s) ? 'bg-rose-50 text-rose-700 border-rose-200'
    : /commit/i.test(s) ? 'bg-amber-50 text-amber-700 border-amber-200' : 'bg-slate-50 text-slate-600 border-slate-200';
  return (
    <a href={sbti?.source || 'https://sciencebasedtargets.org/target-dashboard'} target="_blank" rel="noreferrer"
       className={cx('inline-flex items-center gap-1 text-[11px] font-medium border rounded px-2 py-0.5', tone)}>
      SBTi: {s}{sbti?.status_reason ? ` · ${sbti.status_reason}` : ''} <ExternalLink className="w-3 h-3" />
    </a>
  );
}

export default function Pathway({ pathway: p }) {
  if (!p) return null;
  if (p.status !== 'computed') {
    return <Card title="Emissions pathway & carbon suggestion"><Empty>{p.note}</Empty></Card>;
  }
  const chart = p.rows.map((r) => ({ year: r.year, Actual: r.actual, '1.5°C pathway': r.pathway_1_5c, 'Company target': r.company_target }));
  const cs = p.credit_suggestion;
  let cumulative = 0;
  const projects = (cs.projects || []).map((x) => { cumulative += x.available; return { ...x, cumulative }; });
  const above = p.gap_latest > 0;

  return (
    <Card title="Emissions pathway & carbon suggestion"
          subtitle={`${p.scope} · how much the company emits vs how much it should emit · ${p.version}`}
          action={<SbtiBadge sbti={p.sbti} />}>
      <div className="grid grid-cols-2 lg:grid-cols-5 gap-3">
        <Stat label={`Emitting (${p.latest_period})`} value={`${fmt(p.latest_value)} t`} sub="Scope 1+2, disclosed" />
        <Stat label="Should emit (1.5°C)" value={`${fmt(p.rows.find((r) => r.period === p.latest_period)?.pathway_1_5c)} t`} sub={`−4.2%/yr from ${p.base_period}`} />
        <Stat label="Gap vs pathway" value={`${above ? '+' : ''}${fmt(p.gap_latest)} t`} sub={above ? 'above the 1.5°C pathway' : 'on or below pathway'}
              tone={above ? 'text-rose-600' : 'text-emerald-700'} />
        <Stat label="Cut needed by 2030" value={`${fmt(p.required_cut_by_2030)} t`} sub={`≈ ${p.required_annual_rate_to_2030}% of today's emissions per year`} />
        <Stat label="Residual at net zero" value={`${fmt(p.residual_at_net_zero)} t`} sub="10% of base year (2050)" />
      </div>

      <div className="grid xl:grid-cols-[1.2fr_1fr] gap-5 mt-5">
        <div>
          <ResponsiveContainer width="100%" height={260}>
            <ComposedChart data={chart} margin={{ left: 8, right: 8 }}>
              <CartesianGrid stroke="#eef2f7" />
              <XAxis dataKey="year" type="number" domain={['dataMin', 'dataMax']} tick={{ fontSize: 11 }} />
              <YAxis tickFormatter={(v) => fmt(v)} tick={{ fontSize: 11 }} width={60} />
              <Tooltip formatter={(v) => (v == null ? '—' : `${Number(v).toLocaleString()} tCO2e`)} labelFormatter={(y) => `Year ${y}`} />
              <Legend wrapperStyle={{ fontSize: 11 }} />
              <Line isAnimationActive={false} type="linear" dataKey="1.5°C pathway" stroke="#0f766e" strokeWidth={2} dot={false} />
              {p.company_target && <Line isAnimationActive={false} type="linear" dataKey="Company target" stroke="#b45309" strokeDasharray="5 4" strokeWidth={2} dot={false} connectNulls />}
              <Scatter isAnimationActive={false} dataKey="Actual" fill="#08292f" />
            </ComposedChart>
          </ResponsiveContainer>
          {p.company_target && <div className="text-[11px] text-slate-500 mt-1">Company target line: {p.company_target.label}. {p.company_target.assumption}. {p.company_target.evidence_id && <EvidenceLink id={p.company_target.evidence_id}>source</EvidenceLink>}</div>}
          {p.sbti?.target?.note && <div className="text-[11px] text-amber-700 mt-1">{p.sbti.target.label}: {p.sbti.target.note}</div>}
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-[13px]">
            <thead className="text-[11px] uppercase text-slate-500 bg-slate-50">
              <tr><th className="text-left px-2 py-1.5">Year</th><th className="text-right px-2">Emitting</th><th className="text-right px-2">Should emit (1.5°C)</th><th className="text-right px-2">Company target</th><th className="text-right px-2">Gap</th></tr>
            </thead>
            <tbody>
              {p.rows.map((r) => (
                <tr key={r.year} className="border-t border-slate-100">
                  <td className="px-2 py-1.5">{r.period || r.year}</td>
                  <td className="px-2 text-right font-mono">{r.actual != null ? fmtFull(Math.round(r.actual)) : <span className="text-slate-300">—</span>}</td>
                  <td className="px-2 text-right font-mono">{fmtFull(Math.round(r.pathway_1_5c))}</td>
                  <td className="px-2 text-right font-mono">{r.company_target != null ? fmtFull(Math.round(r.company_target)) : '—'}</td>
                  <td className={cx('px-2 text-right font-mono', r.gap > 0 ? 'text-rose-600' : r.gap != null ? 'text-emerald-700' : '')}>
                    {r.gap != null ? `${r.gap > 0 ? '+' : ''}${fmtFull(Math.round(r.gap))}` : ''}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          <div className="text-[11px] text-slate-400 mt-1">tCO2e. Future years show what the company should emit; actuals appear as they are disclosed.</div>
        </div>
      </div>

      <div className="grid lg:grid-cols-2 gap-5 mt-6">
        <div>
          <div className="text-[12px] font-semibold uppercase tracking-wide text-slate-700 mb-2 flex items-center gap-1.5"><TrendingDown className="w-4 h-4" /> 1 · Reduce first: suggested levers</div>
          {p.levers.length === 0 ? <Empty>No specific levers flagged from the disclosed data.</Empty> : (
            <ol className="space-y-2">
              {p.levers.map((l, i) => (
                <li key={i} className="text-[13px] border border-slate-200 rounded-md p-2.5 bg-white">
                  <div className="font-medium text-slate-800">{i + 1}. {l.lever} <span className="text-[10px] font-normal uppercase text-slate-400 ml-1">{l.addresses}</span></div>
                  <div className="text-xs text-slate-500 mt-0.5">{l.why}</div>
                </li>
              ))}
            </ol>
          )}
        </div>
        <div>
          <div className="text-[12px] font-semibold uppercase tracking-wide text-slate-700 mb-2 flex items-center gap-1.5">
            {above ? <TriangleAlert className="w-4 h-4 text-rose-600" /> : <CheckCircle2 className="w-4 h-4 text-emerald-600" />} 2 · Matching carbon suggestion
          </div>
          <div className="text-[13px] text-slate-700">
            <span className="font-mono font-semibold">{fmtFull(Math.round(cs.sizing_tco2e))} tCO2e</span> <span className="text-slate-500">— {cs.basis}.</span>
          </div>
          <div className="text-xs text-slate-500 mt-1">{cs.rule}</div>
          {projects.length === 0 ? <div className="mt-2"><Empty>No matching projects found in the registry data.</Empty></div> : (
            <table className="w-full text-[12.5px] mt-2">
              <thead className="text-[10.5px] uppercase text-slate-500 bg-slate-50">
                <tr><th className="text-left px-2 py-1.5">Project</th><th className="px-1">Type</th><th className="text-right px-2">Unretired</th><th className="text-right px-2">Covers</th><th className="px-2">Rating</th></tr>
              </thead>
              <tbody>
                {projects.map((x) => (
                  <tr key={`${x.project_id}-${x.kind}`} className="border-t border-slate-100 align-top">
                    <td className="px-2 py-1.5"><Link to={`/sylithe/project/${x.project_id}`} className="hover:underline line-clamp-2">{x.name}</Link>
                      <div className="text-[10.5px] text-slate-400">{x.project_id} · {x.category} · {(x.protocol || []).join(', ')}</div></td>
                    <td className="px-1 text-center"><span className={cx('text-[10px] px-1.5 py-0.5 rounded', x.kind === 'removal' ? 'bg-emerald-50 text-emerald-700' : 'bg-sky-50 text-sky-700')}>{x.kind}</span></td>
                    <td className="px-2 text-right font-mono">{fmt(x.available)}</td>
                    <td className="px-2 text-right text-[11px]">{x.covers_gap ? 'full need' : `${Math.min(100, Math.round((x.cumulative / cs.sizing_tco2e) * 100))}% cum.`}</td>
                    <td className="px-2 text-center">{x.grade ? <Grade grade={x.grade} size="sm" /> : <Link to={`/sylithe/project/${x.project_id}`} className="text-[10.5px] text-[#08292f] underline">rate it</Link>}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
          <div className="text-[11px] text-slate-400 mt-1">Same country first; removals before avoidance; methodologies with cited integrity concerns and grades below BBB excluded. Unrated projects should be rated before purchase.</div>
        </div>
      </div>

      <details className="mt-5 text-xs text-slate-500">
        <summary className="cursor-pointer">Assumptions & sources</summary>
        <ul className="list-disc pl-4 mt-2 space-y-1">{p.assumptions.map((a, i) => <li key={i}>{a}</li>)}</ul>
        <ul className="mt-2 space-y-1">{p.sources.map((s, i) => <li key={i}><a href={s.url} target="_blank" rel="noreferrer" className="underline">{s.title}</a></li>)}</ul>
      </details>
    </Card>
  );
}
