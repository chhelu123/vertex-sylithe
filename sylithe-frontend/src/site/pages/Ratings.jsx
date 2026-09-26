import React, { useEffect, useState } from 'react';
import { ExternalLink } from 'lucide-react';
import { api } from '../../sylithe/api';
import { IMAGES } from '../theme';
import { CtaBand, Eyebrow, SectionTitle } from '../components';

const DIM_TEXT = {
  additionality: 'Would this have happened without carbon finance? Financial barriers, regulation and common practice.',
  baseline: 'Is the counterfactual credible and conservative, and does issuance track what was estimated?',
  permanence: 'Could stored carbon be released by fire, harvest or land-use change, and is there a buffer?',
  leakage: 'Does the activity simply push emissions somewhere else?',
  monitoring: 'Are key parameters metered or surveyed, how often, and with what quality checks?',
  verification: 'Who verified the project, how often, and with what findings?',
  developer: "The developer's portfolio and track record across all registries.",
  methodology: 'The integrity of the methodology itself, using ICVCM decisions and peer-reviewed research.',
  transparency: 'How much of the project is publicly documented and disclosed.',
  co_benefits: 'Evidence of SDG, community, biodiversity or livelihood benefits.',
  data_quality: 'How much evidence the rating could draw on.',
};

export default function Ratings() {
  const [m, setM] = useState(null);
  useEffect(() => { api.methodology().then(setM).catch(() => {}); }, []);

  return (
    <>
      <section className="relative text-white">
        <img src={IMAGES.agroforestry} alt="" className="absolute inset-0 w-full h-full object-cover" />
        <div className="absolute inset-0 bg-[#141810]/65" />
        <div className="relative mx-auto max-w-7xl px-5 lg:px-8 py-28">
          <Eyebrow light>Methodology {m ? `· ${m.version}` : ''}</Eyebrow>
          <h1 className="font-display font-light text-5xl md:text-6xl leading-[1.05] mt-4 max-w-3xl">How the Sylithe rating works.</h1>
          <p className="mt-6 max-w-2xl text-lg text-white/80">Published, versioned and explainable. We would rather show a gap than hide one.</p>
        </div>
      </section>

      <section className="mx-auto max-w-7xl px-5 lg:px-8 py-24 grid lg:grid-cols-[1fr_1.4fr] gap-14">
        <SectionTitle eyebrow="What we assess" title="Eleven dimensions, weighted and documented." intro="Specialised agents each assess one dimension, using only the evidence they're given. Code rejects any citation that doesn't exist, and a fixed rubric turns the scores into a grade." />
        <div className="divide-y divide-[#E4DFD3] border-y border-[#E4DFD3]">
          {(m?.dimensions || Object.keys(DIM_TEXT).map((k) => ({ key: k, label: k }))).map((d) => (
            <div key={d.key} className="py-5 grid grid-cols-[1fr_auto] gap-4">
              <div>
                <div className="font-display text-xl">{d.label}</div>
                <p className="text-[#5B6152] mt-1">{DIM_TEXT[d.key]}</p>
              </div>
              {d.weight !== undefined && <div className="text-right"><div className="font-display text-2xl">{d.weight}%</div><div className="text-xs text-[#8E8B7E]">weight</div></div>}
            </div>
          ))}
        </div>
      </section>

      <section className="bg-[#EFEBE2] py-24">
        <div className="mx-auto max-w-7xl px-5 lg:px-8 grid md:grid-cols-3 gap-10">
          {[
            ['Evidence or it didn’t happen', 'Every score lists its evidence: registry transactions, project-document pages and cited methodology research. Agents can’t cite what they weren’t given.'],
            ['Provisional when evidence is thin', 'Without project documents, a rating is marked provisional with Low confidence. Missing data is never filled with estimates.'],
            ['Humans in the loop', 'Analysts can annotate or override any dimension with a written reason. The AI assessment is always kept alongside for audit.'],
          ].map(([t, d]) => (
            <div key={t}><h3 className="font-display text-2xl">{t}</h3><p className="mt-3 text-[#5B6152] leading-relaxed">{d}</p></div>
          ))}
        </div>
      </section>

      {m && (
        <section className="mx-auto max-w-7xl px-5 lg:px-8 py-24">
          <SectionTitle eyebrow="Research we build on" title="Methodology findings, with sources." intro="Class-level findings about specific methodologies. When applied to a project, they're always labelled as inference." />
          <div className="mt-10 grid md:grid-cols-2 gap-5">
            {Object.entries(m.methodology_notes).flatMap(([proto, notes]) => notes.map((n) => ({ proto, ...n })))
              .filter((n, i, arr) => arr.findIndex((x) => x.url === n.url) === i)
              .map((n) => (
                <a key={n.url} href={n.url} target="_blank" rel="noreferrer" className="rounded-2xl bg-white border border-[#E4DFD3] p-6 hover:border-[#1D2118] block">
                  <p className="text-[#3A3D36] leading-relaxed">{n.finding}</p>
                  <div className="mt-4 text-sm text-[#7F8A6E] inline-flex items-center gap-1.5">{n.source} <ExternalLink className="w-3.5 h-3.5" /></div>
                </a>
              ))}
          </div>
          <p className="mt-10 text-sm text-[#8E8B7E] max-w-3xl">{m.disclaimer}</p>
        </section>
      )}
      <CtaBand />
    </>
  );
}
