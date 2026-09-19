/* adobe-login-async-patch.js
 * 把"母号登录"从同步长请求(点一下卡 30~130s、常 499 超时)改成异步后台任务:
 * 点击后立即弹出进度浮层,实时显示登录日志(等验证码/取组织/取产品…),
 * 完成后自动刷新列表。实现方式:在 XHR 层拦截 POST .../login,不真正发它,
 * 改调 .../login-async 起后台任务并轮询 .../jobs/{id}。后端不支持时自动回退到原同步请求。
 */
(function () {
  if (window.__adobeLoginAsyncPatch) return;
  window.__adobeLoginAsyncPatch = true;

  var XP = XMLHttpRequest.prototype;
  var origOpen = XP.open;
  var origSend = XP.send;
  var origSetHeader = XP.setRequestHeader;

  var LOGIN_RE = /\/adobe-accounts\/(\d+)\/login(?:$|\?)/;

  XP.open = function (method, url) {
    this.__la_method = method;
    this.__la_url = url;
    return origOpen.apply(this, arguments);
  };

  XP.setRequestHeader = function (k, v) {
    (this.__la_headers = this.__la_headers || {})[k] = v;
    return origSetHeader.apply(this, arguments);
  };

  XP.send = function () {
    try {
      var m = String(this.__la_method || "").toUpperCase();
      var u = String(this.__la_url || "");
      var mm = u.match(LOGIN_RE);
      if (m === "POST" && mm) {
        var asyncUrl = u.replace(/\/login(?=$|\?)/, "/login-async");
        startAsyncLogin(mm[1], asyncUrl, this, arguments);
        return; // 吞掉原同步请求
      }
    } catch (e) { /* 出错就走原逻辑 */ }
    return origSend.apply(this, arguments);
  };

  // ---------- 进度浮层 ----------
  function buildModal(id) {
    var overlay = document.createElement("div");
    overlay.className = "la-overlay";
    overlay.style.cssText =
      "position:fixed;inset:0;z-index:99999;background:rgba(0,0,0,.45);" +
      "display:flex;align-items:center;justify-content:center;" +
      "font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;";

    var card = document.createElement("div");
    card.style.cssText =
      "background:#fff;border-radius:10px;box-shadow:0 12px 40px rgba(0,0,0,.22);" +
      "width:520px;max-width:92vw;padding:20px 22px 18px;box-sizing:border-box;";

    var head = document.createElement("div");
    head.style.cssText = "display:flex;align-items:center;gap:10px;margin-bottom:12px;";
    var spin = document.createElement("div");
    spin.className = "la-spin";
    spin.style.cssText =
      "width:18px;height:18px;border-radius:50%;border:2.5px solid #e5e7eb;" +
      "border-top-color:#18a058;flex:0 0 auto;";
    var title = document.createElement("div");
    title.textContent = "母号登录中…";
    title.style.cssText = "font-size:16px;font-weight:600;color:#333639;flex:1;";
    var elapsed = document.createElement("div");
    elapsed.textContent = "0s";
    elapsed.style.cssText = "font-size:13px;color:#9aa0a6;font-variant-numeric:tabular-nums;";
    head.appendChild(spin); head.appendChild(title); head.appendChild(elapsed);

    var sub = document.createElement("div");
    sub.textContent = "#" + id + " · 正在后台登录,可等待完成(约 30~130 秒)";
    sub.style.cssText = "font-size:12.5px;color:#9aa0a6;margin-bottom:10px;";

    var logbox = document.createElement("div");
    logbox.style.cssText =
      "background:#f7f8fa;border:1px solid #eef0f2;border-radius:6px;padding:10px 12px;" +
      "font:12.5px/1.7 ui-monospace,SFMono-Regular,Menlo,Consolas,monospace;color:#555;" +
      "height:240px;overflow:auto;white-space:pre-wrap;word-break:break-all;";
    logbox.textContent = "启动任务…";

    var footer = document.createElement("div");
    footer.style.cssText =
      "display:flex;align-items:center;justify-content:space-between;margin-top:14px;gap:12px;";
    var statusLine = document.createElement("div");
    statusLine.style.cssText = "font-size:13px;color:#606266;flex:1;";
    var btn = document.createElement("button");
    btn.textContent = "刷新并关闭";
    btn.style.cssText =
      "display:none;border:none;border-radius:6px;padding:7px 18px;font-size:13px;cursor:pointer;" +
      "background:#18a058;color:#fff;font-weight:500;";
    btn.onmouseenter = function () { btn.style.background = "#36ad6a"; };
    btn.onmouseleave = function () { btn.style.background = statusLine.__err ? "#d03050" : "#18a058"; };
    btn.onclick = function () { location.reload(); };
    footer.appendChild(statusLine); footer.appendChild(btn);

    card.appendChild(head); card.appendChild(sub);
    card.appendChild(logbox); card.appendChild(footer);
    overlay.appendChild(card);
    document.body.appendChild(overlay);
    ensureSpinKeyframes();
    return { overlay: overlay, spin: spin, title: title, elapsed: elapsed,
             logbox: logbox, statusLine: statusLine, btn: btn };
  }

  function ensureSpinKeyframes() {
    if (document.getElementById("la-spin-kf")) return;
    var s = document.createElement("style");
    s.id = "la-spin-kf";
    s.textContent = "@keyframes la-rot{to{transform:rotate(360deg)}}" +
      ".la-spin{animation:la-rot .8s linear infinite;}";
    document.head.appendChild(s);
  }

  function appendLogs(ui, lines) {
    if (!lines || !lines.length) return;
    var atBottom = ui.logbox.scrollTop + ui.logbox.clientHeight >= ui.logbox.scrollHeight - 8;
    var cur = ui.logbox.__started ? ui.logbox.textContent : "";
    ui.logbox.__started = true;
    ui.logbox.textContent = (cur ? cur + "\n" : "") + lines.join("\n");
    if (atBottom) ui.logbox.scrollTop = ui.logbox.scrollHeight;
  }

  function startAsyncLogin(id, asyncUrl, origXhr, origArgs) {
    if (document.querySelector(".la-overlay")) return; // 已有一个在跑
    var ui = buildModal(id);
    var headers = Object.assign({ "Content-Type": "application/json" }, origXhr.__la_headers || {});
    var startTs = Date.now();
    var timer = setInterval(function () {
      ui.elapsed.textContent = Math.round((Date.now() - startTs) / 1000) + "s";
    }, 500);

    function fallbackSync(reason) {
      clearInterval(timer);
      if (ui.overlay.parentNode) ui.overlay.parentNode.removeChild(ui.overlay);
      try { origSend.apply(origXhr, origArgs); } catch (e) {}
    }

    function finish(ok, message, isError) {
      clearInterval(timer);
      ui.spin.style.animation = "none";
      ui.spin.style.border = "2.5px solid " + (ok ? "#18a058" : (isError ? "#d03050" : "#e6a23c"));
      ui.spin.style.borderTopColor = ui.spin.style.borderColor;
      ui.title.textContent = ok ? "登录成功" : (isError ? "登录失败" : "已完成(未取得组织)");
      ui.statusLine.textContent = message || "";
      ui.statusLine.style.color = ok ? "#18a058" : (isError ? "#d03050" : "#e6a23c");
      ui.statusLine.__err = isError;
      ui.btn.style.display = "inline-block";
      ui.btn.style.background = isError ? "#d03050" : "#18a058";
      if (ok) {
        ui.btn.textContent = "刷新中…";
        setTimeout(function () { location.reload(); }, 1100);
      }
    }

    fetch(asyncUrl, { method: "POST", headers: headers, credentials: "include" })
      .then(function (r) {
        if (r.status === 404 || r.status === 405) { fallbackSync("no-async"); return null; }
        return r.json().then(function (j) { return { ok: r.ok, body: j }; });
      })
      .then(function (res) {
        if (!res) return;
        if (!res.ok || !res.body || res.body.id == null) {
          var msg = (res.body && (res.body.detail || res.body.message)) || "启动任务失败";
          appendLogs(ui, [String(msg)]);
          finish(false, String(msg), true);
          return;
        }
        var jobId = res.body.id;
        var jobsUrl = asyncUrl.replace(/\/adobe-accounts\/\d+\/login-async.*$/, "/adobe-accounts/jobs/" + jobId);
        ui.logbox.textContent = "";
        ui.logbox.__started = false;
        appendLogs(ui, res.body.logs || []);
        var shown = res.body.log_total || (res.body.logs ? res.body.logs.length : 0);
        var failCount = 0;
        var poll = setInterval(function () {
          fetch(jobsUrl + "?log_offset=" + shown, { headers: headers, credentials: "include" })
            .then(function (r) { return r.json(); })
            .then(function (j) {
              failCount = 0;
              if (j.logs && j.logs.length) { appendLogs(ui, j.logs); shown = j.log_total || shown + j.logs.length; }
              if (j.status && j.status !== "running") {
                clearInterval(poll);
                var result = (j.extra && j.extra.result) || {};
                var ok = j.status === "done" && result.success === true;
                var isErr = j.status === "error" || (result.success === false && result.has_org === false && !result.message);
                var message = result.message || j.error ||
                  (ok ? "已获取管理权限" : "未取得可用组织/产品");
                if (result.product_name && ok) message += " · " + result.product_name;
                finish(ok, message, j.status === "error");
              }
            })
            .catch(function () {
              failCount++;
              if (failCount >= 8) { clearInterval(poll); finish(false, "轮询任务状态失败,请刷新后查看结果", true); }
            });
        }, 1200);
      })
      .catch(function () { fallbackSync("fetch-error"); });
  }
})();
