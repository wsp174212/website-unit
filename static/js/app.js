/* SiteUnit frontend — Vue 3 (global build, no build step) */
const { createApp } = Vue;

async function api(path, options = {}) {
  const resp = await fetch('/api' + path, {
    headers: { 'Content-Type': 'application/json' },
    ...options,
  });
  if (!resp.ok) {
    let detail = `请求失败 (${resp.status})`;
    try {
      const body = await resp.json();
      if (typeof body.detail === 'string') detail = body.detail;
    } catch { /* keep default */ }
    throw new Error(detail);
  }
  if (resp.status === 204) return null;
  return resp.json();
}

function hueOf(text) {
  let h = 0;
  for (const ch of text || 'x') h = (h * 31 + ch.codePointAt(0)) % 360;
  return h;
}

createApp({
  data() {
    return {
      sites: [],
      loading: true,
      search: '',
      busyIds: new Set(),
      toast: null,
      toastTimer: null,
      modal: {
        open: false,
        mode: 'add',
        saving: false,
        error: '',
        editingId: null,
        currentLogo: '',
        form: { url: '', name: '', description: '', grp: '', refetch_logo: false },
      },
    };
  },

  computed: {
    filtered() {
      const q = this.search.trim().toLowerCase();
      if (!q) return this.sites;
      return this.sites.filter(s =>
        (s.name || '').toLowerCase().includes(q) ||
        (s.url || '').toLowerCase().includes(q) ||
        (s.description || '').toLowerCase().includes(q) ||
        (s.grp || '').toLowerCase().includes(q)
      );
    },
    groups() {
      const byName = new Map();
      for (const s of this.filtered) {
        const key = s.grp || '未分类';
        if (!byName.has(key)) byName.set(key, []);
        byName.get(key).push(s);
      }
      return [...byName.entries()]
        .sort(([a], [b]) =>
          a === '未分类' ? 1 : b === '未分类' ? -1 : a.localeCompare(b, 'zh-Hans-CN'))
        .map(([name, sites]) => ({ name, sites }));
    },
    allGroupNames() {
      return [...new Set(this.sites.map(s => s.grp).filter(Boolean))].sort(
        (a, b) => a.localeCompare(b, 'zh-Hans-CN'));
    },
  },

  methods: {
    /* ---------- helpers ---------- */
    firstLetter(name) {
      const ch = (name || '?').trim().charAt(0);
      return /[a-z]/i.test(ch) ? ch.toUpperCase() : ch;
    },
    letterStyle(site) {
      const h = hueOf(site.name || site.url);
      return {
        background: `linear-gradient(135deg, hsl(${h} 70% 55%), hsl(${(h + 40) % 360} 70% 45%))`,
      };
    },
    hostOf(url) {
      try { return new URL(url).hostname.replace(/^www\./, ''); }
      catch { return url; }
    },
    showToast(text, type = 'info') {
      clearTimeout(this.toastTimer);
      this.toast = { text, type };
      this.toastTimer = setTimeout(() => { this.toast = null; }, 2600);
    },
    replaceSite(updated) {
      const i = this.sites.findIndex(s => s.id === updated.id);
      if (i >= 0) this.sites.splice(i, 1, { ...this.sites[i], ...updated, _logoFailed: false });
    },

    /* ---------- data ---------- */
    async load() {
      try {
        const list = await api('/sites');
        this.sites = list.map(s => ({ ...s, _logoFailed: false }));
      } catch (e) {
        this.showToast(e.message, 'error');
      } finally {
        this.loading = false;
      }
    },

    openSite(site) {
      window.open(site.url, '_blank', 'noopener');
    },
    onLogoError(site) {
      site._logoFailed = true;
    },

    /* ---------- modal ---------- */
    openAdd() {
      this.modal = {
        open: true, mode: 'add', saving: false, error: '', editingId: null,
        currentLogo: '',
        form: { url: '', name: '', description: '', grp: '', refetch_logo: false },
      };
      this.$nextTick(() => this.$refs.urlInput?.focus());
    },
    openEdit(site) {
      this.modal = {
        open: true, mode: 'edit', saving: false, error: '', editingId: site.id,
        currentLogo: site.logo_url || '无',
        form: {
          url: site.url, name: site.name, description: site.description,
          grp: site.grp, refetch_logo: false,
        },
      };
      this.$nextTick(() => this.$refs.urlInput?.focus());
    },
    closeModal() {
      if (!this.modal.saving) this.modal.open = false;
    },
    async save() {
      const f = this.modal.form;
      if (!f.url) return;
      this.modal.saving = true;
      this.modal.error = '';
      try {
        if (this.modal.mode === 'add') {
          const created = await api('/sites', { method: 'POST', body: JSON.stringify(f) });
          this.sites.push({ ...created, _logoFailed: false });
          this.showToast(created.logo_url ? '已添加，logo 抓取成功 ✓' : '已添加（未抓到 logo，显示首字母）',
            created.logo_url ? 'success' : 'info');
        } else {
          const updated = await api(`/sites/${this.modal.editingId}`, {
            method: 'PUT', body: JSON.stringify(f),
          });
          this.replaceSite(updated);
          this.showToast('已保存 ✓', 'success');
        }
        this.modal.open = false;
      } catch (e) {
        this.modal.error = e.message;
      } finally {
        this.modal.saving = false;
      }
    },

    /* ---------- row actions ---------- */
    async removeSite(site) {
      if (!confirm(`确定删除「${site.name}」吗？`)) return;
      try {
        await api(`/sites/${site.id}`, { method: 'DELETE' });
        this.sites = this.sites.filter(s => s.id !== site.id);
        this.showToast('已删除', 'info');
      } catch (e) {
        this.showToast(e.message, 'error');
      }
    },
    async refetchLogo(site) {
      this.busyIds.add(site.id);
      this.busyIds = new Set(this.busyIds); // trigger reactivity
      try {
        const updated = await api(`/sites/${site.id}/refetch-logo`, { method: 'POST' });
        this.replaceSite(updated);
        this.showToast('logo 已更新 ✓', 'success');
      } catch (e) {
        this.showToast(e.message, 'error');
      } finally {
        this.busyIds.delete(site.id);
        this.busyIds = new Set(this.busyIds);
      }
    },
  },

  mounted() {
    this.load();
    document.addEventListener('keydown', (e) => {
      const tag = document.activeElement?.tagName;
      const typing = tag === 'INPUT' || tag === 'TEXTAREA';
      if (e.key === '/' && !typing && !this.modal.open) {
        e.preventDefault();
        this.$refs.searchInput?.focus();
      }
      if (e.key === 'Escape' && this.modal.open) this.closeModal();
    });
  },
}).mount('#app');
