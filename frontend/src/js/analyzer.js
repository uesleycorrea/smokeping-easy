/* smokeping-easy — AI Analysis tab.
 * Provider / API key / model are configured in Settings; this tab just runs an
 * analysis on a target and shows the chart + AI response. */
function analyzerApp() {
  return {
    loading: true,
    targets: [],
    settings: null,
    analyzing: false,
    result: "",
    _chart: null,
    form: { target_id: "", range: "3h" },

    t(k, p) { return this.$store.i18n.t(k, p); },

    async init() {
      this.loading = true;
      try {
        this.targets = (await Api.targets()).targets || [];
        if (this.targets.length) this.form.target_id = this.targets[0].id;
        this.settings = await Api.settings();
      } catch (e) {
        window.toast(this.t("common.connection_error"), "error");
      } finally {
        this.loading = false;
      }
    },

    get aiConfigured() {
      return this.settings && this.settings.ai && this.settings.ai.api_key_set && this.settings.ai.model;
    },

    async analyze() {
      if (!this.form.target_id) return;
      if (!this.aiConfigured) { window.toast(this.t("errors.ai_not_configured"), "error"); return; }
      this.analyzing = true;
      this.result = "";
      try {
        await this.renderChart();
        const res = await Api.post("/api/analyze", {
          target_id: this.form.target_id,
          range: this.form.range
        });
        this.result = res.analysis || "";
      } catch (e) {
        window.toast(e instanceof Api.ApiError ? e.message_i18n : this.t("errors.generic"), "error");
      } finally {
        this.analyzing = false;
      }
    },

    async renderChart() {
      try {
        const series = await Api.targetSeries(this.form.target_id, this.form.range);
        this._chart = window.renderRttChart(this.$refs.chart, series, this._chart, (k) => this.t(k));
      } catch (e) { /* ignore chart errors */ }
    }
  };
}
