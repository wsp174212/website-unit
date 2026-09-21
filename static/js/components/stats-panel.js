// Stats panel: visit statistics dashboard backed by GET /api/stats/overview.
import { api } from '../api.js';
import { hostOf, firstLetter, hueOf } from '../utils.js';

const DAYS = [7, 30, 90];

export default {
  name: 'StatsPanel',
  props: {
    open: Boolean,
  },
  emits: ['notify'],
  data() {
    return {
      dayOptions: DAYS,
      days: 30,
      data: null,      // last successful overview response
      loading: false,
      failed: false,
      reqId: 0,        // guards against out-of-order responses
    };
  },
  computed: {
    total() { return this.data ? this.data.total_visits : 0; },
    dailyBars() {
      const daily = (this.data && this.data.daily) || [];
      const W = 720, H = 160, TOP_PAD = 6;
      const n = daily.length;
      if (!n) return { W, H, bars: [] };
      const max = daily.reduce((m, d) => Math.max(m, d.count || 0), 0);
      const gap = Math.min(4, (W / n) * 0.3);
      const barW = (W - gap * (n - 1)) / n;
      const bars = daily.map((d, i) => {
        const count = d.count || 0;
        // normalized height; zero stays zero, tiny nonzero values get a 2px floor
        const h = max > 0 ? Math.max((count / max) * (H - TOP_PAD), count > 0 ? 2 : 0) : 0;
        return {
          date: d.date,
          count,
          x: +(i * (barW + gap)).toFixed(2),
          y: +(H - h).toFixed(2),
          w: +barW.toFixed(2),
          h: +h.toFixed(2),
          label: `${d.date}：${count} 次`,
        };
      });
      return { W, H, bars };
    },
    rangeText() {
      const b = this.dailyBars.bars;
      return b.length ? `${b[0].date} ~ ${b[b.length - 1].date}` : '';
    },
    topSites() { return (this.data && this.data.top_sites) || []; },
    groups() { return (this.data && this.data.groups) || []; },
    groupTotal() { return this.groups.reduce((s, g) => s + (g.count || 0), 0); },
  },
  watch: {
    open: { immediate: true, handler(v) { if (v) this.fetch(); } },
    days() { if (this.open) this.fetch(); },
  },
  methods: {
    hostOf, firstLetter,
    letterStyle(name, url) {
      const h = hueOf(name || url);
      return { background: `linear-gradient(135deg, hsl(${h} 70% 55%), hsl(${(h + 40) % 360} 70% 45%))` };
    },
    groupName(g) { return g.name || '未分类'; },
    groupWidth(g) {
      return this.groupTotal > 0 ? Math.round((g.count / this.groupTotal) * 100) + '%' : '0%';
    },
    onLogoError(site) { site._logoFailed = true; },
    async fetch() {
      const seq = ++this.reqId;
      this.loading = true;
      try {
        const d = await api.statsOverview(this.days);
        if (seq !== this.reqId) return;
        this.data = d;
        this.failed = false;
      } catch (e) {
        if (seq !== this.reqId) return;
        this.failed = true;
        this.$emit('notify', e.message, 'error');
      } finally {
        if (seq === this.reqId) this.loading = false;
      }
    },
  },
  template: `
  <section v-if="open" class="stats-panel" aria-label="访问统计">
    <div class="stats-toolbar">
      <h2 class="stats-title">访问统计</h2>
      <div class="seg" role="group" aria-label="统计时间范围">
        <button v-for="d in dayOptions" :key="d" class="seg-btn"
                :class="{ on: days === d }" @click="days = d">{{ d }} 天</button>
      </div>
    </div>

    <div v-if="loading" class="stats-loading">加载中…</div>

    <div v-else-if="failed" class="stats-error">
      <p>统计数据加载失败，请稍后重试。</p>
      <button class="btn btn-sm" @click="fetch">重试</button>
    </div>

    <div v-else-if="data" class="stats-grid">
      <div class="stat-card stat-tile">
        <span class="stat-label">总访问（近 {{ days }} 天）</span>
        <span class="stat-value">{{ total }}</span>
      </div>

      <div class="stat-card stat-chart-card">
        <span class="stat-label">每日访问</span>
        <svg v-if="dailyBars.bars.length" class="stat-chart"
             :viewBox="'0 0 ' + dailyBars.W + ' ' + dailyBars.H">
          <rect v-for="b in dailyBars.bars" :key="b.date" class="stat-bar"
                :x="b.x" :y="b.y" :width="b.w" :height="b.h" rx="2"
                :aria-label="b.label">
            <title>{{ b.label }}</title>
          </rect>
        </svg>
        <div v-if="rangeText" class="stat-axis">
          <span>{{ rangeText }}</span><span>按 UTC 日期</span>
        </div>
      </div>

      <div class="stat-card">
        <span class="stat-label">Top 站点</span>
        <ol v-if="topSites.length" class="stat-list">
          <li v-for="(s, i) in topSites" :key="s.site_id">
            <a class="stat-row" :href="s.url" target="_blank" rel="noopener">
              <span class="stat-rank" :class="{ 'stat-rank-top': i < 3 }">{{ i + 1 }}</span>
              <img v-if="s.logo_url && !s._logoFailed" :src="s.logo_url" class="stat-logo" alt="" loading="lazy" @error="onLogoError(s)">
              <span v-else class="stat-logo stat-logo-fallback" :style="letterStyle(s.name, s.url)" aria-hidden="true">{{ firstLetter(s.name) }}</span>
              <span class="stat-row-main">
                <span class="stat-row-name">{{ s.name }}</span>
                <span class="stat-row-host">{{ hostOf(s.url) }}</span>
              </span>
              <span class="stat-row-visits">{{ s.visits }} 次</span>
            </a>
          </li>
        </ol>
        <p v-else class="stats-empty">窗口内暂无站点访问</p>
      </div>

      <div class="stat-card">
        <span class="stat-label">分组分布</span>
        <ul v-if="groups.length" class="stat-groups">
          <li v-for="(g, i) in groups" :key="i" class="stat-group">
            <span class="stat-group-name" :title="groupName(g)">{{ groupName(g) }}</span>
            <span class="stat-group-track"><span class="stat-group-fill" :style="{ width: groupWidth(g) }"></span></span>
            <span class="stat-group-count">{{ g.count }}</span>
          </li>
        </ul>
        <p v-else class="stats-empty">窗口内暂无分组访问</p>
      </div>
    </div>
  </section>`,
};
