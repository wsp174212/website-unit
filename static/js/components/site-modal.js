// Add / edit site modal.
import { firstLetter } from '../utils.js';

export default {
  name: 'SiteModal',
  props: {
    open: Boolean,
    mode: { type: String, default: 'add' }, // 'add' | 'edit'
    site: { type: Object, default: null },
    groups: { type: Array, default: () => [] },
    saving: Boolean,
    error: String,
  },
  emits: ['close', 'submit'],
  data() {
    return {
      form: { url: '', name: '', description: '', group: '', tags: '', favorite: false, pinned: false, refetch_metadata: false },
    };
  },
  watch: {
    open(v) {
      if (!v) return;
      const s = this.site || {};
      this.form = {
        url: s.url || '',
        name: s.name || '',
        description: s.description || '',
        group: s.group || '',
        tags: (s.tags || []).join(', '),
        favorite: !!s.favorite,
        pinned: !!s.pinned,
        refetch_metadata: false,
      };
      this.$nextTick(() => this.$refs.url?.focus());
    },
  },
  methods: {
    submit() {
      if (!this.form.url.trim()) return;
      this.$emit('submit', {
        ...this.form,
        tags: this.form.tags.split(',').map(t => t.trim()).filter(Boolean),
      });
    },
  },
  template: `
  <div v-if="open" class="overlay" @click.self="$emit('close')">
    <div class="modal" role="dialog" aria-modal="true" aria-labelledby="sm-title">
      <h2 id="sm-title">{{ mode === 'add' ? '添加站点' : '编辑站点' }}</h2>
      <form @submit.prevent="submit">
        <label>
          <span>URL <i class="req">*</i></span>
          <input v-model.trim="form.url" ref="url" type="text" required
                 placeholder="https://example.com" :disabled="saving" autocomplete="off">
          <em class="hint">只需填 URL，名称和 logo 会自动抓取</em>
        </label>
        <label>
          <span>名称</span>
          <input v-model.trim="form.name" type="text" :disabled="saving" placeholder="留空则使用网页标题">
        </label>
        <div class="form-row">
          <label>
            <span>分组</span>
            <input v-model.trim="form.group" type="text" list="group-options" :disabled="saving" placeholder="如：工具 / 项目">
            <datalist id="group-options">
              <option v-for="g in groups" :key="g" :value="g"></option>
            </datalist>
          </label>
          <label>
            <span>标签</span>
            <input v-model.trim="form.tags" type="text" :disabled="saving" placeholder="逗号分隔，如：ai, coding">
          </label>
        </div>
        <label>
          <span>描述</span>
          <input v-model.trim="form.description" type="text" :disabled="saving" placeholder="一句话说明（可选）">
        </label>
        <div class="checkbox-row" v-if="mode === 'edit'">
          <label class="cb"><input v-model="form.favorite" type="checkbox" :disabled="saving"> 收藏</label>
          <label class="cb"><input v-model="form.pinned" type="checkbox" :disabled="saving"> 置顶</label>
          <label class="cb"><input v-model="form.refetch_metadata" type="checkbox" :disabled="saving"> 重新抓取名称与 logo</label>
        </div>
        <p v-if="error" class="form-error">{{ error }}</p>
        <div class="modal-actions">
          <button type="button" class="btn" @click="$emit('close')" :disabled="saving">取消</button>
          <button type="submit" class="btn btn-primary" :disabled="saving || !form.url.trim()">
            <template v-if="saving"><span class="spinner"></span> 抓取中…</template>
            <template v-else>{{ mode === 'add' ? '添加' : '保存' }}</template>
          </button>
        </div>
      </form>
    </div>
  </div>`,
};
