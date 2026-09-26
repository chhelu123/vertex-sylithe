// Sylithe API client — thin fetch wrapper that attaches the Sylithe JWT.
const BASE = `${import.meta.env.VITE_API_URL || ''}/api`;

function token() {
  return localStorage.getItem('sylithe_token');
}

async function request(path, { method = 'GET', body, form } = {}) {
  const headers = {};
  const t = token();
  if (t) headers.Authorization = `Bearer ${t}`;
  if (body !== undefined) headers['Content-Type'] = 'application/json';
  const res = await fetch(`${BASE}${path}`, {
    method,
    headers,
    body: form || (body !== undefined ? JSON.stringify(body) : undefined),
  });
  let data = null;
  try {
    data = await res.json();
  } catch {
    /* non-JSON error page */
  }
  if (!res.ok || data?.status === 'error') {
    throw new Error(data?.message || `Request failed (${res.status})`);
  }
  return data;
}

const qs = (params) => {
  const s = new URLSearchParams(Object.entries(params).filter(([, v]) => v !== undefined && v !== '' && v !== null));
  return s.toString() ? `?${s}` : '';
};

export const api = {
  overview: () => request('/overview'),
  // Module 1
  companies: (q) => request(`/companies${qs({ q })}`),
  company: (slug) => request(`/companies/${slug}`),
  companyMetrics: (slug) => request(`/companies/${slug}/metrics`),
  companyRatings: (slug) => request(`/companies/${slug}/ratings`),
  researchCompany: (symbol) => request('/companies/research', { method: 'POST', body: { symbol } }),
  evidence: (id) => request(`/evidence/${id}`),
  job: (id) => request(`/jobs/${id}`),
  // Module 2
  registryMeta: () => request('/intel/registry/meta'),
  refreshRegistry: () => request('/intel/registry/refresh', { method: 'POST', body: {} }),
  projects: (params) => request(`/intel/projects${qs(params)}`),
  facets: (country) => request(`/intel/projects/facets${qs({ country })}`),
  project: (id) => request(`/intel/projects/${id}`),
  rateProject: (id) => request(`/intel/projects/${id}/rate`, { method: 'POST', body: {} }),
  projectRatings: (id) => request(`/intel/projects/${id}/ratings`),
  linkDocument: (id, doc) => request(`/intel/projects/${id}/documents`, { method: 'POST', body: doc }),
  compare: (ids) => request(`/intel/compare${qs({ ids: ids.join(',') })}`),
  review: (ratingId, body) => request(`/intel/ratings/${ratingId}/review`, { method: 'POST', body }),
  methodology: () => request('/intel/methodology'),
  kpiDefinitions: () => request('/kpi-definitions'),
  // Research agent
  ask: (question, sessionId) => request('/research/ask', { method: 'POST', body: { question, session_id: sessionId } }),
  sessions: () => request('/research/sessions'),
  session: (id) => request(`/research/sessions/${id}`),
  // Calculator (company-user uploads)
  factors: () => request('/calculator/factors'),
  inventories: () => request('/calculator/inventories'),
  createInventory: (body) => request('/calculator/inventories', { method: 'POST', body }),
  inventory: (id) => request(`/calculator/inventories/${id}`),
  deleteInventory: (id) => request(`/calculator/inventories/${id}`, { method: 'DELETE' }),
  saveLine: (id, line) => request(`/calculator/inventories/${id}/lines`, { method: 'POST', body: line }),
  upload: (id, file) => {
    const form = new FormData();
    form.append('file', file);
    return request(`/calculator/inventories/${id}/upload`, { method: 'POST', form });
  },
};
