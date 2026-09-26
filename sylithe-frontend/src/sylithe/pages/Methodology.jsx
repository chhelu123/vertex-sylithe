import React from 'react';
import { ExternalLink } from 'lucide-react';
import { api } from '../api';
import { Card, Disclaimer, ErrorNote, Spinner, useLoad } from '../ui';

export default function Methodology() {
  const proj = useLoad(() => api.methodology(), []);
  const comp = useLoad(() => api.kpiDefinitions(), []);
  if (proj.loading || comp.loading) return <Spinner />;
  if (proj.error || comp.error) return <ErrorNote error={proj.error || comp.error} />;
  const p = proj.data;
  const c = comp.data;
  return (
    <div className="space-y-5 max-w-5xl">
      <div>
        <h1 className="text-xl font-semibold">Methodology</h1>
        <p className="text-sm text-slate-500">Versioned and published. Historical ratings keep the version they were produced with, so they are never silently rewritten.</p>
      </div>

      <Card title={c.methodology_version} subtitle="Module 1: company carbon rating">
        <p className="text-sm text-slate-700 mb-3">Eight dimensions, each scored 0 to 100 by documented rules over disclosed data. An overall grade (A to E) is published only when at least 5 dimensions are scored and data confidence is 50 or higher. Otherwise it reads "Insufficient data".</p>
        <table className="w-full text-[13px]"><thead className="text-[11px] uppercase text-slate-500"><tr><th className="text-left">Dimension</th><th className="text-right">Weight</th></tr></thead>
          <tbody>{Object.entries(c.weights).map(([k, w]) => <tr key={k} className="border-t border-slate-100"><td className="py-1.5">{k.replace(/_/g, ' ')}</td><td className="text-right font-mono">{w}</td></tr>)}</tbody></table>
        <div className="mt-4 text-[11px] uppercase text-slate-500">KPIs (spec §11)</div>
        <div className="grid md:grid-cols-3 gap-x-4 text-[13px] mt-1">{c.kpis.map((k) => <div key={k.key} className="py-0.5">{k.label} <span className="text-slate-400">({k.better || 'n/a'} is better)</span></div>)}</div>
        <p className="text-xs text-slate-500 mt-3">Data sources: SEBI BRSR XBRL filings on NSE, parsed deterministically (High confidence), plus BRSR and annual-report PDFs read by AI agents. Every extracted quote is checked against the cited page; unverified quotes are marked Low confidence.</p>
      </Card>

      <Card title={p.version} subtitle="Module 2: carbon project rating">
        <div className="grid md:grid-cols-2 gap-6">
          <table className="w-full text-[13px]"><thead className="text-[11px] uppercase text-slate-500"><tr><th className="text-left">Dimension</th><th className="text-right">Weight</th></tr></thead>
            <tbody>{p.dimensions.map((d) => <tr key={d.key} className="border-t border-slate-100"><td className="py-1.5">{d.label}</td><td className="text-right font-mono">{d.weight}</td></tr>)}</tbody></table>
          <div>
            <table className="w-full text-[13px]"><thead className="text-[11px] uppercase text-slate-500"><tr><th className="text-left">Grade</th><th className="text-right">Min score</th></tr></thead>
              <tbody>{p.grades.map((g) => <tr key={g.grade} className="border-t border-slate-100"><td className="py-1 font-mono">{g.grade}</td><td className="text-right font-mono">{g.min_score}</td></tr>)}</tbody></table>
          </div>
        </div>
        <ul className="list-disc pl-4 text-[13px] text-slate-700 mt-4 space-y-1">
          <li>Ten specialised agents each score one dimension, using only evidence items they are given. Any citation to an evidence id they were not given is removed in code.</li>
          <li>Permanence has zero weight where the project category stores no carbon (e.g. renewables, cookstoves).</li>
          <li>The base grade comes from the weighted rubric. The adjudicator may move it by at most one notch, and must give a written reason.</li>
          <li>Ratings without analysed project documents are marked <b>provisional</b> with Low confidence.</li>
          <li>Analysts can annotate or override any dimension. The AI assessment is kept alongside the override.</li>
        </ul>
      </Card>

      <Card title={p.kb_version} subtitle="Methodology knowledge base: cited findings used by the Methodology agent">
        <div className="space-y-3">
          {Object.entries(p.methodology_notes).map(([proto, notes]) => (
            <div key={proto} className="text-[13px] border-t border-slate-100 pt-2">
              <div className="font-mono text-xs font-semibold">{proto}</div>
              {notes.map((n, i) => (
                <div key={i} className="mt-1">
                  <div className="text-slate-700">{n.finding}</div>
                  <a href={n.url} target="_blank" rel="noreferrer" className="text-xs underline inline-flex items-center gap-1 text-[#08292f]">{n.source} <ExternalLink className="w-3 h-3" /></a>
                </div>
              ))}
            </div>
          ))}
        </div>
      </Card>
      <Disclaimer>{p.disclaimer}</Disclaimer>
    </div>
  );
}
