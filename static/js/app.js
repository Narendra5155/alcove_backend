/* Alcove shared frontend: API helper, WebSocket helper, Alpine stores. */
(function () {
  function getCookie(name) {
    const m = document.cookie.match("(^|;)\\s*" + name + "\\s*=\\s*([^;]+)");
    return m ? decodeURIComponent(m.pop()) : "";
  }

  /** fetch wrapper: JSON in/out, CSRF header, readable errors. */
  async function api(url, { method = "GET", body, form } = {}) {
    const headers = { "X-CSRFToken": getCookie("csrftoken"), Accept: "application/json" };
    let payload;
    if (form) payload = form;
    else if (body !== undefined) { headers["Content-Type"] = "application/json"; payload = JSON.stringify(body); }
    const res = await fetch(url, { method, headers, body: payload, credentials: "same-origin" });
    let data = null;
    if (res.status !== 204) { try { data = await res.json(); } catch (_) { data = null; } }
    if (!res.ok) {
      const err = new Error(firstError(data) || `Request failed (${res.status})`);
      err.status = res.status; err.data = data;
      throw err;
    }
    return data;
  }

  function firstError(data) {
    if (!data) return "";
    if (typeof data === "string") return data;
    if (data.detail) return Array.isArray(data.detail) ? data.detail[0] : data.detail;
    if (data.non_field_errors) return data.non_field_errors[0];
    const k = Object.keys(data)[0];
    if (!k) return "";
    const v = data[k];
    return Array.isArray(v) ? v[0] : typeof v === "string" ? v : "";
  }

  /** Reconnecting JSON WebSocket. */
  function socket(path, { onMessage, onOpen } = {}) {
    const proto = location.protocol === "https:" ? "wss" : "ws";
    let ws, retry = 0, closed = false, queue = [];
    function connect() {
      ws = new WebSocket(`${proto}://${location.host}${path}`);
      ws.onopen = () => { retry = 0; queue.splice(0).forEach((m) => ws.send(m)); onOpen && onOpen(); };
      ws.onmessage = (e) => { try { onMessage && onMessage(JSON.parse(e.data)); } catch (_) {} };
      ws.onclose = (e) => {
        if (closed) return;
        const delay = Math.min(15000, 1000 * 2 ** retry++);
        // The 15-minute access cookie may have expired: any authenticated HTTP request lets
        // the server middleware mint a fresh one from the refresh cookie before we reconnect.
        setTimeout(() => {
          fetch("/api/notifications/?limit=1", { credentials: "same-origin" }).catch(() => {}).finally(connect);
        }, delay);
      };
    }
    connect();
    return {
      send(obj) { const m = JSON.stringify(obj); ws.readyState === 1 ? ws.send(m) : queue.push(m); },
      close() { closed = true; ws.close(); },
    };
  }

  const inr = new Intl.NumberFormat("en-IN", { style: "currency", currency: "INR", maximumFractionDigits: 0 });
  function money(v) { return v == null ? "" : inr.format(Number(v)); }

  function timeAgo(iso) {
    const s = Math.max(1, (Date.now() - new Date(iso).getTime()) / 1000);
    if (s < 60) return "just now";
    if (s < 3600) return `${Math.floor(s / 60)} min ago`;
    if (s < 86400) return `${Math.floor(s / 3600)} h ago`;
    return new Date(iso).toLocaleDateString("en-IN", { day: "numeric", month: "short" });
  }

  window.Alcove = { api, socket, money, timeAgo, getCookie };

  document.addEventListener("alpine:init", () => {
    Alpine.store("toasts", {
      items: [],
      push(t) {
        const id = Math.random().toString(36).slice(2);
        this.items.push({ id, kind: "info", ...t });
        setTimeout(() => this.dismiss(id), t.timeout || 6000);
      },
      dismiss(id) { this.items = this.items.filter((t) => t.id !== id); },
    });

    Alpine.store("notifs", {
      items: [], unread: 0, loaded: false, ws: null,
      init() {
        if (!document.body.dataset.auth) return;
        this.ws = socket("/ws/notifications/", { onMessage: (m) => this.onMessage(m) });
      },
      onMessage(m) {
        if (m.type === "unread") this.unread = m.count;
        if (m.type === "notification") {
          this.items.unshift(m.notification);
          this.unread += 1;
          Alpine.store("toasts").push({ title: m.notification.title, body: m.notification.body, url: m.notification.url });
          window.dispatchEvent(new CustomEvent("alcove:notification", { detail: m.notification }));
        }
      },
      async load() {
        if (this.loaded) return;
        const d = await api("/api/notifications/?limit=15");
        this.items = d.results; this.unread = d.unread; this.loaded = true;
      },
      async markRead(n) {
        if (n.is_read) return;
        n.is_read = true; this.unread = Math.max(0, this.unread - 1);
        await api("/api/notifications/read/", { method: "POST", body: { ids: [n.id] } });
      },
      async markAll() {
        this.items.forEach((n) => (n.is_read = true)); this.unread = 0;
        await api("/api/notifications/read/", { method: "POST", body: { ids: "all" } });
      },
    });
  });

  window.logout = async function () {
    await api("/api/auth/logout/", { method: "POST" });
    location.href = "/";
  };
})();
