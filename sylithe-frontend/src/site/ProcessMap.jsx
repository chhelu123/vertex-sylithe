import React, { useState } from 'react';

// Sylithe's corporate sustainability & green-project due-diligence process (five stages).
export const STAGES = [
  {
    color: '#7F8A6E', title: 'Disclosure review',
    summary: 'We read the filings first: annual report, SOPs and the BRSR.',
    groups: [
      { name: 'Annual report & SOP review', items: ['Financials analysis', 'Operational SOPs review', 'Legal structure'] },
      { name: 'BRSR', items: ['Disclosures compliance', 'Metric alignment', 'Sustainability goals'] },
    ],
  },
  {
    color: '#C3B64C', title: 'CSR & carbon footprint',
    summary: 'What the company spends, emits and offsets today.',
    groups: [
      { name: 'CSR analysis & expenditure', items: ['Historical CSR spending', 'Impact metrics', 'Alignment with NGT'] },
      { name: 'Carbon footprint & credits', items: ['Baseline emissions', 'Carbon credit status', 'Exceeding-credits strategy'] },
    ],
  },
  {
    color: '#4B5244', title: 'ESG & green-credit due diligence',
    summary: 'Environmental, social and governance checks against targets.',
    groups: [
      { name: 'Environment (net zero)', items: ['Net-zero timeline', 'Climate resilience', 'Biodiversity & water', 'Supply-chain ethics'] },
      { name: 'Social (stakeholder welfare)', items: ['Human rights', 'Benefit sharing'] },
      { name: 'Governance (policy & compliance)', items: ['Policy integration', 'Maintenance plan'] },
    ],
  },
  {
    color: '#E9731F', title: 'Project proposal & green credits',
    summary: 'Finding and testing the right project for the company.',
    groups: [
      { name: 'Project feasibility check', items: ['Land identification (green credits)', 'Site due diligence', 'Location coordinates'] },
      { name: 'Project benefits analysis', items: ['Additionality check'] },
    ],
  },
  {
    color: '#3A3D36', title: 'Recommendations & outcomes',
    summary: 'A decision the board can act on, and defend.',
    groups: [
      { name: 'Corporate decision making', items: ['Corporate reputation', 'ESG compliance'] },
      { name: 'Actionable suggestions & project fit', items: ['SDG alignment', 'Internal & external rating'] },
    ],
  },
];

export default function ProcessMap({ compact = false }) {
  const [active, setActive] = useState(0);
  const s = STAGES[active];
  return (
    <div className="grid lg:grid-cols-[minmax(0,0.9fr)_minmax(0,1.1fr)] gap-6">
      <ol className="space-y-2">
        {STAGES.map((st, i) => (
          <li key={st.title}>
            <button onClick={() => setActive(i)} onMouseEnter={() => !compact && setActive(i)}
                    className={`w-full text-left rounded-2xl border px-5 py-4 transition-colors flex items-start gap-4 ${active === i ? 'bg-white border-[#D8D2C4] shadow-sm' : 'border-transparent hover:bg-white/60'}`}>
              <span className="mt-1 w-3 h-3 rounded-full shrink-0" style={{ background: st.color }} />
              <span>
                <span className="block text-[11px] uppercase tracking-[0.18em] text-[#8E8B7E]">Stage {i + 1}</span>
                <span className="block font-display text-xl text-[#1D2118]">{st.title}</span>
                <span className="block text-sm text-[#5B6152] mt-0.5">{st.summary}</span>
              </span>
            </button>
          </li>
        ))}
      </ol>
      <div className="rounded-3xl bg-white border border-[#E4DFD3] p-6 md:p-8 relative overflow-hidden">
        <div className="absolute inset-x-0 top-0 h-1.5" style={{ background: s.color }} />
        <div className="text-[11px] uppercase tracking-[0.18em] text-[#8E8B7E]">Stage {active + 1} of {STAGES.length}</div>
        <h3 className="font-display text-3xl mt-1">{s.title}</h3>
        <div className="mt-6 space-y-6">
          {s.groups.map((g) => (
            <div key={g.name} className="grid sm:grid-cols-[minmax(0,1fr)_minmax(0,1.3fr)] gap-3 items-start">
              <div className="rounded-lg px-3 py-2 text-white text-[15px] font-medium" style={{ background: s.color }}>{g.name}</div>
              <ul className="space-y-1.5 border-l-2 border-dashed pl-4" style={{ borderColor: `${s.color}66` }}>
                {g.items.map((it) => (
                  <li key={it} className="flex items-center gap-2 text-[15px] text-[#1D2118]">
                    <span className="w-1.5 h-1.5 rounded-full" style={{ background: s.color }} />{it}
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
