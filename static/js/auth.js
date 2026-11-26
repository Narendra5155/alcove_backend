/* Auth flows: credentials -> emailed OTP -> JWT cookies. */
function otpBoxes() {
  const box = (i) => document.getElementById("otp" + i);
  return {
    digits: ["", "", "", "", "", ""],
    get code() { return this.digits.join(""); },
    reset() { this.digits = ["", "", "", "", "", ""]; this.$nextTick(() => box(0) && box(0).focus()); },
    input(i, e) {
      const v = e.target.value.replace(/\D/g, "");
      if (v.length > 1) return this.fill(v);
      this.digits[i] = v;
      if (v && i < 5) box(i + 1).focus();
      if (this.code.length === 6) this.$dispatch("otp-complete");
    },
    back(i, e) { if (!this.digits[i] && i > 0) { box(i - 1).focus(); e.preventDefault(); } },
    fill(text) {
      const v = (text || "").replace(/\D/g, "").slice(0, 6).split("");
      this.digits = [0, 1, 2, 3, 4, 5].map((i) => v[i] || "");
      box(Math.min(v.length, 5)).focus();
      if (this.code.length === 6) this.$dispatch("otp-complete");
    },
  };
}

function authFlow(mode, defaults = {}) {
  return {
    mode, step: "credentials", busy: false, error: "", info: "", errors: {},
    form: { full_name: "", email: "", password: "", role: defaults.role || "RENTER", new_password: "" },
    challenge: null, cooldown: 0, timer: null,

    startCooldown(s = 60) {
      this.cooldown = s; clearInterval(this.timer);
      this.timer = setInterval(() => { if (--this.cooldown <= 0) clearInterval(this.timer); }, 1000);
    },

    async submitCredentials() {
      this.busy = true; this.error = ""; this.errors = {};
      const urls = { login: "/api/auth/login/", register: "/api/auth/register/", reset: "/api/auth/password-reset/" };
      try {
        const d = await Alcove.api(urls[this.mode], { method: "POST", body: this.form });
        this.challenge = d.challenge_id;
        this.step = "otp";
        this.startCooldown();
        this.$nextTick(() => this.$dispatch("otp-reset"));
      } catch (e) {
        this.errors = (e.data && typeof e.data === "object") ? e.data : {};
        this.error = e.message;
      } finally { this.busy = false; }
    },

    async verify(code) {
      if (this.busy || code.length !== 6) return;
      this.busy = true; this.error = "";
      try {
        if (this.mode === "reset") {
          await Alcove.api("/api/auth/password-reset/confirm/", {
            method: "POST", body: { challenge_id: this.challenge, code, new_password: this.form.new_password },
          });
          this.step = "done";
          return;
        }
        const d = await Alcove.api("/api/auth/verify-otp/", { method: "POST", body: { challenge_id: this.challenge, code } });
        const next = new URLSearchParams(location.search).get("next");
        location.href = next && next.startsWith("/") && !next.startsWith("//") ? next : d.redirect;
      } catch (e) {
        this.error = e.message;
        if (/expired|start again/i.test(e.message)) { this.step = "credentials"; }
        else this.$dispatch("otp-reset");
      } finally { this.busy = false; }
    },

    async resend() {
      if (this.cooldown > 0) return;
      this.error = "";
      try {
        const d = await Alcove.api("/api/auth/resend-otp/", { method: "POST", body: { challenge_id: this.challenge } });
        this.info = d.detail; this.startCooldown();
      } catch (e) { this.error = e.message; }
    },
  };
}
