// SiteUnit frontend — Vue 3 (ESM, no build step).
import { createApp } from '../vendor/vue.esm-browser.prod.js';
import { api, downloadUrl } from './api.js';
import { hostOf, firstLetter, hueOf, parseSearch, relativeTime } from './utils.js';
import SiteModal from './components/site-modal.js';
import CommandPalette from './components/command-palette.js';
import SettingsModal from './components/settings-modal.js';
import ImportModal from './components/import-modal.js';

const PREFS = {
  theme: localStorage.getItem('siteunit-theme') || 'system',
  density: localStorage.getItem('siteunit-density') || 'comfortable',
  sort: localStorage.getItem('siteunit-sort') || 'custom',
};

createApp({
  components: { SiteModal, CommandPalette, SettingsModal, ImportModal },
  data() {
    return {
      sites: [],
      loading: true,
      search: '',
      view: 'all',           // all | archived | broken
      sort: PREFS.sort,
      theme: PREFS.theme,
      density: PREFS.density,
      selectMode: false,
      selection: new Set(),
      busyIds: new Set(),
      toast: null, toastTimer: null,
      dbInfo: null,
      groupNames: [],
      siteModal: { open: false, mode: 'add', site: null, saving: false, error: '' },
      ui: { command: false, settings: false, import: false, busy: false },
      dragId: null,
    };
  },

  computed: {
    parsed() { return parseSearch(this.search); },
    filtered() {
      const p = this.parsed;
      let list = this.sites;
      if (p.text || p.group || p.tag || p.favorite || p.pinned) {
        const tl = (p.text || '').toLowerCase();
        list = list.filter(s =>
          (!tl || (s.name + ' ' + s.url + ' ' + (s.description||'') + ' ' + (s.group||'')).toLowerCase().includes(tl))
          && (!p.group || (s.group||'未分类') === p.group)
          && (!p.tag || (s.tags||[]).some(t => t.toLowerCase() === p.tag.toLowerCase()))
          && (!p.favorite || s.favorite)
          && (!p.pinned || s.pinned)
        );
      }
      return this.sortList(list);
    },
    grouped() {
      const m = new Map();
      for (const s of this.filtered) {
        const k = s.group || '未分类';
        if (!m.has(k)) m.set(k, []);
        m.get(k).push(s);
      }
      return [...m.entries()]
        .sort(([a],[b]) => a === '未分类' ? 1 : b === '未分类' ? -1 : a.localeCompare(b, 'zh-Hans-CN'))
        .map(([name, sites]) => ({ name, sites }));
    },
    allGroupNames() {
      return [...new Set(this.sites.map(s => s.group).filter(Boolean))].sort((a,b)=>a.localeCompare(b,'zh-Hans-CN'));
    },
    selectedCount() { return this.selection.size; },
    emptyState() {
      if (this.loading) return null;
      if (!this.sites.length) return { icon: '🗂️', title: '还没有任何站点', desc: '点击右上角「添加站点」或用命令面板（Ctrl/Cmd+K）开始。' };
      if (!this.filtered.length) return { icon: '🔍', title: '没有匹配的站点', desc: '试试清空搜索或切换视图。' };
      return null;
    },
  },

  methods: {
    hostOf, firstLetter,
    letterStyle(site) {
      const h = hueOf(site.name || site.url);
      return { background: `linear-gradient(135deg, hsl(${h} 70% 55%), hsl(${(h+40)%360} 70% 45%))` };
    },
    rel: relativeTime,
    notify(text, type = 'info') {
      clearTimeout(this.toastTimer);
      this.toast = { text, type };
      this.toastTimer = setTimeout(() => { this.toast = null; }, 2800);
    },
    sortList(list) {
      const by = this.sort;
      const arr = list.slice();
      const cmp = (a, b) => {
        if (a.pinned !== b.pinned) return a.pinned ? -1 : 1;
        if (by === 'recent') return (b.last_visited_at||'').localeCompare(a.last_visited_at||'');
        if (by === 'most') return (b.visit_count - a.visit_count) || (b.last_visited_at||'').localeCompare(a.last_visited_at||'');
        if (by === 'added') return (b.created_at||'').localeCompare(a.created_at||'');
        if (by === 'name') return (a.name||'').localeCompare(b.name||'', 'zh-Hans-CN');
        return (a.sort_order - b.sort_order) || (a.id - b.id); // custom
      };
      arr.sort(cmp);
      return arr;
    },

    // ---------- data ----------
    async load() {
      this.loading = true;
      try {
        if (this.view === 'archived') this.sites = await api.listSites('order=' + this.sort + '&archived=true');
        else if (this.view === 'broken') this.sites = await api.brokenSites();
        else this.sites = await api.listSites('order=' + this.sort);
        this.groupNames = this.allGroupNames;
      } catch (e) { this.notify(e.message, 'error'); }
      finally { this.loading = false; }
    },
    reloadMeta() { Promise.all([api.tags(), api.groups(), api.dbInfo()]).then(([t,g,i]) => { this.$refs && (this.dbInfo = i); }).catch(()=>{}); },

    openSite(site) {
      // record visit without blocking the jump
      api.visit(site.id).then(r => { site.visit_count = r.visit_count; site.last_visited_at = r.last_visited_at; }).catch(()=>{});
      window.open(site.url, '_blank', 'noopener');
    },
    onLogoError(site) { site._logoFailed = true; },

    // ---------- single-site actions ----------
    async toggleFav(site) {
      site.favorite = !site.favorite;
      try { await api.updateSite(site.id, { favorite: site.favorite }); }
      catch (e) { site.favorite = !site.favorite; this.notify(e.message, 'error'); }
    },
    async togglePin(site) {
      site.pinned = !site.pinned;
      try { await api.updateSite(site.id, { pinned: site.pinned }); }
      catch (e) { site.pinned = !site.pinned; this.notify(e.message, 'error'); }
    },
    async refetchLogo(site) {
      this.busyIds.add(site.id); this.busyIds = new Set(this.busyIds);
      try {
        const u = await api.refetchLogo(site.id);
        Object.assign(site, u, { _logoFailed: false });
        this.notify('logo 已更新', 'success');
      } catch (e) { this.notify(e.message, 'error'); }
      finally { this.busyIds.delete(site.id); this.busyIds = new Set(this.busyIds); }
    },
    async archiveSite(site) {
      try {
        await api.updateSite(site.id, { archived: true });
        this.sites = this.sites.filter(s => s.id !== site.id);
        this.notify('已归档', 'info');
      } catch (e) { this.notify(e.message, 'error'); }
    },
    async removeSite(site) {
      if (!confirm(`确定删除「${site.name}」吗？`)) return;
      try { await api.deleteSite(site.id); this.sites = this.sites.filter(s => s.id !== site.id); this.notify('已删除', 'info'); }
      catch (e) { this.notify(e.message, 'error'); }
    },

    // ---------- add / edit ----------
    openAdd() { this.siteModal = { open: true, mode: 'add', site: null, saving: false, error: '', }; },
    openEdit(site) { this.siteModal = { open: true, mode: 'edit', site: { ...site }, saving: false, error: '', }; },
    async saveSite(form) {
      this.siteModal.saving = true; this.siteModal.error = '';
      try {
        if (this.siteModal.mode === 'add') {
          const created = await api.createSite(form);
          this.sites.push({ ...created, _logoFailed: false });
          this.groupNames = this.allGroupNames;
          this.notify(created.logo_url ? '已添加，logo 抓取成功' : '已添加（未抓到 logo，显示首字母）',
                      created.logo_url ? 'success' : 'info');
        } else {
          const id = this.siteModal.site.id;
          const updated = await api.updateSite(id, form);
          const i = this.sites.findIndex(s => s.id === id);
          if (i >= 0) this.sites.splice(i, 1, { ...this.sites[i], ...updated, _logoFailed: false });
          this.groupNames = this.allGroupNames;
          this.notify('已保存', 'success');
        }
        this.siteModal.open = false;
      } catch (e) {
        this.siteModal.error = e.message;
      } finally { this.siteModal.saving = false; }
    },

    // ---------- selection / bulk ----------
    toggleSelect(site) {
      if (this.selection.has(site.id)) this.selection.delete(site.id);
      else this.selection.add(site.id);
      this.selection = new Set(this.selection);
    },
    selectAllVisible() { this.selection = new Set(this.filtered.map(s => s.id)); },
    clearSelect() { this.selection = new Set(); this.selectMode = false; },
    async bulkDelete() {
      const ids = [...this.selection];
      if (!confirm(`确定删除选中的 ${ids.length} 个站点吗？`)) return;
      try { await api.bulk('delete', ids); this.sites = this.sites.filter(s => !this.selection.has(s.id)); this.clearSelect(); this.notify('已批量删除', 'info'); }
      catch (e) { this.notify(e.message, 'error'); }
    },
    async bulkArchive() {
      const ids = [...this.selection];
      try { await api.bulk('archive', ids); this.sites = this.sites.filter(s => !this.selection.has(s.id)); this.clearSelect(); this.notify('已批量归档', 'success'); }
      catch (e) { this.notify(e.message, 'error'); }
    },
    async bulkMove() {
      const g = prompt('移动到分组：', '');
      if (g === null) return;
      const ids = [...this.selection];
      try { await api.bulk('move_group', ids, { group: g }); this.clearSelect(); await this.load(); this.notify('已移动分组', 'success'); }
      catch (e) { this.notify(e.message, 'error'); }
    },
    async bulkAddTag() {
      const t = prompt('添加标签（逗号分隔）：', '');
      if (!t) return;
      const ids = [...this.selection];
      try { await api.bulk('add_tag', ids, { tags: t.split(',').map(x=>x.trim()).filter(Boolean) }); this.clearSelect(); await this.load(); this.notify('已添加标签', 'success'); }
      catch (e) { this.notify(e.message, 'error'); }
    },
    async bulkRefresh() {
      const ids = [...this.selection];
      this.ui.busy = true;
      try { const r = await api.bulk('refresh_metadata', ids); this.clearSelect(); await this.load(); this.notify(`刷新完成：${r.affected}/${ids.length}`, 'success'); }
      catch (e) { this.notify(e.message, 'error'); }
      finally { this.ui.busy = false; }
    },

    // ---------- drag & drop reorder ----------
    onDragStart(site) { this.dragId = site.id; },
    onDragOver(site, e) {
      if (!this.dragId || this.dragId === site.id) return;
      e.preventDefault();
    },
    onDrop(target) {
      const dragId = this.dragId;
      this.dragId = null;
      if (!dragId || dragId === target.id) return;
      const list = this.sites;
      const from = list.findIndex(s => s.id === dragId);
      const to = list.findIndex(s => s.id === target.id);
      if (from < 0 || to < 0) return;
      const moved = list.splice(from, 1)[0];
      moved.group = target.group;             // cross-group move
      list.splice(to, 0, moved);
      // reassign sort_order within each group by current list order
      const order = [];
      const perGroupIdx = {};
      for (const s of list) {
        const g = s.group || '未分类';
        const idx = perGroupIdx[g] || 0;
        s.sort_order = idx; perGroupIdx[g] = idx + 1;
        order.push({ site_id: s.id, sort_order: s.sort_order });
      }
      api.reorder(order).catch(e => this.notify('排序保存失败：' + e.message, 'error'));
    },

    // ---------- prefs ----------
    setPref(patch) {
      if (patch.theme !== undefined) { this.theme = patch.theme; localStorage.setItem('siteunit-theme', patch.theme); }
      if (patch.density !== undefined) { this.density = patch.density; localStorage.setItem('siteunit-density', patch.density); }
      if (patch.sort !== undefined) { this.sort = patch.sort; localStorage.setItem('siteunit-sort', patch.sort); }
    },
    applyThemeAttr() {
      const el = document.documentElement;
      el.setAttribute('data-theme', this.theme);
      el.setAttribute('data-density', this.density);
    },
    cycleTheme() {
      const order = ['system','light','dark'];
      this.setPref({ theme: order[(order.indexOf(this.theme)+1) % order.length] });
    },

    // ---------- maintenance ----------
    async runHealth() {
      this.ui.busy = true;
      try { const r = await api.healthCheck(null); await this.load(); this.notify(`已检查 ${r.checked} 个站点`, 'success'); }
      catch (e) { this.notify(e.message, 'error'); }
      finally { this.ui.busy = false; }
    },
    async refreshAll() {
      if (!confirm('将刷新全部非归档站点的元数据（标题/描述/logo），可能耗时较长。继续？')) return;
      this.ui.busy = true;
      try { const r = await api.refreshMetadata(null); await this.load(); this.notify(`刷新完成：${r.updated}/${r.checked}`, 'success'); }
      catch (e) { this.notify(e.message, 'error'); }
      finally { this.ui.busy = false; }
    },
    async gcLogos() {
      try { const r = await api.gcLogos(); this.notify(`已清理 ${r.removed} 个无用 logo`, 'success'); }
      catch (e) { this.notify(e.message, 'error'); }
    },

    switchView(v) { this.view = v; this.search = ''; this.load(); },
    exportJson() { downloadUrl(api.exportJsonUrl(), 'siteunit-export.json'); },
    openSiteFromPalette(site) { this.openSite(site); },

    // ---------- keyboard ----------
    onKeydown(e) {
      const tag = document.activeElement?.tagName;
      const typing = tag === 'INPUT' || tag === 'TEXTAREA';
      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'k') { e.preventDefault(); this.ui.command = !this.ui.command; return; }
      if (typing) return;
      if (e.key === '/') { e.preventDefault(); this.$refs.search?.focus(); }
      else if (e.key.toLowerCase() === 'a' && !this.ui.command) { e.preventDefault(); this.openAdd(); }
      else if (e.key.toLowerCase() === 's' && !this.ui.command) { e.preventDefault(); this.ui.settings = true; }
      else if (e.key === 'Escape') {
        if (this.ui.command) this.ui.command = false;
        else if (this.selectMode) this.clearSelect();
      }
    },
  },

  watch: {
    theme() { this.applyThemeAttr(); },
    density() { this.applyThemeAttr(); },
    sort() { /* client-side re-sort is reactive via computed */ },
    view() {},
  },

  mounted() {
    this.applyThemeAttr();
    this.load();
    Promise.all([api.dbInfo(), api.tags(), api.groups()]).then(([info]) => { this.dbInfo = info; }).catch(()=>{});
    document.addEventListener('keydown', (e) => this.onKeydown(e));
  },

  template: `
  <div class="app" :data-view="view">
    <header class="topbar">
      <div class="brand" @click="switchView('all')">
        <span class="brand-mark">🚀</span>
        <div><h1>SiteUnit</h1><p class="brand-sub">我的站点导航</p></div>
      </div>
      <nav class="view-tabs" v-if="!selectMode">
        <button v-for="v in [['all','全部'],['archived','已归档'],['broken','死链']]" :key="v[0]"
                class="tab" :class="{on: view === v[0]}" @click="switchView(v[0])">{{ v[1] }}</button>
      </nav>
      <div class="topbar-actions" v-if="!selectMode">
        <div class="search-box">
          <svg viewBox="0 0 24 24" class="search-icon"><path d="M21 21l-4.35-4.35M17 10.5a6.5 6.5 0 1 1-13 0 6.5 6.5 0 0 1 13 0z" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"/></svg>
          <input ref="search" v-model="search" type="text" placeholder="搜索 /  group:  tag:  fav:true  （⌘K 命令面板）" @keydown.esc="search=''">
          <button v-if="search" class="search-clear" @click="search=''" title="清空" aria-label="清空">✕</button>
        </div>
        <button class="btn btn-icon" @click="ui.command = true" title="命令面板 (⌘K)" aria-label="命令面板">⌘K</button>
        <button class="btn btn-icon" @click="ui.settings = true" title="设置" aria-label="设置">⚙</button>
        <button class="btn btn-primary" @click="openAdd"><span class="btn-plus">＋</span> 添加</button>
      </div>
      <div class="select-bar" v-if="selectMode">
        <span>已选 {{ selectedCount }} 项</span>
        <button class="btn btn-sm" @click="selectAllVisible">全选可见</button>
        <button class="btn btn-sm" @click="bulkMove">移动分组</button>
        <button class="btn btn-sm" @click="bulkAddTag">加标签</button>
        <button class="btn btn-sm" @click="bulkRefresh" :disabled="ui.busy">刷新元数据</button>
        <button class="btn btn-sm" @click="bulkArchive">归档</button>
        <button class="btn btn-sm btn-danger" @click="bulkDelete">删除</button>
        <button class="btn btn-sm" @click="clearSelect">退出</button>
      </div>
    </header>

    <main v-if="loading" class="state-msg">加载中…</main>
    <main v-else-if="emptyState" class="empty-state">
      <div class="empty-emoji">{{ emptyState.icon }}</div>
      <h2>{{ emptyState.title }}</h2>
      <p>{{ emptyState.desc }}</p>
      <button v-if="!sites.length" class="btn btn-primary" @click="openAdd">＋ 添加第一个站点</button>
      <button v-else class="btn" @click="search=''">清空搜索</button>
    </main>

    <main v-else class="groups">
      <section v-for="g in grouped" :key="g.name" class="group">
        <h2 class="group-title">{{ g.name }} <span class="group-count">{{ g.sites.length }}</span></h2>
        <div class="grid">
          <article v-for="site in g.sites" :key="site.id" class="card"
                   :class="{ busy: busyIds.has(site.id), pinned: site.pinned, broken: ['unreachable','timeout','error'].includes(site.status) }"
                   :draggable="!selectMode && view === 'all'"
                   tabindex="0" role="link" :aria-label="site.name"
                   @click="selectMode ? toggleSelect(site) : openSite(site)"
                   @keydown.enter="openSite(site)"
                   @dragstart="onDragStart(site)" @dragover="onDragOver(site, $event)"
                   @drop="onDrop(site)" @dragend="dragId = null">
            <label class="card-check" v-if="selectMode" @click.stop>
              <input type="checkbox" :checked="selection.has(site.id)" @change="toggleSelect(site)" :aria-label="['选择', site.name]">
            </label>
            <div class="card-actions" @click.stop v-if="!selectMode">
              <button class="icon-btn" :class="{on: site.favorite}" title="收藏" @click="toggleFav(site)">★</button>
              <button class="icon-btn" :class="{on: site.pinned}" title="置顶" @click="togglePin(site)">📌</button>
              <button class="icon-btn" title="重抓 logo" :disabled="busyIds.has(site.id)" @click="refetchLogo(site)">↻</button>
              <button class="icon-btn" title="编辑" @click="openEdit(site)">✎</button>
              <button class="icon-btn" title="归档" @click="archiveSite(site)">📦</button>
              <button class="icon-btn icon-btn-danger" title="删除" @click="removeSite(site)">🗑</button>
            </div>
            <div class="card-head">
              <img v-if="site.logo_url && !site._logoFailed" :src="site.logo_url" class="logo" alt="" loading="lazy" @error="onLogoError(site)">
              <div v-else class="logo logo-fallback" :style="letterStyle(site)" aria-hidden="true">{{ firstLetter(site.name) }}</div>
              <div class="card-title-wrap">
                <h3 class="card-name" :title="site.name">{{ site.name }}</h3>
                <p class="card-url">{{ hostOf(site.url) }}</p>
              </div>
              <span v-if="['unreachable','timeout','error'].includes(site.status)" class="badge badge-bad" :title="'状态：'+site.status">⚠</span>
            </div>
            <p v-if="site.description" class="card-desc" :title="site.description">{{ site.description }}</p>
            <div class="card-foot">
              <span class="tags" v-if="site.tags && site.tags.length">
                <span v-for="t in site.tags" :key="t" class="tag" @click.stop="search='tag:'+t">{{ t }}</span>
              </span>
              <span class="meta" v-if="site.visit_count > 0">{{ site.visit_count }} 次 · {{ rel(site.last_visited_at) }}</span>
            </div>
          </article>
        </div>
      </section>
    </main>

    <footer class="footbar" v-if="!loading">
      <button class="link-btn" @click="selectMode = !selectMode">{{ selectMode ? '退出选择' : '批量选择' }}</button>
      <span class="foot-sep">·</span>
      <span v-if="dbInfo" class="foot-info">{{ dbInfo.sites }} 站点 / {{ dbInfo.tags }} 标签</span>
    </footer>

    <SiteModal :open="siteModal.open" :mode="siteModal.mode" :site="siteModal.site"
               :groups="groupNames" :saving="siteModal.saving" :error="siteModal.error"
               @close="siteModal.open = false" @submit="saveSite"></SiteModal>

    <CommandPalette :open="ui.command" :sites="sites"
      @close="ui.command = false" @open-site="openSiteFromPalette" @add-site="openAdd"
      @show-settings="ui.settings = true" @show-import="ui.import = true" @set-theme="cycleTheme"
      @view="switchView($event)" @export="exportJson"></CommandPalette>

    <SettingsModal :open="ui.settings" :theme="theme" :density="density" :sort="sort"
      :db-info="dbInfo" :busy="ui.busy"
      @close="ui.settings = false" @set="setPref" @gc-logos="gcLogos" @check-health="runHealth" @refresh-all="refreshAll"></SettingsModal>

    <ImportModal :open="ui.import" @close="ui.import = false" @notify="notify" @done="load"></ImportModal>

    <transition name="toast">
      <div v-if="toast" class="toast" :class="'toast-'+toast.type">{{ toast.text }}</div>
    </transition>
  </div>`,
}).mount('#app');
