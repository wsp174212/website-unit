// Settings modal: theme, density, sort, maintenance.
export default {
  name: 'SettingsModal',
  props: {
    open: Boolean,
    theme: String,
    density: String,
    sort: String,
    dbInfo: { type: Object, default: null },
    busy: Boolean,
  },
  emits: ['close', 'set', 'gc-logos', 'check-health', 'refresh-all'],
  template: `
  <div v-if="open" class="overlay" @click.self="$emit('close')">
    <div class="modal" role="dialog" aria-modal="true" aria-labelledby="set-title">
      <h2 id="set-title">设置</h2>

      <div class="set-group">
        <span class="set-label">主题</span>
        <div class="seg">
          <button v-for="t in ['light','dark','system']" :key="t" class="seg-btn"
                  :class="{on: theme === t}" @click="$emit('set', {theme: t})">
            {{ t === 'light' ? '浅色' : t === 'dark' ? '深色' : '跟随系统' }}
          </button>
        </div>
      </div>

      <div class="set-group">
        <span class="set-label">密度</span>
        <div class="seg">
          <button v-for="d in ['comfortable','compact']" :key="d" class="seg-btn"
                  :class="{on: density === d}" @click="$emit('set', {density: d})">
            {{ d === 'comfortable' ? '舒适' : '紧凑' }}
          </button>
        </div>
      </div>

      <div class="set-group">
        <span class="set-label">默认排序</span>
        <div class="seg">
          <button v-for="s in [['custom','自定义'],['recent','最近访问'],['most','最常访问'],['added','最近添加'],['name','名称']]"
                  :key="s[0]" class="seg-btn" :class="{on: sort === s[0]}"
                  @click="$emit('set', {sort: s[0]})">{{ s[1] }}</button>
        </div>
      </div>

      <div class="set-group" v-if="dbInfo">
        <span class="set-label">数据库</span>
        <p class="set-info">
          {{ dbInfo.sites }} 个站点 · {{ dbInfo.archived }} 已归档 · {{ dbInfo.broken }} 失效 · {{ dbInfo.tags }} 标签 · schema v{{ dbInfo.schema_version }}
        </p>
      </div>

      <div class="set-group">
        <span class="set-label">维护</span>
        <div class="set-actions">
          <button class="btn btn-sm" :disabled="busy" @click="$emit('gc-logos')">清理无用 logo</button>
          <button class="btn btn-sm" :disabled="busy" @click="$emit('check-health')">检查全部站点</button>
          <button class="btn btn-sm" :disabled="busy" @click="$emit('refresh-all')">刷新全部元数据</button>
        </div>
      </div>

      <div class="modal-actions">
        <button type="button" class="btn btn-primary" @click="$emit('close')">完成</button>
      </div>
    </div>
  </div>`,
};
