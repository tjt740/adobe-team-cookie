/* Sub2 账号管理 —— 嵌入式面板(注入现有 SPA,只占内容区、保留侧边栏,不跳转)。
   一次性拉全部账号到本地,支持搜索/状态筛选/表头排序/每页条数;批量刷新/测活/删除/推送
   全走 Sub2 自己的接口(经本地后端 /api/sub2/* 代理)。风格对齐号池管理页。 */

/* 运行时兜底:把慢接口(母号登录/检测、号池登录、Sub2、拉号)的 XHR 超时抬到 280s,
   不受前端包缓存的旧超时值影响。 */
(function () {
  try {
    var SLOW = /\/api\/(adobe-accounts\/\d+\/(login|check)|pool\/[^/]+\/(refresh|login)|pool\/batch-login|sub2\/|adobe-accounts\/[^/]*build-team)/;
    var O = XMLHttpRequest.prototype.open;
    XMLHttpRequest.prototype.open = function (m, u) { try { this.__s2u = u; } catch (e) {} return O.apply(this, arguments); };
    var S = XMLHttpRequest.prototype.send;
    XMLHttpRequest.prototype.send = function () {
      try { if (this.__s2u && SLOW.test(this.__s2u) && (!this.timeout || this.timeout < 280000)) this.timeout = 280000; } catch (e) {}
      return S.apply(this, arguments);
    };
  } catch (e) {}
})();

