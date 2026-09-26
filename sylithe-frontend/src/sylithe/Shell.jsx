import React, { useEffect, useRef, useState } from 'react';
import { Link, NavLink, Outlet, useNavigate } from 'react-router-dom';
import {
  LayoutDashboard, Building2, Trees, GitCompareArrows, Sparkles, Calculator, BookOpen, Search, LogOut, ArrowLeft,
} from 'lucide-react';
import { useAuth } from '../context/AuthContext';
import { api } from './api';
import { EvidenceProvider, cx, Grade } from './ui';

const NAV = [
  { to: '/sylithe', label: 'Overview', icon: LayoutDashboard, end: true },
  { section: 'Module 1 · Companies' },
  { to: '/sylithe/companies', label: 'Company Intelligence', icon: Building2 },
  { to: '/sylithe/calculator', label: 'Carbon Calculator', icon: Calculator },
  { section: 'Module 2 · Projects' },
  { to: '/sylithe/projects', label: 'Project Ratings', icon: Trees },
  { to: '/sylithe/compare', label: 'Compare Projects', icon: GitCompareArrows },
  { section: 'Research' },
  { to: '/sylithe/research', label: 'AI Research Agent', icon: Sparkles },
  { to: '/sylithe/methodology', label: 'Methodology', icon: BookOpen },
];

function GlobalSearch() {
  const nav = useNavigate();
  const [q, setQ] = useState('');
  const [res, setRes] = useState(null);
  const [open, setOpen] = useState(false);
  const box = useRef(null);

  useEffect(() => {
    if (q.trim().length < 2) { setRes(null); return undefined; }
    const t = setTimeout(async () => {
      const [c, p] = await Promise.allSettled([api.companies(q), api.projects({ q, per_page: 6 })]);
      setRes({
        companies: c.status === 'fulfilled' ? c.value.companies.slice(0, 5) : [],
        nse: c.status === 'fulfilled' ? (c.value.nse_matches || []).filter((m) => !m.tracked).slice(0, 4) : [],
        projects: p.status === 'fulfilled' ? p.value.projects : [],
      });
      setOpen(true);
    }, 250);
    return () => clearTimeout(t);
  }, [q]);

  useEffect(() => {
    const h = (e) => { if (box.current && !box.current.contains(e.target)) setOpen(false); };
    document.addEventListener('mousedown', h);
    return () => document.removeEventListener('mousedown', h);
  }, []);

  const go = (path) => { setOpen(false); setQ(''); nav(path); };
  const ask = () => go(`/sylithe/research?q=${encodeURIComponent(q)}`);

  return (
    <div ref={box} className="relative w-full max-w-2xl">
      <div className="flex items-center gap-2 bg-slate-50 border border-slate-200 rounded-md px-3 py-1.5 focus-within:border-[#08292f] focus-within:bg-white">
        <Search className="w-4 h-4 text-slate-400" />
        <input
          value={q}
          onChange={(e) => setQ(e.target.value)}
          onFocus={() => res && setOpen(true)}
          onKeyDown={(e) => { if (e.key === 'Enter' && q.trim()) ask(); }}
          placeholder="Search company, project, developer, methodology… (Enter = ask the AI agent)"
          className="flex-1 bg-transparent text-sm outline-none placeholder:text-slate-400"
        />
        <kbd className="hidden md:inline text-[10px] text-slate-400 border border-slate-200 rounded px-1">Enter</kbd>
      </div>
      {open && res && (
        <div className="absolute z-50 mt-1 w-full bg-white border border-slate-200 rounded-md shadow-lg max-h-[70vh] overflow-y-auto text-sm">
          <button onClick={ask} className="w-full text-left px-3 py-2 hover:bg-slate-50 flex items-center gap-2 border-b border-slate-100">
            <Sparkles className="w-4 h-4 text-[#08292f]" /> Ask the research agent: <span className="font-medium truncate">“{q}”</span>
          </button>
          {res.companies.length > 0 && <div className="px-3 pt-2 pb-1 text-[10px] uppercase tracking-wider text-slate-400">Tracked companies</div>}
          {res.companies.map((c) => (
            <button key={c.slug} onClick={() => go(`/sylithe/company/${c.slug}`)} className="w-full text-left px-3 py-1.5 hover:bg-slate-50 flex items-center justify-between">
              <span>{c.name} <span className="text-slate-400 text-xs">{c.symbol}</span></span>
              <Grade grade={c.rating?.grade} size="sm" />
            </button>
          ))}
          {res.nse.length > 0 && <div className="px-3 pt-2 pb-1 text-[10px] uppercase tracking-wider text-slate-400">NSE-listed · not yet researched</div>}
          {res.nse.map((m) => (
            <button key={m.symbol} onClick={() => go(`/sylithe/companies?research=${m.symbol}`)} className="w-full text-left px-3 py-1.5 hover:bg-slate-50 flex items-center justify-between">
              <span>{m.name} <span className="text-slate-400 text-xs">{m.symbol}</span></span>
              <span className="text-[11px] text-[#08292f] font-medium">Run agents →</span>
            </button>
          ))}
          {res.projects.length > 0 && <div className="px-3 pt-2 pb-1 text-[10px] uppercase tracking-wider text-slate-400">Carbon projects</div>}
          {res.projects.map((p) => (
            <button key={p.project_id} onClick={() => go(`/sylithe/project/${p.project_id}`)} className="w-full text-left px-3 py-1.5 hover:bg-slate-50 flex items-center justify-between gap-3">
              <span className="truncate">{p.name} <span className="text-slate-400 text-xs">{p.project_id} · {p.country}</span></span>
              <Grade grade={p.latest_rating?.grade} size="sm" />
            </button>
          ))}
        </div>
      )}
    </div>
  );
}

