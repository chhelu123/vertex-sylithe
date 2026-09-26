import React, { useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import { Bar, BarChart, CartesianGrid, Legend, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';
import { AlertTriangle, ArrowLeft, Bot, ExternalLink, Link2, UserCheck } from 'lucide-react';
import { api } from '../api';
import { useAuth } from '../../context/AuthContext';
import {
  Card, Confidence, DataState, Disclaimer, Empty, ErrorNote, Grade, JobProgress, Risk, ScoreBar, Spinner,
  fmt, useEvidence, useJob, useLoad, cx,
  InfoGrid, StatusPill, Tabs, DistributionList, chartAxis, chartGrid, chartTooltip, chartLegend,
} from '../ui';

const ADMINS = ['karan270905@gmail.com', 'chhelurathore773@gmail.com'];

function ReviewForm({ ratingId, dim, onSaved }) {
  const [open, setOpen] = useState(false);
  const [score, setScore] = useState(dim.score ?? '');
  const [risk, setRisk] = useState(dim.risk);
  const [reason, setReason] = useState('');
  const [err, setErr] = useState(null);
  if (!open) return <button onClick={() => setOpen(true)} className="text-[11px] text-slate-500 hover:text-slate-800 inline-flex items-center gap-1"><UserCheck className="w-3 h-3" /> Analyst review</button>;
  const save = () => api.review(ratingId, { dimension: dim.key, score: score === '' ? null : Number(score), risk, reason })
    .then(() => { setOpen(false); onSaved(); }).catch(setErr);
  return (
    <div className="mt-2 p-2 bg-slate-50 border border-slate-200 rounded space-y-2 text-xs">
      <div className="flex gap-2">
        <input type="number" value={score} onChange={(e) => setScore(e.target.value)} placeholder="Score" className="w-20 border rounded px-2 py-1" />
        <select value={risk} onChange={(e) => setRisk(e.target.value)} className="border rounded px-2 py-1">
          {['low', 'medium', 'high', 'unknown'].map((r) => <option key={r}>{r}</option>)}
        </select>
      </div>
      <textarea value={reason} onChange={(e) => setReason(e.target.value)} placeholder="Reason and evidence for the override (required)" className="w-full border rounded px-2 py-1" rows={2} />
      <ErrorNote error={err} />
      <div className="flex gap-2"><button onClick={save} className="bg-[#08292f] text-white px-2 py-1 rounded">Save review</button><button onClick={() => setOpen(false)} className="px-2 py-1">Cancel</button></div>
    </div>
  );
}

function Dimension({ d, ratingId, isAdmin, onReviewed }) {
  const open = useEvidence();
  const hr = d.human_review;
  return (
    <div className="bg-white border border-slate-200 rounded-lg p-3.5 flex flex-col gap-2">
      <div className="flex items-start justify-between gap-2">
        <div className="font-medium text-[14px]">{d.label}</div>
        <div className="flex items-center gap-1.5"><Risk risk={d.risk} /><span className="font-mono font-semibold w-9 text-right">{d.score ?? '—'}</span></div>
      </div>
      <ScoreBar score={d.score} />
      <div className="flex items-center gap-2 flex-wrap"><DataState state={d.status} /><Confidence level={d.confidence} /></div>
      <p className="text-[13px] text-slate-700">{d.reason}</p>
      {d.reasoning_summary && <p className="text-xs text-slate-500"><span className="font-medium">AI reasoning:</span> {d.reasoning_summary}</p>}
      {(d.evidence || []).length > 0 && (
        <ul className="space-y-1">
          {d.evidence.map((e) => (
            <li key={e.evidence_id} className="text-xs">
              <button onClick={() => open(e.evidence_id)} className="text-left hover:underline text-[#08292f]">
                <span className="font-mono text-[10px] text-slate-400 mr-1">[{e.kind}]</span>{e.supports}
              </button>
              <span className="text-slate-400"> — {e.source}{e.page ? `, p.${e.page}` : ''}</span>
            </li>
          ))}
        </ul>
      )}
      {(d.data_gaps || []).length > 0 && (
        <div className="text-[11px] text-slate-500"><span className="font-medium">Data gaps:</span> {d.data_gaps.join('; ')}</div>
      )}
      {d.evidence_dropped > 0 && <div className="text-[11px] text-amber-700">{d.evidence_dropped} uncited claim(s) removed by evidence validation</div>}
      {hr && (
        <div className="text-xs bg-sky-50 border border-sky-200 rounded p-2">
          <div className="font-medium text-sky-800">Human review by {hr.reviewer}: score {hr.human_score ?? '—'}, {hr.human_risk} risk</div>
          <div className="text-sky-900">{hr.reason}</div>
          <div className="text-[10px] text-sky-700 mt-0.5">AI assessment kept: {hr.ai_assessment?.score ?? '—'} · {new Date(hr.created_at).toLocaleString()}</div>
        </div>
      )}
      {isAdmin && ratingId && d.key !== 'data_quality' && <ReviewForm ratingId={ratingId} dim={d} onSaved={onReviewed} />}
    </div>
  );
}

function LinkDocument({ projectId, onDone }) {
  const [url, setUrl] = useState('');
  const [type, setType] = useState('pdd');
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState(null);
  const submit = () => {
    setBusy(true); setErr(null);
    api.linkDocument(projectId, { url, document_type: type }).then(() => { setUrl(''); onDone(); }).catch(setErr).finally(() => setBusy(false));
  };
  return (
    <div className="space-y-2">
      <div className="flex gap-2">
        <input value={url} onChange={(e) => setUrl(e.target.value)} placeholder="https://… public PDD / monitoring / verification report PDF" className="flex-1 border border-slate-300 rounded px-2 py-1.5 text-sm" />
        <select value={type} onChange={(e) => setType(e.target.value)} className="border border-slate-300 rounded px-2 text-sm">
          <option value="pdd">PDD</option><option value="monitoring_report">Monitoring report</option><option value="verification_report">Verification report</option><option value="validation_report">Validation report</option><option value="other">Other</option>
        </select>
        <button disabled={!url || busy} onClick={submit} className="inline-flex items-center gap-1 text-sm bg-slate-800 text-white px-3 rounded disabled:opacity-40"><Link2 className="w-4 h-4" /> {busy ? 'Reading…' : 'Link'}</button>
      </div>
      <ErrorNote error={err} />
    </div>
  );
}

export default function ProjectDetail() {
  const { id } = useParams();
  const { user } = useAuth();
  const isAdmin = ADMINS.includes(user?.email?.toLowerCase());
  const { data: p, error, loading, reload } = useLoad(() => api.project(id), [id]);
  const history = useLoad(() => api.projectRatings(id), [id]);
  const [jobId, setJobId] = useState(null);
  const [runErr, setRunErr] = useState(null);
  const job = useJob(jobId || p?.active_job?.id, () => { reload(); history.reload(); });
  const [tab, setTab] = useState('overview');

  if (loading && !p) return <Spinner label="Loading project…" />;
  if (error) return <ErrorNote error={error} />;
  const r = p.rating;
  const run = () => { setRunErr(null); api.rateProject(id).then((x) => setJobId(x.job_id)).catch(setRunErr); };
  const years = [...new Set([...Object.keys(p.issuance_by_year || {}), ...Object.keys(p.retirement_by_year || {})])].filter((y) => y !== 'unknown').sort();
  const flow = years.map((y) => ({ year: y, Issued: p.issuance_by_year?.[y] || 0, Retired: p.retirement_by_year?.[y] || 0 }));
  const vint = Object.entries(p.issuance_by_vintage || {}).filter(([v]) => v !== 'unknown').map(([v, q]) => ({ vintage: v, credits: q }));

  return (
    <div className="space-y-5">
      <div>
        <Link to="/sylithe/projects" className="inline-flex items-center gap-1.5 text-[15px] text-slate-500 hover:text-slate-800"><ArrowLeft className="w-4 h-4" /> Back</Link>
        <div className="mt-3 flex items-start justify-between gap-4 flex-wrap">
          <div className="min-w-0 max-w-4xl">
            <h1 className="text-[26px] font-bold tracking-tight uppercase text-slate-900 leading-tight">{p.name}</h1>
            <div className="text-[15px] text-slate-400 mt-0.5">{p.project_type || p.category} · {p.country}</div>
          </div>
          <div className="flex items-center gap-2">
            <StatusPill>{p.status === 'unknown' ? 'Status not reported' : p.status}</StatusPill>
            <button onClick={run} disabled={job?.status === 'running'} className="inline-flex items-center gap-1.5 text-sm bg-[#08292f] text-white px-3.5 py-1.5 rounded-lg disabled:opacity-50">
              <Bot className="w-4 h-4" /> {r ? 'Re-run rating agents' : 'Run rating agents'}
            </button>
          </div>
        </div>
        <div className="mt-6"><Tabs value={tab} onChange={setTab} tabs={[['overview', 'Overview'], ['assessment', 'Assessment'], ['issuance', 'Issuance'], ['developer', 'Developer & documents'], ['history', 'History']]} /></div>
      </div>
      <ErrorNote error={runErr} />
      {job && job.status === 'running' && <JobProgress job={job} title="Project due-diligence agents" />}

      {tab === 'overview' && (
        <>
          <InfoGrid
            title="Project Information"
            badge={<StatusPill>{p.status === 'unknown' ? 'Status not reported' : p.status}</StatusPill>}
            cells={[
              { label: 'Credits issued', value: fmt(p.issued), unit: 't', sub: `${p.n_issuances || 0} issuance transactions`, subNote: `first ${p.first_issuance_at || '—'}` },
              { label: 'Credits retired', dot: '#D9964A', value: fmt(p.retired), unit: 't', sub: p.retirement_ratio != null ? `${(p.retirement_ratio * 100).toFixed(1)}% of issued` : '—', subNote: 'Retirement ratio' },
              { label: 'Registry', dot: '#DCC46B', value: p.registry_name, sub: p.project_id, subNote: 'Registry ID' },
              { label: 'Project type', dot: '#5B9BD5', value: (p.category || '—').replace(/-/g, ' ').replace(/^./, (x) => x.toUpperCase()), sub: (p.protocol || []).join(', ').toUpperCase() || '—', subNote: 'Methodology' },
              { label: 'Sylithe rating', value: r?.grade || 'N/R', unit: r?.overall_score != null ? `${r.overall_score}/100` : '', sub: r ? `${r.confidence} confidence` : 'Not rated yet', subNote: r?.provisional ? 'Provisional' : r?.methodology_version },
            ]}
            footerCells={[
              { label: 'Developer', value: p.proponent },
              { label: 'Country', value: p.country },
              { label: 'Last issuance', value: p.last_issuance_at || '—' },
              { label: 'Registry page', value: p.project_url ? <a href={p.project_url} target="_blank" rel="noreferrer" className="underline inline-flex items-center gap-1">Open <ExternalLink className="w-3 h-3" /></a> : '—' },
            ]}
          />
          {r?.adjustment?.summary && (
            <Card title="Assessment summary" subtitle={`${r.methodology_version} · ${new Date(r.created_at).toLocaleDateString()}`} footer={r.disclaimer}>
              <p className="text-[15px] text-slate-700 leading-relaxed">{r.adjustment.summary}</p>
            </Card>
          )}
        </>
      )}

      {tab === 'assessment' && (!r ? (
        <Card title="Sylithe Project Assessment"><Empty>Not rated yet. Run the rating agents to assess this project across 11 dimensions with linked evidence.</Empty></Card>
      ) : (
        <>
          <Card title="Sylithe Project Assessment" subtitle={`${r.methodology_version} · ${r.kb_version} · models ${r.models?.dimensions} / ${r.models?.adjudicator} · ${new Date(r.created_at).toLocaleString()}`}>
            <div className="grid md:grid-cols-[auto_1fr] gap-5 items-start">
              <div className="flex flex-col items-center gap-2">
                <Grade grade={r.grade} size="lg" provisional={r.provisional} />
                <div className="text-xs text-slate-500">score <span className="font-mono">{r.overall_score ?? '—'}</span></div>
                <Confidence level={r.confidence} />
              </div>
              <div className="space-y-2 text-sm">
                {r.adjustment?.summary && <p className="text-slate-800">{r.adjustment.summary}</p>}
                {r.base_grade && <p className="text-xs text-slate-500">Rubric grade {r.base_grade}; adjudicator adjustment {r.adjustment.adjustment} — {r.adjustment.reason}</p>}
                {r.note && <p className="text-xs text-amber-700">{r.note}</p>}
                {(r.adjustment?.key_risks || []).length > 0 && (
                  <div><div className="text-[11px] uppercase tracking-wide text-slate-500">Key documented risks</div>
                    <ul className="list-disc pl-4 text-[13px] text-slate-700">{r.adjustment.key_risks.map((k, i) => <li key={i}>{k}</li>)}</ul></div>
                )}
                <Disclaimer>{r.disclaimer}</Disclaimer>
              </div>
            </div>
          </Card>

          {(r.anomalies || []).length > 0 && (
            <Card title="Anomaly Agent — registry consistency signals">
              <ul className="space-y-1.5">
                {r.anomalies.map((a) => (
                  <li key={a.key} className="flex items-start gap-2 text-[13px]">
                    <AlertTriangle className={cx('w-4 h-4 mt-0.5 shrink-0', a.severity === 'high' ? 'text-rose-600' : a.severity === 'medium' ? 'text-amber-500' : 'text-slate-400')} />
                    <span><span className="uppercase text-[10px] font-semibold text-slate-500 mr-1">{a.severity}</span>{a.text}</span>
                  </li>
                ))}
              </ul>
            </Card>
          )}

          <div className="grid md:grid-cols-2 xl:grid-cols-3 gap-3">
            {r.dimensions.map((d) => <Dimension key={d.key} d={d} ratingId={r.id} isAdmin={isAdmin} onReviewed={reload} />)}
          </div>
        </>
      ))}

      {tab === 'issuance' && (
      <div className="grid lg:grid-cols-2 gap-4">
        <Card title="Issuance & retirement trends" subtitle="Registry transactions (OffsetsDB)"
              footer="Credits issued and retired in each calendar year, from every registry transaction on record.">
          {flow.length ? (<>
            <div className="text-[12px] font-semibold text-slate-500 mb-2">Credits</div>
            <ResponsiveContainer width="100%" height={260}>
              <BarChart data={flow}>
                <CartesianGrid {...chartGrid} /><XAxis dataKey="year" {...chartAxis} /><YAxis tickFormatter={(v) => fmt(v)} {...chartAxis} width={55} />
                <Tooltip {...chartTooltip} cursor={{ fill: '#F5F5F3' }} formatter={(v) => Number(v).toLocaleString()} /><Legend {...chartLegend} />
                <Bar isAnimationActive={false} dataKey="Issued" fill="#4E9BD6" barSize={28} /><Bar isAnimationActive={false} dataKey="Retired" fill="#E8A23D" barSize={28} />
              </BarChart>
            </ResponsiveContainer></>
          ) : <Empty>No issuance recorded.</Empty>}
        </Card>
        <Card title="Issuance by vintage" subtitle="Share of credits issued per vintage year"
              footer="The precise fraction of issued credits from each vintage. Heavy concentration in one vintage is flagged by the Anomaly Agent.">
          {vint.length ? (
            <DistributionList unit="t" format={fmt} legend="Credits in" totalLabel="100% of credits issued"
                              items={vint.map((v, i) => ({ label: `Vintage ${v.vintage}`, value: v.credits, color: ['#4E7F4F', '#5B9BD5', '#DCC46B', '#D9964A', '#93B35F', '#8B7FBF'][i % 6] }))} />
          ) : <Empty>No vintage data.</Empty>}
        </Card>
      </div>
      )}

      {tab === 'developer' && (
      <div className="grid lg:grid-cols-2 gap-4">
        <Card title="Developer track record" subtitle={p.proponent || '—'} footer="Every project by this developer across all registries in OffsetsDB.">
          {!p.developer ? <Empty>Developer not recorded.</Empty> : (
            <div className="text-[13px] space-y-2">
              <div className="grid grid-cols-3 gap-2">
                <div><div className="text-[11.5px] font-semibold uppercase tracking-[0.12em] text-slate-500">Projects</div><div className="text-[26px] font-semibold tracking-tight">{p.developer.projects}</div></div>
                <div><div className="text-[11.5px] font-semibold uppercase tracking-[0.12em] text-slate-500">Issued</div><div className="text-[26px] font-semibold tracking-tight">{fmt(p.developer.total_issued)}<span className="text-sm font-normal text-slate-400 ml-1">t</span></div></div>
                <div><div className="text-[11.5px] font-semibold uppercase tracking-[0.12em] text-slate-500">Retired</div><div className="text-[26px] font-semibold tracking-tight">{fmt(p.developer.total_retired)}<span className="text-sm font-normal text-slate-400 ml-1">t</span></div></div>
              </div>
              <div className="text-xs text-slate-500">Registries: {p.developer.registries.join(', ')} · Countries: {p.developer.countries.join(', ')}</div>
              <table className="w-full text-xs"><tbody>{p.developer.sample.map((s) => (
                <tr key={s.project_id} className="border-t border-slate-100"><td className="py-1"><Link to={`/sylithe/project/${s.project_id}`} className="hover:underline">{s.name}</Link></td><td className="text-right font-mono">{fmt(s.issued)}</td></tr>
              ))}</tbody></table>
            </div>
          )}
        </Card>
        <Card title="Project documents" subtitle="Link public PDFs (PDD, monitoring, verification). Linked documents raise evidence quality and confidence.">
          {(p.documents || []).length > 0 && (
            <ul className="mb-3 space-y-1 text-[13px]">
              {p.documents.map((d) => (
                <li key={d.id} className="flex items-center justify-between gap-2">
                  <a href={d.source_url} target="_blank" rel="noreferrer" className="hover:underline truncate">{d.title}</a>
                  <span className="text-[11px] text-slate-500 shrink-0">{d.document_type} · {d.page_count} pages · {d.status}</span>
                </li>
              ))}
            </ul>
          )}
          <LinkDocument projectId={p.project_id} onDone={reload} />
          <p className="text-[11px] text-slate-400 mt-2">After linking, re-run the rating agents to include the document.</p>
        </Card>
      </div>
      )}

      {tab === 'history' && ((history.data?.ratings || []).length === 0 ? <Card title="Rating history"><Empty>No ratings yet.</Empty></Card> : (
        <Card title="Rating history" subtitle="Historical ratings keep the methodology version they were made with" bodyClass="p-0">
          <table className="w-full text-[13px]"><tbody>{history.data.ratings.map((h) => (
            <tr key={h.id} className="border-t border-slate-100"><td className="px-4 py-2">{new Date(h.created_at).toLocaleString()}</td><td className="px-2">{h.methodology_version}</td>
              <td className="px-2 font-mono">{h.overall_score ?? '—'}</td><td className="px-2"><Confidence level={h.confidence} /></td><td className="px-4"><Grade grade={h.grade} size="sm" /></td></tr>
          ))}</tbody></table>
        </Card>
      ))}
    </div>
  );
}
