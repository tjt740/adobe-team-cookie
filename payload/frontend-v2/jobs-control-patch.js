(function () {
  if (window.__okadJobsControlPatch) return;
  window.__okadJobsControlPatch = true;

  var BUTTON_ID = "okad-job-cancel-button";
  var TOKEN_KEY = "okad_token";

  function isJobsPage() {
    return location.pathname.replace(/\/+$/, "") === "/jobs";
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
      console.log("[jobs-control]", message);
    }
  }

  async function request(path, options) {
    var headers = { Accept: "application/json", "Content-Type": "application/json" };
    var tk = token();
    if (tk) headers.Authorization = "Bearer " + tk;
    var res = await fetch("/api" + path, Object.assign({}, options || {}, { headers: headers }));
    var text = await res.text();
    var data = {};
    try {
      data = text ? JSON.parse(text) : {};
    } catch (_err) {
      data = { message: text };
    }
    if (!res.ok) throw new Error(data.detail || data.message || "HTTP " + res.status);
    return data;
  }

  function closestCard(el) {
    var node = el;
    while (node && node !== document.body) {
      if (node.classList && node.classList.contains("n-card")) return node;
      node = node.parentElement;
    }
    return null;
  }

  function findDetailCard() {
    var nodes = Array.from(document.querySelectorAll("div, section, article"));
    for (var i = 0; i < nodes.length; i += 1) {
      var text = (nodes[i].textContent || "").replace(/\s+/g, " ");
      if (text.indexOf("任务详情") >= 0 && /#\d+/.test(text)) {
        return closestCard(nodes[i]) || nodes[i];
      }
    }
    return null;
  }

  function detailInfo(card) {
    var text = (card.textContent || "").replace(/\s+/g, " ");
    var idMatch = text.match(/#(\d+)/);
    return {
      id: idMatch ? Number(idMatch[1]) : 0,
      running: text.indexOf("进行中") >= 0 || text.indexOf("running") >= 0,
    };
  }

  function makeButton(jobId) {
    var btn = document.createElement("button");
    btn.id = BUTTON_ID;
    btn.type = "button";
    btn.dataset.jobId = String(jobId);
    btn.textContent = "停止任务";
    btn.style.cssText = [
      "height:28px",
      "padding:0 12px",
      "border:1px solid #dc2626",
      "border-radius:3px",
      "background:#fff",
      "color:#dc2626",
      "font-size:13px",
      "line-height:26px",
      "cursor:pointer",
      "white-space:nowrap",
      "margin-left:8px",
    ].join(";");
    btn.addEventListener("click", async function () {
      var id = Number(btn.dataset.jobId || "0");
      if (!id) return;
      if (!window.confirm("确认停止任务 #" + id + "？\\n\\n停止后会保留当前任务日志。")) return;
      btn.disabled = true;
      btn.style.opacity = "0.65";
      btn.textContent = "停止中...";
      try {
        var data = await request("/adobe-accounts/jobs/" + id + "/cancel", { method: "POST" });
        notify(data.success === false ? "warning" : "success", data.message || "已请求停止任务");
        window.setTimeout(function () { location.reload(); }, 800);
      } catch (err) {
        notify("error", err && err.message ? err.message : "停止失败");
        btn.disabled = false;
        btn.style.opacity = "1";
        btn.textContent = "停止任务";
      }
    });
    return btn;
  }

  function install() {
    if (!isJobsPage()) {
      var old = document.getElementById(BUTTON_ID);
      if (old) old.remove();
      return;
    }
    var card = findDetailCard();
    if (!card) return;
    var info = detailInfo(card);
    var existing = document.getElementById(BUTTON_ID);
    if (!info.id || !info.running) {
      if (existing) existing.remove();
      return;
    }
    if (existing) {
      existing.dataset.jobId = String(info.id);
      return;
    }
    var anchors = Array.from(card.querySelectorAll("button"));
    var anchor = anchors.length ? anchors[0] : null;
    var btn = makeButton(info.id);
    if (anchor && anchor.parentElement) {
      anchor.parentElement.appendChild(btn);
    } else {
      card.insertBefore(btn, card.firstChild);
    }
  }

  new MutationObserver(install).observe(document.documentElement, { childList: true, subtree: true });
  window.setInterval(install, 1000);
  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", install);
  } else {
    install();
  }
})();
