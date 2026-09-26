import React, { useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import { Bar, BarChart, CartesianGrid, Cell, LabelList, Legend, Pie, PieChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';
import { AlertTriangle, ArrowDownRight, ArrowUpRight, FileText, Sparkles } from 'lucide-react';
import { api } from '../api';
import {
  Card, Confidence, Empty, ErrorNote, Grade, Spinner, fmt, useLoad, cx, InfoGrid, Section, DistributionList, StatusPill,
  CHART_COLORS, chartAxis, chartGrid, chartTooltip, chartLegend,
} from '../ui';

const REG = { verra: 'Verra', 'gold-standard': 'Gold Standard', 'american-carbon-registry': 'ACR', 'climate-action-reserve': 'CAR', 'art-trees': 'ART', isometric: 'Isometric', cercarbono: 'Cercarbono' };
const CAT_COLORS = ['#DCC46B', '#D9964A', '#4E7F4F', '#5B9BD5', '#93B35F', '#8B7FBF', '#C9A26B', '#7A9E9F'];
const GRADE_COLORS = { AAA: '#2F5D46', AA: '#3E7358', A: '#4F8A6B', BBB: '#7F8A6E', BB: '#A3A35A', B: '#C3A13B', C: '#E07A2F', D: '#C2410C' };


function Delta({ value }) {
  if (value == null) return <span className="text-slate-300">—</span>;
  const up = value > 0;
  return (
    <span className={cx('inline-flex items-center gap-0.5 rounded-full px-2 py-0.5 text-xs font-medium',
      up ? 'bg-rose-50 text-rose-700' : 'bg-emerald-50 text-emerald-700')}>
      {up ? <ArrowUpRight className="w-3 h-3" /> : <ArrowDownRight className="w-3 h-3" />}{Math.abs(value).toFixed(1)}%
    </span>
  );
}

function Toggle({ value, onChange, options }) {
  return (
    <div className="inline-flex rounded-lg bg-slate-100 p-0.5 text-xs">
      {options.map(([k, l]) => (
        <button key={k} onClick={() => onChange(k)} className={cx('px-2.5 py-1 rounded-md', value === k ? 'bg-white shadow-sm text-slate-900 font-medium' : 'text-slate-500')}>{l}</button>
      ))}
    </div>
  );
}

function EmissionsTrend({ companies }) {
  const [mode, setMode] = useState('indexed');
  const data = useMemo(() => {
    const periods = [...new Set(companies.flatMap((c) => c.trend.map((t) => t.period)))].sort();
    return periods.map((p) => {
      const row = { period: p };
      companies.forEach((c) => {
        const v = c.trend.find((t) => t.period === p)?.total_tco2e;
        const base = c.trend[0]?.total_tco2e;
        row[c.name] = v == null ? null : mode === 'indexed' ? +(v / base * 100).toFixed(1) : v;
      });
      return row;
    });
  }, [companies, mode]);
  // even 10- or 20-step ticks around the indexed values
  const indexedTicks = useMemo(() => {
    const vals = data.flatMap((r) => companies.map((c) => r[c.name])).filter((v) => v != null);
    if (!vals.length || mode !== 'indexed') return { domain: [0, 'auto'], ticks: undefined };
    // bars must start at zero so their length is honest
    const step = Math.max(...vals) > 150 ? 50 : 20;
    const lo = 0;
    const hi = Math.ceil((Math.max(...vals) + 5) / step) * step;
    const ticks = [];
    for (let t = lo; t <= hi; t += step) ticks.push(t);
    return { domain: [lo, hi], ticks };
  }, [data, companies, mode]);
  return (
    <Card title="Company emissions trend"
          subtitle={mode === 'indexed' ? 'Scope 1+2, indexed to each company’s first disclosed year = 100' : 'Scope 1+2, tCO2e as reported in BRSR filings'}
          action={<Toggle value={mode} onChange={setMode} options={[['indexed', 'Indexed'], ['absolute', 'Absolute']]} />}
          className="xl:col-span-2"
          footer="Scope 1+2 emissions for every researched company, read from BRSR filings. Indexed view sets each company's first disclosed year to 100 so companies of any size can be compared.">
      {companies.length === 0 ? (
        <Empty>No companies researched yet. <Link className="underline" to="/sylithe/companies">Run the company agents →</Link></Empty>
      ) : (
        <ResponsiveContainer width="100%" height={280}>
          <BarChart data={data} margin={{ top: 8, left: 0, right: 16 }} barCategoryGap="28%" barGap={4}>
            <CartesianGrid {...chartGrid} />
            <XAxis dataKey="period" {...chartAxis} />
            <YAxis {...chartAxis} width={56} tickFormatter={(v) => (mode === 'indexed' ? Math.round(v) : fmt(v))}
                   domain={mode === 'indexed' ? indexedTicks.domain : [0, 'auto']}
                   ticks={mode === 'indexed' ? indexedTicks.ticks : undefined} allowDecimals={false} />
            <Tooltip {...chartTooltip} cursor={{ fill: '#F5F5F3' }} formatter={(v) => (mode === 'indexed' ? `${v} (base = 100)` : `${Number(v).toLocaleString()} tCO2e`)} />
            <Legend {...chartLegend} />
            {companies.map((c, i) => (
              <Bar key={c.slug} isAnimationActive={false} dataKey={c.name} fill={CHART_COLORS[i % CHART_COLORS.length]} maxBarSize={36} radius={[5, 5, 0, 0]}>
                <LabelList dataKey={c.name} position="top" style={{ fontSize: 10.5, fill: '#64748B' }}
                           formatter={(v) => (v == null ? '' : mode === 'indexed' ? Math.round(v) : fmt(v))} />
              </Bar>
            ))}
          </BarChart>
        </ResponsiveContainer>
      )}
    </Card>
  );
}


export default function Overview() {
  const { data, error, loading } = useLoad(() => api.overview(), []);
  if (loading) return <Spinner label="Loading overview…" />;
  if (error) return <ErrorNote error={error} />;
  const { counts, companies, registry, recent_ratings: ratings, alerts, new_disclosures: docs, ai_usage: ai } = data;
  const grades = ['AAA', 'AA', 'A', 'BBB', 'BB', 'B', 'C', 'D'].map((g) => ({ grade: g, count: registry.rating_distribution?.find((r) => r.grade === g)?.count || 0 }));

  return (
    <div className="space-y-6">
      <div className="flex items-end justify-between gap-4 flex-wrap">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight text-slate-900">Overview</h1>
          <p className="text-sm text-slate-500 mt-0.5">Evidence-backed carbon intelligence for companies and carbon projects.</p>
        </div>
        <Link to="/sylithe/research" className="inline-flex items-center gap-1.5 text-sm bg-[#08292f] text-white px-4 py-2 rounded-lg shadow-sm">
          <Sparkles className="w-4 h-4" /> Ask the research agent
        </Link>
      </div>

      <InfoGrid
        title="Platform summary"
        badge={<StatusPill>Live data</StatusPill>}
        cells={[
          { label: 'Companies tracked', value: fmt(counts.companies_tracked), dot: CHART_COLORS[0], sub: `${counts.companies_with_kpis} with KPIs`, subNote: 'NSE-listed, BRSR filings' },
          { label: 'Carbon data points', value: fmt(counts.carbon_data_points), dot: CHART_COLORS[3], sub: 'Evidence-linked', subNote: 'XBRL tag or cited page' },
          { label: 'Projects tracked', value: fmt(counts.projects_tracked), dot: CHART_COLORS[2], sub: '7 registries', subNote: 'OffsetsDB snapshot' },
          { label: 'Projects rated', value: fmt(counts.projects_rated), dot: CHART_COLORS[1], sub: 'Project Rating v0.1', subNote: '11 dimensions' },
          { label: 'AI spend', value: `$${(ai.cost_usd || 0).toFixed(3)}`, sub: `${ai.runs} agent runs`, subNote: `${ai.cache_hits} served from cache` },
        ]}
        footerCells={[
          { label: 'Evidence items', value: fmt(counts.evidence_items) },
          { label: 'Registry snapshot', value: registry.snapshot ? registry.snapshot.slice(0, 10) : '—' },
          { label: 'Credits on record', value: registry.total_issued ? `${fmt(registry.total_issued)} t` : '—' },
          { label: 'Running jobs', value: String(data.running_jobs?.length || 0) },
        ]}
      />

      <div className="grid xl:grid-cols-3 gap-4">
        <EmissionsTrend companies={companies} />
        <Card title="Companies" subtitle="Latest reported period" bodyClass="px-3 pb-3 pt-2"
              footer="Renewable share of energy and the year-on-year change in Scope 1+2.">
          <table className="w-full text-[13px]">
            <thead className="text-xs text-slate-500">
              <tr><th className="text-left px-2 py-2 font-medium">Company</th><th className="text-right px-1.5 font-medium">Renew.</th><th className="text-right px-1.5 font-medium">YoY</th><th className="px-2 font-medium text-center">Rating</th></tr>
            </thead>
            <tbody>
              {companies.map((c, i) => (
                <tr key={c.slug} className="border-t border-slate-100 hover:bg-slate-50/70">
                  <td className="px-3 py-2.5">
                    <Link to={`/sylithe/company/${c.slug}`} className="flex items-center gap-2 hover:underline min-w-0" title={c.name}>
                      <span className="w-2 h-2 rounded-full shrink-0" style={{ background: CHART_COLORS[i % CHART_COLORS.length] }} />
                      <span className="truncate max-w-[120px] 2xl:max-w-[200px]">{c.name.replace(/ (Limited|Ltd\.?)$/i, '')}</span>
                    </Link>
                  </td>
                  <td className="text-right px-2 tabular-nums">{c.renewable_pct != null ? `${c.renewable_pct.toFixed(1)}%` : '—'}</td>
                  <td className="text-right px-2"><Delta value={c.total_change_pct} /></td>
                  <td className="px-3 text-center"><Grade grade={c.grade} size="sm" /></td>
                </tr>
              ))}
              {companies.length === 0 && <tr><td colSpan={4} className="px-3 py-6 text-center text-slate-400">—</td></tr>}
            </tbody>
          </table>
        </Card>
      </div>

      <Section title="Carbon project landscape">
        {!registry.by_registry ? <Empty>An admin must load registry data from the Project Ratings page.</Empty> : (
          <div className="grid xl:grid-cols-3 gap-5">
            <Card title="Credits issued by category" subtitle="All registries · tCO2e"
                  footer="This donut shows how the credits issued across all seven registries split by project category. Each sector is its share of total issuance.">
              <ResponsiveContainer width="100%" height={280}>
                <PieChart>
                  <Pie isAnimationActive={false} data={registry.by_category.slice(0, 8)} dataKey="issued" nameKey="category"
                       innerRadius="58%" outerRadius="88%" paddingAngle={1.5} stroke="#fff" strokeWidth={3}>
                    {registry.by_category.slice(0, 8).map((c, i) => <Cell key={c.category} fill={CAT_COLORS[i % CAT_COLORS.length]} />)}
                  </Pie>
                  <Tooltip {...chartTooltip} formatter={(v) => `${fmt(v)} credits`} />
                </PieChart>
              </ResponsiveContainer>
            </Card>
            <Card title="Issuance by category" subtitle="Share of all credits issued"
                  footer="The precise fraction of issued credits in each category, from the latest registry snapshot.">
              <DistributionList unit="t" format={fmt} legend="Credits in"
                                totalLabel="100% of issued credits"
                                items={registry.by_category.slice(0, 6).map((c, i) => ({ label: c.category, value: c.issued, color: CAT_COLORS[i % CAT_COLORS.length] }))} />
            </Card>
            <Card title="Projects by registry" subtitle={`OffsetsDB snapshot ${registry.snapshot?.slice(0, 10) || ''}`}
                  footer="Number of projects listed on each registry, including projects not yet issuing credits.">
              <DistributionList unit="projects" format={fmt} legend="Projects in"
                                items={registry.by_registry.map((r, i) => ({ label: REG[r.registry] || r.registry, value: r.projects, color: CHART_COLORS[i % CHART_COLORS.length] }))} />
            </Card>
          </div>
        )}
        {registry.rating_distribution?.length > 0 && (
          <Card title="Project rating distribution" subtitle="Sylithe Project Rating v0.1" className="mt-5"
                footer="Grades from Sylithe's rating agents. Provisional ratings (no project documents analysed) are included.">
            <div className="text-[12px] font-semibold text-slate-500 mb-2">Projects</div>
            <ResponsiveContainer width="100%" height={220}>
              <BarChart data={grades} margin={{ top: 8 }}>
                <CartesianGrid {...chartGrid} />
                <XAxis dataKey="grade" {...chartAxis} />
                <YAxis allowDecimals={false} {...chartAxis} width={28} />
                <Tooltip {...chartTooltip} cursor={{ fill: '#F5F5F3' }} />
                <Bar isAnimationActive={false} dataKey="count" barSize={44}>
                  {grades.map((g) => <Cell key={g.grade} fill={GRADE_COLORS[g.grade]} />)}
                  <LabelList dataKey="count" position="top" style={{ fontSize: 12, fill: '#334155', fontWeight: 600 }} formatter={(v) => (v ? v : '')} />
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </Card>
        )}
      </Section>

      <div className="grid xl:grid-cols-3 gap-4">
        <Card title="Alerts" subtitle="Registry anomalies found by the Anomaly Agent" bodyClass="px-2 pb-3 pt-1">
          {alerts.length === 0 ? <div className="p-3"><Empty>No alerts.</Empty></div> : (
            <ul className="divide-y divide-slate-100">
              {alerts.map((a, i) => (
                <li key={i} className="px-3 py-3 text-[13px]">
                  <div className="flex items-center gap-2 font-medium text-slate-800">
                    <span className={cx('w-6 h-6 rounded-full flex items-center justify-center', a.severity === 'high' ? 'bg-rose-50' : 'bg-amber-50')}>
                      <AlertTriangle className={cx('w-3.5 h-3.5', a.severity === 'high' ? 'text-rose-600' : 'text-amber-600')} />
                    </span>
                    <Link to={`/sylithe/project/${a.project_id}`} className="hover:underline truncate">{a.project_name}</Link>
                  </div>
                  <div className="text-slate-500 text-xs mt-1 pl-8">{a.text}</div>
                </li>
              ))}
            </ul>
          )}
        </Card>
        <Card title="Recent project ratings" bodyClass="px-2 pb-3 pt-1">
          {ratings.length === 0 ? <div className="p-3"><Empty>—</Empty></div> : (
            <ul className="divide-y divide-slate-100">
              {ratings.map((r) => (
                <li key={r.id} className="px-3 py-2.5 flex items-center justify-between gap-2 text-[13px]">
                  <Link to={`/sylithe/project/${r.project_id}`} className="truncate hover:underline text-slate-800">{r.project_name}</Link>
                  <div className="flex items-center gap-2 shrink-0"><Confidence level={r.confidence} /><Grade grade={r.grade} size="sm" /></div>
                </li>
              ))}
            </ul>
          )}
        </Card>
        <Card title="New disclosures" subtitle="Filings discovered by the Document Discovery Agent" bodyClass="px-2 pb-3 pt-1">
          {docs.length === 0 ? <div className="p-3"><Empty>—</Empty></div> : (
            <ul className="divide-y divide-slate-100">
              {docs.map((d) => (
                <li key={d.id} className="px-3 py-2.5 text-[13px] flex items-start gap-2.5">
                  <span className="w-7 h-7 rounded-lg bg-slate-100 flex items-center justify-center shrink-0"><FileText className="w-3.5 h-3.5 text-slate-500" /></span>
                  <div className="min-w-0">
                    <a href={d.source_url} target="_blank" rel="noreferrer" className="hover:underline text-slate-800">{d.title}</a>
                    <div className="text-xs text-slate-500 truncate">
                      <Link to={`/sylithe/company/${d.company_id}`} className="hover:underline">{d.company_id}</Link> · filed {d.publication_date || '—'}
                    </div>
                  </div>
                </li>
              ))}
            </ul>
          )}
        </Card>
      </div>
      {registry.citation && <p className="text-[11px] text-slate-400">Registry data: {registry.citation}. Registry terms may apply.</p>}
    </div>
  );
}
