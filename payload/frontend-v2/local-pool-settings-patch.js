(function () {
  if (window.__localPoolSettingsPatch) return;
  window.__localPoolSettingsPatch = true;

  var CARD_ID = "okad-local-pool-settings";
  var TOKEN_KEY = "okad_token";

  function isSettingsPage() {
    return location.pathname.replace(/\/+$/, "") === "/settings";
  }

  function token() {
    return localStorage.getItem(TOKEN_KEY) || "";
  }

  function notify(type, message) {
    var api = window.$message;
    if (api && typeof api[type] === "function") {
      api[type](message);
    } else if (type === "error") {
      alert(message);
    } else {
      console.log("[local-pool-settings]", message);
    }
  }

  async function request(path, options) {
    var headers = Object.assign(
      { Accept: "application/json", "Content-Type": "application/json" },
      (options && options.headers) || {}
    );
    var tk = token();
    if (tk) headers.Authorization = "Bearer " + tk;
    var res = await fetch(path, Object.assign({}, options || {}, { headers: headers }));
    var text = await res.text();
    var data = text ? JSON.parse(text) : {};
    if (!res.ok) {
      throw new Error(data.detail || data.message || "HTTP " + res.status);
    }
    return data;
  }

  function field(label, input) {
    var wrap = document.createElement("label");
    wrap.className = "lp-field";
    var span = document.createElement("span");
    span.textContent = label;
    wrap.appendChild(span);
    wrap.appendChild(input);
    return wrap;
  }

  function input(type, placeholder) {
    var el = document.createElement("input");
    el.type = type || "text";
    el.placeholder = placeholder || "";
    el.autocomplete = "off";
    el.className = "lp-input";
    return el;
  }

  function findMount() {
    // Wait for the actual settings view; never append cards beside the app shell.
    var content = document.querySelector("#app .n-layout-content.content");
    if (!content) return null;
    var base = Array.prototype.find.call(content.querySelectorAll(".n-card"), function (card) {
      var title = card.querySelector(".n-card-header__main");
      return title && title.textContent.trim() === "修改管理员密码";
    });
    if (!base) return null;
    return base;
  }

  function installStyles() {
    if (document.getElementById("okad-local-pool-settings-style")) return;
    var style = document.createElement("style");
    style.id = "okad-local-pool-settings-style";
    style.textContent = [
      "#" + CARD_ID + "{background:#fff;border:1px solid #efeff5;border-radius:3px;padding:20px 24px;margin-top:20px;max-width:860px;box-sizing:border-box}",
      "#" + CARD_ID + " .lp-title{font-size:16px;font-weight:600;color:#333639;margin-bottom:18px}",
      "#" + CARD_ID + " .lp-row{display:grid;grid-template-columns:120px minmax(0,1fr);gap:12px 16px;align-items:start;margin-bottom:16px}",
      "#" + CARD_ID + " .lp-field{display:contents}",
      "#" + CARD_ID + " .lp-field span{font-size:14px;color:#333639;line-height:34px;text-align:right}",
      "#" + CARD_ID + " .lp-input{height:34px;border:1px solid #dcdfe6;border-radius:3px;padding:0 11px;font:13px system-ui,-apple-system,BlinkMacSystemFont,'Segoe UI','PingFang SC',sans-serif;color:#333639;outline:none;box-sizing:border-box;width:100%}",
      "#" + CARD_ID + " .lp-input:focus{border-color:#2080f0;box-shadow:0 0 0 2px rgba(32,128,240,.12)}",
      "#" + CARD_ID + " .lp-help{grid-column:2;color:#909399;font-size:12px;line-height:1.5;margin-top:-8px}",
      "#" + CARD_ID + " .lp-actions{display:flex;align-items:center;gap:10px;margin-left:136px}",
      "#" + CARD_ID + " .lp-btn{height:34px;padding:0 16px;border-radius:3px;border:1px solid #2080f0;background:#2080f0;color:#fff;cursor:pointer;font-size:14px}",
      "#" + CARD_ID + " .lp-btn:disabled{opacity:.55;cursor:not-allowed}",
      "#" + CARD_ID + " .lp-muted{font-size:12px;color:#909399}",
      "@media(max-width:720px){#" + CARD_ID + " .lp-row{grid-template-columns:1fr}#" + CARD_ID + " .lp-field span{text-align:left}#" + CARD_ID + " .lp-help{grid-column:1}#" + CARD_ID + " .lp-actions{margin-left:0}}",
    ].join("\n");
    document.head.appendChild(style);
  }

  async function hydrate(baseInput, keyInput) {
    try {
      var data = await request("/api/settings");
      baseInput.value = data.pool_api_base_url || "";
      keyInput.value = data.pool_api_key || "";
    } catch (err) {
      notify("error", "加载自建号池配置失败: " + err.message);
    }
  }

  function createCard() {
    installStyles();
    var card = document.createElement("section");
    card.id = CARD_ID;

    var title = document.createElement("div");
    title.className = "lp-title";
    title.textContent = "自建号池";

    var row1 = document.createElement("div");
    row1.className = "lp-row";
    var baseInput = input("text", "https://your-pool.example.com");
    row1.appendChild(field("Base URL", baseInput));
    var help1 = document.createElement("div");
    help1.className = "lp-help";
    help1.textContent = "填写自建号池服务地址,不需要以 / 结尾。";
    row1.appendChild(help1);

    var row2 = document.createElement("div");
    row2.className = "lp-row";
    var keyInput = input("password", "Bearer Key / API Key");
    row2.appendChild(field("Key", keyInput));
    var help2 = document.createElement("div");
    help2.className = "lp-help";
    help2.textContent = "后续批量新增和批量删除自建号池时使用。";
    row2.appendChild(help2);

    var actions = document.createElement("div");
    actions.className = "lp-actions";
    var btn = document.createElement("button");
    btn.type = "button";
    btn.className = "lp-btn";
    btn.textContent = "保存自建号池";
    var status = document.createElement("span");
    status.className = "lp-muted";
    actions.appendChild(btn);
    actions.appendChild(status);

    btn.addEventListener("click", async function () {
      btn.disabled = true;
      status.textContent = "保存中...";
      try {
        await request("/api/settings", {
          method: "PUT",
          body: JSON.stringify({
            pool_api_base_url: baseInput.value.trim(),
            pool_api_key: keyInput.value.trim(),
          }),
        });
        status.textContent = "已保存";
        notify("success", "自建号池配置已保存");
      } catch (err) {
        status.textContent = "";
        notify("error", "保存失败: " + err.message);
      } finally {
        btn.disabled = false;
      }
    });

    card.appendChild(title);
    card.appendChild(row1);
    card.appendChild(row2);
    card.appendChild(actions);
    hydrate(baseInput, keyInput);
    return card;
  }

  function install() {
    if (!isSettingsPage()) return;
    if (document.getElementById(CARD_ID)) return;
    var mount = findMount();
    if (!mount) return;
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

  new MutationObserver(tick).observe(document.documentElement, {
    childList: true,
    subtree: true,
  });
  window.addEventListener("popstate", tick);
  window.setInterval(tick, 800);
  tick();
})();
