/* 外部子号管理 —— 点侧边栏菜单在「右侧内容区」内嵌显示(按实际测量左侧菜单宽度/顶栏高度
   定位,只覆盖内容区,绝不遮挡左侧菜单与顶栏);点其它菜单自动收起。菜单项排第一、设置排第二。
   接口:/api/external/*(JWT,取 localStorage.okad_token)。 */
(function () {
  "use strict";
  var TK = "okad_token";
  var NAV_ID = "extm-nav";
  var st = { rows: [], sel: new Set(), statusF: "", subF: "", q: "", busy: false, open: false, expanded: new Set(), pending: new Set(), details: {}, loadSeq: 0, polling: false };

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
    '.extm-batch-controls{display:flex;align-items:center;gap:10px}.extm-detail:not(.extm-manage-history) .extm-history-select,.extm-detail:not(.extm-manage-history) [data-action=delete]{display:none}.extm-pill.info{background:#eaf2ff;color:#3b82f6}',
    '.extm-tw{overflow-x:auto}',
    '.extm-t{border-collapse:collapse;table-layout:fixed;width:100%;font-size:13px;min-width:1440px}',
    '.extm-t th{text-align:left;padding:11px 16px;font-size:13px;font-weight:500;color:#909399;background:#fafafc;border-bottom:1px solid #efeff5;white-space:nowrap}',
    '.extm-t td{padding:12px;border-bottom:1px solid #f2f3f5;color:#333639;vertical-align:middle;white-space:nowrap}.extm-t th{padding:11px 12px}',
    '.extm-t td:last-child{white-space:nowrap}',
    '.extm-t>thead>tr>th:last-child,.extm-t>tbody>tr[data-member]>td:last-child{position:sticky;right:0;box-shadow:-3px 0 5px rgba(0,0,0,.025)}.extm-t>thead>tr>th:last-child{background:#fafafc}',
    '.extm-t>tbody>tr[data-member]{--extm-row-bg:#fff}.extm-t>tbody>tr[data-member]>td{background:var(--extm-row-bg)}.extm-history tbody tr:hover>td{background:#f5f7fa}',
    '.extm-t .mono{font-family:ui-monospace,Menlo,Consolas,monospace;font-size:12.5px}',
    '.extm-t .cr{font-variant-numeric:tabular-nums;font-size:12.5px;color:#606266}',
    '.extm-t .cr b{color:#18a058}',
    '.extm-t input[type=checkbox]{width:15px;height:15px;cursor:pointer;accent-color:#18a058;margin:0;vertical-align:middle}',
    '.extm-pill{display:inline-block;font-size:12px;padding:1px 9px;border-radius:11px;line-height:1.7;white-space:nowrap}',
    '.extm-pill.ok{background:#e8f7f0;color:#18a058}.extm-pill.bad{background:#fce9ec;color:#d03050}.extm-pill.warn{background:#fdf3e6;color:#f0a020}.extm-pill.mut{background:#f0f2f5;color:#909399}',
    '.extm-cap{display:inline-block;font-size:10.5px;padding:1px 6px;border-radius:3px;margin-left:6px;font-family:ui-monospace,Menlo,monospace}',
    '.extm-cap.ok{background:#e8f7f0;color:#18a058}.extm-cap.no{background:#f0f2f5;color:#c0c4cc}',
    '.extm-empty{text-align:center;color:#c0c4cc;padding:48px 0;font-size:13px}',
    '.extm-msg{font-size:12.5px;min-height:18px}.extm-msg.ok{color:#18a058}.extm-msg.err{color:#d03050}.extm-msg.mut{color:#909399}',
    '.extm-clip{display:block;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;min-width:0}.extm-email{font:12.5px ui-monospace,Menlo,monospace;text-align:left;width:100%}',
    '.extm-link{border:0;background:transparent;color:inherit;padding:0;cursor:pointer}.extm-link:hover{color:#18a058}.extm-t>tbody>tr[data-member]>td:nth-child(-n+2){padding:0;text-align:center}.extm-toggle{display:flex;align-items:center;justify-content:center;width:28px;height:28px;margin:0 auto;border-radius:6px;color:#858d99;line-height:1}.extm-toggle:hover{background:#e9edf2}.extm-toggle .okad-icon{display:block;transition:transform .18s}.extm-toggle[aria-expanded=true]{color:#18a058;background:#e8f5ee}.extm-toggle[aria-expanded=true] .okad-icon{transform:rotate(90deg)}',
    '.extm-status{display:flex;align-items:center;gap:8px;min-width:0}.extm-status .extm-pill{flex-shrink:0}.extm-status .extm-cap{flex-shrink:0;margin:0}.extm-status .extm-cap.no{color:#909399}.extm-status .extm-link{font:inherit;font-size:12px;text-align:left;color:#606266}.extm-actions{display:flex;gap:7px}',
    '.extm-success{display:inline-flex;align-items:center;gap:4px;border:0;cursor:pointer;font-family:inherit;border-radius:4px;padding:2px 8px}.extm-success:focus-visible{outline:2px solid #18a058;outline-offset:3px}.extm-success:hover{background:#d8f1e2}',
    '.extm-spin{display:inline-block;width:13px;height:13px;border:2px solid currentColor;border-right-color:transparent;border-radius:50%;animation:extm-spin .75s linear infinite;flex-shrink:0}@keyframes extm-spin{to{transform:rotate(360deg)}}',
    '.extm-btn[aria-busy=true]{opacity:.8}.extm-btn:focus-visible,.extm-link:focus-visible{outline:2px solid #18a058;outline-offset:3px}',
    '.extm-t tr.extm-detail-row>td,.extm-t tr.extm-detail-row:hover>td{padding:0 18px;background:#f2f2f2;white-space:normal}',
    '.extm-fold{position:sticky;left:18px;width:var(--extm-detail-width);max-width:100%;display:grid;grid-template-rows:1fr;opacity:1;transition:grid-template-rows .28s cubic-bezier(.2,.7,.2,1),opacity .22s ease}.extm-fold.is-closed{grid-template-rows:0fr;opacity:0;pointer-events:none}.extm-fold-clip{min-height:0;overflow:hidden}.extm-detail{padding:16px 0 18px}.extm-fold.is-closed .extm-detail{visibility:hidden;transition:visibility 0s .28s}@media(prefers-reduced-motion:reduce){.extm-fold,.extm-fold.is-closed .extm-detail{transition:none}}',
    '.extm-task-layout{display:grid;grid-template-columns:440px minmax(0,1fr);gap:16px}.extm-task-card{background:#fff;border:1px solid #e5e9e7;border-radius:6px;min-width:0;overflow:hidden}.extm-task-head{display:flex;align-items:center;gap:10px;padding:12px 14px;border-bottom:1px solid #edf0ee;min-height:51px}.extm-task-head strong{font-size:14px;font-weight:600}.extm-task-head .sp{flex:1}.extm-task-actions{display:flex;align-items:center;gap:8px;flex-wrap:wrap;margin-left:auto}.extm-task-head{flex-wrap:wrap;background:#fafbfc}.extm-task-head .extm-btn{border-radius:5px}.extm-task-head .extm-auto{margin-right:8px}.extm-auto{font-size:12px;color:#606266;display:flex;align-items:center;gap:5px;white-space:nowrap;cursor:pointer}',
    '.extm-auto input[type=checkbox]{appearance:none;width:28px;height:16px;border-radius:10px;background:#cdd3da;position:relative;transition:background .15s}.extm-auto input[type=checkbox]:checked{background:#18a058}.extm-auto input[type=checkbox]:after{content:"";position:absolute;left:2px;top:2px;width:12px;height:12px;background:#fff;border-radius:50%;transition:transform .15s}.extm-auto input[type=checkbox]:checked:after{transform:translateX(12px)}.extm-auto input[type=checkbox]:focus-visible{outline:2px solid #18a058;outline-offset:2px}',
    '.extm-history-wrap{max-height:366px;overflow:auto}.extm-history{table-layout:fixed;border-collapse:collapse;width:100%;font-size:12px}.extm-history th,.extm-history td{padding:9px 8px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.extm-history td:first-child{padding:9px 7px;text-overflow:clip}.extm-history th{font-size:12px;background:#fafcfb;color:#909399}.extm-history tr[data-job]{cursor:pointer}.extm-history tr.active td{background:#edf8f1!important}.extm-history .extm-pill{padding:1px 6px;font-size:11px}.extm-history td:nth-child(2){color:#18a058}',
    '.extm-task-body{padding:14px}.extm-job-title{display:flex;align-items:center;gap:8px}.extm-job-meta{color:#909399;font-size:12px;display:flex;gap:8px 20px;flex-wrap:wrap;margin:12px 0 16px}.extm-job-meta span{display:inline-flex;align-items:center;gap:7px}.extm-job-meta b{font-weight:400;color:#667080;font-variant-numeric:tabular-nums}.extm-job-title{justify-content:space-between;flex-wrap:wrap}.extm-job-title strong{font-size:14px}.extm-counts{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:8px}.extm-counts>span{display:flex;align-items:center;justify-content:space-between;gap:8px;background:#f6f8fa;border:1px solid #edf0f3;border-radius:6px;padding:8px 12px;color:#7a8492;font-size:12px}.extm-counts b{font-size:16px;font-weight:600;color:#354052;font-variant-numeric:tabular-nums}.extm-counts .extm-count-success b{color:#18a058}.extm-counts .extm-count-fail b{color:#d03050}.extm-counts .extm-count-zero b{color:#99a2ad}.extm-progress{height:6px;background:#eef0f2;border-radius:8px;overflow:hidden;margin:10px 0}.extm-progress>div{height:100%;background:#18a058;transition:width .2s}.extm-progress>div.failed{background:#d03050}',
    '.extm-log-tools{display:flex;align-items:center;gap:8px;margin:12px 0 8px;color:#909399;font-size:12px}.extm-log-tools .sp{flex:1}.extm-log-tools .extm-in{height:28px;font-size:12px}.extm-logs{margin:0;background:#1b2330;color:#cbd5e1;padding:12px;border-radius:5px;font:12px/1.8 ui-monospace,Menlo,Consolas,monospace;height:248px;overflow:auto;white-space:pre;tab-size:2}.extm-scope-note{color:#909399;font-size:12px;margin-top:8px}.extm-detail-error{color:#d03050;font-size:12px;white-space:normal;overflow-wrap:anywhere;margin:8px 0}.extm-detail-error:empty{display:none}',
    '.extm-log-legend{display:flex;align-items:center;gap:14px;flex-wrap:wrap;margin:0 0 8px;font-size:11px;color:#7a8492}.extm-log-legend span{display:inline-flex;align-items:center;gap:5px}.extm-log-legend i{width:6px;height:6px;border-radius:50%;background:currentColor}.extm-log-line{display:inline-block;min-width:100%;padding:0 6px 0 8px;border-left:2px solid transparent}.extm-log-time{color:#8794a8}.extm-log-account{color:#9baec4}.extm-log-success{color:#86efac}.extm-log-warn{color:#fcd34d}.extm-log-error{color:#fda4af;border-left-color:#f87171;background:rgba(248,113,113,.06)}.extm-log-progress{color:#93c5fd}.extm-log-info{color:#cbd5e1}.extm-log-legend .success{color:#18a058}.extm-log-legend .warn{color:#d49a24}.extm-log-legend .error{color:#d03050}.extm-log-legend .progress{color:#4e8acf}.extm-log-legend .info{color:#94a0af}',
    '@media(max-width:1200px){.extm-task-layout{grid-template-columns:minmax(0,1fr)}.extm-history-wrap{max-height:180px}}',
    '.extm-fab{position:fixed;right:22px;bottom:74px;z-index:1999;display:inline-flex;align-items:center;gap:7px;padding:10px 16px;border-radius:22px;background:#18a058;color:#fff;font:600 13px system-ui;cursor:pointer;box-shadow:0 6px 16px rgba(24,160,88,.4)}',
  ].join("");

  function injectStyle() { if (document.getElementById("extm-style")) return; var s = document.createElement("style"); s.id = "extm-style"; s.textContent = CSS; (document.head || document.documentElement).appendChild(s); }

  function api(path, opts) {
    opts = opts || {};
    var token = localStorage.getItem(TK) || "";
    var ctrl = new AbortController();
    var to = setTimeout(function () { ctrl.abort(); }, opts.timeout || 30000);
    return fetch((opts.base || "/api/external") + path, {
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
  function toast(type, m) { opMsg(m, type === "error" ? "err" : (type === "success" ? "ok" : "mut")); var a = window.$message; if (a && typeof a[type] === "function") a[type](m); }
  function opMsg(t, c) { var e = el("extm-op"); if (e) { e.className = "extm-msg" + (c ? " " + c : ""); e.textContent = t || ""; } }
  function fmtTime(s) { if (!s) return "—"; var d = new Date(typeof s === "number" ? s * 1000 : (/^\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d(?:\.\d+)?$/.test(s) ? s + "Z" : s)); if (isNaN(d)) return "—"; function p(n){return (n<10?"0":"")+n;} return d.getFullYear() + "-" + p(d.getMonth()+1) + "-" + p(d.getDate()) + " " + p(d.getHours()) + ":" + p(d.getMinutes()); }

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
          '<textarea id="extm-import" class="extm-ta" placeholder="user@example.com----邮箱密码----ClientID(UUID)----M.RefreshToken\n带 Adobe 密码则再加一段:…----M.RefreshToken----AdobePwd\n首次补全账号时会生成并保存独立密码"></textarea>' +
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
          '<div class="extm-batch-controls"><span class="selc">已选 <b id="extm-selc">0</b></span>' +
          '<button class="extm-btn o sm" id="extm-batch-login">批量登录</button>' +
          '<button class="extm-btn del sm" id="extm-batch-del">删除选中</button></div>' +
          '<button class="extm-btn o sm" id="extm-export">导出 Cookie</button>' +
        '</div>' +
        '<div class="extm-tw"><table class="extm-t"><colgroup><col class="extm-select-col" style="width:38px"><col style="width:34px"><col style="width:280px"><col style="width:110px"><col><col style="width:96px"><col style="width:96px"><col style="width:158px"><col style="width:158px"><col style="width:174px"></colgroup><thead><tr>' +
          '<th class="extm-select-cell"><input type="checkbox" id="extm-ckall" aria-label="选择全部账号"></th><th></th>' +
          '<th>邮箱</th><th>积分(可用/总)</th><th>登录状态</th><th>订阅</th><th title="最近一次导入或登录的操作人">操作人</th><th>邮箱导入时间</th><th>最后登录</th><th>操作</th>' +
        '</tr></thead><tbody id="extm-tbody"><tr><td colspan="10" class="extm-empty">加载中…</td></tr></tbody></table></div>' +
      '</div>';

    el("extm-do-import").onclick = doImport;
    el("extm-refresh").onclick = function () { refreshAll(true); };
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

  function jobApi(path, opts) { opts = opts || {}; opts.base = "/api/adobe-accounts/jobs"; return api(path, opts); }
  function spinner() { return '<span class="extm-spin" aria-hidden="true"></span>'; }
  function setLoading(btn, busy, text) { if (!btn) return; btn.disabled = busy; btn.setAttribute("aria-busy", String(busy)); btn.innerHTML = (busy ? spinner() : "") + esc(text); }
  function rowById(id) { return st.rows.find(function (r) { return r.id === id; }); }
  function running(r) { return st.pending.has(r.id) || !!(r.latest_job && r.latest_job.status === "running"); }
  function detailState(id) { return st.details[id] || (st.details[id] = { jobs: [], checked: new Set(), manage: false, closing: false, closeTimer: null, selected: null, job: null, auto: true, scope: "member", loading: false, action: false, error: "" }); }
  function jobPill(job) {
    var m = { running: ["info", "运行中"], done: [job.fail ? "bad" : "ok", job.fail ? (job.success ? "部分失败" : "失败") : "已完成"], error: ["bad", "失败"], cancelled: ["mut", "已停止"] }[job.status] || ["mut", job.status];
    return '<span class="extm-pill ' + m[0] + '">' + esc(m[1]) + '</span>';
  }
  function setHTML(node, html) { if (node && node._html !== html) { node.innerHTML = html; node._html = html; } }
  function setText(node, value) { if (node && node.textContent !== String(value)) node.textContent = value; }

  function load(silent) {
    var body = el("extm-tbody"); if (!body) return Promise.resolve();
    var seq = ++st.loadSeq;
    if (!st.rows.length && !silent) body.innerHTML = '<tr><td colspan="10" class="extm-empty">加载中…</td></tr>';
    return api("/members?" + qs().concat(["size=1000"]).join("&")).then(function (d) {
      if (seq !== st.loadSeq) return;
      st.rows = d.items || [];
      var visible = new Set(st.rows.map(function (r) { return r.id; }));
      st.sel.forEach(function (id) { if (!visible.has(id)) st.sel.delete(id); });
      setText(el("extm-total"), d.total != null ? d.total : st.rows.length);
      renderRows();
    }).catch(function (e) {
      if (seq !== st.loadSeq) return;
      if (!st.rows.length) body.innerHTML = '<tr><td colspan="10" class="extm-empty" style="color:#d03050">' + esc(e.message) + '</td></tr>';
      else opMsg("刷新失败: " + e.message + "，当前显示上次结果", "err");
    });
  }

  async function refreshAll(force) {
    if (st.polling) return;
    st.polling = true;
    try {
      await load(true);
      await Promise.all(Array.from(st.expanded).filter(function (id) { return rowById(id) && (force || detailState(id).auto); }).map(function (id) { return refreshDetail(id); }));
    } finally { st.polling = false; }
  }

  function renderRows() {
    var body = el("extm-tbody"); if (!body) return;
    if (!st.rows.length) { body.innerHTML = '<tr><td colspan="10" class="extm-empty">暂无匹配的外部子号</td></tr>'; updSel(); return; }
    Array.prototype.forEach.call(body.querySelectorAll(":scope > tr"), function (tr) {
      var id = Number(tr.dataset.member || tr.dataset.detail);
      if (!rowById(id) || (tr.dataset.detail && !st.expanded.has(id) && !detailState(id).closing)) tr.remove();
    });
    // Keep unchanged rows attached in place so polling cannot interrupt a fold transition.
    var cursor = body.firstElementChild;
    st.rows.forEach(function (r) {
      var tr = body.querySelector('tr[data-member="' + r.id + '"]');
      if (!tr) { tr = document.createElement("tr"); tr.dataset.member = r.id; }
      var busy = running(r), expanded = st.expanded.has(r.id);
      tr.className = expanded ? "extm-expanded" : "";
      var message = busy ? (st.pending.has(r.id) ? "正在提交任务…" : "任务 #" + r.latest_job.id + " · 展开查看实时进度") : r.message;
      setHTML(tr,
        '<td class="extm-select-cell"><input type="checkbox" class="extm-rowck" data-id="' + r.id + '" aria-label="选择 ' + esc(r.email) + '"' + (st.sel.has(r.id) ? ' checked' : '') + '></td>' +
        '<td><button class="extm-link extm-toggle" data-expand="' + r.id + '" aria-label="' + (expanded ? '收起' : '展开') + ' ' + esc(r.email) + ' 的任务详情" aria-expanded="' + expanded + '" aria-controls="extm-detail-' + r.id + '">' + window.OKAD_ICONS.svg('chevron', 16) + '</button></td>' +
        '<td><button class="extm-link extm-clip extm-email" data-expand="' + r.id + '" title="' + esc(r.email) + '">' + esc(r.email) + '</button></td>' +
        '<td>' + creditCell(r) + '</td>' +
        '<td><div class="extm-status">' +
          '<span class="extm-cap ' + (r.has_cookie ? 'ok' : 'no') + '">' + (r.has_cookie ? '有 Cookie' : '无 Cookie') + '</span>' +
          '<span class="extm-cap ' + (r.has_adobe_password ? 'ok' : 'no') + '" title="Adobe 密码">' + (r.has_adobe_password ? '有密码' : '无密码') + '</span>' +
          (busy ? '<span class="extm-pill warn">登录中</span>' : r.login_status === 'ok' ? '<button class="extm-pill ok extm-success" data-expand="' + r.id + '" title="' + esc(r.message || '登录成功，展开查看任务详情') + '">' + window.OKAD_ICONS.svg('check', 14) + '登录成功</button>' : statusPill(r.login_status)) +
          (!busy && r.login_status === 'ok' && (!message || message.trim() === '登录成功') ? '' : '<button class="extm-link extm-clip" data-expand="' + r.id + '" title="' + esc(message || "展开查看任务详情") + '">' + esc(message || "展开查看详情") + '</button>') + '</div></td>' +
        '<td>' + subPill(r) + '</td>' +
        '<td><span class="extm-clip" title="' + esc(r.operator || "历史记录未记录操作人") + '">' + esc(r.operator || "—") + '</span></td>' +
        '<td class="cr">' + esc(fmtTime(r.created_at)) + '</td><td class="cr">' + esc(fmtTime(r.last_login_at)) + '</td>' +
        '<td><div class="extm-actions"><button class="extm-btn o sm" data-login="' + r.id + '" aria-busy="' + busy + '"' + (busy ? ' disabled' : '') + '>' + (busy ? spinner() + (st.pending.has(r.id) ? '提交中' : '登录中') : '重登') + '</button>' +
        '<button class="extm-btn del sm" data-del="' + r.id + '"' + (busy ? ' disabled' : '') + '>删除</button></div></td>');
      var cb = tr.querySelector(".extm-rowck"); cb.checked = st.sel.has(r.id);
      if (tr !== cursor) body.insertBefore(tr, cursor);
      cursor = tr.nextElementSibling;
      if (expanded || detailState(r.id).closing) {
        var fresh = false;
        var detail = body.querySelector('tr[data-detail="' + r.id + '"]');
        if (!detail) { fresh = true; detail = document.createElement("tr"); detail.dataset.detail = r.id; detail.className = "extm-detail-row"; detail.innerHTML = '<td><div class="extm-fold is-closed"><div class="extm-fold-clip"><div class="extm-detail" id="extm-detail-' + r.id + '"></div></div></div></td>'; }
        detail.firstElementChild.colSpan = 10;
        if (detail !== cursor) body.insertBefore(detail, cursor);
        cursor = detail.nextElementSibling;
        renderDetail(r.id);
        if (expanded) {
          var state = detailState(r.id), fold = detail.querySelector('.extm-fold');
          clearTimeout(state.closeTimer); state.closing = false;
          if (fresh) fold.getBoundingClientRect();
          fold.classList.remove('is-closed'); fold.removeAttribute('aria-hidden'); fold.inert = false;
        }
      }
    });
    body.onchange = function (e) {
      if (!e.target.matches(".extm-rowck")) return;
      var id = Number(e.target.dataset.id); if (e.target.checked) st.sel.add(id); else st.sel.delete(id); updSel();
    };
    body.onclick = function (e) {
      var b = e.target.closest("button"); if (!b || b.disabled) return;
      if (b.hasAttribute("data-expand")) toggleDetail(Number(b.dataset.expand));
      if (b.hasAttribute("data-login")) reloginOne(Number(b.dataset.login));
      if (b.hasAttribute("data-del")) doDelete([Number(b.dataset.del)]);
    };
    updSel();
  }

  function toggleDetail(id) {
    var d = detailState(id), panel = el('extm-detail-' + id);
    clearTimeout(d.closeTimer);
    if (st.expanded.has(id) && panel) {
      st.expanded.delete(id); d.closing = true;
      var row = panel.closest('tr[data-detail]'), fold = panel.closest('.extm-fold');
      renderRows();
      fold.getBoundingClientRect();
      fold.classList.add('is-closed');
      fold.setAttribute('aria-hidden', 'true'); fold.inert = true;
      var finish = function () {
        if (st.expanded.has(id)) return;
        d.closing = false; row.remove();
      };
      d.closeTimer = setTimeout(finish, window.matchMedia('(prefers-reduced-motion: reduce)').matches ? 0 : 300);
    } else {
      st.expanded.add(id); d.closing = false;
      renderRows();
      var openFold = el('extm-detail-' + id).closest('.extm-fold');
      openFold.classList.remove('is-closed'); openFold.removeAttribute('aria-hidden'); openFold.inert = false;
      refreshDetail(id, true);
    }
  }

  function logLevel(line) {
    // Failure counts of zero in task summaries are not errors.
    if (/✗|×|失败(?!\s*[:：=]?\s*0(?:\D|$))|错误|异常|(?:^|[\s\[])(?:ERROR|FATAL|EXCEPTION)(?:[\s\]:]|$)|\b(?:HTTP|status)[\s=:]+[45]\d{2}\b/i.test(line)) return 'error';
    if (/⚠|警告|\bWARN(?:ING)?\b|超时|重试|限流|掉订阅|额度.*偏低|不可用|未能|无可用/i.test(line)) return 'warn';
    if (/✓|✔|成功|已完成|完成[:：]/.test(line)) return 'success';
    if (/开始|正在|等待|扫描|发送|获取|读取|刷新/.test(line)) return 'progress';
    return 'info';
  }
  function renderLogLine(line) {
    var level = logLevel(line), time = /^(\d{2}:\d{2}:\d{2})(\s+)([\s\S]*)$/.exec(line);
    var body = esc(time ? time[3] : line).replace(/\[[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\]/g, '<span class="extm-log-account">$&</span>');
    return '<span class="extm-log-line extm-log-' + level + '" data-level="' + level + '">' +
      (time ? '<span class="extm-log-time">' + time[1] + '</span>' + time[2] : '') + body + '</span>';
  }

  function renderDetail(id) {
    var panel = el("extm-detail-" + id), row = rowById(id); if (!panel || !row) return;
    var d = detailState(id);
    if (!panel.dataset.ready) {
      panel.dataset.ready = "1";
      panel.innerHTML = '<div class="extm-detail-error" role="status"></div><div class="extm-task-layout">' +
        '<section class="extm-task-card"><div class="extm-task-head"><strong>任务历史</strong><span class="sp"></span><button class="extm-btn dft sm" data-action="manage" aria-pressed="false">管理历史</button><button class="extm-btn del sm" data-action="delete">删除选中</button></div>' +
        '<div class="extm-history-wrap"><table class="extm-history"><colgroup><col class="extm-history-select" style="width:30px"><col style="width:48px"><col style="width:92px"><col style="width:55px"><col style="width:65px"><col></colgroup>' +
        '<thead><tr><th class="extm-history-select"></th><th>ID</th><th>状态</th><th>进度</th><th>操作人</th><th>时间</th></tr></thead><tbody></tbody></table></div></section>' +
        '<section class="extm-task-card"><div class="extm-task-head"><strong>任务详情</strong><div class="extm-task-actions"><label class="extm-auto"><input type="checkbox" data-auto checked>自动刷新</label><button class="extm-btn dft sm" data-action="refresh">刷新</button><button class="extm-btn del sm" data-action="cancel">停止任务</button></div></div>' +
        '<div class="extm-task-body"><div class="extm-job-title"></div><div class="extm-job-meta"></div><div class="extm-counts"></div><div class="extm-progress" role="progressbar" aria-label="任务进度"><div></div></div><div class="extm-detail-error extm-job-error"></div>' +
        '<div class="extm-log-tools"><span data-log-count>实时日志</span><span class="sp"></span><select class="extm-in" data-log-scope aria-label="日志范围"><option value="member">当前账号日志</option><option value="all">整批任务日志</option></select><button class="extm-btn dft sm" data-action="clear-logs">清空日志</button></div>' +
        '<div class="extm-log-legend" aria-label="日志颜色说明"><span><i class="success"></i>成功</span><span><i class="warn"></i>警告</span><span><i class="error"></i>错误</span><span><i class="progress"></i>进度</span><span><i class="info"></i>普通</span></div><pre class="extm-logs" tabindex="0" aria-label="任务日志"></pre><div class="extm-scope-note"></div></div></section></div>';
      panel.onclick = function (e) {
        var action = e.target.closest("[data-action]");
        if (action && !action.disabled) { taskAction(id, action.dataset.action); return; }
        var tr = e.target.closest("tr[data-job]");
        if (tr && !e.target.matches("input")) { d.selected = Number(tr.dataset.job); renderDetail(id); refreshDetail(id, true); }
      };
      panel.onchange = function (e) {
        if (e.target.hasAttribute("data-job-check")) { var jid = Number(e.target.dataset.jobCheck); if (e.target.checked) d.checked.add(jid); else d.checked.delete(jid); renderDetail(id); }
        if (e.target.hasAttribute("data-auto")) { d.auto = e.target.checked; if (d.auto) refreshDetail(id, true); }
        if (e.target.hasAttribute("data-log-scope")) { d.scope = e.target.value; renderDetail(id); }
      };
    }
    panel.classList.toggle('extm-manage-history', d.manage);
    var manage = panel.querySelector('[data-action="manage"]');
    manage.setAttribute('aria-pressed', String(d.manage));
    setText(manage, d.manage ? '结束管理' : '管理历史');
    setText(panel.querySelector(":scope > .extm-detail-error"), d.error);
    var history = panel.querySelector(".extm-history tbody");
    setHTML(history, d.jobs.length ? d.jobs.map(function (j) {
      return '<tr data-job="' + j.id + '" class="' + (j.id === d.selected ? 'active' : '') + '" aria-selected="' + (j.id === d.selected) + '">' +
        '<td class="extm-history-select"><input type="checkbox" data-job-check="' + j.id + '" aria-label="选择任务 #' + j.id + '"' + (d.checked.has(j.id) ? ' checked' : '') + (j.status === 'running' ? ' disabled' : '') + '></td>' +
        '<td><button class="extm-link" title="查看任务 #' + j.id + '">#' + j.id + '</button></td><td>' + jobPill(j) + '</td>' +
        '<td title="成功 ' + j.success + '，失败 ' + j.fail + '">' + (j.success + j.fail) + '/' + j.target + '</td>' +
        '<td title="' + esc(j.operator || '历史记录未记录操作人') + '">' + esc(j.operator || '—') + '</td><td title="' + esc(fmtTime(j.created_at)) + '">' + esc(fmtTime(j.created_at).slice(5)) + '</td></tr>';
    }).join("") : '<tr><td colspan="' + (d.manage ? 6 : 5) + '" class="extm-empty">' + (d.loading ? '正在读取任务…' : '暂无关联任务，点击重登开始') + '</td></tr>');
    panel.querySelector("[data-auto]").checked = d.auto;
    panel.querySelector("[data-log-scope]").value = d.scope;
    var job = d.job && d.job.id === d.selected ? d.job : d.jobs.find(function (j) { return j.id === d.selected; });
    var selectedJobs = d.jobs.filter(function (j) { return d.checked.has(j.id) && j.status !== "running"; });
    var del = panel.querySelector('[data-action="delete"]'); del.disabled = !selectedJobs.length || d.action; setText(del, '删除选中 (' + selectedJobs.length + ')');
    panel.querySelector('[data-action="refresh"]').disabled = d.loading || d.action;
    panel.querySelector('[data-action="cancel"]').disabled = !job || job.status !== 'running' || d.action;
    panel.querySelector('[data-action="clear-logs"]').disabled = !job || !job.log_total || d.action;
    setHTML(panel.querySelector(".extm-job-title"), job ? '<strong>外部子号登录 · #' + job.id + '</strong>' + jobPill(job) : '<span class="extm-msg mut">' + (d.loading ? '正在加载…' : '选择历史任务查看详情') + '</span>');
    setHTML(panel.querySelector(".extm-job-meta"), job ? '<span>操作人 <b>' + esc(job.operator || '—') + '</b></span><span>开始 <b>' + esc(fmtTime(job.created_at)) + '</b></span>' + (job.finished_at ? '<span>结束 <b>' + esc(fmtTime(job.finished_at)) + '</b></span>' : '') : '');
    var pct = job && job.target ? Math.min(100, Math.round((job.success + job.fail) / job.target * 100)) : 0;
    var progress = panel.querySelector('.extm-progress'); progress.setAttribute('aria-valuenow', pct); progress.setAttribute('aria-valuemin', '0'); progress.setAttribute('aria-valuemax', '100');
    progress.firstElementChild.style.width = pct + '%'; progress.firstElementChild.className = job && (job.fail || job.status === 'error') ? 'failed' : '';
    setHTML(panel.querySelector('.extm-counts'), job ? '<span>总进度 <b>' + (job.success + job.fail) + '/' + job.target + '</b></span><span class="extm-count-success">成功 <b>' + job.success + '</b></span><span class="' + (job.fail ? 'extm-count-fail' : 'extm-count-zero') + '">失败 <b>' + job.fail + '</b></span>' : '');
    setText(panel.querySelector('.extm-job-error'), job ? job.error || '' : '');
    var lines = job && job.logs || [];
    if (d.scope === 'member') lines = lines.filter(function (line) { return line.toLowerCase().includes(row.email.toLowerCase()) || line.includes('[id=' + id + ']') || !(/[\w.+-]+@[\w.-]+\.[a-z]{2,}|\[id=\d+\]/i.test(line)); });
    setText(panel.querySelector('[data-log-count]'), '实时日志 · ' + lines.length + ' / ' + (job ? job.log_total : 0) + ' 条');
    var logs = panel.querySelector('.extm-logs'), text = lines.join('\n') || (d.loading && (!d.job || d.job.id !== d.selected) ? '正在读取日志…' : '暂无日志');
    if (logs.textContent !== text) { var bottom = logs.scrollHeight - logs.scrollTop - logs.clientHeight < 35, top = logs.scrollTop; logs.innerHTML = lines.length ? lines.map(renderLogLine).join('\n') : esc(text); logs.scrollTop = bottom ? logs.scrollHeight : top; }
    setText(panel.querySelector('.extm-scope-note'), job && job.target > 1 ? '此任务包含 ' + job.target + ' 个账号；进度、停止、清空日志和删除均作用于整批任务。' : '任务历史显示最近 50 条，可在此查看完整日志和登录结果。');
  }

  function refreshDetail(id, force) {
    var d = detailState(id);
    if (d.loading) return d.promise.then(function () { if (force) return refreshDetail(id); });
    d.loading = true; d.error = ''; renderDetail(id);
    d.promise = api('/members/' + id + '/jobs?limit=50').then(function (jobs) {
      d.jobs = jobs;
      d.checked.forEach(function (jid) { if (!jobs.some(function (j) { return j.id === jid && j.status !== 'running'; })) d.checked.delete(jid); });
      if (!jobs.some(function (j) { return j.id === d.selected; })) d.selected = jobs.length ? jobs[0].id : null;
      renderDetail(id);
      var selected = d.selected;
      if (!selected) { d.job = null; return; }
      return jobApi('/' + selected).then(function (job) { if (selected === d.selected) d.job = job; });
    }).catch(function (e) { d.error = '任务刷新失败: ' + e.message; }).finally(function () { d.loading = false; renderDetail(id); });
    return d.promise;
  }

  async function taskAction(id, action) {
    var d = detailState(id);
    if (d.action) return;
    if (action === 'manage') { d.manage = !d.manage; d.checked.clear(); renderDetail(id); return; }
    if (action === 'refresh') { await load(true); await refreshDetail(id, true); return; }
    var ids = action === 'delete' ? d.jobs.filter(function (j) { return d.checked.has(j.id) && j.status !== 'running'; }).map(function (j) { return j.id; }) : [d.selected];
    if (!ids.length || !ids[0]) return;
    var shared = d.jobs.some(function (j) { return ids.includes(j.id) && j.target > 1; });
    var verb = { delete: '删除任务及其日志', cancel: '停止任务（已开始的账号会完成当前登录步骤）', 'clear-logs': '清空日志' }[action];
    if (!confirm('确认' + verb + '？' + (shared ? '这些操作会影响同一批次中的所有账号。' : ''))) return;
    d.action = true; renderDetail(id);
    try {
      var result = await jobApi(action === 'delete' ? '/batch-delete' : '/' + ids[0] + '/' + action, { method: 'POST', body: action === 'delete' ? { ids: ids } : undefined });
      if (result.success === false) throw new Error(result.message);
      toast('success', result.message || '操作完成');
      if (action === 'delete') { d.checked.clear(); d.job = null; }
      await load(true);
      await Promise.all(Array.from(st.expanded).filter(rowById).map(function (mid) { return refreshDetail(mid, true); }));
    } catch (e) { d.error = e.message; toast('error', e.message); }
    finally { d.action = false; renderDetail(id); }
  }

  function updSel() {
    setText(el('extm-selc'), st.sel.size);
    var all = el('extm-ckall'); if (all) { all.checked = !!st.rows.length && st.sel.size === st.rows.length; all.indeterminate = st.sel.size > 0 && st.sel.size < st.rows.length; }
    var busy = st.rows.some(function (r) { return st.sel.has(r.id) && running(r); });
    setLoading(el('extm-batch-login'), busy, busy ? '登录中' : '批量登录');
    if (el('extm-batch-del')) el('extm-batch-del').disabled = busy;
  }
  function selIds() { return Array.from(st.sel); }

  async function doImport() {
    var ta = el('extm-import'), btn = el('extm-do-import'), content = (ta && ta.value || '').trim();
    if (!content) { opMsg('请粘贴要导入的子号', 'err'); return; }
    setLoading(btn, true, '导入中'); opMsg('导入中…', 'mut');
    try {
      var r = await api('/members/import', { method: 'POST', body: { content: content, on_duplicate: el('extm-dup').value } });
      var msg = '导入完成: 新增 ' + r.created + ' · 更新 ' + r.updated + ' · 跳过 ' + r.skipped + ' · 失败 ' + r.failed;
      if (r.job_id) msg += ' · 登录任务 #' + r.job_id + '，展开账号行查看进度和日志';
      opMsg(msg, r.failed ? 'err' : 'ok'); ta.value = ''; await load(true);
      var first = st.rows.find(function (row) { return row.latest_job && (r.job_ids || [r.job_id]).includes(row.latest_job.id); });
      if (first) { st.expanded.add(first.id); detailState(first.id).selected = first.latest_job.id; renderRows(); await refreshDetail(first.id, true); }
    } catch (e) { opMsg(e.message, 'err'); }
    finally { setLoading(btn, false, '批量导入'); }
  }

  async function startLogin(ids) {
    if (ids.some(function (id) { var row = rowById(id); return row && running(row); })) { toast('warning', '所选账号正在登录，请等待任务完成'); return; }
    ids.forEach(function (id) { st.pending.add(id); });
    ++st.loadSeq; renderRows();
    try {
      var job = await api('/members/batch-login', { method: 'POST', body: { ids: ids } });
      ids.forEach(function (id) { var row = rowById(id); if (row) row.latest_job = job; });
      st.expanded.add(ids[0]); detailState(ids[0]).selected = job.id;
      toast('success', '已提交登录任务 #' + job.id + '，可在行内查看进度和日志');
    } catch (e) { toast('error', e.message); }
    finally { ids.forEach(function (id) { st.pending.delete(id); }); renderRows(); await load(true); }
    if (st.expanded.has(ids[0])) await refreshDetail(ids[0], true);
  }
  function reloginOne(id) { return startLogin([id]); }
  function batchLogin() {
    var ids = selIds(); if (!ids.length) { toast('warning', '请先勾选账号'); return; }
    return startLogin(ids);
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
  function positionPanel(w) {
    var r = window.OKAD_NAV.rect(); w.style.left = r.left + "px"; w.style.top = r.top + "px";
    w.style.setProperty("--extm-detail-width", Math.max(320, window.innerWidth - r.left - 86) + "px");
  }
  function show() {
    injectStyle();
    var w = el(HOST_ID);
    if (!w) { w = document.createElement("div"); w.id = HOST_ID; document.body.appendChild(w); buildBody(w); }
    positionPanel(w); w.classList.add("on"); st.open = true; refreshAll(false);
  }
  function hide() { var w = el(HOST_ID); if (w) w.classList.remove("on"); st.open = false; }
  window.OKAD_NAV.register({
    id: NAV_ID, panel: HOST_ID, label: "外部子号", icon: "external", first: true,
    open: show, close: hide,
    layout: function () { var w = el(HOST_ID); if (w) positionPanel(w); }
  });

  setInterval(function () {
    if (st.open && !document.hidden) refreshAll(false);
  }, 3000);

})();
