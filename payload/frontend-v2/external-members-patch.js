/* 外部子号管理 —— 点侧边栏菜单在「右侧内容区」内嵌显示(按实际测量左侧菜单宽度/顶栏高度
   定位,只覆盖内容区,绝不遮挡左侧菜单与顶栏);点其它菜单自动收起。菜单项排第一、设置排第二。
   接口:/api/external/*(JWT,取 localStorage.okad_token)。 */
(function () {
  "use strict";
  var TK = "okad_token";
  var token = localStorage.getItem(TK) || "";
  var NAV_ID = "extm-nav", FAB_ID = "extm-fab";
  var st = { rows: [], sel: new Set(), statusF: "", subF: "", q: "", busy: false, open: false, posBound: false };

  var CSS = [
    // 嵌入右侧内容区:按实际布局测量定位(left=菜单右缘, top=顶栏下缘),只盖内容区、不动左侧菜单/顶栏
    '#extm-embed{position:fixed;right:0;bottom:0;overflow:auto;background:#f5f7fa;color:#333639;z-index:1000;padding:20px 24px 40px;display:none;font:14px/1.6 system-ui,-apple-system,"PingFang SC","Microsoft YaHei",sans-serif}',
    '#extm-embed.on{display:block}',
    '#extm-embed *{box-sizing:border-box}',
    // 页头
    '.extm-hd{display:flex;align-items:center;gap:12px;margin-bottom:16px}',
    '.extm-hd h2{font-size:18px;margin:0;font-weight:600}',
    '.extm-hd .cnt{font-size:13px;color:#909399}.extm-hd .cnt b{color:#18a058;font-variant-numeric:tabular-nums}',
    // 卡片
    '.extm-card{background:#fff;border-radius:6px;box-shadow:0 1px 2px rgba(0,0,0,.04);margin-bottom:16px;border:1px solid #efeff5}',
    '.extm-card .hd{padding:12px 18px;font-size:14px;font-weight:500;border-bottom:1px solid #f2f3f5;display:flex;align-items:center;gap:8px}',
    '.extm-card .hd .tip{font-size:12px;color:#c0c4cc;font-weight:400}',
    '.extm-card .bd{padding:16px 18px}',
    '.extm-ta{width:100%;min-height:96px;border:1px solid #e0e0e6;border-radius:4px;padding:10px 12px;font:12.5px/1.7 ui-monospace,Menlo,Consolas,monospace;color:#333639;outline:none;resize:vertical;background:#fff;transition:.15s}',
    '.extm-ta:focus{border-color:#18a058;box-shadow:0 0 0 2px rgba(24,160,88,.16)}',
    '.extm-row{display:flex;align-items:center;gap:10px;flex-wrap:wrap;margin-top:12px}',
    '.extm-in{height:34px;border:1px solid #e0e0e6;border-radius:4px;padding:0 11px;color:#333639;font-size:13px;outline:none;font-family:inherit;background:#fff;transition:.15s}',
    '.extm-in:focus{border-color:#18a058;box-shadow:0 0 0 2px rgba(24,160,88,.16)}',
    'select.extm-in{cursor:pointer;height:32px}',
    '.extm-btn{font:13px system-ui;border-radius:4px;padding:0 15px;height:34px;border:1px solid #18a058;background:#18a058;color:#fff;cursor:pointer;transition:.12s;white-space:nowrap;display:inline-flex;align-items:center;gap:5px}',
    '.extm-btn:hover:not(:disabled){background:#36ad6a;border-color:#36ad6a}.extm-btn:active{background:#0c7a43}',
    '.extm-btn:disabled{opacity:.5;cursor:not-allowed}',
    '.extm-btn.o{background:#fff;color:#18a058}.extm-btn.o:hover:not(:disabled){background:#eef8f2}',
    '.extm-btn.dft{background:#fff;color:#606266;border-color:#e0e0e6}.extm-btn.dft:hover:not(:disabled){color:#18a058;border-color:#18a058}',
    '.extm-btn.del{background:#fff;color:#d03050;border-color:#f0b3bf}.extm-btn.del:hover:not(:disabled){background:#fef0f2;border-color:#d03050}',
    '.extm-btn.sm{height:28px;padding:0 10px;font-size:12px}',
    '.extm-tools{display:flex;align-items:center;gap:10px;flex-wrap:wrap;padding:12px 16px;border-bottom:1px solid #efeff5;background:#fcfcfd}',
    '.extm-tools .sp{flex:1}',
    '.extm-tools .selc{font-size:13px;color:#909399}.extm-tools .selc b{color:#18a058}',
    '.extm-tw{overflow-x:auto}',
    '.extm-t{border-collapse:collapse;width:100%;font-size:13px;min-width:820px}',
    '.extm-t th{text-align:left;padding:11px 16px;font-size:13px;font-weight:500;color:#909399;background:#fafafc;border-bottom:1px solid #efeff5;white-space:nowrap}',
    '.extm-t td{padding:9px 16px;border-bottom:1px solid #f2f3f5;color:#333639;vertical-align:middle}',
    '.extm-t td:last-child{white-space:nowrap}',
    '.extm-t tbody tr:hover td{background:#f5f7fa}',
    '.extm-t .mono{font-family:ui-monospace,Menlo,Consolas,monospace;font-size:12.5px}',
    '.extm-t .cr{font-variant-numeric:tabular-nums;font-size:12.5px;color:#606266}',
    '.extm-t .cr b{color:#18a058}',
    '.extm-t input[type=checkbox]{width:15px;height:15px;cursor:pointer;accent-color:#18a058}',
    '.extm-pill{display:inline-block;font-size:12px;padding:1px 9px;border-radius:11px;line-height:1.7;white-space:nowrap}',
    '.extm-pill.ok{background:#e8f7f0;color:#18a058}.extm-pill.bad{background:#fce9ec;color:#d03050}.extm-pill.warn{background:#fdf3e6;color:#f0a020}.extm-pill.mut{background:#f0f2f5;color:#909399}',
    '.extm-cap{display:inline-block;font-size:10.5px;padding:1px 6px;border-radius:3px;margin-left:6px;font-family:ui-monospace,Menlo,monospace}',
    '.extm-cap.ok{background:#e8f7f0;color:#18a058}.extm-cap.no{background:#f0f2f5;color:#c0c4cc}',
    '.extm-empty{text-align:center;color:#c0c4cc;padding:48px 0;font-size:13px}',
    '.extm-msg{font-size:12.5px;min-height:18px}.extm-msg.ok{color:#18a058}.extm-msg.err{color:#d03050}.extm-msg.mut{color:#909399}',
    '.extm-fab{position:fixed;right:22px;bottom:74px;z-index:1999;display:inline-flex;align-items:center;gap:7px;padding:10px 16px;border-radius:22px;background:#18a058;color:#fff;font:600 13px system-ui;cursor:pointer;box-shadow:0 6px 16px rgba(24,160,88,.4)}',
  ].join("");

  function injectStyle() { if (document.getElementById("extm-style")) return; var s = document.createElement("style"); s.id = "extm-style"; s.textContent = CSS; (document.head || document.documentElement).appendChild(s); }

  function api(path, opts) {
    opts = opts || {};
    if (!token) token = localStorage.getItem(TK) || "";
    var ctrl = new AbortController();
    var to = setTimeout(function () { ctrl.abort(); }, opts.timeout || 30000);
    return fetch("/api/external" + path, {
      method: opts.method || "GET", signal: ctrl.signal,
      headers: { "Content-Type": "application/json", "Authorization": "Bearer " + token },
      body: opts.body ? JSON.stringify(opts.body) : undefined,
    }).then(function (r) {
      return r.text().then(function (t) {
        var d; try { d = t ? JSON.parse(t) : {}; } catch (e) { d = { raw: t }; }
        if (r.status === 401) throw new Error("未登录,请重新登录后台");
        if (!r.ok) throw new Error((d && (d.detail || d.message)) || ("HTTP " + r.status));
        return d;
      });
    }).catch(function (e) {
      if (e.name === "AbortError") throw new Error("请求超时(" + Math.round((opts.timeout || 30000) / 1000) + "s)");
      throw e;
    }).finally(function () { clearTimeout(to); });
  }

  function esc(s) { return String(s == null ? "" : s).replace(/[&<>"]/g, function (c) { return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]; }); }
  function el(id) { return document.getElementById(id); }
  function toast(type, m) { var a = window.$message; if (a && typeof a[type] === "function") a[type](m); else if (type === "error") console.error("[extm]", m); }
  function opMsg(t, c) { var e = el("extm-op"); if (e) { e.className = "extm-msg" + (c ? " " + c : ""); e.textContent = t || ""; } }
  function fmtTime(s) { if (!s) return "—"; var d = new Date(s); if (isNaN(d)) return "—"; function p(n){return (n<10?"0":"")+n;} return d.getFullYear() + "-" + p(d.getMonth()+1) + "-" + p(d.getDate()) + " " + p(d.getHours()) + ":" + p(d.getMinutes()); }

  var STATUS_MAP = {
    ok: ["ok", "正常"], never: ["mut", "未登录"], login_failed: ["bad", "登录失败"],
    account_disabled: ["bad", "已停用"], rate_limited: ["warn", "频繁登录限流"], internal: ["bad", "内部错误"],
  };
  function statusPill(s) { var m = STATUS_MAP[s] || ["mut", s || "—"]; return '<span class="extm-pill ' + m[0] + '">' + esc(m[1]) + "</span>"; }
  function subPill(row) {
    if (row.login_status === "never" || row.credits_total == null) return '<span class="extm-pill mut">—</span>';
    return row.subscription_ok ? '<span class="extm-pill ok">订阅正常</span>' : '<span class="extm-pill bad">掉订阅</span>';
  }
  function creditCell(row) {
    var a = row.credits_available == null ? "—" : Math.round(row.credits_available);
    var t = row.credits_total == null ? "—" : Math.round(row.credits_total);
    return '<span class="cr"><b>' + a + "</b> / " + t + "</span>";
  }

  // ---------- 页面主体(route 与 overlay 共用) ----------
  function buildBody(host) {
    host.innerHTML =
      '<div class="extm-hd"><h2>外部子号管理</h2><span class="cnt">共 <b id="extm-total">0</b> 个</span></div>' +
      '<div class="extm-card"><div class="hd">批量导入 <span class="tip">每行一个,格式:邮箱----密码----ClientID----RefreshToken[----Adobe密码](兼容 | 分隔)</span></div>' +
        '<div class="bd">' +
          '<textarea id="extm-import" class="extm-ta" placeholder="user@example.com----邮箱密码----ClientID(UUID)----M.RefreshToken\n带 Adobe 密码则再加一段:…----M.RefreshToken----AdobePwd\n不带则首登后自动存我们设的默认密码"></textarea>' +
          '<div class="extm-row">' +
            '<select id="extm-dup" class="extm-in"><option value="skip">重复邮箱:跳过</option><option value="overwrite">重复邮箱:覆盖</option></select>' +
            '<button class="extm-btn" id="extm-do-import">批量导入</button>' +
            '<span class="sp" style="flex:1"></span><span id="extm-op" class="extm-msg mut"></span>' +
          '</div>' +
        '</div>' +
      '</div>' +
      '<div class="extm-card">' +
        '<div class="extm-tools">' +
          '<select id="extm-f-status" class="extm-in"><option value="">全部状态</option><option value="ok">正常</option><option value="never">未登录</option><option value="login_failed">登录失败</option><option value="account_disabled">已停用</option><option value="rate_limited">频繁登录限流</option><option value="internal">内部错误</option></select>' +
          '<select id="extm-f-sub" class="extm-in"><option value="">全部订阅</option><option value="true">订阅正常</option><option value="false">掉订阅</option></select>' +
          '<input id="extm-f-kw" class="extm-in" placeholder="搜索邮箱…" style="width:180px">' +
          '<button class="extm-btn dft sm" id="extm-refresh">刷新</button>' +
          '<span class="sp"></span>' +
          '<span class="selc">已选 <b id="extm-selc">0</b></span>' +
          '<button class="extm-btn o sm" id="extm-batch-login">批量登录</button>' +
          '<button class="extm-btn o sm" id="extm-export">导出 Cookie</button>' +
          '<button class="extm-btn del sm" id="extm-batch-del">删除</button>' +
        '</div>' +
        '<div class="extm-tw"><table class="extm-t"><thead><tr>' +
          '<th style="width:38px"><input type="checkbox" id="extm-ckall"></th>' +
          '<th>邮箱</th><th style="width:130px">积分(可用/总)</th><th style="width:130px">登录状态</th><th style="width:96px">订阅</th><th style="width:150px">最后登录</th><th style="width:150px">操作</th>' +
        '</tr></thead><tbody id="extm-tbody"><tr><td colspan="7" class="extm-empty">加载中…</td></tr></tbody></table></div>' +
      '</div>';

    el("extm-do-import").onclick = doImport;
    el("extm-refresh").onclick = load;
    el("extm-batch-login").onclick = batchLogin;
    el("extm-export").onclick = exportCookies;
    el("extm-batch-del").onclick = batchDelete;
    el("extm-f-status").onchange = function () { st.statusF = this.value; load(); };
    el("extm-f-sub").onchange = function () { st.subF = this.value; load(); };
    var kwT; el("extm-f-kw").oninput = function () { st.q = this.value.trim(); clearTimeout(kwT); kwT = setTimeout(load, 300); };
    el("extm-ckall").onchange = function () {
      var on = this.checked; st.sel.clear();
      if (on) st.rows.forEach(function (r) { st.sel.add(r.id); });
      Array.prototype.forEach.call(document.querySelectorAll(".extm-rowck"), function (c) { c.checked = on; });
      updSel();
    };
    load();
  }

  function qs() {
    var a = [];
    if (st.statusF) a.push("login_status=" + encodeURIComponent(st.statusF));
    if (st.subF !== "") a.push("subscription_ok=" + st.subF);
    if (st.q) a.push("keyword=" + encodeURIComponent(st.q));
    return a;
  }

  function load() {
    var body = el("extm-tbody"); if (!body) return;
    body.innerHTML = '<tr><td colspan="7" class="extm-empty">加载中…</td></tr>';
    var q = qs().concat(["size=1000"]).join("&");
    api("/members?" + q).then(function (d) {
      st.rows = d.items || []; st.sel.clear();
      var tot = el("extm-total"); if (tot) tot.textContent = (d.total != null ? d.total : st.rows.length);
      renderRows(); updSel();
      var ck = el("extm-ckall"); if (ck) ck.checked = false;
    }).catch(function (e) {
      body.innerHTML = '<tr><td colspan="7" class="extm-empty" style="color:#d03050">' + esc(e.message) + "</td></tr>";
    });
  }

  function renderRows() {
    var body = el("extm-tbody"); if (!body) return;
    if (!st.rows.length) { body.innerHTML = '<tr><td colspan="7" class="extm-empty">暂无外部子号,先在上方批量导入</td></tr>'; return; }
    body.innerHTML = st.rows.map(function (r) {
      var cap = r.has_cookie ? '<span class="extm-cap ok">有Cookie</span>' : '<span class="extm-cap no">无Cookie</span>';
      cap += r.has_adobe_password ? '<span class="extm-cap ok">有密码</span>' : '<span class="extm-cap no">无密码</span>';
      return '<tr>' +
        '<td><input type="checkbox" class="extm-rowck" data-id="' + r.id + '"></td>' +
        '<td><span class="mono">' + esc(r.email) + "</span>" + cap + "</td>" +
        "<td>" + creditCell(r) + "</td>" +
        "<td>" + statusPill(r.login_status) + "</td>" +
        "<td>" + subPill(r) + "</td>" +
        '<td class="cr">' + esc(fmtTime(r.last_login_at)) + "</td>" +
        '<td><button class="extm-btn o sm" data-login="' + r.id + '">重登</button> ' +
            '<button class="extm-btn del sm" data-del="' + r.id + '">删除</button></td>' +
        "</tr>";
    }).join("");
    Array.prototype.forEach.call(body.querySelectorAll(".extm-rowck"), function (c) {
      c.onchange = function () { var id = parseInt(c.getAttribute("data-id"), 10); if (c.checked) st.sel.add(id); else st.sel.delete(id); updSel(); };
    });
    Array.prototype.forEach.call(body.querySelectorAll("[data-login]"), function (b) {
      b.onclick = function () { if (!st.busy) reloginOne(parseInt(b.getAttribute("data-login"), 10), b); };
    });
    Array.prototype.forEach.call(body.querySelectorAll("[data-del]"), function (b) {
      b.onclick = function () { if (!st.busy) doDelete([parseInt(b.getAttribute("data-del"), 10)]); };
    });
  }

  function updSel() { var e = el("extm-selc"); if (e) e.textContent = st.sel.size; }
  // st.sel 是 Set:Set 没有 length(只有 size),Array.prototype.slice.call 会当成
  // 0 长度、恒返回 [],勾了也等于没勾。必须用 Array.from。
  function selIds() { return Array.from(st.sel); }

  function doImport() {
    var ta = el("extm-import"); var content = (ta && ta.value || "").trim();
    if (!content) { opMsg("请粘贴要导入的子号", "err"); return; }
    opMsg("导入中…", "mut");
    api("/members/import", { method: "POST", body: { content: content, on_duplicate: el("extm-dup").value } }).then(function (r) {
      var msg = "导入完成:新增 " + r.created + " · 更新 " + r.updated + " · 跳过 " + r.skipped + " · 失败 " + r.failed;
      if (r.job_id) msg += " · 已开批量登录任务 #" + r.job_id + "(去「任务列表」看进度/日志)";
      opMsg(msg, r.failed ? "err" : "ok");
      if (r.job_id) toast("success", "已开始批量登录任务 #" + r.job_id + ",可在「任务列表」看日志");
      if (ta) ta.value = ""; load();
    }).catch(function (e) { opMsg(e.message, "err"); });
  }

  function reloginOne(id, btn) {
    if (btn) { btn.disabled = true; btn.textContent = "登录中…"; }
    st.busy = true;
    api("/members/" + id + "/login", { method: "POST", timeout: 290000 }).then(function (r) {
      toast(r.ok ? "success" : "error", r.ok ? "登录成功" : ((r.code || "失败") + " " + (r.message || "")));
    }).catch(function (e) { toast("error", e.message); }).finally(function () { st.busy = false; load(); });
  }

  function batchLogin() {
    var ids = selIds(); if (!ids.length) { toast("warning", "请先勾选账号"); return; }
    api("/members/batch-login", { method: "POST", body: { ids: ids } }).then(function () {
      toast("success", "已提交批量登录任务(" + ids.length + " 个),去「任务」页看进度");
    }).catch(function (e) { toast("error", e.message); });
  }

  function exportCookies() {
    api("/members/export" + (qs().length ? "?" + qs().join("&") : "")).then(function (data) {
      var blob = new Blob([JSON.stringify(data, null, 2)], { type: "application/json" });
      var url = URL.createObjectURL(blob);
      var a = document.createElement("a"); a.href = url; a.download = "external-cookies.json"; document.body.appendChild(a); a.click(); a.remove();
      setTimeout(function () { URL.revokeObjectURL(url); }, 1000);
      toast("success", "已导出 " + (data.length || 0) + " 条 Cookie");
    }).catch(function (e) { toast("error", e.message); });
  }

  function batchDelete() {
    var ids = selIds(); if (!ids.length) { toast("warning", "请先勾选账号"); return; }
    if (!confirm("确认删除选中的 " + ids.length + " 个外部子号?不可恢复。")) return;
    doDelete(ids);
  }
  function doDelete(ids) {
    api("/members/batch-delete", { method: "DELETE", body: { ids: ids } }).then(function (r) {
      toast("success", (r && r.message) || "已删除"); load();
    }).catch(function (e) { toast("error", e.message); });
  }

  // ---------- 嵌入右侧内容区(按实际布局测量定位,只盖内容区) ----------
  var HOST_ID = "extm-embed";
  function layoutRect() {
    var sider = document.querySelector(".n-layout-sider");
    var header = document.querySelector(".n-layout-header") || document.querySelector("header");
    var left = sider ? Math.max(0, Math.round(sider.getBoundingClientRect().right)) : 0;
    var top = header ? Math.max(0, Math.round(header.getBoundingClientRect().bottom))
                     : (sider ? Math.max(0, Math.round(sider.getBoundingClientRect().top)) : 0);
    return { left: left, top: top };
  }
  function positionPanel(w) { var r = layoutRect(); w.style.left = r.left + "px"; w.style.top = r.top + "px"; }
  function show() {
    injectStyle();
    var w = el(HOST_ID);
    if (!w) { w = document.createElement("div"); w.id = HOST_ID; document.body.appendChild(w); buildBody(w); }
    positionPanel(w); w.classList.add("on"); markNav(true); st.open = true;
    if (!st.posBound) { st.posBound = true; window.addEventListener("resize", function () { var x = el(HOST_ID); if (x && x.classList.contains("on")) positionPanel(x); }); }
  }
  function hide() { var w = el(HOST_ID); if (w) w.classList.remove("on"); markNav(false); st.open = false; }
  function goPage() { show(); }

  // ---------- 侧边栏菜单项:第一位;「设置」第二位 ----------
  function itemText(node) { var h = node.querySelector(".n-menu-item-content-header"); return (h ? h.textContent : (node.textContent || "")).trim(); }
  function reorderMenu(menu) {
    var nav = el(NAV_ID); if (!menu || !nav) return;
    if (menu.firstElementChild !== nav) menu.insertBefore(nav, menu.firstElementChild);
    var setNode = null;
    Array.prototype.forEach.call(menu.querySelectorAll(".n-menu-item"), function (it) {
      if (it.id === NAV_ID || setNode) return;
      if (itemText(it).indexOf("设置") >= 0) setNode = it;
    });
    if (setNode && nav.nextElementSibling !== setNode) menu.insertBefore(setNode, nav.nextElementSibling);
  }
  var SELCLS = "n-menu-item-content--selected";
  function addSel(c) { if (c && c.className.indexOf(SELCLS) < 0) c.className += " " + SELCLS; }
  function delSel(c) { if (c) c.className = c.className.replace(/\s*n-menu-item-content--selected/g, ""); }
  function markNav(on) {
    var nav = el(NAV_ID); if (!nav) return;
    var c = nav.querySelector(".n-menu-item-content") || nav.firstElementChild;
    if (!c) return;
    if (on) {
      // 打开时:记录并清掉原生高亮(如「设置」),只让「外部子号」高亮 → 避免两个都亮
      st.prevSel = document.querySelector(".n-menu-item:not(#" + NAV_ID + ") ." + SELCLS);
      delSel(st.prevSel);
      addSel(c);
    } else {
      // 关闭时:取消本菜单高亮,恢复原来那个(若关闭不是因为点了别的菜单导航)
      delSel(c);
      if (st.prevSel) { addSel(st.prevSel); st.prevSel = null; }
    }
  }
  function relabel(node, label) {
    var hdr = node.querySelector(".n-menu-item-content-header"); if (hdr) { hdr.textContent = label; return true; }
    var done = false; (function walk(n) { Array.prototype.forEach.call(n.childNodes, function (c) { if (done) return; if (c.nodeType === 3 && c.textContent.trim()) { c.textContent = label; done = true; } else if (c.childNodes && c.childNodes.length) walk(c); }); })(node);
    return done;
  }
  function injectNav() {
    var menu = document.querySelector(".n-menu"); if (!menu) return false;
    if (el(NAV_ID)) { reorderMenu(menu); return true; }
    var items = menu.querySelectorAll(".n-menu-item"); if (!items.length) return false;
    var clone = items[items.length - 1].cloneNode(true); clone.id = NAV_ID;
    Array.prototype.forEach.call(clone.querySelectorAll("*"), function (x) { if (x.className && typeof x.className === "string") x.className = x.className.replace(/n-menu-item-content--[a-z-]+/g, "").trim(); });
    if (!relabel(clone, "外部子号")) return false;
    var ic = clone.querySelector(".n-menu-item-content__icon"); if (ic) ic.innerHTML = '<span style="font-size:17px">🔑</span>';
    clone.style.cursor = "pointer";
    clone.addEventListener("click", function (e) { e.preventDefault(); e.stopPropagation(); goPage(); }, true);
    menu.insertBefore(clone, menu.firstElementChild);
    reorderMenu(menu);
    var f = el(FAB_ID); if (f) f.remove();
    return true;
  }
  function fab() { if (el(FAB_ID) || el(NAV_ID)) return; if (!document.body) return; var a = document.createElement("div"); a.id = FAB_ID; a.className = "extm-fab"; a.innerHTML = "<span>🔑</span><span>外部子号</span>"; a.onclick = goPage; document.body.appendChild(a); }

  // ---------- 心跳:注入样式/菜单;打开时跟随布局重定位 ----------
  function onLogin() { var p = location.pathname.replace(/\/+$/, ""); return p === "" || p === "/login"; }
  function ensure() {
    injectStyle();
    if (onLogin()) { hide(); var a = el(NAV_ID); if (a) a.remove(); var b = el(FAB_ID); if (b) b.remove(); return; }
    if (!injectNav()) fab();
    if (st.open) {
      var w = el(HOST_ID); if (w && w.classList.contains("on")) positionPanel(w);
      // 维持「只有外部子号高亮」:清掉其它原生高亮,保留本菜单
      var nav = el(NAV_ID); var c = nav && (nav.querySelector(".n-menu-item-content") || nav.firstElementChild);
      Array.prototype.forEach.call(document.querySelectorAll(".n-menu-item:not(#" + NAV_ID + ") ." + SELCLS), function (x) { delSel(x); });
      addSel(c);
    }
  }
  // 点其它菜单项 → 关闭本页,露出原生页面
  document.addEventListener("click", function (e) {
    if (!st.open) return;
    var mi = e.target.closest && e.target.closest(".n-menu-item");
    if (mi && mi.id !== NAV_ID) hide();
  }, true);

  var ensureT;
  function scheduleEnsure() { clearTimeout(ensureT); ensureT = setTimeout(ensure, 150); }
  var mo = new MutationObserver(scheduleEnsure);
  mo.observe(document.documentElement, { childList: true, subtree: true });
  document.addEventListener("DOMContentLoaded", ensure);
  setTimeout(ensure, 400); setTimeout(ensure, 1000); setTimeout(ensure, 2200); setTimeout(ensure, 4000);
})();
