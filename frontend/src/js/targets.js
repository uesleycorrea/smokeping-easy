/* smokeping-easy — Targets tab: CRUD + live latency/loss. */
function targetsApp() {
  return {
    targets: [],
    groups: [],
    latest: {},          // id -> { avg_latency_ms, loss_pct } | null
    loading: true,
    _timer: null,

    // New-group mini modal (from within the target form)
    newGroupModal: false,
    newGroupName: "",
    savingGroup: false,

    showModal: false,
    editing: null,
    saving: false,
    formError: "",
    form: emptyForm(),

    // Graph modal
    graphModal: false,
    graphTarget: null,
    graphRange: "3h",
    graphLoading: false,
    _graphChart: null,

    // MTR modal
    mtrModal: false,
    mtrTarget: null,
    mtrLoading: false,
    mtrError: "",
    mtrData: null,

    async init() {
      await this.load();
      this._timer = setInterval(() => this.refreshLatest(), 30000);
    },

    // --- Graph modal -------------------------------------------------------
    async openGraph(t) {
      this.graphTarget = t;
      this.graphRange = "3h";
      this.graphModal = true;
      await this.$nextTick();
      await this.renderGraph();
    },
    closeGraph() {
      this.graphModal = false;
      if (this._graphChart) { this._graphChart.destroy(); this._graphChart = null; }
      this.graphTarget = null;
    },
    async setGraphRange(r) {
      this.graphRange = r;
      await this.renderGraph();
    },
    async renderGraph() {
      if (!this.graphTarget) return;
      this.graphLoading = true;
      try {
        const series = await Api.targetSeries(this.graphTarget.id, this.graphRange);
        const canvas = this.$refs.graphCanvas;
        this._graphChart = window.renderRttChart(canvas, series, this._graphChart, (k) => this.t(k));
      } catch (e) {
        window.toast(this.t("common.connection_error"), "error");
      } finally {
        this.graphLoading = false;
      }
    },

    // --- MTR modal ---------------------------------------------------------
    async openMtr(t) {
      this.mtrTarget = t;
      this.mtrModal = true;
      this.mtrData = null;
      await this.runMtr();
    },
    closeMtr() {
      this.mtrModal = false;
      this.mtrTarget = null;
      this.mtrData = null;
      this.mtrError = "";
    },
    async runMtr() {
      if (!this.mtrTarget) return;
      this.mtrLoading = true;
      this.mtrError = "";
      try {
        this.mtrData = await Api.targetMtr(this.mtrTarget.id, 5);
      } catch (e) {
        this.mtrError = e instanceof Api.ApiError ? this.t("mtr.failed") : this.t("common.connection_error");
      } finally {
        this.mtrLoading = false;
      }
    },
    mtrFmt(v) {
      return (v === null || v === undefined) ? "—" : Number(v).toFixed(1);
    },

    t(k, p) { return this.$store.i18n.t(k, p); },

    async load() {
      this.loading = true;
      try {
        const data = await Api.targets();
        this.targets = data.targets || [];
        try { this.groups = (await Api.groups()).groups || []; } catch (e) {}
        await this.refreshLatest();
      } catch (e) {
        window.toast(this.t("common.connection_error"), "error");
      } finally {
        this.loading = false;
      }
    },

    async loadGroups() {
      try { this.groups = (await Api.groups()).groups || []; } catch (e) {}
    },

    async refreshLatest() {
      await Promise.all(
        this.targets.map(async (t) => {
          try {
            const r = await Api.targetLatest(t.id);
            this.latest[t.id] = r.data;
          } catch (e) { /* keep previous */ }
        })
      );
    },

    groupedTargets() {
      const groups = {};
      const order = [];
      for (const t of this.targets) {
        const label = t.group || "Default";
        const slug = label.toLowerCase();
        if (!groups[slug]) { groups[slug] = { slug, label, items: [] }; order.push(slug); }
        groups[slug].items.push(t);
      }
      return order.map((slug) => {
        const g = groups[slug];
        const rows = [{ kind: "group", label: g.label }];
        for (const t of g.items) rows.push({ kind: "target", target: t });
        return { slug, label: g.label, rows };
      });
    },

    _fmt(n, digits) {
      if (n === null || n === undefined) return "—";
      return Number(n).toFixed(digits === undefined ? 1 : digits);
    },

    latencyCell(t) {
      const d = this.latest[t.id];
      if (d === undefined) return '<span class="muted">…</span>';
      if (!d || d.avg_latency_ms === null || d.avg_latency_ms === undefined)
        return '<span class="muted">' + escapeHtml(this.t("targets.no_data")) + "</span>";
      const val = this._fmt(d.avg_latency_ms, 1) + " " + this.t("unit.ms");
      const over = t.latency_threshold_ms != null && d.avg_latency_ms > t.latency_threshold_ms;
      return '<span class="badge ' + (over ? "danger" : "ok") + '">' + escapeHtml(val) + "</span>";
    },

    lossCell(t) {
      const d = this.latest[t.id];
      if (d === undefined) return '<span class="muted">…</span>';
      if (!d || d.loss_pct === null || d.loss_pct === undefined)
        return '<span class="muted">' + escapeHtml(this.t("targets.no_data")) + "</span>";
      const val = this._fmt(d.loss_pct, 1) + " " + this.t("unit.pct");
      const over = t.loss_threshold_pct != null && d.loss_pct > t.loss_threshold_pct;
      return '<span class="badge ' + (over ? "danger" : (d.loss_pct > 0 ? "warn" : "ok")) + '">' + escapeHtml(val) + "</span>";
    },

    _defaultGroupId() {
      return this.groups.length ? this.groups[0].id : "";
    },

    openCreate() {
      this.editing = null;
      this.form = emptyForm();
      this.form.group_id = this._defaultGroupId();
      this.formError = "";
      this.showModal = true;
      this.loadGroups();  // background refresh so the select is up to date
    },

    openEdit(t) {
      this.editing = t;
      this.loadGroups();
      this.form = {
        host: t.host,
        label: t.label,
        group_id: t.group_id || this._defaultGroupId(),
        alert_cooldown_minutes: t.alert_cooldown_minutes,
        latency_threshold_ms: t.latency_threshold_ms == null ? "" : t.latency_threshold_ms,
        loss_threshold_pct: t.loss_threshold_pct == null ? "" : t.loss_threshold_pct
      };
      this.formError = "";
      this.showModal = true;
    },

    closeModal() { this.showModal = false; },

    // New-group mini modal (opened from the target form's "+")
    openNewGroup() { this.newGroupName = ""; this.newGroupModal = true; },
    closeNewGroup() { this.newGroupModal = false; },
    async createGroup() {
      const name = (this.newGroupName || "").trim();
      if (!name) return;
      this.savingGroup = true;
      try {
        const g = (await Api.createGroup(name)).group;
        await this.loadGroups();
        this.form.group_id = g.id;   // auto-select the new group
        this.newGroupModal = false;
      } catch (e) {
        window.toast(e instanceof Api.ApiError ? e.message_i18n : this.t("errors.generic"), "error");
      } finally {
        this.savingGroup = false;
      }
    },

    _payload() {
      const f = this.form;
      const numOrNull = (v) => (v === "" || v === null || v === undefined ? null : Number(v));
      return {
        host: (f.host || "").trim(),
        label: (f.label || "").trim() || (f.host || "").trim(),
        group_id: f.group_id || "",
        alert_cooldown_minutes: Number(f.alert_cooldown_minutes) || 30,
        latency_threshold_ms: numOrNull(f.latency_threshold_ms),
        loss_threshold_pct: numOrNull(f.loss_threshold_pct)
      };
    },

    async save() {
      this.formError = "";
      const payload = this._payload();
      if (!payload.host) { this.formError = this.t("errors.host_required"); return; }
      this.saving = true;
      try {
        const res = this.editing
          ? await Api.updateTarget(this.editing.id, payload)
          : await Api.createTarget(payload);
        window.toast(this.t(this.editing ? "targets.updated" : "targets.created"), "ok");
        if (res && res.reloaded === false) window.toast(this.t("targets.reload_warning"), "warn");
        this.showModal = false;
        await this.load();
      } catch (e) {
        // Map backend error code -> translated message; fall back gracefully.
        this.formError = e instanceof Api.ApiError ? e.message_i18n : this.t("errors.generic");
      } finally {
        this.saving = false;
      }
    },

    async remove(t) {
      if (!window.confirm(this.t("targets.confirm_delete", { label: t.label }))) return;
      try {
        await Api.deleteTarget(t.id);
        window.toast(this.t("targets.deleted"), "ok");
        await this.load();
      } catch (e) {
        window.toast(e instanceof Api.ApiError ? e.message_i18n : this.t("errors.generic"), "error");
      }
    }
  };
}

