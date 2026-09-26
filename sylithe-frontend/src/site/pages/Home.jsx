import React, { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { ArrowRight, FileSearch, ScanSearch, ShieldCheck } from 'lucide-react';
import { api } from '../../sylithe/api';
import { IMAGES, num } from '../theme';
import { CtaBand, Eyebrow, ProjectCard, SectionTitle } from '../components';
import ProcessMap from '../ProcessMap';

const GRADES = ['AAA', 'AA', 'A', 'BBB', 'BB', 'B', 'C', 'D'];
const DIMENSIONS = ['Additionality', 'Baseline integrity', 'Permanence', 'Leakage', 'Monitoring', 'Verification',
  'Developer', 'Methodology', 'Transparency', 'Co-benefits', 'Data quality'];

export default function Home() {
  const [stats, setStats] = useState(null);
  const [featured, setFeatured] = useState([]);

  useEffect(() => {
    api.overview().then(setStats).catch(() => {});
    api.projects({ rated: '1', per_page: 6, sort: 'recent' })
      .then((r) => (r.projects?.length >= 3 ? r : api.projects({ country: 'India', per_page: 6, sort: 'issued' })))
      .then((r) => setFeatured(r.projects || []))
      .catch(() => {});
  }, []);

  const c = stats?.counts;
  return (
    <>
      {/* Hero */}
      <section className="relative min-h-[92vh] flex items-end text-white">
        <img src={IMAGES.mangroves} alt="Mangrove delta seen from above" className="absolute inset-0 w-full h-full object-cover object-bottom" />
        <div className="absolute inset-0 bg-gradient-to-t from-[#141810]/90 via-[#141810]/40 to-[#141810]/30" />
        <div className="relative mx-auto max-w-7xl w-full px-5 lg:px-8 pb-14 pt-32">
          <Eyebrow light>Carbon intelligence · India-first</Eyebrow>
          <h1 className="font-display font-light text-5xl md:text-7xl leading-[1.02] mt-4 max-w-4xl">
            Know what a carbon credit is really worth.
          </h1>
          <p className="mt-6 max-w-2xl text-lg md:text-xl text-white/80 leading-relaxed">
            Sylithe rates carbon projects and measures companies' climate performance with AI research agents, and links every claim back to the document, page or registry record it came from.
          </p>
          <div className="mt-8 flex flex-wrap gap-3">
            <Link to="/projects" className="inline-flex items-center gap-2 rounded-full bg-white text-[#1D2118] px-6 py-3 font-medium">Explore projects <ArrowRight className="w-4 h-4" /></Link>
            <Link to="/companies" className="rounded-full border border-white/50 px-6 py-3 hover:bg-white/10">For companies</Link>
          </div>
          <dl className="mt-14 grid grid-cols-2 md:grid-cols-4 gap-6 border-t border-white/20 pt-6 max-w-4xl">
            {[
              ['Projects tracked', num(c?.projects_tracked)],
              ['Registries covered', '7'],
              ['Credits on record', stats?.registry?.total_issued ? `${num(stats.registry.total_issued)} t` : '—'],
              ['Evidence items linked', num(c?.evidence_items)],
            ].map(([k, v]) => (
              <div key={k}><dt className="text-xs uppercase tracking-[0.16em] text-white/60">{k}</dt><dd className="font-display text-3xl mt-1">{v}</dd></div>
            ))}
          </dl>
        </div>
      </section>

      {/* Statement + pillars */}
      <section className="mx-auto max-w-7xl px-5 lg:px-8 py-24">
        <p className="font-display font-light text-3xl md:text-[2.6rem] leading-[1.2] max-w-5xl text-[#1D2118]">
          The carbon market runs on trust. Too often that trust rests on a PDF nobody checked. <span className="text-[#7F8A6E]">Sylithe makes every claim checkable.</span>
        </p>
        <div className="mt-16 grid md:grid-cols-3 gap-10">
          {[
            [FileSearch, 'Evidence, not opinions', 'Each score cites its source: an XBRL tag in a BRSR filing, a page in a project document, or a registry transaction. Click through and read it yourself.'],
            [ScanSearch, 'Agents that do the reading', 'Specialised AI agents review additionality, baselines, permanence, monitoring and more in parallel. Code checks their citations, and analysts can review the result.'],
            [ShieldCheck, 'Honest about gaps', 'Missing data is marked "Data not found", never estimated behind your back. If the evidence is thin, the rating says it is provisional.'],
          ].map(([Icon, t, d]) => (
            <div key={t}>
              <Icon className="w-7 h-7 text-[#7F8A6E]" strokeWidth={1.5} />
              <h3 className="font-display text-2xl mt-4">{t}</h3>
              <p className="mt-3 text-[#5B6152] leading-relaxed">{d}</p>
            </div>
          ))}
        </div>
      </section>

      {/* Two products */}
      <section className="mx-auto max-w-7xl px-5 lg:px-8 pb-24 grid lg:grid-cols-2 gap-6">
        {[
          { img: IMAGES.agroforestry, eyebrow: 'For buyers & investors', title: 'Carbon project ratings', text: 'An AAA to D assessment of any Verra, Gold Standard, ACR or CAR project, dimension by dimension, with anomalies in its issuance history flagged automatically.', to: '/projects', cta: 'Browse rated projects' },
          { img: IMAGES.deccan, eyebrow: 'For sustainability & finance teams', title: 'Company carbon intelligence', text: 'Scope 1, 2 and 3, energy, water, targets and climate-related legal exposure for any NSE-listed company, read straight from its BRSR and annual report.', to: '/companies', cta: 'See company intelligence' },
        ].map((p) => (
          <Link key={p.title} to={p.to} className="group relative rounded-3xl overflow-hidden min-h-[460px] flex items-end text-white">
            <img src={p.img} alt="" className="absolute inset-0 w-full h-full object-cover group-hover:scale-[1.03] transition-transform duration-700" />
            <div className="absolute inset-0 bg-gradient-to-t from-[#141810]/90 via-[#141810]/30 to-transparent" />
            <div className="relative p-8 md:p-10">
              <Eyebrow light>{p.eyebrow}</Eyebrow>
              <h3 className="font-display text-4xl mt-2">{p.title}</h3>
              <p className="mt-3 text-white/80 max-w-lg leading-relaxed">{p.text}</p>
              <span className="mt-5 inline-flex items-center gap-2 text-sm font-medium">{p.cta} <ArrowRight className="w-4 h-4 group-hover:translate-x-1 transition-transform" /></span>
            </div>
          </Link>
        ))}
      </section>

      {/* Featured projects */}
      {featured.length > 0 && (
        <section className="bg-[#EFEBE2] py-24">
          <div className="mx-auto max-w-7xl px-5 lg:px-8">
            <div className="flex items-end justify-between gap-6 flex-wrap">
              <SectionTitle eyebrow="Marketplace" title="Projects on Sylithe" intro="Registry-verified projects, with Sylithe ratings where our agents have assessed them." />
              <Link to="/projects" className="inline-flex items-center gap-2 rounded-full border border-[#1D2118] px-5 py-2.5 text-sm">View all projects <ArrowRight className="w-4 h-4" /></Link>
            </div>
            <div className="mt-12 grid sm:grid-cols-2 lg:grid-cols-3 gap-6">
              {featured.slice(0, 6).map((p) => <ProjectCard key={p.project_id} p={p} />)}
            </div>
          </div>
        </section>
      )}

      {/* Rating scale */}
      <section className="mx-auto max-w-7xl px-5 lg:px-8 py-24 grid lg:grid-cols-2 gap-14 items-center">
        <div>
          <SectionTitle eyebrow="The Sylithe rating" title="One grade. Eleven dimensions. Every one explained." intro="Each dimension gets a score, a risk level, the evidence behind it and a confidence level. A documented rubric turns them into a grade, so historical ratings keep the methodology version they were made with." />
          <Link to="/ratings" className="mt-8 inline-flex items-center gap-2 text-[#1D2118] font-medium underline underline-offset-4">Read the methodology <ArrowRight className="w-4 h-4" /></Link>
        </div>
        <div className="rounded-3xl bg-white border border-[#E4DFD3] p-8">
          <div className="flex gap-1.5">
            {GRADES.map((g, i) => (
              <div key={g} className="flex-1 text-center">
                <div className="h-16 rounded-lg flex items-end justify-center pb-2 text-sm font-semibold"
                     style={{ background: `color-mix(in srgb, ${i < 3 ? '#2F5D46' : i < 5 ? '#7F8A6E' : i < 7 ? '#C3B64C' : '#E9731F'} ${100 - (i % 3) * 18}%, white)`, color: i < 5 ? 'white' : '#1D2118' }}>{g}</div>
              </div>
            ))}
          </div>
          <div className="flex justify-between text-xs text-[#8E8B7E] mt-2"><span>Strongest evidence, lowest risk</span><span>Highest documented risk</span></div>
          <div className="mt-8 flex flex-wrap gap-2">
            {DIMENSIONS.map((d) => <span key={d} className="rounded-full border border-[#E4DFD3] px-3 py-1.5 text-sm text-[#3A3D36]">{d}</span>)}
          </div>
        </div>
      </section>

      {/* Process */}
      <section className="bg-[#F1EDE4] py-24">
        <div className="mx-auto max-w-7xl px-5 lg:px-8">
          <SectionTitle eyebrow="How we work with companies" title="From annual report to a project you can stand behind." intro="Five stages take a company from what it discloses today to a green-credit project that fits its footprint, its targets and its reputation." />
          <div className="mt-12"><ProcessMap /></div>
        </div>
      </section>

      <CtaBand />
    </>
  );
}
