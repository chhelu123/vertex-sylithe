import { Helmet } from 'react-helmet-async';
import { Link } from 'react-router-dom';

/**
 * 404 page. Marked noindex so Google reports these as genuine "not found"
 * instead of soft 404s (the SPA rewrite always answers 200, so the noindex
 * tag is what tells crawlers the URL has no content).
 */
export default function NotFound() {
  return (
    <div className="w-full min-h-[60vh] bg-white font-sans text-[#0F172A] pt-32 pb-24 px-6 flex flex-col items-center justify-center text-center">
      <Helmet>
        <title>Page not found | Sylithe</title>
        <meta name="robots" content="noindex, follow" />
        <meta name="description" content="This page could not be found on sylithe.com." />
      </Helmet>

      <p className="text-sm font-bold tracking-widest text-[#16a34a] mb-3">404</p>
      <h1 className="text-3xl md:text-4xl font-bold mb-4">This page doesn’t exist</h1>
      <p className="text-[#475569] max-w-md mb-8">
        The page you’re looking for may have been moved or renamed.
      </p>

      <div className="flex flex-wrap gap-4 justify-center">
        <Link to="/" className="px-6 py-3 rounded-lg bg-[#16a34a] text-white font-bold hover:bg-[#15803d] transition-colors">
          Back to home
        </Link>
        <Link to="/insights" className="px-6 py-3 rounded-lg border border-[#CBD5E1] font-bold hover:bg-[#F8FAFC] transition-colors">
          Browse Insights
        </Link>
      </div>
    </div>
  );
}