function emptyForm() {
  return {
    host: "",
    label: "",
    group_id: "",
    alert_cooldown_minutes: 30,
    latency_threshold_ms: "",
    loss_threshold_pct: ""
  };
}

function escapeHtml(s) {
  return String(s).replace(/[&<>"']/g, (c) =>
    ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c])
  );
}

/* Shared Chart.js renderer for latency + loss series (used by Targets and
 * AI Analysis). Destroys any previous chart on the same canvas and returns the
 * new instance. `tfn` is a translate function (key -> string). */
window.renderRttChart = function (canvas, series, prev, tfn) {
  if (prev) { prev.destroy(); }
  if (!canvas || typeof Chart === "undefined") return null;
  const pts = (series.points || []).filter((p) => p.latency_ms !== null);
  const labels = pts.map((p) => {
    const d = new Date(p.t * 1000);
    return String(d.getHours()).padStart(2, "0") + ":" + String(d.getMinutes()).padStart(2, "0");
  });
  const latency = pts.map((p) => p.latency_ms);
  const loss = pts.map((p) => p.loss_pct);
  const css = getComputedStyle(document.documentElement);
  const brand = (css.getPropertyValue("--brand") || "#2563eb").trim();
  const danger = (css.getPropertyValue("--danger") || "#dc2b3d").trim();
  const ms = tfn("unit.ms");
  return new Chart(canvas.getContext("2d"), {
    type: "line",
    data: {
      labels,
      datasets: [
        { label: tfn("targets.latency") + " (" + ms + ")", data: latency,
          borderColor: brand, backgroundColor: brand, tension: 0.25, pointRadius: 0, borderWidth: 2, yAxisID: "y" },
        { label: tfn("targets.loss") + " (%)", data: loss,
          borderColor: danger, backgroundColor: danger, tension: 0.25, pointRadius: 0, borderWidth: 2, yAxisID: "y1" }
      ]
    },
    options: {
      responsive: true, maintainAspectRatio: false, animation: false,
      interaction: { mode: "index", intersect: false },
      scales: {
        y: { position: "left", title: { display: true, text: ms }, beginAtZero: true },
        y1: { position: "right", title: { display: true, text: "%" }, beginAtZero: true, max: 100, grid: { drawOnChartArea: false } }
      },
      plugins: { legend: { labels: { boxWidth: 12 } } }
    }
  });
};
