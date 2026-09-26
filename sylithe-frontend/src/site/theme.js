// Sylithe public site — shared imagery, labels and formatting helpers.
import mangroves from './img/mangroves.jpg';
import agroforestry from './img/agroforestry.jpg';
import deccan from './img/deccan-plateau.jpg';
import biochar from './img/biochar-hero.jpg';
import rice from './img/rice-farmer.jpg';
import soil from './img/soil-field.jpg';

export const IMAGES = { mangroves, agroforestry, deccan, biochar, rice, soil };

// Project category → representative photo (Sylithe's own library).
const CATEGORY_IMAGE = {
  forest: mangroves,
  'land-use': deccan,
  agriculture: rice,
  'biomass-cdr': biochar,
  'alkalinity-cdr': soil,
  'air-capture': biochar,
  'renewable-energy': deccan,
  'energy-efficiency': agroforestry,
  'fuel-switching': agroforestry,
  'ghg-management': soil,
  unknown: deccan,
};
export const imageFor = (category) => CATEGORY_IMAGE[category] || deccan;

export const CATEGORY_LABEL = {
  forest: 'Forestry & land', 'land-use': 'Land use', agriculture: 'Agriculture', 'biomass-cdr': 'Biomass removal',
  'alkalinity-cdr': 'Alkalinity removal', 'air-capture': 'Direct air capture', 'renewable-energy': 'Renewable energy',
  'energy-efficiency': 'Energy efficiency', 'fuel-switching': 'Fuel switching', 'ghg-management': 'Methane & GHG',
  unknown: 'Other',
};

export const REGISTRY_LABEL = {
  verra: 'Verra', 'gold-standard': 'Gold Standard', 'american-carbon-registry': 'ACR',
  'climate-action-reserve': 'CAR', 'art-trees': 'ART TREES', isometric: 'Isometric', cercarbono: 'Cercarbono',
};

export const num = (v) => {
  if (v === null || v === undefined) return '—';
  const a = Math.abs(v);
  if (a >= 1e9) return `${(v / 1e9).toFixed(1)}B`;
  if (a >= 1e6) return `${(v / 1e6).toFixed(1)}M`;
  if (a >= 1e3) return `${(v / 1e3).toFixed(0)}k`;
  return Math.round(v).toLocaleString();
};

export const gradeTone = (g) => {
  if (!g) return 'bg-[#E9E5DC] text-[#5B6152]';
  if (['AAA', 'AA', 'A'].includes(g)) return 'bg-[#2F5D46] text-white';
  if (['BBB', 'BB'].includes(g)) return 'bg-[#7F8A6E] text-white';
  if (['B', 'C'].includes(g)) return 'bg-[#C3B64C] text-[#1D2118]';
  return 'bg-[#E9731F] text-white';
};
