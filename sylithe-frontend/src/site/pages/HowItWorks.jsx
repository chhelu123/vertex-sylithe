import React from 'react';
import { IMAGES } from '../theme';
import { CtaBand, Eyebrow, SectionTitle } from '../components';
import ProcessMap from '../ProcessMap';

const AGENTS = [
  ['Discovery', 'Finds the filings and registry records, straight from official sources.'],
  ['Extraction', 'Reads structured data exactly, and quotes the page for everything else.'],
  ['Assessment', 'Ten specialised agents each assess one dimension, in parallel.'],
  ['Validation', 'Code checks every quote and citation. Unsupported claims are dropped.'],
  ['Adjudication', 'A fixed rubric sets the grade. The adjudicator can move it one notch at most, with a written reason.'],
  ['Review', 'Analysts annotate or override. The AI output stays on record.'],
];

export default function HowItWorks() {
  return (
    <>
      <section className="relative text-white">
        <img src={IMAGES.rice} alt="" className="absolute inset-0 w-full h-full object-cover" />
        <div className="absolute inset-0 bg-[#141810]/60" />
        <div className="relative mx-auto max-w-7xl px-5 lg:px-8 py-28">
          <Eyebrow light>How it works</Eyebrow>
          <h1 className="font-display font-light text-5xl md:text-6xl leading-[1.05] mt-4 max-w-3xl">From disclosure to decision.</h1>
          <p className="mt-6 max-w-2xl text-lg text-white/80">Our due-diligence process takes a company from what it reports today to a green-credit project that fits its footprint, and backs every step with evidence.</p>
        </div>
      </section>

      <section className="mx-auto max-w-7xl px-5 lg:px-8 py-24">
        <SectionTitle eyebrow="The process" title="Five stages of corporate & green-project due diligence." />
        <div className="mt-12"><ProcessMap /></div>
      </section>

      <section className="bg-[#1D2118] text-white py-24">
        <div className="mx-auto max-w-7xl px-5 lg:px-8">
          <SectionTitle light eyebrow="Under the hood" title="Agents do the reading. Code keeps them honest." />
          <ol className="mt-14 grid md:grid-cols-2 lg:grid-cols-3 gap-px bg-white/10 rounded-3xl overflow-hidden">
            {AGENTS.map(([t, d], i) => (
              <li key={t} className="bg-[#1D2118] p-8">
                <div className="font-display text-5xl text-[#C3B64C]">{String(i + 1).padStart(2, '0')}</div>
                <h3 className="font-display text-2xl mt-4">{t}</h3>
                <p className="mt-2 text-white/70 leading-relaxed">{d}</p>
              </li>
            ))}
          </ol>
        </div>
      </section>
      <CtaBand />
    </>
  );
}
