import React, { useEffect, useState } from 'react';
import { Link, NavLink, Outlet, useLocation } from 'react-router-dom';
import { Menu, X, ArrowUpRight } from 'lucide-react';
import { useAuth } from '../context/AuthContext';
import logo from '../assets/treee13.png';

const NAV = [
  { to: '/projects', label: 'Projects' },
  { to: '/ratings', label: 'Ratings' },
  { to: '/companies', label: 'For companies' },
  { to: '/how-it-works', label: 'How it works' },
  { to: '/about', label: 'About' },
];

function Header() {
  const { pathname } = useLocation();
  const { isAuthenticated } = useAuth();
  const [scrolled, setScrolled] = useState(false);
  const [open, setOpen] = useState(false);
  const overHero = pathname === '/' && !scrolled && !open;

  useEffect(() => {
    const onScroll = () => setScrolled(window.scrollY > 40);
    onScroll();
    window.addEventListener('scroll', onScroll, { passive: true });
    return () => window.removeEventListener('scroll', onScroll);
  }, []);
  useEffect(() => setOpen(false), [pathname]);

  return (
    <header className={`fixed inset-x-0 top-0 z-50 transition-colors duration-300 ${overHero ? 'bg-transparent text-white' : 'bg-[#F7F5F0]/95 backdrop-blur text-[#1D2118] border-b border-[#E4DFD3]'}`}>
      <div className="mx-auto max-w-7xl px-5 lg:px-8 h-16 flex items-center justify-between">
        <Link to="/" className="flex items-center gap-2.5">
          <img src={logo} alt="" className="w-8 h-8 object-contain" />
          <span className="font-display text-[22px] tracking-tight">Sylithe</span>
        </Link>
        <nav className="hidden md:flex items-center gap-7 text-[15px]">
          {NAV.map((n) => (
            <NavLink key={n.to} to={n.to} className={({ isActive }) => `hover:opacity-100 ${isActive ? 'opacity-100 underline underline-offset-8 decoration-[1.5px]' : 'opacity-80'}`}>
              {n.label}
            </NavLink>
          ))}
        </nav>
        <div className="hidden md:flex items-center gap-3 text-[15px]">
          {isAuthenticated ? (
            <Link to="/sylithe" className={`inline-flex items-center gap-1.5 rounded-full px-4 py-2 ${overHero ? 'bg-white text-[#1D2118]' : 'bg-[#1D2118] text-white'}`}>
              Open platform <ArrowUpRight className="w-4 h-4" />
            </Link>
          ) : (
            <>
              <Link to="/login" className="opacity-80 hover:opacity-100">Sign in</Link>
              <Link to="/signup" className={`rounded-full px-4 py-2 ${overHero ? 'bg-white text-[#1D2118]' : 'bg-[#1D2118] text-white'}`}>Get started</Link>
            </>
          )}
        </div>
        <button className="md:hidden p-2" onClick={() => setOpen(!open)} aria-label="Menu">{open ? <X /> : <Menu />}</button>
      </div>
      {open && (
        <div className="md:hidden border-t border-[#E4DFD3] bg-[#F7F5F0] px-5 py-4 space-y-3 text-[#1D2118]">
          {NAV.map((n) => <Link key={n.to} to={n.to} className="block text-lg">{n.label}</Link>)}
          <Link to={isAuthenticated ? '/sylithe' : '/login'} className="block rounded-full bg-[#1D2118] text-white text-center py-2.5">{isAuthenticated ? 'Open platform' : 'Sign in'}</Link>
        </div>
      )}
    </header>
  );
}

function Footer() {
  return (
    <footer className="bg-[#1D2118] text-[#D9D5C8]">
      <div className="mx-auto max-w-7xl px-5 lg:px-8 py-16 grid gap-10 md:grid-cols-[1.4fr_1fr_1fr_1fr]">
        <div>
          <div className="flex items-center gap-2.5 text-white"><img src={logo} alt="" className="w-8 h-8" /><span className="font-display text-2xl">Sylithe</span></div>
          <p className="mt-4 max-w-sm text-sm leading-relaxed text-[#A8A597]">
            Evidence-backed carbon intelligence. We rate carbon projects and measure companies' climate performance, with every number traced to its source.
          </p>
        </div>
        <div>
          <div className="text-xs uppercase tracking-[0.18em] text-[#8E8B7E] mb-3">Platform</div>
          <ul className="space-y-2 text-sm">
            <li><Link to="/projects" className="hover:text-white">Project marketplace</Link></li>
            <li><Link to="/ratings" className="hover:text-white">Rating methodology</Link></li>
            <li><Link to="/companies" className="hover:text-white">Company intelligence</Link></li>
            <li><Link to="/how-it-works" className="hover:text-white">Due-diligence process</Link></li>
          </ul>
        </div>
        <div>
          <div className="text-xs uppercase tracking-[0.18em] text-[#8E8B7E] mb-3">Company</div>
          <ul className="space-y-2 text-sm">
            <li><Link to="/about" className="hover:text-white">About</Link></li>
            <li><a href="mailto:info@sylithe.com" className="hover:text-white">Contact</a></li>
            <li><Link to="/login" className="hover:text-white">Sign in</Link></li>
          </ul>
        </div>
        <div>
          <div className="text-xs uppercase tracking-[0.18em] text-[#8E8B7E] mb-3">Legal</div>
          <ul className="space-y-2 text-sm">
            <li><Link to="/terms-of-service" className="hover:text-white">Terms of service</Link></li>
            <li><Link to="/privacy-policy" className="hover:text-white">Privacy policy</Link></li>
          </ul>
        </div>
      </div>
      <div className="border-t border-white/10">
        <div className="mx-auto max-w-7xl px-5 lg:px-8 py-5 text-xs text-[#8E8B7E] flex flex-wrap justify-between gap-2">
          <span>© {new Date().getFullYear()} Sylithe. Ratings are analytical assessments, not registry certifications or investment advice.</span>
          <span>Registry data: CarbonPlan OffsetsDB</span>
        </div>
      </div>
    </footer>
  );
}

export default function SiteLayout() {
  const { pathname } = useLocation();
  useEffect(() => { window.scrollTo(0, 0); }, [pathname]);
  return (
    <div className="min-h-screen bg-[#F7F5F0] text-[#1D2118] font-sans">
      <Header />
      <main className={pathname === '/' ? '' : 'pt-16'}><Outlet /></main>
      <Footer />
    </div>
  );
}
