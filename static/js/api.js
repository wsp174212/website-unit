// API client: wraps fetch, returns parsed JSON or throws {code, message}.
const BASE = '/api';

async function request(path, { method = 'GET', body, signal, raw = false } = {}) {
  const opts = { method, signal };
  if (body !== undefined) {
    opts.headers = { 'Content-Type': 'application/json' };
    opts.body = JSON.stringify(body);
  }
  const resp = await fetch(BASE + path, opts);
  if (resp.status === 204) return null;
  const text = await resp.text();
  let data = null;
  if (text) {
    try { data = JSON.parse(text); } catch { data = text; }
  }
  if (!resp.ok) {
    const code = (data && data.error && data.error.code) || 'HTTP_' + resp.status;
    const message = (data && data.error && data.error.message)
      || (typeof data === 'string' ? data : `请求失败 (${resp.status})`);
    const err = new Error(message);
    err.code = code;
    err.status = resp.status;
    throw err;
  }
  return raw ? resp : data;
}

export const api = {
  // sites
  listSites: (p = '') => request('/sites' + (p ? '?' + p : '')),
  createSite: (s) => request('/sites', { method: 'POST', body: s }),
  getSite: (id) => request('/sites/' + id),
  updateSite: (id, s) => request('/sites/' + id, { method: 'PUT', body: s }),
  deleteSite: (id) => request('/sites/' + id, { method: 'DELETE' }),
  visit: (id) => request('/sites/' + id + '/visit', { method: 'POST' }),
  refetchLogo: (id) => request('/sites/' + id + '/refetch-logo', { method: 'POST' }),
  reorder: (items) => request('/sites/reorder', { method: 'POST', body: { items } }),
  bulk: (action, ids, extra = {}) =>
    request('/sites/bulk', { method: 'POST', body: { action, ids, ...extra } }),

  // stats
  statsOverview: (days) => request('/stats/overview?days=' + days),

  // system
  tags: () => request('/tags'),
  groups: () => request('/groups'),
  gcLogos: () => request('/system/gc-logos', { method: 'POST' }),
  dbInfo: () => request('/system/db-info'),

  // health
  healthCheck: (ids) => request('/health/check', { method: 'POST', body: { ids } }),
  brokenSites: () => request('/health/broken'),
  refreshMetadata: (ids) =>
    request('/health/refresh-metadata', { method: 'POST', body: ids || [] }),

  // io
  exportJsonUrl: () => BASE + '/io/export.json',
  exportCsvUrl: () => BASE + '/io/export.csv',
  importJson: (data, mode = 'merge') =>
    request('/io/import/json?mode=' + mode, { method: 'POST', body: data }),
  importCsv: (file, mode = 'merge') =>
    upload('/io/import/csv?mode=' + mode, file),
  importBookmarks: (file, mode = 'merge') =>
    upload('/io/import/bookmarks?mode=' + mode, file),
  backupUrl: () => BASE + '/backup',
  restore: (file) => upload('/io/restore', file),
};

async function upload(path, file) {
  const fd = new FormData();
  fd.append('file', file);
  const resp = await fetch(BASE + path, { method: 'POST', body: fd });
  const text = await resp.text();
  let data = null;
  if (text) { try { data = JSON.parse(text); } catch { data = text; } }
  if (!resp.ok) {
    const code = (data && data.error && data.error.code) || 'HTTP_' + resp.status;
    const err = new Error((data && data.error && data.error.message) || `上传失败 (${resp.status})`);
    err.code = code;
    throw err;
  }
  return data;
}

export function downloadUrl(url, filename) {
  const a = document.createElement('a');
  a.href = url; a.download = filename;
  document.body.appendChild(a); a.click(); a.remove();
}
