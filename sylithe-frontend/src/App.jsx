import React, { Suspense, lazy } from 'react';
import { BrowserRouter as Router, Routes, Route, Navigate, useLocation } from 'react-router-dom';
import { AuthProvider, useAuth } from './context/AuthContext';
import ErrorBoundary from './ErrorBoundary';
import SiteLayout from './site/SiteLayout';
import Home from './site/pages/Home';

// --- Public site ---
const SiteProjects   = lazy(() => import('./site/pages/Projects'));
const SiteProject    = lazy(() => import('./site/pages/ProjectPage'));
const SiteRatings    = lazy(() => import('./site/pages/Ratings'));
const SiteCompanies  = lazy(() => import('./site/pages/Companies'));
const HowItWorks     = lazy(() => import('./site/pages/HowItWorks'));
const About          = lazy(() => import('./site/pages/About'));
const TermsOfService = lazy(() => import('./pages/TermsOfService'));
const PrivacyPolicy  = lazy(() => import('./pages/PrivacyPolicy'));
const NotFound       = lazy(() => import('./pages/NotFound'));

// --- Auth ---
const Signup = lazy(() => import('./pages/Signup'));
const Login  = lazy(() => import('./pages/Login'));

// --- Platform (Module 1: company intelligence, Module 2: project ratings) ---
const PlatformShell  = lazy(() => import('./sylithe/Shell'));
const PfOverview     = lazy(() => import('./sylithe/pages/Overview'));
const PfCompanies    = lazy(() => import('./sylithe/pages/Companies'));
const PfCompany      = lazy(() => import('./sylithe/pages/CompanyProfile'));
const PfProjects     = lazy(() => import('./sylithe/pages/Projects'));
const PfProject      = lazy(() => import('./sylithe/pages/ProjectDetail'));
const PfCompare      = lazy(() => import('./sylithe/pages/Compare'));
const PfResearch     = lazy(() => import('./sylithe/pages/Research'));
const PfCalculator   = lazy(() => import('./sylithe/pages/Calculator'));
const PfMethodology  = lazy(() => import('./sylithe/pages/Methodology'));
const AdminPanel     = lazy(() => import('./pages/admin/AdminPanel'));

const PageLoader = () => (
  <div className="flex items-center justify-center min-h-screen bg-[#F7F5F0]">
    <div className="w-8 h-8 border-2 border-[#1D2118] border-t-transparent rounded-full animate-spin" />
  </div>
);

// Old /sylverra/... links → same page under /sylithe/...
function LegacyPlatformRedirect() {
  const { pathname, search } = useLocation();
  return <Navigate to={pathname.replace(/^\/sylverra/, '/sylithe') + search} replace />;
}

function PrivateRoute({ children }) {
  const { isAuthenticated } = useAuth();
  return isAuthenticated ? children : <Navigate to="/login" replace />;
}

export default function App() {
  return (
    <AuthProvider>
      <Router>
        <ErrorBoundary>
          <Suspense fallback={<PageLoader />}>
            <Routes>
              <Route element={<SiteLayout />}>
                <Route path="/" element={<Home />} />
                <Route path="/projects" element={<SiteProjects />} />
                <Route path="/projects/:id" element={<SiteProject />} />
                <Route path="/ratings" element={<SiteRatings />} />
                <Route path="/companies" element={<SiteCompanies />} />
                <Route path="/how-it-works" element={<HowItWorks />} />
                <Route path="/about" element={<About />} />
                <Route path="/terms-of-service" element={<TermsOfService />} />
                <Route path="/privacy-policy" element={<PrivacyPolicy />} />
              </Route>

              <Route path="/signup" element={<Signup />} />
              <Route path="/login" element={<Login />} />

              <Route path="/sylithe" element={<PrivateRoute><PlatformShell /></PrivateRoute>}>
                <Route index element={<PfOverview />} />
                <Route path="companies" element={<PfCompanies />} />
                <Route path="company/:slug" element={<PfCompany />} />
                <Route path="calculator" element={<PfCalculator />} />
                <Route path="projects" element={<PfProjects />} />
                <Route path="project/:id" element={<PfProject />} />
                <Route path="compare" element={<PfCompare />} />
                <Route path="research" element={<PfResearch />} />
                <Route path="methodology" element={<PfMethodology />} />
              </Route>
              <Route path="/dashboard/*" element={<Navigate to="/sylithe" replace />} />
              <Route path="/sylverra/*" element={<LegacyPlatformRedirect />} />
              <Route path="/admin" element={<PrivateRoute><AdminPanel /></PrivateRoute>} />

              <Route path="*" element={<NotFound />} />
            </Routes>
          </Suspense>
        </ErrorBoundary>
      </Router>
    </AuthProvider>
  );
}
