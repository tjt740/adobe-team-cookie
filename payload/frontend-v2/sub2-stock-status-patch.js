/* sub2-stock-status-patch.js
 * 在「号池」(/pool) 和「母号」(/adobe 成员抽屉) 的表格里,给每个子号行打一个
 * 「在库 Sub2 / 未推送」标签 —— 直接看出这个号推没推过、在不在下游 Sub2 网关。
 * 判定来自后端 GET /api/sub2/pool-membership(按 account_id/邮箱真实比对,权威),
 * 前端只按行邮箱去匹配。网关不可达时后端返回 ok:false,本补丁不打标(中性态),
 * 并在号池页给一条「Sub2 未连接」提示,避免把所有号误标成未推送。
 */
(function () {
  if (window.__sub2StockPatch) return;
  window.__sub2StockPatch = true;

  var PILL = "data-s2stock";
  var TTL = 60000;
  var cache = { at: 0, ok: false, set: null, msg: "" };
  var fetching = null;
  var pending = false;

  function token() { return localStorage.getItem("okad_token") || ""; }
  function path() { return location.pathname.replace(/\/+$/, ""); }
  function onTarget() { var p = path(); return p === "/pool" || p === "/adobe"; }
  function isPool() { return path() === "/pool"; }

  var EMAIL_RE = /[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}/;

  function fetchData() {
    if (fetching) return fetching;
    fetching = fetch("/api/sub2/pool-membership", { headers: { Authorization: "Bearer " + token() } })
      .then(function (r) { return r.json(); })
      .then(function (j) {
        cache = { at: Date.now(), ok: !!j.ok, msg: j.message || "",
                  set: new Set((j.in_sub2 || []).map(function (e) { return String(e).toLowerCase(); })) };
      })
      .catch(function () { cache = { at: Date.now(), ok: false, msg: "网络错误", set: new Set() }; })
      .finally(function () { fetching = null; clearPills(); });
    return fetching;
  }

  function ensureData() {
    if (cache.at && Date.now() - cache.at < TTL) return Promise.resolve();
    return fetchData();
  }

  function clearPills() {
    document.querySelectorAll("[" + PILL + "]").forEach(function (n) { n.remove(); });
    var note = document.getElementById("s2stock-note");
    if (note) note.remove();
  }

  function pill(text, kind) {
    var s = document.createElement("span");
    s.setAttribute(PILL, "1");
    s.textContent = text;
    var green = kind === "in";
    s.style.cssText =
      "display:inline-block;margin-left:6px;padding:0 7px;border-radius:9px;font-size:11px;" +
      "line-height:18px;vertical-align:middle;white-space:nowrap;font-weight:500;" +
      (green
        ? "background:#e7f6ee;color:#18a058;border:1px solid #b7e3ca;"
        : "background:#f2f3f5;color:#909399;border:1px solid #e3e5e8;");
    return s;
  }

  function emailCellOf(tr) {
    var account = tr.querySelector('[data-pool-email]');
    if (account) return {cell: tr.querySelector('[data-pool-stock]') || account.parentElement,
      email: account.getAttribute('data-pool-email').toLowerCase()};
    var cells = tr.querySelectorAll("td, .n-data-table-td");
    for (var i = 0; i < cells.length; i++) {
      var m = (cells[i].textContent || "").trim().match(EMAIL_RE);
      if (m) return { cell: cells[i], email: m[0].toLowerCase() };
    }
    return null;
  }

  function isMasterRow(tr) {
    var cells = tr.querySelectorAll("td, .n-data-table-td");
    for (var i = 0; i < cells.length; i++) {
      var t = (cells[i].textContent || "").trim();
      if (t === "母号" || t === "主号") return true;
    }
    return false;
  }

  function inDrawer(tr) { return !!tr.closest(".n-drawer, .n-modal"); }

  function notice(msg) {
    if (!isPool() || document.getElementById("s2stock-note")) return;
    var host = document.querySelector(".n-data-table") || document.querySelector("table");
    if (!host || !host.parentElement) return;
    var d = document.createElement("div");
    d.id = "s2stock-note";
    d.textContent = "⚠ " + msg + " —— Sub2 库存状态暂不可用";
    d.style.cssText =
      "margin:0 0 8px;padding:6px 12px;border-radius:6px;font-size:12.5px;" +
      "background:#fff7e6;color:#d48806;border:1px solid #ffe0a3;";
    host.parentElement.insertBefore(d, host);
  }

  function annotate() {
    if (!onTarget()) return;
    if (!cache.at) return;
    if (!cache.ok) { notice(cache.msg || "Sub2 未连接"); return; }
    var pool = isPool();
    var trs = document.querySelectorAll(".n-data-table-tbody .n-data-table-tr, tbody tr");
    trs.forEach(function (tr) {
      // 外部子号有独立的账号/任务表,不能按日志里的邮箱给整个详情打库存标签。
      if (tr.closest("#extm-embed")) return;
      var found = emailCellOf(tr);
      if (!found) return;
      if (found.cell.querySelector("[" + PILL + "]")) return;       // 本格已打标
      if (isMasterRow(tr)) return;                                   // 母号镜像行不打标
      var isSub = pool || inDrawer(tr);                             // 号池行都是子号;母号页只在抽屉里
      var inStock = cache.set.has(found.email);
      if (inStock) found.cell.appendChild(pill("在库 Sub2", "in"));
      else if (isSub) found.cell.appendChild(pill("未推送", "out"));
    });
  }

  function schedule() {
    if (pending) return;
    pending = true;
    setTimeout(function () {
      pending = false;
      if (!onTarget()) return;
      ensureData().then(annotate);
    }, 140);
  }

  var _push = history.pushState, _replace = history.replaceState;
  history.pushState = function () { var r = _push.apply(this, arguments); schedule(); return r; };
  history.replaceState = function () { var r = _replace.apply(this, arguments); schedule(); return r; };
  window.addEventListener("popstate", schedule);
  window.addEventListener("okad:sub2-stock-changed", function () {
    cache.at = 0;
    clearPills();
    schedule();
  });
  new MutationObserver(schedule).observe(document.documentElement, { childList: true, subtree: true });
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", schedule);
  else schedule();
})();
