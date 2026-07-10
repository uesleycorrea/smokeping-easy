/* smokeping-easy — Settings tab: the single configuration hub.
 * Password, language/timezone, Telegram, AI provider, and background jobs. */
function settingsApp() {
  return {
    loading: true,
    savingPw: false,
    savingApp: false,
    savingTelegram: false,
    savingAi: false,
    testing: false,
    sendingReport: false,
    loadingModels: false,

    settings: null,
    status: null,
    models: [],

    // Groups management
    groups: [],
    newGroupName: "",
    creatingGroup: false,
    editingGroupId: null,
    editingGroupName: "",

    pw: { current_password: "", new_password: "", confirm: "" },
    app: { timezone: "" },
    tg: { bot_token: "", chat_id: "", daily_report_enabled: false, daily_report_hour: 7, daily_report_minute: 0 },
    ai: { provider: "claude", api_key: "", model: "", analysis_prompt: "" },

    t(k, p) { return this.$store.i18n.t(k, p); },

    async init() {
      this.loading = true;
      try {
        await this.reload();
        await this.loadStatus();
      } catch (e) {
        window.toast(this.t("common.connection_error"), "error");
      } finally {
        this.loading = false;
      }
    },

    async reload() {
      const s = await Api.settings();
      this.settings = s;
      this.app.timezone = (s.app && s.app.timezone) || "";
      const tg = s.telegram || {};
      this.tg.daily_report_enabled = !!tg.daily_report_enabled;
      this.tg.daily_report_hour = tg.daily_report_hour ?? 7;
      this.tg.daily_report_minute = tg.daily_report_minute ?? 0;
      this.tg.bot_token = ""; this.tg.chat_id = "";
      const ai = s.ai || {};
      this.ai.provider = ai.provider || "claude";
      this.ai.model = ai.model || "";
      this.ai.analysis_prompt = ai.analysis_prompt || "";
      this.ai.api_key = "";
    },

    async loadStatus() {
      try { this.status = await Api.get("/api/alerts/status"); } catch (e) {}
      try { this.groups = (await Api.groups()).groups || []; } catch (e) {}
    },

    // --- Groups ------------------------------------------------------------
    async addGroup() {
      const name = (this.newGroupName || "").trim();
      if (!name) return;
      this.creatingGroup = true;
      try {
        await Api.createGroup(name);
        this.newGroupName = "";
        await this.loadStatus();
      } catch (e) {
        window.toast(e instanceof Api.ApiError ? e.message_i18n : this.t("errors.generic"), "error");
      } finally { this.creatingGroup = false; }
    },
    startRename(g) { this.editingGroupId = g.id; this.editingGroupName = g.name; },
    cancelRename() { this.editingGroupId = null; this.editingGroupName = ""; },
    async saveRename(g) {
      const name = (this.editingGroupName || "").trim();
      if (!name || name === g.name) { this.cancelRename(); return; }
      try {
        await Api.renameGroup(g.id, name);
        this.cancelRename();
        await this.loadStatus();
      } catch (e) {
        window.toast(e instanceof Api.ApiError ? e.message_i18n : this.t("errors.generic"), "error");
      }
    },
    async deleteGroup(g) {
      if (g.is_default) { window.toast(this.t("errors.group_is_default"), "error"); return; }
      if (g.target_count > 0) { window.toast(this.t("errors.group_in_use"), "error"); return; }
      if (!window.confirm(this.t("groups.confirm_delete", { name: g.name }))) return;
      try {
        await Api.deleteGroup(g.id);
        await this.loadStatus();
      } catch (e) {
        window.toast(e instanceof Api.ApiError ? e.message_i18n : this.t("errors.generic"), "error");
      }
    },

    get botConfigured() { return this.settings && this.settings.telegram && this.settings.telegram.bot_token_set; },
    get chatConfigured() { return this.settings && this.settings.telegram && this.settings.telegram.chat_id_set; },
    get telegramReady() { return this.botConfigured && this.chatConfigured; },
    get apiKeySet() { return this.settings && this.settings.ai && this.settings.ai.api_key_set; },

    fmtTime(iso) {
      if (!iso) return this.t("settings.never");
      try { return new Date(iso).toLocaleString(this.$store.i18n.lang); } catch (e) { return iso; }
    },

    // --- Password ----------------------------------------------------------
    async changePassword() {
      if (this.pw.new_password.length < 8) { window.toast(this.t("settings.password_too_short"), "error"); return; }
      if (this.pw.new_password !== this.pw.confirm) { window.toast(this.t("settings.password_mismatch"), "error"); return; }
      this.savingPw = true;
      try {
        await Api.changePassword(this.pw.current_password, this.pw.new_password);
        window.toast(this.t("settings.password_changed"), "ok");
        setTimeout(() => { window.location.href = "/index.html"; }, 1200);
      } catch (e) {
        window.toast(e instanceof Api.ApiError ? e.message_i18n : this.t("errors.generic"), "error");
      } finally { this.savingPw = false; }
    },

    // --- App (language / timezone) ----------------------------------------
    async saveApp() {
      this.savingApp = true;
      try {
        await Api.saveAppSettings({ timezone: this.app.timezone, language: this.$store.i18n.lang });
        window.toast(this.t("settings.app_saved"), "ok");
        await this.loadStatus();
      } catch (e) {
        window.toast(e instanceof Api.ApiError ? e.message_i18n : this.t("errors.generic"), "error");
      } finally { this.savingApp = false; }
    },

    // --- Telegram ----------------------------------------------------------
    async saveTelegram() {
      this.savingTelegram = true;
      try {
        const payload = {
          daily_report_enabled: this.tg.daily_report_enabled,
          daily_report_hour: Number(this.tg.daily_report_hour),
          daily_report_minute: Number(this.tg.daily_report_minute)
        };
        if (this.tg.bot_token) payload.bot_token = this.tg.bot_token;
        if (this.tg.chat_id) payload.chat_id = this.tg.chat_id;
        await Api.put("/api/settings/telegram", payload);
        window.toast(this.t("common.saved"), "ok");
        await this.reload();
        await this.loadStatus();
      } catch (e) {
        window.toast(e instanceof Api.ApiError ? e.message_i18n : this.t("errors.generic"), "error");
      } finally { this.savingTelegram = false; }
    },

    async testTelegram() {
      this.testing = true;
      try {
        await Api.post("/api/alerts/test");
        window.toast(this.t("alerts.test_ok"), "ok");
      } catch (e) {
        window.toast(e instanceof Api.ApiError ? e.message_i18n : this.t("alerts.test_fail"), "error");
      } finally { this.testing = false; }
    },

    async sendReportNow() {
      this.sendingReport = true;
      try {
        await Api.post("/api/reports/daily/run");
        window.toast(this.t("alerts.report_sent"), "ok");
        await this.loadStatus();
      } catch (e) {
        window.toast(e instanceof Api.ApiError ? e.message_i18n : this.t("errors.generic"), "error");
      } finally { this.sendingReport = false; }
    },

    // --- AI ----------------------------------------------------------------
    onProviderChange() { this.models = []; this.ai.model = ""; },

    async loadModels() {
      this.loadingModels = true;
      this.models = [];
      try {
        const qs = "provider=" + encodeURIComponent(this.ai.provider) +
          (this.ai.api_key ? "&api_key=" + encodeURIComponent(this.ai.api_key) : "");
        const res = await Api.get("/api/models?" + qs);
        this.models = res.models || [];
        if (this.models.length && !this.models.find((m) => m.id === this.ai.model)) {
          this.ai.model = this.models[0].id;
        }
        if (!this.models.length) window.toast(this.t("analyzer.no_models"), "warn");
      } catch (e) {
        window.toast(e instanceof Api.ApiError ? e.message_i18n : this.t("analyzer.no_models"), "error");
      } finally { this.loadingModels = false; }
    },

    async saveAi() {
      this.savingAi = true;
      try {
        const payload = {
          provider: this.ai.provider,
          model: this.ai.model,
          analysis_prompt: this.ai.analysis_prompt
        };
        if (this.ai.api_key) payload.api_key = this.ai.api_key;
        await Api.put("/api/settings/ai", payload);
        window.toast(this.t("common.saved"), "ok");
        await this.reload();
      } catch (e) {
        window.toast(e instanceof Api.ApiError ? e.message_i18n : this.t("errors.generic"), "error");
      } finally { this.savingAi = false; }
    }
  };
}
