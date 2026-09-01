// Import / export modal: bookmarks HTML, JSON, CSV; export; backup/restore.
import { api, downloadUrl } from '../api.js';

export default {
  name: 'ImportModal',
  props: { open: Boolean },
  emits: ['close', 'notify', 'done'],
  data() {
    return {
      tab: 'bookmarks', // bookmarks | json | csv
      file: null,
      mode: 'merge',
      preview: null,    // {total, added, duplicates, invalid, errors}
      working: false,
      result: null,
    };
  },
  watch: { open(v) { if (v) this.reset(); } },
  computed: {
    replaceDanger() { return this.mode === 'replace'; },
  },
  methods: {
    reset() { this.file = null; this.preview = null; this.result = null; this.working = false; this.mode = 'merge'; },
    onFile(e) { this.file = e.target.files[0] || null; this.preview = null; this.result = null; },
    async doPreview() {
      if (!this.file) return;
      this.working = true; this.preview = null; this.result = null;
      try {
        if (this.tab === 'bookmarks') this.preview = await this._postFile('/api/io/import/preview/bookmarks');
        else if (this.tab === 'json') this.preview = await this._postJson('/api/io/import/preview/json');
        else this.$emit('notify', 'CSV 暂无预览，可直接导入（建议先用合并模式）', 'info');
      } catch (e) { this.$emit('notify', e.message, 'error'); }
      finally { this.working = false; }
    },
    async _postFile(path) {
      const fd = new FormData(); fd.append('file', this.file);
      const r = await fetch(path, { method: 'POST', body: fd });
      return this._parse(r);
    },
    async _postJson(path) {
      const data = JSON.parse(await this.file.text());
      const r = await fetch(path, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(data) });
      return this._parse(r);
    },
    async _parse(r) {
      if (!r.ok) {
        const b = await r.json().catch(() => ({}));
        throw new Error(b?.error?.message || `预览失败 (${r.status})`);
      }
      return r.json();
    },
    async doImport() {
      if (!this.file) return;
      if (this.mode === 'replace' && !confirm('替换模式将清空当前所有站点数据（已自动备份）。确认继续？')) return;
      this.working = true; this.result = null;
      try {
        let res;
        if (this.tab === 'bookmarks') res = await api.importBookmarks(this.file, this.mode);
        else if (this.tab === 'csv') res = await api.importCsv(this.file, this.mode);
        else { const data = JSON.parse(await this.file.text()); res = await api.importJson(data, this.mode); }
        this.result = res;
        this.$emit('notify', `导入完成：新增 ${res.added} / 重复 ${res.duplicates} / 无效 ${res.invalid}`, 'success');
        this.$emit('done');
      } catch (e) { this.$emit('notify', e.message, 'error'); }
      finally { this.working = false; }
    },
    async doRestore(e) {
      const f = e.target.files[0];
      if (!f) return;
      if (!confirm('恢复将用备份覆盖当前数据（已自动备份当前数据）。确认继续？')) { e.target.value = ''; return; }
      this.working = true;
      try {
        const res = await api.restore(f);
        this.$emit('notify', res.message || '已恢复', 'success');
        this.$emit('done');
      } catch (err) { this.$emit('notify', err.message, 'error'); }
      finally { this.working = false; e.target.value = ''; }
    },
    expJson() { downloadUrl(api.exportJsonUrl(), 'siteunit-export.json'); },
    expCsv() { downloadUrl(api.exportCsvUrl(), 'siteunit-export.csv'); },
    backup() { downloadUrl(api.backupUrl(), 'siteunit-backup.zip'); },
  },
  template: `
  <div v-if="open" class="overlay" @click.self="$emit('close')">
    <div class="modal wide" role="dialog" aria-modal="true" aria-labelledby="io-title">
      <h2 id="io-title">导入 / 导出 / 备份</h2>

      <div class="seg seg-block">
        <button v-for="t in [['bookmarks','浏览器书签'],['json','JSON'],['csv','CSV']]" :key="t[0]"
                class="seg-btn" :class="{on: tab === t[0]}" @click="reset(); tab = t[0]">{{ t[1] }}</button>
      </div>

      <div class="io-area">
        <div class="io-file">
          <input type="file" @change="onFile" :accept="tab === 'bookmarks' ? 'text/html' : tab === 'json' ? 'application/json' : 'text/csv'" :disabled="working">
          <span v-if="file" class="io-fname">{{ file.name }}</span>
        </div>
        <div class="seg">
          <button class="seg-btn" :class="{on: mode === 'merge'}" @click="mode='merge'">合并</button>
          <button class="seg-btn" :class="{on: mode === 'replace'}" @click="mode='replace'">替换</button>
        </div>
        <div class="io-actions">
          <button class="btn btn-sm" :disabled="!file || working" @click="doPreview">预览</button>
          <button class="btn btn-sm btn-primary" :disabled="!file || working" @click="doImport">导入</button>
        </div>
      </div>

      <div v-if="preview" class="io-preview">
        发现 {{ preview.total }} · 新增 {{ preview.added }} · 重复 {{ preview.duplicates }} · 无效 {{ preview.invalid }}
      </div>
      <div v-if="result" class="io-preview ok">
        导入完成：新增 {{ result.added }} · 重复 {{ result.duplicates }} · 无效 {{ result.invalid }}
      </div>

      <hr class="io-divider">
      <div class="io-exports">
        <button class="btn btn-sm" @click="expJson">导出 JSON</button>
        <button class="btn btn-sm" @click="expCsv">导出 CSV</button>
        <button class="btn btn-sm" @click="backup">下载备份 (zip)</button>
        <label class="btn btn-sm">
          恢复备份
          <input type="file" accept="application/zip" hidden @change="doRestore" :disabled="working">
        </label>
      </div>

      <div class="modal-actions">
        <button type="button" class="btn" @click="$emit('close')" :disabled="working">关闭</button>
      </div>
    </div>
  </div>`,
};
