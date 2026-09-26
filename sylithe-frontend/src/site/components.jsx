import React from 'react';
import { Link } from 'react-router-dom';
import { MapPin } from 'lucide-react';
import { CATEGORY_LABEL, REGISTRY_LABEL, gradeTone, imageFor, num } from './theme';

export function Eyebrow({ children, light }) {
  return <div className={`text-[12px] uppercase tracking-[0.2em] ${light ? 'text-white/70' : 'text-[#7F8A6E]'}`}>{children}</div>;
}

export function SectionTitle({ eyebrow, title, intro, light, className = '' }) {
  return (
    <div className={`max-w-3xl ${className}`}>
      {eyebrow && <Eyebrow light={light}>{eyebrow}</Eyebrow>}
      <h2 className={`font-display font-light text-4xl md:text-5xl leading-[1.08] mt-3 ${light ? 'text-white' : 'text-[#1D2118]'}`}>{title}</h2>
      {intro && <p className={`mt-5 text-lg leading-relaxed ${light ? 'text-white/75' : 'text-[#5B6152]'}`}>{intro}</p>}
    </div>
  );
}

export function GradeBadge({ grade, provisional, size = 'md' }) {
  const s = size === 'lg' ? 'text-2xl px-4 py-2' : 'text-sm px-2.5 py-1';
  return (
    <span className={`inline-flex items-center gap-1 rounded-full font-semibold ${gradeTone(grade)} ${s}`} title={provisional ? 'Provisional rating' : undefined}>
      {grade || 'Unrated'}{provisional && grade ? <span className="text-[10px] font-normal opacity-80">prov.</span> : null}
    </span>
  );
}

export function ProjectCard({ p }) {
  const r = p.latest_rating;
  return (
    <Link to={`/projects/${p.project_id}`} className="group block rounded-2xl overflow-hidden bg-white border border-[#E4DFD3] hover:shadow-[0_12px_40px_-12px_rgba(29,33,24,0.25)] transition-shadow">
      <div className="relative aspect-[4/3] overflow-hidden">
        <img src={imageFor(p.category)} alt="" loading="lazy" className="w-full h-full object-cover object-bottom group-hover:scale-[1.03] transition-transform duration-500" />
        <div className="absolute top-3 left-3 rounded-full bg-white/90 px-3 py-1 text-xs text-[#1D2118]">{CATEGORY_LABEL[p.category] || p.category}</div>
        <div className="absolute top-3 right-3"><GradeBadge grade={r?.grade} provisional={r?.provisional} /></div>
      </div>
      <div className="p-5">
        <div className="flex items-center gap-1.5 text-xs text-[#7F8A6E]"><MapPin className="w-3.5 h-3.5" />{p.country || '—'} · {REGISTRY_LABEL[p.registry] || p.registry}</div>
        <h3 className="mt-2 font-display text-xl leading-snug text-[#1D2118] line-clamp-2 min-h-[3.3rem]">{p.name}</h3>
        <div className="mt-4 grid grid-cols-2 gap-3 text-sm border-t border-[#EFEBE2] pt-4">
          <div><div className="text-[11px] uppercase tracking-wider text-[#8E8B7E]">Issued</div><div className="font-medium">{num(p.issued)} t</div></div>
          <div><div className="text-[11px] uppercase tracking-wider text-[#8E8B7E]">Retired</div><div className="font-medium">{num(p.retired)} t</div></div>
        </div>
      </div>
    </Link>
  );
}

export function Pill({ active, onClick, children }) {
  return (
    <button onClick={onClick} className={`rounded-full px-4 py-2 text-sm border transition-colors ${active ? 'bg-[#1D2118] text-white border-[#1D2118]' : 'bg-white text-[#1D2118] border-[#E4DFD3] hover:border-[#1D2118]'}`}>
      {children}
    </button>
  );
}

export function CtaBand() {
  return (
    <section className="mx-auto max-w-7xl px-5 lg:px-8 py-20">
      <div className="rounded-3xl bg-[#2F3A2A] text-white px-8 md:px-14 py-14 grid md:grid-cols-[1.5fr_1fr] gap-8 items-center">
        <div>
          <h2 className="font-display font-light text-4xl leading-tight">Due diligence you can defend.</h2>
          <p className="mt-4 text-white/75 text-lg max-w-xl">Run Sylithe's rating agents on any project, or measure a company from its own filings. Every claim links to the page it came from.</p>
        </div>
        <div className="flex flex-wrap gap-3 md:justify-end">
          <Link to="/signup" className="rounded-full bg-[#C3B64C] text-[#1D2118] px-6 py-3 font-medium">Get started</Link>
          <a href="mailto:info@sylithe.com?subject=Sylithe%20demo" className="rounded-full border border-white/40 px-6 py-3">Book a demo</a>
        </div>
      </div>
    </section>
  );
}
