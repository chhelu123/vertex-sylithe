import React, { useMemo, useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import { Bar, BarChart, CartesianGrid, Cell, Legend, Pie, PieChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';
import { ArrowLeft, ExternalLink, RefreshCw, Target, Gavel, Coins, FileText, AlertCircle } from 'lucide-react';
import { api } from '../api';
import Pathway from './Pathway';
import {
  Card, Confidence, DataState, Disclaimer, Empty, ErrorNote, EvidenceLink, Grade, JobProgress, ScoreBar, Spinner,
  fmt, fmtFull, useJob, useLoad,
  InfoGrid, Section, DistributionList, StatusPill, Tabs, SourceChips, chartAxis, chartGrid, chartTooltip, chartLegend,
} from '../ui';

const SCOPE_COLORS = { 'Scope 1': '#4E7F4F', 'Scope 2': '#5B9BD5', 'Scope 3': '#D9964A' };

function ScopeSplit({ kpis }) {
  const k = Object.fromEntries(kpis.map((x) => [x.key, x]));
  const items = [['Scope 1', k.scope1], ['Scope 2', k.scope2], ['Scope 3', k.scope3]]
    .filter(([, x]) => x?.current != null)
    .map(([label, x]) => ({ label, value: x.current, color: SCOPE_COLORS[label] }));
  if (!items.length) return <Empty>No scope data disclosed.</Empty>;
  const period = k.scope1?.period;
  return (
    <div className="grid lg:grid-cols-2 gap-5">
      <Card title="Emissions split" subtitle={`By scope · ${period || ''}`}
            footer="Direct (Scope 1) and purchased-energy (Scope 2) emissions from the BRSR filing. Scope 3 appears only when the company discloses it.">
        <ResponsiveContainer width="100%" height={260}>
          <PieChart>
            <Pie isAnimationActive={false} data={items} dataKey="value" nameKey="label" innerRadius="58%" outerRadius="88%" paddingAngle={1.5} stroke="#fff" strokeWidth={3}>
              {items.map((it) => <Cell key={it.label} fill={it.color} />)}
            </Pie>
            <Tooltip {...chartTooltip} formatter={(v) => `${fmtFull(v)} tCO2e`} />
          </PieChart>
        </ResponsiveContainer>
      </Card>
      <Card title="Emissions by scope" subtitle={`Reported · ${period || ''}`}
            footer="The precise share of reported emissions in each scope.">
        <DistributionList items={items} unit="tCO2e" format={fmt} legend="Emissions in" totalLabel="Scope 1+2 (+3 where disclosed)" />
      </Card>
    </div>
  );
}

function KpiCard({ k }) {
  const up = k.change_pct > 0;
  const good = k.change_pct == null ? null : (k.direction === 'lower' ? !up : k.direction === 'higher' ? up : null);
  if (k.current == null) {
    return (
      <div className="bg-[#FAFAF8] border border-dashed border-[#E0DED9] rounded-xl px-4 py-3.5 flex items-center justify-between gap-3">
        <div className="min-w-0">
          <div className="text-[13.5px] font-medium text-slate-600 leading-snug">{k.label}</div>
          <div className="text-[12.5px] text-slate-400 mt-0.5">Not disclosed in the filings reviewed</div>
        </div>
        <DataState state={k.status} />
      </div>
    );
  }
  return (
    <div className="bg-white border border-[#E6E4DF] rounded-xl p-4 flex flex-col gap-2.5">
      <div className="flex items-start justify-between gap-2">
        <div className="text-[13.5px] font-medium text-slate-600 leading-snug">{k.label}</div>
        <DataState state={k.status} />
      </div>
      <div className="text-[24px] font-semibold tracking-tight text-slate-900 leading-none">
        {fmt(k.current)}
        <span className="text-[12px] font-sans font-normal text-slate-500 ml-1">{k.unit}</span>
      </div>
      <div className="text-[11px] text-slate-500 flex flex-wrap gap-x-3">
        {k.period && <span>{k.period}</span>}
        {k.previous != null && <span>prev {fmt(k.previous)} ({k.previous_period})</span>}
        {k.change_pct != null && (
          <span className={good === null ? 'text-slate-600' : good ? 'text-emerald-700' : 'text-rose-600'}>
            {up ? '▲' : '▼'} {Math.abs(k.change_pct)}%
          </span>
        )}
      </div>
      {k.progress_pct != null && (
        <div>
          <div className="text-[11px] text-slate-500 mb-0.5">Progress to target: {k.progress_pct}%</div>
          <ScoreBar score={k.progress_pct} />
        </div>
      )}
      {k.note && <div className="text-[11px] text-slate-400">{k.note}</div>}
      <div className="mt-auto flex items-center justify-between gap-2 pt-1">
        <Confidence level={k.confidence} />
        <SourceChips sources={k.sources} max={3} />
      </div>
    </div>
  );
}

function RatingPanel({ rating }) {
  if (!rating) return null;
  return (
    <Card title="Sylithe Company Carbon Rating" subtitle={rating.methodology_version}>
      <div className="flex items-start gap-4">
        <Grade grade={rating.grade} size="lg" />
        <div className="text-sm space-y-1.5 min-w-0">
          <div className="whitespace-nowrap"><span className="text-[22px] font-semibold tracking-tight">{rating.overall_score ?? '—'}</span><span className="text-slate-500"> / 100 · {rating.band || 'grade withheld'}</span></div>
          <div className="flex items-center gap-2 text-[12.5px] text-slate-500">Confidence <Confidence level={rating.confidence} /></div>
          <div className="text-[12.5px] text-slate-400 whitespace-nowrap">{rating.dimensions_scored} of {rating.dimensions.length} dimensions scored</div>
          {rating.note && <div className="text-xs text-amber-700 flex gap-1"><AlertCircle className="w-3.5 h-3.5 mt-0.5" />{rating.note}</div>}
        </div>
      </div>
      <div className="mt-5 divide-y divide-[#EEECE8]">
        {rating.dimensions.map((d) => (
          <div key={d.key} className="py-4 first:pt-0 last:pb-0">
            <div className="flex items-center justify-between gap-3 text-[14px] mb-2">
              <span className="font-medium text-slate-800 truncate min-w-0">
                {d.label}
                <span className="ml-2 text-[11px] font-normal text-slate-400">{rating.weights?.[d.key]}%</span>
              </span>
              <span className="flex items-center gap-2 shrink-0"><DataState state={d.status} /><span className="w-9 text-right font-semibold tabular-nums">{d.score ?? '—'}</span></span>
            </div>
            <ScoreBar score={d.score} />
            <div className="text-[12.5px] leading-relaxed text-slate-500 mt-2">{d.reason}</div>
            <div className="mt-1.5"><SourceChips sources={d.evidence_ids} label="Evidence" /></div>
          </div>
        ))}
      </div>
      <p className="text-[11px] text-slate-400 mt-4">
        Scores come from documented rules over disclosed data (<Link to="/sylithe/methodology" className="underline">methodology</Link>). No LLM sets the score.
      </p>
    </Card>
  );
}

function EmissionsChart({ slug }) {
  const { data } = useLoad(() => api.companyMetrics(slug), [slug]);
  const rows = useMemo(() => {
    if (!data) return [];
    const pick = (metric) => {
      const best = {};
      for (const m of data.metrics.filter((x) => x.metric === metric)) {
        const rank = m.document_type === 'brsr_xbrl' ? 0 : 1;
        if (!best[m.period] || rank < best[m.period].rank) best[m.period] = { rank, v: m.value_norm ?? m.value };
      }
      return best;
    };
    const s1 = pick('scope1_tco2e');
    const s2 = { ...pick('scope2_tco2e'), ...pick('scope2_location_tco2e'), ...pick('scope2_market_tco2e') };
    const s3 = pick('scope3_tco2e');
    const periods = [...new Set([...Object.keys(s1), ...Object.keys(s2), ...Object.keys(s3)])].filter((p) => p && p !== 'null').sort();
    return periods.map((p) => ({ period: p, 'Scope 1': s1[p]?.v, 'Scope 2': s2[p]?.v, 'Scope 3': s3[p]?.v }));
  }, [data]);
  if (!rows.length) return <Empty>No emissions time series found.</Empty>;
  return (
    <>
    <div className="text-[12px] font-semibold text-slate-500 mb-2">tCO2e</div>
    <ResponsiveContainer width="100%" height={260}>
      <BarChart data={rows} margin={{ top: 4 }}>
        <CartesianGrid {...chartGrid} />
        <XAxis dataKey="period" {...chartAxis} />
        <YAxis tickFormatter={(v) => fmt(v)} {...chartAxis} width={60} />
        <Tooltip {...chartTooltip} cursor={{ fill: '#F5F5F3' }} formatter={(v) => `${Number(v).toLocaleString()} tCO2e`} />
        <Legend {...chartLegend} />
        <Bar isAnimationActive={false} dataKey="Scope 1" stackId="a" fill={SCOPE_COLORS['Scope 1']} barSize={56} />
        <Bar isAnimationActive={false} dataKey="Scope 2" stackId="a" fill={SCOPE_COLORS['Scope 2']} barSize={56} />
        <Bar isAnimationActive={false} dataKey="Scope 3" fill={SCOPE_COLORS['Scope 3']} barSize={56} />
      </BarChart>
    </ResponsiveContainer>
    </>
  );
}

const FIN_LABEL = {
  revenue_inr_cr: 'Revenue', ebitda_inr_cr: 'EBITDA', pat_inr_cr: 'Profit after tax', capex_inr_cr: 'Capex',
  environmental_capex_inr_cr: 'Environmental capex', sustainability_expenditure_inr_cr: 'Sustainability expenditure',
  csr_spend_inr_cr: 'CSR spend', legal_professional_fees_inr_cr: 'Legal & professional fees',
  carbon_credit_spend_inr_cr: 'Carbon-credit purchases', renewable_investment_inr_cr: 'Renewable-energy investment',
  environmental_penalties_inr_cr: 'Environmental penalties',
};

export default function CompanyProfile() {
  const { slug } = useParams();
  const { data: c, error, loading, reload } = useLoad(() => api.company(slug), [slug]);
  const [jobId, setJobId] = useState(null);
  const [runErr, setRunErr] = useState(null);
  const job = useJob(jobId, () => reload());
  const [tab, setTab] = useState('overview');

  if (loading && !c) return <Spinner label="Loading company…" />;
  if (error) return <ErrorNote error={error} />;
  const symbol = c.listing?.nse_symbol;
  const rerun = () => { setRunErr(null); api.researchCompany(symbol).then((r) => setJobId(r.job_id)).catch(setRunErr); };
  const kpis = (c.kpis || []).filter(Boolean);
  const legal = c.legal_disclosures || [];

  return (
    <div className="space-y-6">
      <div>
        <Link to="/sylithe/companies" className="inline-flex items-center gap-1.5 text-[15px] text-slate-500 hover:text-slate-800"><ArrowLeft className="w-4 h-4" /> Back</Link>
        <div className="mt-3 flex items-start justify-between gap-4 flex-wrap">
          <div>
            <h1 className="text-[28px] font-bold tracking-tight uppercase text-slate-900">{c.name}</h1>
            <div className="text-[15px] text-slate-400 mt-0.5">{c.industry || 'Industry —'} · {c.country || 'India'}</div>
          </div>
          <div className="flex items-center gap-2">
            <StatusPill>{c.rating?.grade ? `Rated ${c.rating.grade}` : 'Not rated'}</StatusPill>
            <button onClick={rerun} disabled={job?.status === 'running'} className="inline-flex items-center gap-1.5 text-sm border border-[#E0DED9] bg-white px-3 py-1.5 rounded-lg hover:bg-slate-50 disabled:opacity-50">
              <RefreshCw className="w-4 h-4" /> Re-run agents
            </button>
          </div>
        </div>
        <div className="mt-6"><Tabs value={tab} onChange={setTab} tabs={[['overview', 'Overview'], ['pathway', 'Pathway'], ['targets', 'Targets & credits'], ['financial', 'Financial & legal'], ['documents', 'Documents']]} /></div>
      </div>
      <ErrorNote error={runErr} />
      {job && <JobProgress job={job} />}
      {c.status === 'no_filings' && <ErrorNote error="No BRSR or annual-report filings were found on NSE for this company." />}

      {tab === 'overview' && (<>
      <InfoGrid
        title="Company Information"
        badge={<StatusPill>{c.status === 'ready' ? 'Researched' : c.status}</StatusPill>}
        cells={(() => {
          const k = Object.fromEntries(kpis.map((x) => [x.key, x]));
          const chg = (x) => (x?.change_pct != null ? `${x.change_pct > 0 ? '▲' : '▼'} ${Math.abs(x.change_pct)}% vs ${x.previous_period}` : 'No prior year');
          return [
            { label: 'Scope 1+2', value: fmt(k.total_emissions?.current), unit: 'tCO2e', sub: chg(k.total_emissions), subNote: k.total_emissions?.period },
            { label: 'Renewable share', dot: '#4E7F4F', value: k.renewable_pct?.current != null ? `${k.renewable_pct.current.toFixed(1)}` : '—', unit: '%', sub: chg(k.renewable_pct), subNote: 'of total energy' },
            { label: 'Emissions intensity', dot: '#D9964A', value: k.emissions_intensity?.current != null ? fmt(k.emissions_intensity.current) : '—', unit: 'tCO2e/₹cr', sub: chg(k.emissions_intensity), subNote: 'per ₹ crore revenue' },
            { label: 'Carbon rating', dot: '#5B9BD5', value: c.rating?.grade || '—', unit: c.rating?.overall_score != null ? `${c.rating.overall_score}/100` : '', sub: c.rating?.band || 'Grade withheld', subNote: c.rating?.methodology_version },
            { label: 'SBTi status', value: c.sbti?.near_term_status ? (/validated/i.test(c.sbti.near_term_status) ? 'Validated' : /removed/i.test(c.sbti.near_term_status) ? 'Removed' : 'Committed') : 'None', sub: c.sbti?.status_reason || (c.sbti ? c.sbti.near_term_classification : 'Not on dashboard'), subNote: 'SBTi Target Dashboard' },
          ];
        })()}
        footerCells={[
          { label: 'NSE symbol', value: symbol },
          { label: 'ISIN', value: c.listing?.isin },
          { label: 'Reporting boundary', value: c.reporting_boundary },
          { label: 'Last researched', value: c.last_researched_at ? new Date(c.last_researched_at).toLocaleDateString(undefined, { day: 'numeric', month: 'short', year: 'numeric' }) : '—' },
        ]}
      />

      <Section title="Emissions by scope">
        <ScopeSplit kpis={kpis} />
        <Card title="Emissions over time" subtitle="tCO2e as reported (BRSR XBRL preferred over PDF extraction)" className="mt-5"
              footer="Stacked Scope 1 and Scope 2 for each reported fiscal year.">
          <EmissionsChart slug={slug} />
        </Card>
      </Section>

      <div className="grid xl:grid-cols-3 gap-4 items-start">
        <div className="xl:col-span-2 space-y-4">
          <Card title="Carbon KPIs" subtitle="Every value: current · previous · change · source · confidence (click a source link to see the exact page and quote)">
            {kpis.length ? (
              <div className="grid sm:grid-cols-2 2xl:grid-cols-3 gap-4">{kpis.map((k) => <KpiCard key={k.key} k={k} />)}</div>
            ) : <Empty>No KPIs yet — run the research agents.</Empty>}
          </Card>
        </div>
        <RatingPanel rating={c.rating} />
      </div>
      </>)}

      {tab === 'pathway' && <Pathway pathway={c.pathway} />}

      {tab === 'targets' && (
      <div className="grid lg:grid-cols-2 gap-4">
        <Card title={<span className="inline-flex items-center gap-1.5"><Target className="w-3.5 h-3.5" /> Climate targets</span>}>
          {(c.targets || []).length === 0 ? <Empty>No climate targets found in the disclosures.</Empty> : (
            <ul className="space-y-3">
              {c.targets.map((t, i) => (
                <li key={i} className="text-[13px]">
                  <div className="flex items-center gap-2 flex-wrap">
                    <span className="px-1.5 py-0.5 bg-slate-100 rounded text-[11px] font-semibold uppercase">{t.type.replace(/_/g, ' ')}</span>
                    {t.target_year && <span className="text-xs text-slate-500">by {t.target_year}</span>}
                    {t.base_year && <span className="text-xs text-slate-500">base {t.base_year}</span>}
                    {t.sbti_status !== 'not_mentioned' && <span className="text-xs text-slate-500">SBTi: {t.sbti_status}</span>}
                    <Confidence level={t.confidence} />
                  </div>
                  <div className="mt-1 text-slate-700">{t.description}</div>
                  <EvidenceLink id={t.evidence_id}>{t.source_title} p.{t.page}</EvidenceLink>
                </li>
              ))}
            </ul>
          )}
          {(c.transition_actions || []).length > 0 && (
            <div className="mt-4 border-t border-slate-100 pt-3">
              <div className="text-[11px] uppercase tracking-wide text-slate-500 mb-1">Transition actions disclosed</div>
              <ul className="list-disc pl-4 text-[13px] space-y-1">
                {c.transition_actions.slice(0, 6).map((a, i) => <li key={i}>{a.description} <EvidenceLink id={a.evidence_id}>p.{a.page}</EvidenceLink></li>)}
              </ul>
            </div>
          )}
        </Card>

        <Card title={<span className="inline-flex items-center gap-1.5"><Coins className="w-3.5 h-3.5" /> Carbon credits & Scope 3</span>}>
          {(c.carbon_credits || []).length === 0 ? <Empty>No carbon-credit purchases, retirements or generation disclosed.</Empty> : (
            <table className="w-full text-[13px]">
              <thead className="text-[11px] uppercase text-slate-500"><tr><th className="text-left">Activity</th><th className="text-right">tCO2e</th><th className="text-left pl-3">Registry / project</th><th /></tr></thead>
              <tbody>{c.carbon_credits.map((x, i) => (
                <tr key={i} className="border-t border-slate-100"><td className="py-1.5 capitalize">{x.activity}</td><td className="text-right font-mono">{fmtFull(x.quantity_tco2e)}</td>
                  <td className="pl-3">{[x.registry, x.project, x.vintage].filter(Boolean).join(' · ') || '—'}</td><td><EvidenceLink id={x.evidence_id}>p.{x.page}</EvidenceLink></td></tr>
              ))}</tbody>
            </table>
          )}
          {(c.scope3_categories || []).length > 0 && (
            <div className="mt-4">
              <div className="text-[11px] uppercase tracking-wide text-slate-500 mb-1">Scope 3 categories</div>
              {c.scope3_categories.map((s, i) => (
                <div key={i} className="flex justify-between text-[13px] border-t border-slate-100 py-1">
                  <span>{s.category} <span className="text-slate-400 text-xs">{s.period}</span></span>
                  <span className="font-mono">{fmtFull(s.value)} {s.unit} <EvidenceLink id={s.evidence_id} /></span>
                </div>
              ))}
            </div>
          )}
        </Card>
      </div>
      )}

      {tab === 'financial' && (
      <Card title={<span className="inline-flex items-center gap-1.5"><Gavel className="w-4 h-4" /> Climate financial exposure</span>}
            subtitle="Financial context from the annual report, and legal/environmental matters. Legal costs are never attributed to climate unless the source says so explicitly.">
        <div className="grid lg:grid-cols-2 gap-6">
          <div>
            {(c.financials || []).length === 0 ? <Empty>No financial lines extracted.</Empty> : (
              <table className="w-full text-[13px]">
                <thead className="text-[11px] uppercase text-slate-500"><tr><th className="text-left">Line</th><th className="text-left">Period</th><th className="text-right">₹ crore</th><th className="text-left pl-2">Basis</th><th /></tr></thead>
                <tbody>{c.financials.map((f, i) => (
                  <tr key={i} className="border-t border-slate-100">
                    <td className="py-1.5">{FIN_LABEL[f.metric] || f.metric}</td><td className="text-slate-500">{f.period}</td>
                    <td className="text-right font-mono">{fmtFull(f.value_norm ?? f.value)}</td><td className="pl-2 text-xs text-slate-500">{f.boundary}</td>
                    <td className="text-right"><EvidenceLink id={f.evidence_id}>{f.page ? `p.${f.page}` : 'XBRL'}</EvidenceLink></td>
                  </tr>
                ))}</tbody>
              </table>
            )}
          </div>
          <div>
            {legal.length === 0 ? (
              <Empty>{c.legal_reviewed ? 'No climate or environmental legal matters found in the annual-report pages reviewed.' : 'Legal disclosures not reviewed.'}</Empty>
            ) : (
              <ul className="space-y-2.5">
                {legal.map((x, i) => (
                  <li key={i} className="text-[13px] border-l-2 pl-2.5 border-slate-300">
                    <div className="flex gap-2 items-center flex-wrap">
                      <span className="text-[11px] font-semibold uppercase text-slate-600">{x.category.replace(/_/g, ' ')}</span>
                      <span className={`text-[11px] ${x.climate_related_explicit ? 'text-rose-700' : 'text-slate-500'}`}>{x.climate_related_explicit ? 'explicitly climate-related' : 'not attributed to climate'}</span>
                      {x.amount != null && <span className="font-mono text-xs">{fmtFull(x.amount)} {x.amount_unit}</span>}
                    </div>
                    <div className="text-slate-700">{x.description}</div>
                    <EvidenceLink id={x.evidence_id}>{x.source_title} p.{x.page}</EvidenceLink>
                  </li>
                ))}
              </ul>
            )}
          </div>
        </div>
      </Card>
      )}

      {tab === 'documents' && (
      <div className="grid lg:grid-cols-2 gap-4">
        <Card title={<span className="inline-flex items-center gap-1.5"><FileText className="w-4 h-4" /> Evidence documents</span>} subtitle="Discovered automatically from NSE filings" bodyClass="p-0">
          <table className="w-full text-[13px]">
            <tbody>{(c.documents || []).map((d) => (
              <tr key={d.id} className="border-t border-slate-100">
                <td className="px-4 py-2"><a href={d.source_url} target="_blank" rel="noreferrer" className="hover:underline inline-flex items-center gap-1">{d.title} <ExternalLink className="w-3 h-3" /></a>
                  <div className="text-[11px] text-slate-400">{d.found_via} · filed {d.publication_date || '—'}{d.page_count ? ` · ${d.page_count} pages` : ''}</div></td>
                <td className="px-4 text-right"><span className={`text-[11px] px-1.5 py-0.5 rounded ${d.status === 'parsed' ? 'bg-emerald-50 text-emerald-700' : d.status === 'failed' ? 'bg-rose-50 text-rose-700' : 'bg-slate-100 text-slate-500'}`}>{d.status}</span></td>
              </tr>
            ))}</tbody>
          </table>
        </Card>
        <Card title="Data gaps" subtitle="What the agents looked for and could not find">
          {(c.data_gaps || []).length === 0 ? <Empty>None recorded.</Empty> : (
            <ul className="list-disc pl-4 text-[13px] text-slate-600 space-y-1">{c.data_gaps.map((g, i) => <li key={i}>{g}</li>)}</ul>
          )}
        </Card>
      </div>
      )}
      <Disclaimer>
        Values are labelled Reported (as disclosed), Calculated (derived from disclosed values) or Data not found. Sylithe never fills gaps with estimates on this page.
      </Disclaimer>
    </div>
  );
}
