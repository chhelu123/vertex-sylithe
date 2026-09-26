import { Helmet } from 'react-helmet-async';
import { absoluteUrl, isoDate, SITE_ORIGIN } from '../lib/seo';

const SITE_NAME = 'Sylithe';
const BASE_URL = SITE_ORIGIN;
const DEFAULT_IMAGE = `${BASE_URL}/og-image.png`;

// --- Breadcrumb name map for human-readable labels ---
const BREADCRUMB_NAMES = {
  '/': 'Home',
  '/about': 'About Us',
  '/platform': 'dMRV Platform',
  '/what-we-offer': 'Solutions',
  '/for-buyers': 'For Buyers',
  '/insights': 'Insights',
  '/methodology': 'Methodology',
  '/methodology/lulc': 'LULC Classification',
  '/methodology/chm': 'Canopy Height Model',
  '/methodology/dcab': 'Dynamic Baseline',
  '/methodology/agb': 'AGB Estimation',
  '/project-types': 'Project Types',
  '/project-types/biochar': 'Biochar Carbon Removal',
  '/project-types/arr': 'ARR Carbon Projects',
  '/project-types/redd': 'REDD+ Carbon Projects',
  '/privacy-policy': 'Privacy Policy',
  '/terms-of-service': 'Terms of Service',
};

/**
 * Generate BreadcrumbList JSON-LD from a path like "/methodology/chm"
 */
function buildBreadcrumbs(path) {
  if (path === '/') return null;

  const segments = path.split('/').filter(Boolean);
  const items = [
    { '@type': 'ListItem', position: 1, name: 'Home', item: `${BASE_URL}/` },
  ];

  let currentPath = '';
  segments.forEach((seg, idx) => {
    currentPath += `/${seg}`;
    const name = BREADCRUMB_NAMES[currentPath] || seg.replace(/-/g, ' ').replace(/\b\w/g, c => c.toUpperCase());
    items.push({
      '@type': 'ListItem',
      position: idx + 2,
      name,
      item: `${BASE_URL}${currentPath}`,
    });
  });

  return {
    '@context': 'https://schema.org',
    '@type': 'BreadcrumbList',
    itemListElement: items,
  };
}

/**
 * SEOHead — drop into any page for per-page <title>, meta description,
 * canonical URL, Open Graph, Twitter Card, BreadcrumbList, hreflang, and speakable.
 *
 * @param {string}  title       — Page title (will be suffixed with " | Sylithe")
 * @param {string}  description — Meta description for the page
 * @param {string}  path        — Route path, e.g. "/about" (used for canonical & OG url)
 * @param {string}  [image]     — OG / Twitter image URL (defaults to og-image.png 1200×630)
 * @param {string}  [imageAlt]  — Alt text for the OG image
 * @param {string}  [type]      — OG type, e.g. "article" or "website"
 * @param {string}  [publishedTime] — ISO date string for articles
 * @param {string}  [author]    — Author name for articles
 * @param {string}  [keywords]  — Meta keywords for the page
 * @param {Object}  [jsonLd]    — Additional JSON-LD schema to inject
 * @param {string[]} [speakableSelectors] — CSS selectors for speakable content
 */
export default function SEOHead({ 
  title, 
  description, 
  path = '/', 
  image, 
  imageAlt,
  type = 'website',
  publishedTime,
  author,
  keywords,
  jsonLd,
  speakableSelectors,
}) {
  const fullTitle = title.includes(SITE_NAME) ? title : `${title} | ${SITE_NAME}`;

  // Normalise canonical: root stays as-is, all other paths strip trailing slash
  const normPath = path === '/' ? '/' : path.replace(/\/$/, '');
  const canonicalUrl = `${BASE_URL}${normPath}`;

  // og:image must be absolute — Vite hands us "/assets/foo-hash.png".
  const ogImage = absoluteUrl(image) || DEFAULT_IMAGE;
  const publishedIso = isoDate(publishedTime);
  const ogImageAlt = imageAlt || fullTitle;

  // Auto-generate breadcrumb schema
  const breadcrumbSchema = buildBreadcrumbs(normPath);

  // Speakable schema
  const speakableSchema = speakableSelectors && speakableSelectors.length > 0
    ? {
        '@context': 'https://schema.org',
        '@type': 'WebPage',
        name: fullTitle,
        speakable: {
          '@type': 'SpeakableSpecification',
          cssSelector: speakableSelectors,
        },
        url: canonicalUrl,
      }
    : null;

  return (
    <Helmet>
      <title>{fullTitle}</title>
      <meta name="description" content={description} />
      <meta name="robots" content="index, follow, max-snippet:-1, max-image-preview:large, max-video-preview:-1" />
      <link rel="canonical" href={canonicalUrl} />

      {/* Keywords (if provided) */}
      {keywords && <meta name="keywords" content={keywords} />}

      {/* hreflang — English India + x-default */}
      <link rel="alternate" hrefLang="en-IN" href={canonicalUrl} />
      <link rel="alternate" hrefLang="x-default" href={canonicalUrl} />

      {/* Social profile links */}
      <link rel="me" href="https://x.com/Sylithe_" />
      <link rel="me" href="https://www.linkedin.com/company/sylithe/" />

      {/* Open Graph */}
      <meta property="og:title" content={fullTitle} />
      <meta property="og:description" content={description} />
      <meta property="og:url" content={canonicalUrl} />
      <meta property="og:image" content={ogImage} />
      <meta property="og:image:width" content="1200" />
      <meta property="og:image:height" content="630" />
      <meta property="og:image:alt" content={ogImageAlt} />
      <meta property="og:type" content={type} />
      <meta property="og:site_name" content={SITE_NAME} />
      <meta property="og:locale" content="en_IN" />

      {/* Article-specific OG tags */}
      {type === 'article' && publishedIso && (
        <meta property="article:published_time" content={publishedIso} />
      )}
      {type === 'article' && author && (
        <meta property="article:author" content={author} />
      )}

      {/* Twitter / X Card */}
      <meta name="twitter:card" content="summary_large_image" />
      <meta name="twitter:site" content="@Sylithe_" />
      <meta name="twitter:title" content={fullTitle} />
      <meta name="twitter:description" content={description} />
      <meta name="twitter:image" content={ogImage} />
      <meta name="twitter:image:alt" content={ogImageAlt} />

      {/* BreadcrumbList JSON-LD */}
      {breadcrumbSchema && (
        <script type="application/ld+json">
          {JSON.stringify(breadcrumbSchema)}
        </script>
      )}

      {/* Speakable JSON-LD */}
      {speakableSchema && (
        <script type="application/ld+json">
          {JSON.stringify(speakableSchema)}
        </script>
      )}

      {/* Custom JSON-LD */}
      {jsonLd && (
        <script type="application/ld+json">
          {JSON.stringify(jsonLd)}
        </script>
      )}
    </Helmet>
  );
}
