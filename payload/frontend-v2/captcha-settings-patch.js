/* 在「设置」页注入 Arkose 打码配置:captcha_provider + captcha_key。
   被邀请子号补全资料走 PUT /signin/v4/accounts,Adobe 开了 Arkose 必须打码。 */
(function () {
  if (window.__captchaSettingsPatch) return;
  window.__captchaSettingsPatch = true;

  var CARD_ID = "okad-captcha-settings";
  var TOKEN_KEY = "okad_token";

  function isSettingsPage() { return location.pathname.replace(/\/+$/, "") === "/settings"; }
  function token() { return localStorage.getItem(TOKEN_KEY) || ""; }
  function notify(type, m) { var a = window.$message; if (a && typeof a[type] === "function") a[type](m); else if (type === "error") alert(m); else console.log("[captcha-settings]", m); }

  async function request(path, options) {
    var headers = Object.assign({ Accept: "application/json", "Content-Type": "application/json" }, (options && options.headers) || {});
    var tk = token(); if (tk) headers.Authorization = "Bearer " + tk;
    var res = await fetch(path, Object.assign({}, options || {}, { headers: headers }));
    var text = await res.text();
    var data = text ? JSON.parse(text) : {};
    if (!res.ok) throw new Error(data.detail || data.message || "HTTP " + res.status);
    return data;
  }

  function installStyles() {
    if (document.getElementById(CARD_ID + "-style")) return;
    var style = document.createElement("style");
    style.id = CARD_ID + "-style";
    style.textContent = [
      "#" + CARD_ID + "{background:#fff;border:1px solid #efeff5;border-radius:3px;padding:20px 24px;margin-top:20px;max-width:860px;box-sizing:border-box}",
      "#" + CARD_ID + " .cs-title{font-size:16px;font-weight:600;color:#333639;margin-bottom:8px}",
      "#" + CARD_ID + " .cs-lead{font-size:12px;color:#909399;line-height:1.5;margin-bottom:16px}",
      "#" + CARD_ID + " .cs-row{display:grid;grid-template-columns:120px minmax(0,1fr);gap:12px 16px;align-items:start;margin-bottom:16px}",
      "#" + CARD_ID + " .cs-row>span{font-size:14px;color:#333639;line-height:34px;text-align:right}",
      "#" + CARD_ID + " .cs-input,#" + CARD_ID + " .cs-select{height:34px;border:1px solid #dcdfe6;border-radius:3px;padding:0 11px;font:13px system-ui,-apple-system,'PingFang SC',sans-serif;color:#333639;outline:none;box-sizing:border-box;width:100%;background:#fff}",
      "#" + CARD_ID + " .cs-input:focus,#" + CARD_ID + " .cs-select:focus{border-color:#18a058;box-shadow:0 0 0 2px rgba(24,160,88,.12)}",
      "#" + CARD_ID + " .cs-help{grid-column:2;color:#909399;font-size:12px;line-height:1.5;margin-top:-8px}",
      "#" + CARD_ID + " .cs-actions{display:flex;align-items:center;gap:10px;margin-left:136px}",
      "#" + CARD_ID + " .cs-btn{height:34px;padding:0 16px;border-radius:3px;border:1px solid #18a058;background:#18a058;color:#fff;cursor:pointer;font-size:14px}",
      "#" + CARD_ID + " .cs-btn:disabled{opacity:.55;cursor:not-allowed}",
      "#" + CARD_ID + " .cs-muted{font-size:12px;color:#909399}",
      "@media(max-width:720px){#" + CARD_ID + " .cs-row{grid-template-columns:1fr}#" + CARD_ID + " .cs-row>span{text-align:left}#" + CARD_ID + " .cs-help{grid-column:1}#" + CARD_ID + " .cs-actions{margin-left:0}}",
    ].join("\n");
    document.head.appendChild(style);
  }

  function createCard() {
    installStyles();
    var card = document.createElement("section");
    card.id = CARD_ID;

    var title = document.createElement("div");
    title.className = "cs-title";
    title.textContent = "Arkose 打码(补全账号)";
    var lead = document.createElement("div");
    lead.className = "cs-lead";
    lead.textContent = "被邀请子号首次登录要 PUT /signin/v4/accounts。Adobe 开了 Arkose 时必须同一场 gt2 解题:本机收 gt2,YesCaptcha 只分类图。不要用 FunCaptcha 整段 token(工人另开窗口会被拒)。";

    var row1 = document.createElement("div"); row1.className = "cs-row";
    var lb1 = document.createElement("span"); lb1.textContent = "打码平台";
    var sel = document.createElement("select"); sel.className = "cs-select";
    [["", "不使用"], ["yescaptcha", "yescaptcha(分类,推荐)"], ["2captcha", "2captcha"], ["capsolver", "capsolver"], ["ez", "ez-captcha"]].forEach(function (opt) {
      var o = document.createElement("option"); o.value = opt[0]; o.textContent = opt[1]; sel.appendChild(o);
    });
    row1.appendChild(lb1); row1.appendChild(sel);

    var row2 = document.createElement("div"); row2.className = "cs-row";
    var lb2 = document.createElement("span"); lb2.textContent = "API Key";
    var keyInput = document.createElement("input");
    keyInput.type = "password"; keyInput.className = "cs-input";
    keyInput.placeholder = "打码平台 clientKey"; keyInput.autocomplete = "off";
    row2.appendChild(lb2); row2.appendChild(keyInput);
    var help = document.createElement("div"); help.className = "cs-help";
    help.textContent = "推荐 yescaptcha:本机收同一场 gt2,平台只分类。也可在后端 .env 写 ADOBE_CAPTCHA_PROVIDER / ADOBE_CAPTCHA_KEY,环境变量优先。";
    row2.appendChild(help);

    var actions = document.createElement("div"); actions.className = "cs-actions";
    var btn = document.createElement("button"); btn.type = "button"; btn.className = "cs-btn"; btn.textContent = "保存";
    var status = document.createElement("span"); status.className = "cs-muted";
    actions.appendChild(btn); actions.appendChild(status);

    btn.addEventListener("click", async function () {
      btn.disabled = true; status.textContent = "保存中…";
      try {
        await request("/api/settings", {
          method: "PUT",
          body: JSON.stringify({
            captcha_provider: sel.value,
            captcha_key: keyInput.value.trim(),
          }),
        });
        status.textContent = sel.value ? "已保存" : "已清空";
        notify("success", "Arkose 打码配置已保存");
      } catch (err) {
        status.textContent = "";
        notify("error", "保存失败: " + err.message);
      } finally {
        btn.disabled = false;
      }
    });

    card.appendChild(title);
    card.appendChild(lead);
    card.appendChild(row1);
    card.appendChild(row2);
    card.appendChild(actions);
    request("/api/settings").then(function (d) {
      sel.value = d.captcha_provider || "";
      keyInput.value = d.captcha_key || "";
    }).catch(function () {});
    return card;
  }

  function findMount() {
    var app = document.getElementById("app"); if (!app) return null;
    var after = document.getElementById("okad-external-apikey") || document.getElementById("okad-local-pool-settings");
    if (after) return after;
    var cards = Array.prototype.slice.call(app.querySelectorAll(".n-card"));
    return cards[cards.length - 1] || app.querySelector("main") || app.firstElementChild || app;
  }

  function install() {
    if (!isSettingsPage()) return;
    if (document.getElementById(CARD_ID)) return;
    var mount = findMount(); if (!mount) return;
    mount.insertAdjacentElement("afterend", createCard());
  }

  var lastPath = "";
  function tick() {
    var path = location.pathname;
    if (path !== lastPath) {
      lastPath = path;
      var old = document.getElementById(CARD_ID);
      if (old && !isSettingsPage()) old.remove();
    }
    install();
  }
  new MutationObserver(tick).observe(document.documentElement, { childList: true, subtree: true });
  window.addEventListener("popstate", tick);
  window.setInterval(tick, 800);
  tick();
})();