(function () {
  "use strict";
  var TK = "okad_token";
  var token = localStorage.getItem(TK) || "";
  var NAV_ID = "sub2-nav-mng", PANEL_ID = "sub2-panel";
  var st = {
    all: [], view: [], page: 1, size: 20, sel: new Set(), cfg: null, groups: [],
    busy: false, q: "", statusF: "", sortKey: "", sortDir: 1,
  };

  var CSS = [
    '#' + PANEL_ID + '{position:fixed;top:0;right:0;bottom:0;left:220px;z-index:1000;display:none;background:#f5f7fa;color:#333639;font:14px/1.6 system-ui,-apple-system,"PingFang SC","Microsoft YaHei",sans-serif}',
    '#' + PANEL_ID + '.on{display:flex;flex-direction:column}',
    '#' + PANEL_ID + ' *{box-sizing:border-box}',
    '.s2-top{display:flex;align-items:center;gap:12px;height:56px;padding:0 24px;background:#fff;border-bottom:1px solid #efeff5;flex:none}',
    '.s2-top h2{font-size:17px;margin:0;font-weight:600}',
    '.s2-top .sp{flex:1}',
    '.s2-conn{display:inline-flex;align-items:center;gap:6px;font-size:12px;padding:3px 10px;border-radius:4px;background:#f0f2f5;color:#909399}',
    '.s2-conn .d{width:7px;height:7px;border-radius:50%;background:#c0c4cc}',
    '.s2-conn.ok{background:#e8f7f0;color:#18a058}.s2-conn.ok .d{background:#18a058}',
    '.s2-conn.bad{background:#fce9ec;color:#d03050}.s2-conn.bad .d{background:#d03050}',
    '.s2-body{flex:1;overflow:auto;padding:20px 24px 48px}',
    '.s2-card{background:#fff;border-radius:6px;box-shadow:0 1px 2px rgba(0,0,0,.04);margin-bottom:16px;border:1px solid #efeff5}',
    '.s2-cfg .hd{padding:12px 18px;font-size:14px;font-weight:500;cursor:pointer;display:flex;align-items:center;gap:8px;user-select:none}',
    '.s2-cfg .hd .ar{margin-left:auto;color:#c0c4cc;transition:.15s;font-size:12px}',
    '.s2-cfg.collapsed .bd{display:none}.s2-cfg.collapsed .hd .ar{transform:rotate(-90deg)}',
    '.s2-cfg .bd{padding:4px 18px 18px;border-top:1px solid #f2f3f5}',
    '.s2-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:12px 14px;margin-top:14px}',
    '.s2-f{display:flex;flex-direction:column;gap:5px;min-width:0}',
    '.s2-f label{font-size:12px;color:#606266}',
    '.s2-in{height:34px;border:1px solid #e0e0e6;border-radius:4px;padding:0 11px;color:#333639;font-size:13px;outline:none;width:100%;font-family:inherit;background:#fff;transition:.15s}',
    '.s2-in:focus{border-color:#2080f0;box-shadow:0 0 0 2px rgba(32,128,240,.16)}',
    'select.s2-in{cursor:pointer}',
    '.s2-chips{display:flex;flex-wrap:wrap;gap:7px;min-height:36px;padding:6px;border:1px solid #e0e0e6;border-radius:4px;background:#fafafc}',
    '.s2-chip{padding:4px 11px;border-radius:15px;border:1px solid #e0e0e6;background:#fff;font-size:12.5px;cursor:pointer;color:#606266;transition:.12s}',
    '.s2-chip:hover{border-color:#2080f0;color:#2080f0}',
    '.s2-chip.on{background:#2080f0;border-color:#2080f0;color:#fff}',
    '.s2-chip .i{opacity:.6;font-size:10px;margin-left:3px}',
    '.s2-sw{display:inline-flex;align-items:center;gap:8px;font-size:13px;cursor:pointer;color:#333639}',
    '.s2-sw input{display:none}.s2-sw .t{width:40px;height:22px;border-radius:11px;background:#dcdfe6;position:relative;transition:.2s;flex:none}',
    '.s2-sw .t::after{content:"";position:absolute;top:2px;left:2px;width:18px;height:18px;border-radius:50%;background:#fff;transition:.2s;box-shadow:0 1px 2px rgba(0,0,0,.2)}',
    '.s2-sw input:checked+.t{background:#2080f0}.s2-sw input:checked+.t::after{transform:translateX(18px)}',
    '.s2-btn{font:13px system-ui;border-radius:4px;padding:0 15px;height:34px;border:1px solid #2080f0;background:#2080f0;color:#fff;cursor:pointer;transition:.12s;white-space:nowrap;display:inline-flex;align-items:center;gap:5px}',
    '.s2-btn:hover:not(:disabled){background:#4098fc;border-color:#4098fc}.s2-btn:active{background:#1060c9}',
    '.s2-btn:disabled{opacity:.5;cursor:not-allowed}',
    '.s2-btn.o{background:#fff;color:#2080f0}.s2-btn.o:hover:not(:disabled){background:#ecf5ff}',
    '.s2-btn.dft{background:#fff;color:#606266;border-color:#e0e0e6}.s2-btn.dft:hover:not(:disabled){color:#2080f0;border-color:#2080f0}',
    '.s2-btn.del{background:#fff;color:#d03050;border-color:#f0b3bf}.s2-btn.del:hover:not(:disabled){background:#fef0f2;border-color:#d03050}',
    '.s2-btn.sm{height:28px;padding:0 10px;font-size:12px}',
    '.s2-tools{display:flex;align-items:center;gap:10px;flex-wrap:wrap;padding:14px 16px;border-bottom:1px solid #efeff5}',
    '.s2-tools .cnt{font-size:13px;color:#909399}.s2-tools .cnt b{color:#2080f0}',
    '.s2-tools .sp{flex:1}',
    '.s2-stats{display:flex;gap:8px}',
    '.s2-stbox{padding:5px 14px;border-right:1px solid #efeff5}',
    '.s2-stbox b{font-size:18px;font-variant-numeric:tabular-nums;font-weight:600}.s2-stbox .l{font-size:11px;color:#909399}',
    '.s2-filters{display:flex;align-items:center;gap:10px;flex-wrap:wrap;padding:12px 16px;border-bottom:1px solid #efeff5;background:#fcfcfd}',
    '.s2-filters .s2-in{height:32px;width:auto}',
    '.s2-tw{overflow-x:auto}',
    '.s2-t{border-collapse:collapse;width:100%;font-size:13px;min-width:900px}',
    '.s2-t th{text-align:left;padding:11px 16px;font-size:13px;font-weight:500;color:#909399;background:#fafafc;border-bottom:1px solid #efeff5;white-space:nowrap}',
    '.s2-t th.sortable{cursor:pointer;user-select:none}.s2-t th.sortable:hover{color:#2080f0}',
    '.s2-t th .arw{font-size:10px;margin-left:3px;color:#2080f0}',
    '.s2-t td{padding:8px 16px;border-bottom:1px solid #f2f3f5;color:#333639;vertical-align:middle}',
    '.s2-t td:last-child{white-space:nowrap}',
    '.s2-t tbody tr:hover td{background:#f5f7fa}',
    '.s2-t .mono{font-family:ui-monospace,Menlo,Consolas,monospace;font-size:12px;color:#909399}',
    '.s2-t input[type=checkbox]{width:15px;height:15px;cursor:pointer;accent-color:#2080f0}',
    '.s2-pill{display:inline-block;font-size:12px;padding:1px 9px;border-radius:11px;line-height:1.7}',
    '.s2-pill.ok{background:#e8f7f0;color:#18a058}.s2-pill.bad{background:#fce9ec;color:#d03050}.s2-pill.warn{background:#fdf3e6;color:#f0a020}',
    '.s2-gtag{display:inline-block;font-size:11px;background:#f0f2f5;color:#606266;border-radius:3px;padding:1px 6px;margin:1px 3px 1px 0}',
    '.s2-cap{display:inline-block;font-size:10.5px;padding:1px 4px;border-radius:3px;margin-right:2px;font-family:ui-monospace,Menlo,monospace}',
    '.s2-cap.ok{background:#e8f7f0;color:#18a058}.s2-cap.no{background:#fce9ec;color:#d03050}.s2-cap.na{background:#f0f2f5;color:#c0c4cc}',
    '.s2-pg{display:flex;align-items:center;justify-content:flex-end;gap:12px;padding:14px 18px;font-size:13px;color:#909399}',
    '.s2-msg{font-size:12.5px}.s2-msg.ok{color:#18a058}.s2-msg.err{color:#d03050}.s2-msg.mut{color:#909399}',
    '.s2-empty{text-align:center;color:#c0c4cc;padding:48px 0;font-size:13px}',
    '.s2-x{border:1px solid #e0e0e6;background:#fff;color:#909399;border-radius:4px;width:32px;height:32px;cursor:pointer;font-size:15px}',
    '.s2-x:hover{color:#2080f0;border-color:#2080f0}',
    '.s2-warn{background:#fdf3e6;color:#b9770f;font-size:12.5px;padding:8px 16px;border-bottom:1px solid #f5e6cf}',
    '.s2-fab{position:fixed;right:22px;bottom:22px;z-index:1999;display:inline-flex;align-items:center;gap:7px;padding:10px 16px;border-radius:22px;background:#2080f0;color:#fff;font:600 13px system-ui;cursor:pointer;box-shadow:0 6px 16px rgba(32,128,240,.4)}',
  ].join("");

  function injectStyle() { if (document.getElementById("s2-style")) return; var s = document.createElement("style"); s.id = "s2-style"; s.textContent = CSS; (document.head || document.documentElement).appendChild(s); }

  // ---------- api(带超时+可取消) ----------
  function api(path, opts) {
    opts = opts || {};
    var ctrl = new AbortController();
    var to = setTimeout(function () { ctrl.abort(); }, opts.timeout || 30000);
    return fetch("/api/sub2" + path, {
      method: opts.method || "GET", signal: ctrl.signal,
      headers: { "Content-Type": "application/json", "Authorization": "Bearer " + token },
      body: opts.body ? JSON.stringify(opts.body) : undefined,
    }).then(function (r) {
      return r.text().then(function (t) {
        var d; try { d = JSON.parse(t); } catch (e) { d = { raw: t }; }
        if (r.status === 401) { throw new Error("未登录,请重新登录后台"); }
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
  function setMsg(id, t, c) { var e = el(id); if (e) { e.className = "s2-msg" + (c ? " " + c : ""); e.textContent = t || ""; } }
  function setConn(s, t) { var e = el("s2-conn"); if (e) { e.className = "s2-conn" + (s ? " " + s : ""); el("s2-conn-t").textContent = t; } }

  // ---------- panel ----------
  function buildPanel() {
    if (el(PANEL_ID)) return;
    var p = document.createElement("div"); p.id = PANEL_ID;
    p.innerHTML =
      '<div class="s2-top"><h2>Sub2 账号管理</h2>' +
        '<span class="s2-conn" id="s2-conn"><span class="d"></span><span id="s2-conn-t">未测试</span></span>' +
        '<div class="sp"></div>' +
        '<button class="s2-btn dft sm" id="s2-reload">↻ 刷新列表</button>' +
        '<button class="s2-x" id="s2-close" title="关闭">✕</button></div>' +
      '<div class="s2-body">' +
        '<div class="s2-card s2-cfg collapsed" id="s2-cfg"><div class="hd" id="s2-cfghd">连接配置 <span class="s2-msg" id="s2-cfgstate"></span><span class="ar">▾</span></div>' +
          '<div class="bd">' +
            '<div class="s2-grid">' +
              '<div class="s2-f" style="grid-column:1/-1"><label>Sub2API 地址</label><input class="s2-in" id="s2-base" placeholder="http://主机(自动补 /api/v1)"></div>' +
              '<div class="s2-f" style="grid-column:1/-1"><label>管理员 Token(留空=不改)</label><input class="s2-in" id="s2-token" placeholder="粘贴 admin key"></div>' +
              '<div class="s2-f"><label>平台</label><select class="s2-in" id="s2-plat"><option value="adobe_gemini">Adobe-Gemini</option><option value="adobe_gpt">Adobe-GPT</option></select></div>' +
              '<div class="s2-f"><label>协议</label><select class="s2-in" id="s2-proto"><option value="default">默认 / 18 slot</option><option value="fi_free">FI无消耗</option></select></div>' +
            '</div>' +
            '<div class="s2-f" style="margin-top:12px"><label>推送绑定分组(点选)</label><div class="s2-chips" id="s2-groups"></div><input class="s2-in" id="s2-gids" placeholder="或手填 26,32" style="margin-top:7px;height:30px;max-width:240px;font-size:12px"></div>' +
            '<div style="display:flex;gap:22px;margin-top:14px"><label class="s2-sw"><input type="checkbox" id="s2-en"><span class="t"></span>启用推送</label><label class="s2-sw"><input type="checkbox" id="s2-auto"><span class="t"></span>巡航自动推送</label></div>' +
            '<div style="display:flex;gap:10px;align-items:center;margin-top:16px"><button class="s2-btn" id="s2-save">保存</button><button class="s2-btn o" id="s2-test">测试连接</button><button class="s2-btn dft" id="s2-loadg">加载分组</button><span class="s2-msg" id="s2-cfgmsg"></span></div>' +
          '</div></div>' +
        '<div class="s2-card">' +
          '<div class="s2-tools">' +
            '<div class="s2-stats"><div class="s2-stbox"><b id="s2-st-total">–</b><div class="l">Sub2 账号</div></div>' +
              '<div class="s2-stbox"><b id="s2-st-active" style="color:#18a058">–</b><div class="l">正常</div></div>' +
              '<div class="s2-stbox"><b id="s2-st-new" style="color:#2080f0">–</b><div class="l">号池新可用</div></div></div>' +
            '<div class="sp"></div>' +
            '<label class="s2-sw" style="font-size:13px"><input type="checkbox" id="s2-selall"><span class="t"></span>全选本页</label>' +
            '<button class="s2-btn dft sm" id="s2-selall2">全选筛选结果</button>' +
            '<span class="cnt">已选 <b id="s2-seln">0</b> <a id="s2-selclr" style="color:#909399;cursor:pointer">清空</a></span>' +
            '<button class="s2-btn o sm" id="s2-bref">批量刷新 token</button>' +
            '<button class="s2-btn o sm" id="s2-bbal">批量测活/刷额度</button>' +
            '<button class="s2-btn del sm" id="s2-bdel">批量删除</button>' +
            '<button class="s2-btn sm" id="s2-push">推送新号 (<span id="s2-pushn">0</span>)</button>' +
            '<span class="s2-msg" id="s2-opmsg"></span>' +
          '</div>' +
          '<div class="s2-warn" id="s2-trunc" style="display:none"></div>' +
          '<div class="s2-filters">' +
            '<input class="s2-in" id="s2-q" placeholder="搜索邮箱 / 归属母号" style="min-width:220px">' +
            '<select class="s2-in" id="s2-statusf"><option value="">全部状态</option><option value="ok">正常</option><option value="bad">异常</option></select>' +
            '<div class="sp"></div>' +
            '<span style="font-size:12px;color:#909399">每页</span>' +
            '<select class="s2-in" id="s2-pagesize"><option value="20">20</option><option value="50">50</option><option value="100">100</option><option value="99999">全部</option></select>' +
          '</div>' +
          '<div class="s2-tw"><table class="s2-t"><thead><tr>' +
            '<th style="width:38px"></th>' +
            '<th class="sortable" data-sk="name">邮箱</th>' +
            '<th class="sortable" data-sk="owner" style="width:150px">归属母号</th>' +
            '<th class="sortable" data-sk="status" style="width:64px">状态</th>' +
            '<th class="sortable" data-sk="credits" style="width:92px">积分</th>' +
            '<th style="width:110px">出图能力</th>' +
            '<th class="sortable" data-sk="fails" style="width:46px">失败</th>' +
            '<th class="sortable" data-sk="token_exp" style="width:104px">token到期</th>' +
            '<th>分组</th><th style="width:90px">操作</th>' +
          '</tr></thead><tbody id="s2-tbody"></tbody></table></div>' +
          '<div class="s2-pg"><span id="s2-pginfo">–</span>' +
            '<button class="s2-btn dft sm" id="s2-prev">上一页</button>' +
            '<button class="s2-btn dft sm" id="s2-next">下一页</button></div>' +
        '</div>' +
      '</div>';
    document.body.appendChild(p);
    wire();
  }

  function wire() {
    el("s2-close").onclick = window.OKAD_NAV.close;
    el("s2-reload").onclick = function () { if (!st.busy) { loadAll(); loadStats(); } };
    el("s2-cfghd").onclick = function () { el("s2-cfg").classList.toggle("collapsed"); };
    el("s2-save").onclick = saveConfig; el("s2-test").onclick = testConn; el("s2-loadg").onclick = loadGroups;
    el("s2-plat").addEventListener("change", function () { st.sel.clear(); renderGroups(); loadAll(); loadStats(); });
    el("s2-gids").addEventListener("input", renderGroups);
    el("s2-q").addEventListener("input", debounce(function () { st.q = el("s2-q").value.trim().toLowerCase(); st.page = 1; applyView(); }, 200));
    el("s2-statusf").addEventListener("change", function () { st.statusF = el("s2-statusf").value; st.page = 1; applyView(); });
    el("s2-pagesize").addEventListener("change", function () { st.size = parseInt(el("s2-pagesize").value, 10) || 20; st.page = 1; applyView(); });
    el("s2-selall").onchange = function (e) { curPageItems().forEach(function (a) { if (e.target.checked) st.sel.add(String(a.id)); else st.sel.delete(String(a.id)); }); renderTable(); };
    el("s2-selall2").onclick = function () { st.view.forEach(function (a) { st.sel.add(String(a.id)); }); setMsg("s2-opmsg", "已选中筛选结果 " + st.sel.size + " 个", "ok"); renderTable(); };
    el("s2-selclr").onclick = function () { st.sel.clear(); renderTable(); setMsg("s2-opmsg", ""); };
    el("s2-bref").onclick = function () { batchRefresh(false); };
    el("s2-bbal").onclick = function () { batchRefresh(true); };
    el("s2-bdel").onclick = batchDelete; el("s2-push").onclick = pushNew;
    el("s2-prev").onclick = function () { if (st.page > 1) { st.page--; applyView(); } };
    el("s2-next").onclick = function () { if (st.page * st.size < st.view.length) { st.page++; applyView(); } };
    Array.prototype.forEach.call(el("s2-tbody").parentNode.querySelectorAll("th.sortable"), function (th) {
      th.onclick = function () { var k = th.getAttribute("data-sk"); if (st.sortKey === k) st.sortDir = -st.sortDir; else { st.sortKey = k; st.sortDir = 1; } st.page = 1; applyView(); };
    });
  }
  function debounce(fn, ms) { var t; return function () { clearTimeout(t); t = setTimeout(fn, ms); }; }

  // ---------- config ----------
  function loadConfig() {
    return api("/config").then(function (c) {
      st.cfg = c;
      el("s2-base").value = c.base_url || ""; el("s2-plat").value = c.platform || "adobe_gemini"; el("s2-proto").value = c.protocol || "default";
      el("s2-gids").value = c.group_ids || ""; el("s2-en").checked = !!c.enabled; el("s2-auto").checked = !!c.auto_push;
      el("s2-token").placeholder = c.admin_token_set ? "已配置(留空=不改)" : "粘贴 admin key";
      el("s2-cfgstate").textContent = c.admin_token_set ? "已配置" : "未配置";
      el("s2-cfgstate").className = "s2-msg " + (c.admin_token_set ? "ok" : "err");
      if (c.admin_token_set) setConn("ok", "已配置");
      renderGroups(); if (c.admin_token_set) loadGroups();
    }).catch(function (e) { setMsg("s2-cfgmsg", e.message, "err"); });
  }
  function readCfg() { var b = { base_url: el("s2-base").value.trim(), platform: el("s2-plat").value, protocol: el("s2-proto").value, group_ids: el("s2-gids").value.trim(), enabled: el("s2-en").checked, auto_push: el("s2-auto").checked }; var tk = el("s2-token").value.trim(); if (tk) b.admin_token = tk; return b; }
  function saveConfig() { setMsg("s2-cfgmsg", "保存中…"); return api("/config", { method: "PUT", body: readCfg() }).then(function (r) { el("s2-token").value = ""; if (r && r.ok === false) { setMsg("s2-cfgmsg", r.message || "保存失败", "err"); return; } setMsg("s2-cfgmsg", "已保存", "ok"); loadConfig(); loadAll(); loadStats(); }).catch(function (e) { setMsg("s2-cfgmsg", e.message, "err"); }); }
  function testConn() { setMsg("s2-cfgmsg", "测试中…"); setConn("", "测试中"); api("/test", { method: "POST" }).then(function (r) { setMsg("s2-cfgmsg", r.message, r.ok ? "ok" : "err"); setConn(r.ok ? "ok" : "bad", r.ok ? "已连接" : "未连接"); }).catch(function (e) { setMsg("s2-cfgmsg", e.message, "err"); setConn("bad", "未连接"); }); }
  function parseGids() { return (el("s2-gids").value || "").replace(/，/g, ",").split(",").map(function (s) { return s.trim(); }).filter(function (s) { return /^\d+$/.test(s); }); }
  function renderGroups() {
    var box = el("s2-groups"); if (!box) return; var plat = el("s2-plat").value, sel = new Set(parseGids());
    if (!st.groups.length) { box.innerHTML = '<span style="font-size:12px;color:#c0c4cc">保存令牌后点「加载分组」</span>'; return; }
    var list = st.groups.filter(function (g) { return !g.platform || g.platform === plat; });
    box.innerHTML = ""; list.forEach(function (g) { var c = document.createElement("span"); c.className = "s2-chip" + (sel.has(String(g.id)) ? " on" : ""); c.innerHTML = esc(g.name || g.id) + '<span class="i">#' + g.id + '</span>'; c.onclick = function () { var cur = new Set(parseGids()); var k = String(g.id); cur.has(k) ? cur.delete(k) : cur.add(k); el("s2-gids").value = Array.from(cur).join(","); renderGroups(); }; box.appendChild(c); });
  }
  function loadGroups() { setMsg("s2-cfgmsg", "加载分组…"); api("/groups").then(function (r) { if (!r.ok) { setMsg("s2-cfgmsg", r.message || "失败", "err"); return; } st.groups = r.groups || []; setMsg("s2-cfgmsg", "分组已加载", "ok"); renderGroups(); }).catch(function (e) { setMsg("s2-cfgmsg", e.message, "err"); }); }

  // ---------- stats + accounts ----------
  function loadStats() { api("/candidates").then(function (c) { var n = (typeof c.new_count === "number") ? c.new_count : 0; el("s2-st-new").textContent = c.sub2_ok ? n : "?"; el("s2-pushn").textContent = c.sub2_ok ? n : "0"; if (c.sub2_ok) el("s2-st-total").textContent = c.sub2_total; }).catch(function () { el("s2-st-new").textContent = "?"; }); }

  function loadAll() {
    if (st.busy) return; st.busy = true; setBusy(true);
    el("s2-tbody").innerHTML = '<tr><td colspan="10" class="s2-empty">加载中…</td></tr>';
    st.all = [];
    var acc = [];
    function page(n) {
      return api("/accounts?page=" + n + "&size=100", { timeout: 60000 }).then(function (r) {
        if (!r.ok) throw new Error(r.message || "加载失败");
        var items = r.items || []; acc = acc.concat(items);
        if (items.length >= 100 && n < 200) return page(n + 1);
        return acc;
      });
    }
    page(1).then(function (all) {
      st.all = all; st.busy = false; setBusy(false);
      el("s2-trunc").style.display = "none";
      applyView();
    }).catch(function (e) {
      st.busy = false; setBusy(false);
      el("s2-tbody").innerHTML = '<tr><td colspan="10" class="s2-empty" style="color:#d03050">' + esc(e.message) + '</td></tr>';
    });
  }

  function statusBad(a) { return !(a.status === "active" && a.schedulable !== false) || !!a.error; }
  function applyView() {
    var q = st.q, sf = st.statusF;
    var v = st.all.filter(function (a) {
      if (q && (esc(a.name).toLowerCase().indexOf(q) < 0) && (String(a.owner || "").toLowerCase().indexOf(q) < 0)) return false;
      if (sf === "ok" && statusBad(a)) return false;
      if (sf === "bad" && !statusBad(a)) return false;
      return true;
    });
    if (st.sortKey) {
      var k = st.sortKey, dir = st.sortDir;
      v.sort(function (a, b) {
        var x = a[k], y = b[k];
        if (k === "credits" || k === "fails" || k === "token_exp") { x = Number(x) || 0; y = Number(y) || 0; }
        else if (k === "status") { x = statusBad(a) ? 1 : 0; y = statusBad(b) ? 1 : 0; }
        else { x = String(x || "").toLowerCase(); y = String(y || "").toLowerCase(); }
        return x < y ? -dir : (x > y ? dir : 0);
      });
    }
    st.view = v;
    el("s2-st-active").textContent = st.all.filter(function (a) { return !statusBad(a); }).length + "/" + st.all.length;
    if (!el("s2-st-total").textContent || el("s2-st-total").textContent === "–") el("s2-st-total").textContent = st.all.length;
    renderTable();
  }
  function curPageItems() { var s = (st.page - 1) * st.size; return st.view.slice(s, s + st.size); }

  function capBadge(a) {
    var mk = function (l, val) { return val === true ? '<span class="s2-cap ok">' + l + '</span>' : (val === false ? '<span class="s2-cap no">' + l + '</span>' : '<span class="s2-cap na">' + l + '</span>'); };
    if (a.cap1k == null && a.cap2k == null && a.cap4k == null) return '<span style="color:#c0c4cc;font-size:11px">未测</span>';
    return mk("1K", a.cap1k) + mk("2K", a.cap2k) + mk("4K", a.cap4k);
  }
  function creditsCell(a) {
    var av = a.credits_avail, tot = a.credits_total;
    if (av == null && tot == null) return '<span style="color:#c0c4cc">-</span>';
    var color = (av != null && av <= 0) ? "#d03050" : ((av != null && tot && av < tot * 0.15) ? "#f0a020" : "#18a058");
    var s = '<span style="color:' + color + ';font-variant-numeric:tabular-nums;font-weight:600">' + (av == null ? "?" : av) + '</span>';
    if (tot != null) s += '<span style="color:#c0c4cc;font-size:11px">/' + tot + '</span>';
    return s;
  }
  function statusPill(a) { if (!statusBad(a)) return '<span class="s2-pill ok">正常</span>'; if (a.error) return '<span class="s2-pill bad" title="' + esc(a.error) + '">' + esc(a.status || "异常") + '</span>'; return '<span class="s2-pill warn">' + esc(a.status || "未知") + '</span>'; }
  function fmtExp(ts) { if (!ts) return "-"; try { var n = Number(ts); var d = new Date(String(ts).length <= 10 ? n * 1000 : n); if (isNaN(d.getTime())) return "-"; var cls = d.getTime() < Date.now() ? "color:#d03050" : "color:#909399"; return '<span style="' + cls + '">' + (d.getFullYear() % 100) + "-" + (d.getMonth() + 1) + "-" + d.getDate() + '</span>'; } catch (e) { return "-"; } }

  function renderTable() {
    var b = el("s2-tbody"); var rows = curPageItems();
    if (!rows.length) { b.innerHTML = '<tr><td colspan="10" class="s2-empty">' + (st.all.length ? "无匹配结果" : "该平台暂无账号") + '</td></tr>'; }
    else {
      b.innerHTML = rows.map(function (a) {
        var gtags = (a.group_ids || []).map(function (g) { return '<span class="s2-gtag">#' + g + '</span>'; }).join("") || '<span style="color:#c0c4cc">-</span>';
        return '<tr><td><input type="checkbox" data-id="' + a.id + '" class="s2-rowck"' + (st.sel.has(String(a.id)) ? " checked" : "") + '></td>' +
          '<td title="' + esc(a.account_id) + '">' + esc(a.name) + '</td>' +
          '<td>' + (a.owner ? '<span style="font-size:12.5px;color:#606266">' + esc(a.owner) + '</span>' : '<span style="color:#c0c4cc">-</span>') + '</td>' +
          '<td>' + statusPill(a) + '</td>' +
          '<td>' + creditsCell(a) + '</td>' +
          '<td>' + capBadge(a) + '</td>' +
          '<td class="mono">' + (a.fails ? '<span style="color:#d03050">' + a.fails + '</span>' : '0') + '</td>' +
          '<td class="mono">' + fmtExp(a.token_exp) + '</td>' +
          '<td>' + gtags + '</td>' +
          '<td><button class="s2-btn dft sm" data-ref="' + a.id + '"' + (st.busy ? " disabled" : "") + '>刷新</button> <button class="s2-btn del sm" data-del="' + a.id + '"' + (st.busy ? " disabled" : "") + '>删</button></td></tr>';
      }).join("");
      Array.prototype.forEach.call(b.querySelectorAll(".s2-rowck"), function (ck) { ck.onchange = function () { var id = String(ck.getAttribute("data-id")); if (ck.checked) st.sel.add(id); else st.sel.delete(id); updSel(); }; });
      Array.prototype.forEach.call(b.querySelectorAll("[data-ref]"), function (btn) { btn.onclick = function () { if (!st.busy) doRefresh([parseInt(btn.getAttribute("data-ref"), 10)], false); }; });
      Array.prototype.forEach.call(b.querySelectorAll("[data-del]"), function (btn) { btn.onclick = function () { if (!st.busy) doDelete([parseInt(btn.getAttribute("data-del"), 10)]); }; });
    }
    // 表头排序箭头
    Array.prototype.forEach.call(el("s2-tbody").parentNode.querySelectorAll("th.sortable"), function (th) {
      var base = th.textContent.replace(/[▲▼]/g, "").trim();
      th.innerHTML = base + (st.sortKey === th.getAttribute("data-sk") ? ' <span class="arw">' + (st.sortDir > 0 ? "▲" : "▼") + "</span>" : "");
    });
    var total = st.view.length, pages = Math.max(1, Math.ceil(total / st.size));
    el("s2-pginfo").textContent = "共 " + total + " 个 · 第 " + st.page + "/" + pages + " 页";
    el("s2-prev").disabled = st.busy || st.page <= 1;
    el("s2-next").disabled = st.busy || st.page >= pages;
    var sa = el("s2-selall"); if (sa) { var cp = curPageItems(); sa.checked = cp.length > 0 && cp.every(function (a) { return st.sel.has(String(a.id)); }); }
    updSel();
  }
  function updSel() { el("s2-seln").textContent = st.sel.size; }

  // ---------- batch ops ----------
  function selIds() { return Array.from(st.sel).map(function (x) { return parseInt(x, 10); }).filter(function (x) { return !isNaN(x); }); }
  function setBusy(v) {
    st.busy = st.busy && v ? true : v;
    ["s2-bref", "s2-bbal", "s2-bdel", "s2-push", "s2-reload", "s2-selall2", "s2-prev", "s2-next"].forEach(function (id) { var e = el(id); if (e) e.disabled = v; });
    Array.prototype.forEach.call(document.querySelectorAll("#s2-tbody [data-ref],#s2-tbody [data-del]"), function (b) { b.disabled = v; });
  }
  function batchRefresh(bal) { var ids = selIds(); if (!ids.length) { setMsg("s2-opmsg", "请先勾选账号", "err"); return; } doRefresh(ids, bal); }
  function doRefresh(ids, bal) {
    setMsg("s2-opmsg", (bal ? "刷额度" : "刷新 token") + "中(" + ids.length + " 个)…"); setBusy(true);
    api("/batch-refresh", { method: "POST", body: { account_ids: ids, balance: !!bal }, timeout: 280000 }).then(function (r) {
      setMsg("s2-opmsg", r.ok ? ((bal ? "额度" : "token") + "刷新完成") : ("失败:" + (r.message || "")), r.ok ? "ok" : "err");
      setBusy(false); loadAll();
    }).catch(function (e) { setBusy(false); setMsg("s2-opmsg", e.message, "err"); });
  }
  function batchDelete() {
    var ids = selIds(); if (!ids.length) { setMsg("s2-opmsg", "请先勾选账号", "err"); return; }
    var byId = {}; st.all.forEach(function (a) { byId[a.id] = a.name; });
    var emails = ids.slice(0, 12).map(function (i) { return byId[i] || ("#" + i); });
    var msg = "确认从 Sub2 删除这 " + ids.length + " 个账号?不可逆。\n\n" + emails.join("\n") + (ids.length > 12 ? ("\n…等共 " + ids.length + " 个") : "");
    if (!confirm(msg)) return;
    doDelete(ids);
  }
  function doDelete(ids) {
    if (ids.length === 1) { var a = st.all.filter(function (x) { return x.id === ids[0]; })[0]; if (!confirm("确认从 Sub2 删除 " + (a ? a.name : ("#" + ids[0])) + " ?不可逆。")) return; }
    setMsg("s2-opmsg", "删除中(" + ids.length + " 个)…"); setBusy(true);
    api("/batch-delete", { method: "POST", body: { account_ids: ids }, timeout: 280000 }).then(function (r) {
      setMsg("s2-opmsg", r.message || "完成", r.ok ? "ok" : "err"); ids.forEach(function (i) { st.sel.delete(String(i)); }); setBusy(false); loadAll(); loadStats();
    }).catch(function (e) { setBusy(false); setMsg("s2-opmsg", e.message, "err"); });
  }
  function pushNew() {
    var n = parseInt(el("s2-pushn").textContent, 10);
    if (!n || isNaN(n)) { setMsg("s2-opmsg", "没有新可用子号(或 Sub2 未连接)", "mut"); return; }
    if (!confirm("把号池里 " + n + " 个新可用子号推进 Sub2 分组?会真实写入。")) return;
    setMsg("s2-opmsg", "推送中…"); setBusy(true);
    api("/push", { method: "POST", body: { dry_run: false }, timeout: 280000 }).then(function (r) {
      setMsg("s2-opmsg", r.ok ? ("推送完成:创建 " + (r.created || 0) + " · 失败 " + (r.failed || 0)) : ("失败:" + (r.message || "")), r.ok ? "ok" : "err");
      setBusy(false); loadAll(); loadStats();
    }).catch(function (e) { setBusy(false); setMsg("s2-opmsg", e.message, "err"); });
  }

  // ---------- open/close ----------
  function positionPanel() {
    var pnl = el(PANEL_ID), r = window.OKAD_NAV.rect();
    if (pnl) { pnl.style.left = r.left + "px"; pnl.style.top = r.top + "px"; }
  }
  function openPanel() {
    token = localStorage.getItem(TK) || "";
    injectStyle(); buildPanel();
    positionPanel(); el(PANEL_ID).classList.add("on");
    st.page = 1; st.sel.clear(); st.q = ""; st.statusF = "";
    loadConfig().then(loadStats); loadAll();
  }
  function closePanel() { var p = el(PANEL_ID); if (p) p.classList.remove("on"); }
  window.OKAD_NAV.register({
    id: NAV_ID, panel: PANEL_ID, label: "Sub2 管理", icon: "sub2",
    open: openPanel, close: closePanel, layout: positionPanel
  });
})();
