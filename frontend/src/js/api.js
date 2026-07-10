/* smokeping-easy — API client.
 *
 * Thin fetch wrapper: JSON in/out, same-origin cookies for the session, and a
 * global 401 interceptor that bounces the user back to the login page. Errors
 * are normalised into { code, detail, status } so callers can translate the
 * code via i18n (errors.<code>).
 */
(function () {
  "use strict";

  const LOGIN_PAGE = "/index.html";

  class ApiError extends Error {
    constructor(code, detail, status, body) {
      super(detail || code);
      this.code = code || "generic";
      this.detail = detail || "";
      this.status = status || 0;
      this.body = body || {};
    }
    /** Human, translated message for this error. */
    get message_i18n() {
      const key = "errors." + this.code;
      const t = window.I18n ? window.I18n.t(key) : this.code;
      // If i18n had no mapping it returns the key unchanged -> fall back.
      return t === key ? (window.I18n ? window.I18n.t("errors.generic") : this.code) : t;
    }
  }

  async function request(method, path, body, opts) {
    opts = opts || {};
    const headers = { "Accept": "application/json" };
    let payload;
    if (body !== undefined && body !== null) {
      headers["Content-Type"] = "application/json";
      payload = JSON.stringify(body);
    }
    let resp;
    try {
      resp = await fetch(path, {
        method,
        headers,
        body: payload,
        credentials: "same-origin",
        cache: "no-store"
      });
    } catch (netErr) {
      throw new ApiError("connection", "network error", 0);
    }

    // Global 401 handling: redirect to login (unless caller opts out).
    if (resp.status === 401 && !opts.noRedirect) {
      if (!window.location.pathname.endsWith("index.html")) {
        window.location.href = LOGIN_PAGE;
      }
    }

    let data = null;
    const text = await resp.text();
    if (text) {
      try { data = JSON.parse(text); } catch (e) { data = { raw: text }; }
    }

    if (!resp.ok) {
      const code = (data && data.error) || "generic";
      const detail = (data && data.detail) || "";
      throw new ApiError(code, detail, resp.status, data);
    }
    return data;
  }

  window.Api = {
    ApiError,
    get: (p, opts) => request("GET", p, null, opts),
    post: (p, b, opts) => request("POST", p, b, opts),
    put: (p, b, opts) => request("PUT", p, b, opts),
    del: (p, opts) => request("DELETE", p, null, opts),

    // --- Typed helpers ---------------------------------------------------
    status: () => request("GET", "/api/status", null, { noRedirect: true }),
    login: (password) =>
      request("POST", "/api/auth/login", { password }, { noRedirect: true }),
    logout: () => request("POST", "/api/auth/logout"),
    me: () => request("GET", "/api/auth/me", null, { noRedirect: true }),

    groups: () => request("GET", "/api/groups"),
    createGroup: (name) => request("POST", "/api/groups", { name }),
    renameGroup: (id, name) => request("PUT", "/api/groups/" + encodeURIComponent(id), { name }),
    deleteGroup: (id) => request("DELETE", "/api/groups/" + encodeURIComponent(id)),

    targets: () => request("GET", "/api/targets"),
    createTarget: (t) => request("POST", "/api/targets", t),
    updateTarget: (id, t) => request("PUT", "/api/targets/" + encodeURIComponent(id), t),
    deleteTarget: (id) => request("DELETE", "/api/targets/" + encodeURIComponent(id)),
    targetLatest: (id) => request("GET", "/api/targets/" + encodeURIComponent(id) + "/latest"),
    targetSeries: (id, range) =>
      request("GET", "/api/targets/" + encodeURIComponent(id) + "/series?range=" +
        encodeURIComponent(range || "3h")),
    targetMtr: (id, cycles) =>
      request("GET", "/api/targets/" + encodeURIComponent(id) + "/mtr?cycles=" +
        encodeURIComponent(cycles || 5)),

    settings: () => request("GET", "/api/settings"),
    saveAppSettings: (s) => request("PUT", "/api/settings/app", s),
    changePassword: (current_password, new_password) =>
      request("POST", "/api/auth/password", { current_password, new_password })
  };

  // Global toast store + helper, usable from any Alpine component.
  document.addEventListener("alpine:init", () => {
    Alpine.store("toasts", {
      items: [],
      _id: 0,
      push(message, type, timeout) {
        const id = ++this._id;
        this.items.push({ id, message, type: type || "ok" });
        const ms = timeout === undefined ? 4500 : timeout;
        if (ms) setTimeout(() => this.dismiss(id), ms);
      },
      dismiss(id) { this.items = this.items.filter((t) => t.id !== id); }
    });
  });
  window.toast = (message, type, timeout) => {
    if (window.Alpine && Alpine.store("toasts")) Alpine.store("toasts").push(message, type, timeout);
  };
})();
