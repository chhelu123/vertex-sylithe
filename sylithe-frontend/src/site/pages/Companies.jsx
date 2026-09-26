import React, { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { ArrowRight, FileText, Calculator, Gavel, Target } from 'lucide-react';
import { api } from '../../sylithe/api';
import { IMAGES, num } from '../theme';
import { CtaBand, Eyebrow, GradeBadge, SectionTitle } from '../components';

export default function Companies() {
  const [list, setList] = useState([]);
  useEffect(() => { api.companies('').then((d) => setList(d.companies || [])).catch(() => {}); }, []);

  return (
    <>
      <section className="relative text-white">
        <img src={IMAGES.deccan} alt="" className="absolute inset-0 w-full h-full object-cover" />
        <div className="absolute inset-0 bg-gradient-to-r from-[#141810]/90 via-[#141810]/60 to-[#141810]/20" />
        <div className="relative mx-auto max-w-7xl px-5 lg:px-8 py-28">
          <Eyebrow light>Company carbon intelligence</Eyebrow>
          <h1 className="font-display font-light text-5xl md:text-6xl leading-[1.05] mt-4 max-w-3xl">A company's climate record, read from its own filings.</h1>
          <p className="mt-6 max-w-2xl text-lg text-white/80">Pick any NSE-listed company. Our agents fetch its BRSR and annual report, extract emissions, energy, targets, carbon credits and climate-related legal exposure, and cite the page for every number.</p>
          <div className="mt-8 flex flex-wrap gap-3">
            <Link to="/sylithe/companies" className="inline-flex items-center gap-2 rounded-full bg-white text-[#1D2118] px-6 py-3 font-medium">Research a company <ArrowRight className="w-4 h-4" /></Link>
            <Link to="/sylithe/calculator" className="rounded-full border border-white/50 px-6 py-3 hover:bg-white/10">Measure your own footprint</Link>
          </div>
        </div>
      </section>

      <section className="mx-auto max-w-7xl px-5 lg:px-8 py-24 grid md:grid-cols-2 lg:grid-cols-4 gap-8">
        {[
          [FileText, 'Exact disclosed data', 'Scope 1 and 2, energy, water and waste come straight from the tagged BRSR filing, with no guesswork. Values that fail plausibility checks are flagged, not used.'],
          [Target, 'Targets & transition', 'Net-zero dates, interim targets, SBTi status and concrete transition actions, each quoted from its page.'],
          [Gavel, 'Climate legal exposure', 'Environmental proceedings and penalties from the annual report. Legal costs are never counted as climate-related unless the source says so.'],
          [Calculator, 'Your own inventory', 'Company teams can upload their bills and invoices. Scope 1 and 2 are then calculated using CEA and IPCC emission factors.'],
        ].map(([Icon, t, d]) => (
          <div key={t}><Icon className="w-7 h-7 text-[#7F8A6E]" strokeWidth={1.5} /><h3 className="font-display text-2xl mt-4">{t}</h3><p className="mt-3 text-[#5B6152] leading-relaxed">{d}</p></div>
        ))}
      </section>

      {list.length > 0 && (
        <section className="bg-[#EFEBE2] py-24">
          <div className="mx-auto max-w-7xl px-5 lg:px-8">
            <SectionTitle eyebrow="Tracked companies" title="Latest climate records on Sylithe." />
            <div className="mt-10 rounded-3xl bg-white border border-[#E4DFD3] overflow-hidden">
              <table className="w-full text-[15px]">
                <thead className="text-xs uppercase tracking-[0.14em] text-[#8E8B7E]">
                  <tr className="border-b border-[#EFEBE2]"><th className="text-left px-6 py-4 font-normal">Company</th><th className="text-right px-4 font-normal">Scope 1+2</th><th className="text-right px-4 font-normal hidden md:table-cell">Change</th><th className="text-right px-4 font-normal hidden md:table-cell">Renewables</th><th className="px-6 font-normal">Rating</th></tr>
                </thead>
                <tbody>
                  {list.map((c) => (
                    <tr key={c.slug} className="border-b border-[#EFEBE2] last:border-0">
                      <td className="px-6 py-4"><Link to={`/sylithe/company/${c.slug}`} className="font-display text-lg hover:underline">{c.name}</Link><div className="text-xs text-[#8E8B7E]">{c.industry}</div></td>
                      <td className="text-right px-4">{num(c.total_emissions?.current)} t<div className="text-xs text-[#8E8B7E]">{c.total_emissions?.period}</div></td>
                      <td className={`text-right px-4 hidden md:table-cell ${c.total_emissions?.change_pct > 0 ? 'text-[#C2410C]' : 'text-[#2F5D46]'}`}>{c.total_emissions?.change_pct != null ? `${c.total_emissions.change_pct > 0 ? '+' : ''}${c.total_emissions.change_pct}%` : '—'}</td>
                      <td className="text-right px-4 hidden md:table-cell">{c.renewable_pct?.current != null ? `${c.renewable_pct.current.toFixed(0)}%` : '—'}</td>
                      <td className="px-6 text-center"><GradeBadge grade={c.rating?.grade} /></td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </section>
      )}
      <CtaBand />
    </>
  );
}
