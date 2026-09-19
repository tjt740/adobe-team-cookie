/* 在「设置」页注入「对外接口」卡片:填 X-API-Key(external_api_key)。
   与 local-pool-settings-patch.js 同款注入方式。 */
(function () {
  if (window.__externalApiKeyPatch) return;
  window.__externalApiKeyPatch = true;

  var CARD_ID = "okad-external-apikey";
  var TOKEN_KEY = "okad_token";

  function isSettingsPage() { return location.pathname.replace(/\/+$/, "") === "/settings"; }
  function token() { return localStorage.getItem(TOKEN_KEY) || ""; }
  function notify(type, m) { var a = window.$message; if (a && typeof a[type] === "function") a[type](m); else if (type === "error") alert(m); else console.log("[external-apikey]", m); }

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
      "#" + CARD_ID + " .ea-title{font-size:16px;font-weight:600;color:#333639;margin-bottom:18px}",
      "#" + CARD_ID + " .ea-row{display:grid;grid-template-columns:120px minmax(0,1fr);gap:12px 16px;align-items:start;margin-bottom:16px}",
      "#" + CARD_ID + " .ea-row>span{font-size:14px;color:#333639;line-height:34px;text-align:right}",
      "#" + CARD_ID + " .ea-input{height:34px;border:1px solid #dcdfe6;border-radius:3px;padding:0 11px;font:13px system-ui,-apple-system,'PingFang SC',sans-serif;color:#333639;outline:none;box-sizing:border-box;width:100%}",
      "#" + CARD_ID + " .ea-input:focus{border-color:#18a058;box-shadow:0 0 0 2px rgba(24,160,88,.12)}",
      "#" + CARD_ID + " .ea-help{grid-column:2;color:#909399;font-size:12px;line-height:1.5;margin-top:-8px}",
      "#" + CARD_ID + " .ea-actions{display:flex;align-items:center;gap:10px;margin-left:136px}",
      "#" + CARD_ID + " .ea-btn{height:34px;padding:0 16px;border-radius:3px;border:1px solid #18a058;background:#18a058;color:#fff;cursor:pointer;font-size:14px}",
      "#" + CARD_ID + " .ea-btn:disabled{opacity:.55;cursor:not-allowed}",
      "#" + CARD_ID + " .ea-muted{font-size:12px;color:#909399}",
      "@media(max-width:720px){#" + CARD_ID + " .ea-row{grid-template-columns:1fr}#" + CARD_ID + " .ea-row>span{text-align:left}#" + CARD_ID + " .ea-help{grid-column:1}#" + CARD_ID + " .ea-actions{margin-left:0}}",
    ].join("\n");
    document.head.appendChild(style);
  }

  function createCard() {
    installStyles();
    var card = document.createElement("section");
    card.id = CARD_ID;
    var title = document.createElement("div"); title.className = "ea-title"; title.textContent = "对外接口(外部子号 Cookie 刷新)";

    var row = document.createElement("div"); row.className = "ea-row";
    var lb = document.createElement("span"); lb.textContent = "X-API-Key";
    var keyInput = document.createElement("input"); keyInput.type = "password"; keyInput.className = "ea-input"; keyInput.placeholder = "与对接方约定的固定字符串"; keyInput.autocomplete = "off";
    row.appendChild(lb); row.appendChild(keyInput);
    var help = document.createElement("div"); help.className = "ea-help";
    help.textContent = "对接方调 POST /api/v1/adobe/cookie/refresh 时带的 X-API-Key,双方约定一个固定值;留空则对外接口拒绝所有请求。";
    row.appendChild(help);

    var actions = document.createElement("div"); actions.className = "ea-actions";
    var btn = document.createElement("button"); btn.type = "button"; btn.className = "ea-btn"; btn.textContent = "保存";
    var status = document.createElement("span"); status.className = "ea-muted";
    actions.appendChild(btn); actions.appendChild(status);

    btn.addEventListener("click", async function () {
      btn.disabled = true; status.textContent = "保存中…";
      try {
        await request("/api/settings", { method: "PUT", body: JSON.stringify({ external_api_key: keyInput.value.trim() }) });
        status.textContent = keyInput.value.trim() ? "已保存" : "已清空";
        notify("success", "对外接口 API Key 已保存");
      } catch (err) { status.textContent = ""; notify("error", "保存失败: " + err.message); }
      finally { btn.disabled = false; }
    });

    card.appendChild(title); card.appendChild(row); card.appendChild(actions);
    request("/api/settings").then(function (d) { keyInput.value = d.external_api_key || ""; }).catch(function () {});
    return card;
  }

  function findMount() {
    var app = document.getElementById("app"); if (!app) return null;
    var mine = document.getElementById("okad-local-pool-settings");
    if (mine) return mine; // 排在「自建号池」卡之后
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
    if (path !== lastPath) { lastPath = path; var old = document.getElementById(CARD_ID); if (old && !isSettingsPage()) old.remove(); }
    install();
  }
  new MutationObserver(tick).observe(document.documentElement, { childList: true, subtree: true });
  window.addEventListener("popstate", tick);
  window.setInterval(tick, 800);
  tick();
})();
