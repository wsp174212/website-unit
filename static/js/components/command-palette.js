// Command palette: Ctrl/Cmd+K. Search sites + run commands.
import { hostOf } from '../utils.js';

export default {
  name: 'CommandPalette',
  props: {
    open: Boolean,
    sites: { type: Array, default: () => [] },
  },
  emits: ['close', 'open-site', 'add-site', 'edit-site', 'set-theme', 'show-settings', 'show-import', 'view', 'export'],
  data() {
    return { q: '', index: 0, items: [] };
  },
  watch: {
    open(v) {
      if (!v) return;
      this.q = '';
      this.rebuild();
      this.$nextTick(() => this.$refs.input?.focus());
    },
    q() { this.rebuild(); this.index = 0; },
  },
  methods: {
    commands() {
      return [
        { type: 'cmd', label: '添加站点', hint: 'A', action: () => this.$emit('add-site'), icon: '＋' },
        { type: 'cmd', label: '导入 / 导出', hint: 'I', action: () => this.$emit('show-import'), icon: '⇅' },
        { type: 'cmd', label: '设置（主题 / 密度 / 排序）', hint: 'S', action: () => this.$emit('show-settings'), icon: '⚙' },
        { type: 'cmd', label: '切换主题', hint: 'T', action: () => this.$emit('set-theme'), icon: '◐' },
        { type: 'cmd', label: '导出 JSON', hint: '', action: () => this.$emit('export'), icon: '⬇' },
        { type: 'cmd', label: '查看：已归档', hint: '', action: () => this.$emit('view', 'archived'), icon: '📦' },
        { type: 'cmd', label: '查看：死链', hint: '', action: () => this.$emit('view', 'broken'), icon: '⚠' },
        { type: 'cmd', label: '查看：全部', hint: '', action: () => this.$emit('view', 'all'), icon: '☰' },
      ];
    },
    rebuild() {
      const ql = this.q.trim().toLowerCase();
      const siteItems = this.sites
        .filter(s => !ql || (s.name + ' ' + s.url + ' ' + (s.group||'')).toLowerCase().includes(ql))
        .slice(0, 8)
        .map(s => ({ type: 'site', site: s, label: s.name, hint: hostOf(s.url), icon: '↗' }));
      const cmds = this.commands().filter(c => !ql || c.label.toLowerCase().includes(ql));
      this.items = [...siteItems, ...cmds].slice(0, 12);
    },
    choose(item) {
      if (!item) return;
      if (item.type === 'site') this.$emit('open-site', item.site);
      else item.action();
      this.$emit('close');
    },
    onKeydown(e) {
      if (e.key === 'ArrowDown') { e.preventDefault(); this.index = Math.min(this.index + 1, this.items.length - 1); }
      else if (e.key === 'ArrowUp') { e.preventDefault(); this.index = Math.max(this.index - 1, 0); }
      else if (e.key === 'Enter') { e.preventDefault(); this.choose(this.items[this.index]); }
      else if (e.key === 'Escape') { this.$emit('close'); }
    },
    iconFor(item) {
      return item.type === 'site' ? '↗' : item.icon;
    },
  },
  template: `
  <div v-if="open" class="overlay" @click.self="$emit('close')">
    <div class="palette" role="dialog" aria-modal="true" aria-label="命令面板">
      <div class="palette-input">
        <span class="palette-icon">⌘</span>
        <input ref="input" v-model="q" type="text" placeholder="搜索站点或输入命令…"
               @keydown="onKeydown" autocomplete="off">
        <kbd class="kbd">Esc</kbd>
      </div>
      <ul class="palette-list" v-if="items.length">
        <li v-for="(it, i) in items" :key="i" class="palette-item"
            :class="{active: i === index}" @mouseenter="index = i" @click="choose(it)">
          <span class="palette-item-icon">{{ iconFor(it) }}</span>
          <span class="palette-item-label">{{ it.label }}</span>
          <span class="palette-item-hint">{{ it.hint }}</span>
        </li>
      </ul>
      <p v-else class="palette-empty">无匹配项</p>
    </div>
  </div>`,
};
