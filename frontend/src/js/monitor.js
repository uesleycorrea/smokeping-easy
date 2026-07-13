/* smokeping-easy — Monitor (NOC) tab.
 * Big status tiles for a wall/TV display, with drag-to-reorder, hide/show and
 * a fullscreen mode. Auto-refreshes while the tab is active. */
function monitorApp() {
  return {
    loading: true,
    tiles: [],          // all targets with their latest sample
    order: [],          // saved display order (target ids)
    hidden: [],         // target ids excluded from the monitor
    fullscreen: false,
    dragId: null,
    showHidden: false,
    _timer: null,

    t(k, p) { return this.$store.i18n.t(k, p); },

    // Started/stopped by the section's x-effect on the active tab, so we keep
    // a single refresh interval and never accumulate them.
    onTab(tab) {
      if (tab === "monitor") this.start();
      else this.stop();
    },
    start() {
      if (this._timer) return;
      this.load();
      this._timer = setInterval(() => this.load(), 15000);
    },
    stop() {
      if (this._timer) { clearInterval(this._timer); this._timer = null; }
    },

    async load() {
      try {
        const m = await Api.get("/api/monitor");
        this.tiles = m.targets || [];
        this.order = m.order || [];
        this.hidden = m.hidden || [];
      } catch (e) { /* keep previous */ } finally {
        this.loading = false;
      }
    },

    get visibleTiles() {
      const hidden = new Set(this.hidden);
      const byId = {};
      this.tiles.forEach((t) => { byId[t.id] = t; });
      const out = [];
      const placed = new Set();
      this.order.forEach((id) => {
        if (byId[id] && !hidden.has(id)) { out.push(byId[id]); placed.add(id); }
      });
      this.tiles.forEach((t) => {
        if (!placed.has(t.id) && !hidden.has(t.id)) out.push(t);
      });
      return out;
    },
    get hiddenTiles() {
      const hidden = new Set(this.hidden);
      return this.tiles.filter((t) => hidden.has(t.id));
    },

    status(t) {
      const d = t.latest;
      if (!d || (d.avg_latency_ms == null && d.loss_pct == null)) return "nodata";
      const loss = d.loss_pct, lat = d.avg_latency_ms;
      const lossOver = t.loss_threshold_pct != null && loss != null && loss > t.loss_threshold_pct;
      const latOver = t.latency_threshold_ms != null && lat != null && lat > t.latency_threshold_ms;
      if (lossOver || latOver || (loss != null && loss >= 50)) return "down";
      if (loss != null && loss > 0) return "warn";
      return "ok";
    },
    fmt(n, d) { return (n == null) ? "—" : Number(n).toFixed(d == null ? 1 : d); },

    // --- Organize ----------------------------------------------------------
    async hide(t) {
      if (!this.hidden.includes(t.id)) this.hidden.push(t.id);
      await this._save({ hidden: this.hidden });
    },
    async unhide(t) {
      this.hidden = this.hidden.filter((id) => id !== t.id);
      await this._save({ hidden: this.hidden });
    },
    async _save(patch) {
      try { await Api.put("/api/settings/monitor", patch); } catch (e) {}
    },

    onDragStart(id, ev) {
      this.dragId = id;
      if (ev && ev.dataTransfer) ev.dataTransfer.effectAllowed = "move";
    },
    onDrop(targetId) {
      const from = this.dragId;
      this.dragId = null;
      if (!from || from === targetId) return;
      const ids = this.visibleTiles.map((t) => t.id);
      const i = ids.indexOf(from), j = ids.indexOf(targetId);
      if (i < 0 || j < 0) return;
      ids.splice(j, 0, ids.splice(i, 1)[0]);
      this.order = ids;
      this._save({ order: ids });
    },

    // --- Fullscreen --------------------------------------------------------
    toggleFullscreen() {
      const el = this.$refs.monitorRoot;
      if (!document.fullscreenElement) {
        (el.requestFullscreen ? el.requestFullscreen() : Promise.reject())
          .then(() => { this.fullscreen = true; })
          .catch(() => { this.fullscreen = true; });
      } else {
        if (document.exitFullscreen) document.exitFullscreen();
        this.fullscreen = false;
      }
    }
  };
}
