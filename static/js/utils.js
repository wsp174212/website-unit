// Small UI helpers shared across components.

export function hueOf(text) {
  let h = 0;
  for (const ch of (text || 'x')) h = (h * 31 + ch.codePointAt(0)) % 360;
  return h;
}

export function firstLetter(name) {
  const ch = (name || '?').trim().charAt(0);
  return /[a-z]/i.test(ch) ? ch.toUpperCase() : ch;
}

export function hostOf(url) {
  try { return new URL(url).hostname.replace(/^www\./, ''); }
  catch { return url; }
}

export function debounce(fn, ms = 300) {
  let t;
  return (...args) => {
    clearTimeout(t);
    t = setTimeout(() => fn(...args), ms);
  };
}

export function relativeTime(iso) {
  if (!iso) return '';
  const d = new Date(iso);
  if (isNaN(d)) return '';
  const s = (Date.now() - d.getTime()) / 1000;
  if (s < 60) return '刚刚';
  if (s < 3600) return Math.floor(s / 60) + ' 分钟前';
  if (s < 86400) return Math.floor(s / 3600) + ' 小时前';
  if (s < 2592000) return Math.floor(s / 86400) + ' 天前';
  return d.toLocaleDateString();
}

// token-aware search: returns {text, group, tag, favorite, pinned}
export function parseSearch(q) {
  const out = { text: [], group: null, tag: null, favorite: false, pinned: false };
  for (const tok of (q || '').split(/\s+/)) {
    const low = tok.toLowerCase();
    if (low.startsWith('group:')) out.group = tok.slice(6) || null;
    else if (low.startsWith('tag:')) out.tag = tok.slice(4) || null;
    else if (low.startsWith('fav:')) out.favorite = ['1', 'true', 'yes'].includes(low.slice(4));
    else if (low.startsWith('pinned:')) out.pinned = ['1', 'true', 'yes'].includes(low.slice(7));
    else if (tok) out.text.push(tok);
  }
  out.text = out.text.join(' ') || null;
  return out;
}

export function buildQuery({ order, archived, q, group, tag, favorite, pinned }) {
  const p = new URLSearchParams();
  if (order) p.set('order', order);
  if (archived !== undefined && archived !== null) p.set('archived', archived);
  if (q) p.set('q', q);
  if (group) p.set('group', group);
  if (tag) p.set('tag', tag);
  if (favorite) p.set('favorite', 'true');
  if (pinned) p.set('pinned', 'true');
  return p.toString();
}