export default function Shell() {
  const { user, logout } = useAuth();
  return (
    <EvidenceProvider>
      <div className="min-h-screen bg-[#F4F5F7] text-slate-900 flex">
        <aside className="hidden lg:flex w-60 shrink-0 flex-col bg-[#08292f] text-slate-200 sticky top-0 h-screen">
          <Link to="/sylithe" className="px-5 py-4 border-b border-white/10">
            <div className="text-lg font-bold tracking-tight text-white">Sylithe</div>
            <div className="text-[11px] text-slate-400">Carbon intelligence platform</div>
          </Link>
          <nav className="flex-1 overflow-y-auto py-3">
            {NAV.map((n, i) => n.section ? (
              <div key={i} className="px-5 pt-4 pb-1 text-[10px] uppercase tracking-widest text-slate-500">{n.section}</div>
            ) : (
              <NavLink key={n.to} to={n.to} end={n.end}
                className={({ isActive }) => cx('flex items-center gap-2.5 mx-2 px-3 py-2 rounded text-[13px]',
                  isActive ? 'bg-white/10 text-white font-medium' : 'text-slate-300 hover:bg-white/5 hover:text-white')}>
                <n.icon className="w-4 h-4" /> {n.label}
              </NavLink>
            ))}
          </nav>
          <div className="px-5 py-3 border-t border-white/10 text-xs text-slate-400 space-y-2">
            <Link to="/" className="flex items-center gap-1.5 hover:text-white"><ArrowLeft className="w-3.5 h-3.5" /> Sylithe website</Link>
            <div className="truncate">{user?.email}</div>
            <button onClick={logout} className="flex items-center gap-1.5 hover:text-white"><LogOut className="w-3.5 h-3.5" /> Log out</button>
          </div>
        </aside>
        <div className="flex-1 min-w-0 flex flex-col">
          <header className="sticky top-0 z-40 bg-white border-b border-slate-200 px-4 lg:px-6 py-2.5 flex items-center gap-4">
            <Link to="/sylithe" className="lg:hidden font-bold text-[#08292f]">Sylithe</Link>
            <GlobalSearch />
          </header>
          <nav className="lg:hidden flex gap-1 overflow-x-auto px-3 py-2 bg-white border-b border-slate-200">
            {NAV.filter((n) => !n.section).map((n) => (
              <NavLink key={n.to} to={n.to} end={n.end}
                className={({ isActive }) => cx('shrink-0 px-2.5 py-1 rounded text-xs', isActive ? 'bg-[#08292f] text-white' : 'text-slate-600 bg-slate-100')}>
                {n.label}
              </NavLink>
            ))}
          </nav>
          <main className="flex-1 px-4 lg:px-6 py-5 max-w-[1400px] w-full mx-auto">
            <Outlet />
          </main>
        </div>
      </div>
    </EvidenceProvider>
  );
}
