import React, { useRef, useState } from 'react';
import { CheckCircle2, FileUp, Plus, Trash2, XCircle } from 'lucide-react';
import { api } from '../api';
import { Card, DataState, Disclaimer, Empty, ErrorNote, Spinner, fmtFull, useLoad, cx } from '../ui';

const ACT = {
  electricity_grid: 'Grid electricity', electricity_renewable: 'Renewable electricity (contracted)', diesel: 'Diesel', petrol: 'Petrol',
  lpg: 'LPG', natural_gas: 'Natural gas', coal: 'Coal', fuel_oil: 'Fuel oil', kerosene: 'Kerosene',
};

function Inventory({ id, onDeleted }) {
  const { data, error, loading, reload, setData } = useLoad(() => api.inventory(id), [id]);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState(null);
  const [line, setLine] = useState({ activity_type: 'electricity_grid', quantity: '', unit: 'kWh', period: '', facility: '' });
  const file = useRef(null);
  if (loading && !data) return <Spinner />;
  if (error) return <ErrorNote error={error} />;
  const calc = data.calculation;

  const upload = async (f) => {
    if (!f) return;
    setBusy(true); setErr(null);
    try { await api.upload(id, f); await reload(); } catch (e) { setErr(e); } finally { setBusy(false); if (file.current) file.current.value = ''; }
  };
  const save = (body) => api.saveLine(id, body).then((r) => setData({ ...data, calculation: r.calculation, lines: r.calculation.lines })).catch(setErr);

  return (
    <div className="space-y-4">
      <div className="grid md:grid-cols-3 gap-3">
        {['Scope 1', 'Scope 2', 'Scope 1+2'].map((k) => (
          <div key={k} className="bg-white border border-slate-200 rounded-lg px-4 py-3">
            <div className="text-[11px] uppercase tracking-wider text-slate-500 flex items-center justify-between">{k} <DataState state="Estimated" /></div>
            <div className="text-2xl font-mono font-semibold mt-1">{fmtFull(calc.totals[k])} <span className="text-xs font-sans text-slate-500">tCO2e</span></div>
          </div>
        ))}
      </div>

      <Card title="Upload your activity documents" subtitle="Electricity bills, fuel invoices or energy statements (PDF), or a CSV with columns activity_type, quantity, unit, period, facility">
        <div className="flex items-center gap-3 flex-wrap">
          <input ref={file} type="file" accept=".pdf,.csv" onChange={(e) => upload(e.target.files?.[0])} className="hidden" id="calc-up" />
          <label htmlFor="calc-up" className={cx('inline-flex items-center gap-1.5 text-sm px-3 py-1.5 rounded-md cursor-pointer', busy ? 'bg-slate-300 text-slate-600' : 'bg-[#08292f] text-white')}>
            <FileUp className="w-4 h-4" /> {busy ? 'Extracting with AI…' : 'Upload PDF / CSV'}
          </label>
          <span className="text-xs text-slate-500">Files are private to your account. AI-extracted lines are marked unreviewed until you confirm them.</span>
        </div>
        <div className="mt-2"><ErrorNote error={err} /></div>
        {(data.uploads || []).length > 0 && (
          <ul className="mt-3 text-xs text-slate-600 space-y-1">
            {data.uploads.map((u) => <li key={u.id}>{u.filename} — {u.lines_extracted} line(s){u.pages ? ` from ${u.pages} pages` : ''}{u.data_gaps?.length ? ` · gaps: ${u.data_gaps.join('; ')}` : ''}</li>)}
          </ul>
        )}
      </Card>

      <Card title="Activity data" subtitle="Review each line. Calculations use cited emission factors — no AI in the maths." bodyClass="p-0">
        {calc.lines.length === 0 ? <div className="p-4"><Empty>No activity lines yet.</Empty></div> : (
          <div className="overflow-x-auto">
            <table className="w-full text-[13px]">
              <thead className="text-[11px] uppercase text-slate-500 bg-slate-50">
                <tr><th className="text-left px-3 py-2">Activity</th><th className="text-right px-2">Quantity</th><th className="text-left px-2">Unit</th><th className="text-left px-2">Period / facility</th><th className="text-left px-2">Source</th><th className="text-right px-2">tCO2e</th><th className="text-left px-2">Factor</th><th className="px-3" /></tr>
              </thead>
              <tbody>
                {calc.lines.map((l) => (
                  <tr key={l.line_id} className={cx('border-t border-slate-100 align-top', l.excluded && 'opacity-40')}>
                    <td className="px-3 py-2">{ACT[l.activity_type] || l.activity_type}<div className="text-[10px] text-slate-400">{l.result?.scope}</div></td>
                    <td className="px-2 text-right font-mono">{fmtFull(l.quantity)}</td>
                    <td className="px-2">{l.unit}</td>
                    <td className="px-2 text-xs text-slate-600">{l.period || '—'}{l.facility ? ` · ${l.facility}` : ''}</td>
                    <td className="px-2 text-xs">
                      {l.source === 'manual' ? 'manual entry' : (
                        <span title={l.quote}>{l.upload}{l.page ? ` p.${l.page}` : ''} {l.verified ? <CheckCircle2 className="inline w-3 h-3 text-emerald-600" /> : <XCircle className="inline w-3 h-3 text-rose-500" />}</span>
                      )}
                      {!l.reviewed && <div className="text-[10px] text-amber-700">unreviewed</div>}
                    </td>
                    <td className="px-2 text-right font-mono">{l.result ? fmtFull(l.result.tco2e) : '—'}{l.error && <div className="text-[10px] text-rose-600 max-w-[160px]">{l.error}</div>}</td>
                    <td className="px-2 text-[11px] text-slate-500 max-w-[220px]">{l.result?.factor}{l.result?.url && <a href={l.result.url} target="_blank" rel="noreferrer" className="block underline">{l.result.source}</a>}</td>
                    <td className="px-3 text-right whitespace-nowrap">
                      {!l.reviewed && <button onClick={() => save({ line_id: l.line_id, reviewed: true })} className="text-[11px] text-emerald-700 mr-2">Confirm</button>}
                      <button onClick={() => save({ line_id: l.line_id, excluded: !l.excluded })} className="text-[11px] text-slate-500">{l.excluded ? 'Include' : 'Exclude'}</button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
        <div className="border-t border-slate-100 p-3 grid grid-cols-2 md:grid-cols-6 gap-2 text-sm">
          <select value={line.activity_type} onChange={(e) => setLine({ ...line, activity_type: e.target.value })} className="border rounded px-2 py-1.5 col-span-2 md:col-span-1">
            {Object.entries(ACT).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
          </select>
          <input value={line.quantity} onChange={(e) => setLine({ ...line, quantity: e.target.value })} placeholder="Quantity" className="border rounded px-2 py-1.5" />
          <input value={line.unit} onChange={(e) => setLine({ ...line, unit: e.target.value })} placeholder="Unit (kWh, L, t, GJ)" className="border rounded px-2 py-1.5" />
          <input value={line.period} onChange={(e) => setLine({ ...line, period: e.target.value })} placeholder="Period" className="border rounded px-2 py-1.5" />
          <input value={line.facility} onChange={(e) => setLine({ ...line, facility: e.target.value })} placeholder="Facility" className="border rounded px-2 py-1.5" />
          <button onClick={() => save(line).then(() => setLine({ ...line, quantity: '' }))} disabled={!line.quantity} className="inline-flex items-center justify-center gap-1 bg-slate-800 text-white rounded disabled:opacity-40"><Plus className="w-4 h-4" /> Add line</button>
        </div>
      </Card>

      <Disclaimer>{calc.notes.join(' ')} Factor set: {calc.factors_version}.</Disclaimer>
      <button onClick={() => api.deleteInventory(id).then(onDeleted)} className="text-xs text-rose-600 inline-flex items-center gap-1"><Trash2 className="w-3.5 h-3.5" /> Delete inventory</button>
    </div>
  );
}

export default function Calculator() {
  const list = useLoad(() => api.inventories(), []);
  const [active, setActive] = useState(null);
  const [name, setName] = useState('');
  const [period, setPeriod] = useState('FY2025-26');
  const create = () => api.createInventory({ name: name || 'My inventory', period }).then((inv) => { setActive(inv.id); setName(''); list.reload(); });

  return (
    <div className="space-y-4">
      <div>
        <h1 className="text-xl font-semibold">Company Carbon Calculator</h1>
        <p className="text-sm text-slate-500 max-w-3xl">For company users measuring their own footprint. Upload your bills and invoices, and the Activity Extraction Agent reads the quantities with page-verified quotes. Scope 1 and 2 are then calculated from IPCC 2006 and CEA V21.0 factors.</p>
      </div>
      <div className="grid lg:grid-cols-[260px_1fr] gap-4 items-start">
        <Card title="Inventories" bodyClass="p-0">
          <ul className="text-[13px]">
            {(list.data?.inventories || []).map((i) => (
              <li key={i.id}><button onClick={() => setActive(i.id)} className={cx('w-full text-left px-4 py-2 border-b border-slate-100 hover:bg-slate-50', active === i.id && 'bg-slate-100')}>
                <div className="font-medium">{i.name}</div><div className="text-xs text-slate-500">{i.period} · {i.lines} lines · {fmtFull(i.summary['Scope 1+2'])} tCO2e</div></button></li>
            ))}
          </ul>
          <div className="p-3 space-y-2">
            <input value={name} onChange={(e) => setName(e.target.value)} placeholder="Inventory name (e.g. Pune plant)" className="w-full border rounded px-2 py-1.5 text-sm" />
            <input value={period} onChange={(e) => setPeriod(e.target.value)} placeholder="Reporting period" className="w-full border rounded px-2 py-1.5 text-sm" />
            <button onClick={create} className="w-full inline-flex items-center justify-center gap-1 bg-[#08292f] text-white rounded py-1.5 text-sm"><Plus className="w-4 h-4" /> New inventory</button>
          </div>
        </Card>
        {active ? <Inventory key={active} id={active} onDeleted={() => { setActive(null); list.reload(); }} /> : <Empty>Create or select an inventory to start.</Empty>}
      </div>
    </div>
  );
}
