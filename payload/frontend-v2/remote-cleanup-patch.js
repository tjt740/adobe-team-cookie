(function () {
  const BUTTON_ID = "okad-remote-cleanup-button";
  const MISSING_BUTTON_ID = "okad-remote-missing-button";
  const CREDIT_BUTTON_ID = "okad-credit-refresh-button";
  const EMPTY_BUTTON_ID = "okad-empty-credit-remove-button";
  const ALL_CHILDREN_BUTTON_ID = "okad-all-children-cleanup-button";
  const REMOTE_ALL_BUTTON_ID = "okad-remote-all-delete-button";
  const LOCAL_ALL_BUTTON_ID = "okad-local-all-delete-button";
  const BATCH_LOGIN_BUTTON_ID = "okad-batch-login-button";
  const SELECTED_ALL_BUTTON_ID = "okad-selected-all-children-cleanup-button";
  const IMPORT_POOL_BUTTON_ID = "okad-import-pool-button";
  const POOL_API_SETTINGS_ID = "okad-pool-api-settings";
  const REPORT_ID = "okad-remote-cleanup-report";
  const TOKEN_KEY = "okad_token";
  const API_TIMEOUT_MS = 300000;
  const MEMBER_PAGE_SIZE = 200;
  const CREDIT_REFRESH_CONCURRENCY = 3;
  const EXPECTED_CREDITS = 4000;

  const text = {
    button: "\u6e05\u7406\u8fdc\u7a0b\u5360\u4f4d",
    missingButton: "\u67e5\u770b\u8fdc\u7a0b\u7f3a\u5931",
    creditButton: "\u6279\u91cf\u5237\u65b0\u4f59\u989d",
    emptyButton: "\u6e05\u9000\u65e0\u4f59\u989d",
    allChildrenButton: "\u6e05\u9000\u6240\u6709\u5b50\u53f7",
    remoteAllButton: "\u5220\u9664\u8fdc\u7a0b\u6240\u6709\u5b50\u53f7",
    localAllButton: "\u5220\u9664\u672c\u5730\u6240\u6709\u5b50\u53f7",
    batchLoginButton: "\u6279\u91cf\u767b\u5f55",
    selectedAllButton: "\u6e05\u9000\u6240\u6709\u5b50\u53f7",
    importPoolButton: "\u6279\u91cf\u66f4\u65b0\u53f7\u6c60",
    loading: "\u6e05\u7406\u4e2d...",
    loadingMissing: "\u83b7\u53d6\u4e2d...",
    loadingCredits: "\u5237\u65b0\u4e2d...",
    loadingEmpty: "\u6e05\u9000\u4e2d...",
    noEmail: "\u6ca1\u6709\u8bc6\u522b\u5230\u5f53\u524d\u6bcd\u53f7\u90ae\u7bb1",
    noAccount: "\u6ca1\u6709\u627e\u5230\u6bcd\u53f7: ",
    noMembers: "\u5f53\u524d\u6bcd\u53f7\u6ca1\u6709\u672c\u5730\u5b50\u8d26\u53f7",
    noCandidates: "\u8fdc\u7a0b\u6ca1\u6709\u53ef\u6e05\u7406\u5360\u4f4d",
    requestFailed: "\u8bf7\u6c42\u5931\u8d25: HTTP ",
    cleanupFailed: "\u6e05\u7406\u8fdc\u7a0b\u5360\u4f4d\u5931\u8d25",
    creditFailed: "\u5237\u65b0\u4f59\u989d\u5931\u8d25",
    emptyFailed: "\u6e05\u9000\u65e0\u4f59\u989d\u5931\u8d25",
    jobStartFailed: "\u521b\u5efa\u6e05\u9000\u4efb\u52a1\u5931\u8d25",
    batchLoginFailed: "\u521b\u5efa\u6279\u91cf\u767b\u5f55\u4efb\u52a1\u5931\u8d25",
    importPoolFailed: "\u521b\u5efa\u6279\u91cf\u66f4\u65b0\u53f7\u6c60\u4efb\u52a1\u5931\u8d25",
    done: "\u8fdc\u7a0b\u5360\u4f4d\u6e05\u7406\u5b8c\u6210",
    creditDone: "\u4f59\u989d\u5237\u65b0\u5b8c\u6210",
    emptyDone: "\u65e0\u4f59\u989d\u6e05\u9000\u5b8c\u6210",
    jobStarted: "\u5df2\u521b\u5efa\u6e05\u9000\u4efb\u52a1,\u524d\u5f80\u4efb\u52a1\u5217\u8868\u67e5\u770b\u8fdb\u5ea6",
    noSelectedAdmin: "\u8bf7\u5148\u52fe\u9009\u8981\u6e05\u9000\u7684\u6bcd\u53f7",
    noSelectedLoginAdmin: "\u8bf7\u5148\u52fe\u9009\u8981\u767b\u5f55\u7684\u6bcd\u53f7",
    noSelectedImportAdmin: "\u8bf7\u5148\u52fe\u9009\u8981\u66f4\u65b0\u53f7\u6c60\u7684\u6bcd\u53f7",
    confirmTitle: "\u5f53\u524d\u6bcd\u53f7: ",
    remoteTotal: "\u8fdc\u7a0b\u6210\u5458: ",
    localTotal: "\u672c\u5730\u5b50\u8d26\u53f7: ",
    candidates: "\u53ef\u6e05\u7406\u8fdc\u7a0b\u5360\u4f4d: ",
    confirmBody:
      "\u6e05\u7406\u5bf9\u8c61\u662f\u8fdc\u7a0b\u5b58\u5728\u3001\u4f46\u672c\u5730\u5217\u8868\u6ca1\u6709\u8bb0\u5f55\u6216\u672c\u5730\u975e\u53ef\u7528 4000 \u989d\u5ea6\u7684\u6210\u5458\u3002\u786e\u8ba4\u6267\u884c\u6e05\u7406\uff1f",
    emptyConfirmBody:
      "\u4f1a\u5148\u5237\u65b0\u5f53\u524d\u6bcd\u53f7\u4e0b\u6240\u6709\u672c\u5730\u5b50\u8d26\u53f7\u7684\u4f59\u989d\u3002\u4f59\u989d\u4e3a 0 \u6216\u4e0d\u662f 4000 \u7684\u53f7\u4f1a\u4ece\u8fdc\u7a0b\u7ec4\u7ec7\u79fb\u9664\uff0c\u5e76\u540c\u6b65\u5220\u9664\u672c\u5730\u53f7\u6c60/\u90ae\u7bb1\u6c60\u8bb0\u5f55\u3002\u4f59\u989d\u65e0\u6cd5\u786e\u8ba4\u7684\u4e0d\u4f1a\u5220\u9664\u3002\u786e\u8ba4\u6267\u884c\uff1f",
    allConfirmBody:
      "\u5c06\u521b\u5efa\u540e\u53f0\u4efb\u52a1:\u5148\u5220\u9664 Adobe \u8fdc\u7a0b\u7ec4\u7ec7\u91cc\u7684\u6240\u6709\u5b50\u53f7,\u8fdc\u7a0b\u5168\u90e8\u6210\u529f\u540e\u518d\u5220\u9664\u672c\u5730\u6240\u6709\u5b50\u53f7\u8bb0\u5f55\u3002\u786e\u8ba4\u6267\u884c\uff1f",
    remoteAllConfirmBody:
      "\u5c06\u521b\u5efa\u540e\u53f0\u4efb\u52a1,\u5220\u9664 Adobe \u8fdc\u7a0b\u7ec4\u7ec7\u91cc\u7684\u6240\u6709\u5b50\u53f7,\u4e0d\u5220\u9664\u672c\u5730\u8bb0\u5f55\u3002\u786e\u8ba4\u6267\u884c\uff1f",
    localAllConfirmBody:
      "\u5c06\u521b\u5efa\u540e\u53f0\u4efb\u52a1,\u53ea\u5220\u9664\u672c\u5730\u6240\u6709\u5b50\u53f7\u8bb0\u5f55,\u4e0d\u64cd\u4f5c Adobe \u8fdc\u7a0b\u7ec4\u7ec7\u3002\u786e\u8ba4\u6267\u884c\uff1f",
    reportTitle: "\u8fdc\u7a0b\u5360\u4f4d\u6e05\u7406\u62a5\u544a",
    missingTitle: "\u8fdc\u7a0b\u6210\u5458\u5bf9\u6bd4\u62a5\u544a",
    creditTitle: "\u4f59\u989d\u5237\u65b0\u62a5\u544a",
    emptyTitle: "\u65e0\u4f59\u989d\u6e05\u9000\u62a5\u544a",
    remoteOnly: "\u8fdc\u7a0b\u6709 / \u672c\u5730\u6ca1\u6709",
    localBad: "\u672c\u5730\u6709 / \u975e 4000 \u5408\u683c",
    close: "\u5173\u95ed",
    refresh: "\u5237\u65b0\u9875\u9762",
    attempted: "\u5c1d\u8bd5\u6e05\u7406",
    removed: "\u6210\u529f\u6e05\u7406",
    kept: "\u4fdd\u7559",
    refreshed: "\u5237\u65b0\u6210\u529f",
    poolRemoved: "\u540c\u6b65\u5220\u9664\u90ae\u7bb1\u6c60",
    failed: "\u5931\u8d25",
    remaining: "\u5269\u4f59\u5019\u9009",
  };

  function notify(type, message) {
    const api = window.$message;
    if (api && typeof api[type] === "function") {
      api[type](message);
      return;
    }
    if (type === "error") {
      window.alert(message);
    } else {
      console.log("[remote-cleanup]", message);
    }
  }

  function getToken() {
    return localStorage.getItem(TOKEN_KEY) || "";
  }

  async function api(path, options) {
    const controller = new AbortController();
    const timer = window.setTimeout(() => controller.abort(), API_TIMEOUT_MS);
    try {
      const headers = { Accept: "application/json" };
      const token = getToken();
      if (token) headers.Authorization = "Bearer " + token;
      if (options && options.body !== undefined) headers["Content-Type"] = "application/json";

      const res = await fetch("/api" + path, {
        method: (options && options.method) || "GET",
        headers,
        body: options && options.body !== undefined ? JSON.stringify(options.body) : undefined,
        signal: controller.signal,
      });
      const raw = await res.text();
      let data = null;
      try {
        data = raw ? JSON.parse(raw) : null;
      } catch (_err) {
        data = raw;
      }
      if (!res.ok) {
        const detail = data && typeof data === "object" ? data.detail || data.message : data;
        throw new Error(detail || text.requestFailed + res.status);
      }
      return data;
    } finally {
      window.clearTimeout(timer);
    }
  }

  function ownText(el) {
    return Array.from(el.childNodes)
      .filter((node) => node.nodeType === Node.TEXT_NODE)
      .map((node) => node.textContent || "")
      .join("")
      .trim();
  }

  function findDrawerTitle() {
    const nodes = Array.from(
      document.querySelectorAll(".n-drawer-header__main, .n-drawer-header, [role='dialog'] header, header")
    );
    return nodes.find((el) => {
      const value = (ownText(el) || el.textContent || "").replace(/\s+/g, " ").trim();
      return /^子账号管理\s*·\s*[\w.+-]+@(hotmail|outlook)\.com$/i.test(value);
    });
  }

  function parseEmail(titleEl) {
    const value = (ownText(titleEl) || titleEl.textContent || "").replace(/\s+/g, " ").trim();
    const match = value.match(/[\w.+-]+@(hotmail|outlook)\.com/i);
    return match ? match[0] : "";
  }

  function findDrawerRoot(titleEl) {
    return (
      titleEl.closest(".n-drawer, .n-drawer-content, .n-modal, [role='dialog']") ||
      titleEl.parentElement ||
      document.body
    );
  }

  function findButtonByText(root, expected) {
    return Array.from(root.querySelectorAll("button")).find((btn) => {
      const value = (btn.textContent || "").replace(/\s+/g, "");
      return value === expected.replace(/\s+/g, "");
    });
  }

  function extractItems(data) {
    if (Array.isArray(data)) return data;
    if (data && Array.isArray(data.items)) return data.items;
    if (data && data.data && Array.isArray(data.data.items)) return data.data.items;
    if (data && Array.isArray(data.data)) return data.data;
    return [];
  }

  async function getAccountIdByEmail(email) {
    const data = await api("/adobe-accounts?page=1&size=200&keyword=" + encodeURIComponent(email));
    const items = extractItems(data);
    const lowered = email.toLowerCase();
    const account = items.find((item) => String(item.email || "").toLowerCase() === lowered);
    if (!account || !account.id) {
      throw new Error(text.noAccount + email);
    }
    return account.id;
  }

  async function getAllMembers(accountId) {
    const out = [];
    let page = 1;
    let total = 0;
    do {
      const data = await api(
        "/adobe-accounts/" +
          accountId +
          "/members?page=" +
          page +
          "&size=" +
          MEMBER_PAGE_SIZE +
          "&keyword="
      );
      const items = extractItems(data);
      total = Number(data && data.total ? data.total : items.length);
      out.push.apply(out, items);
      if (!items.length || out.length >= total) break;
      page += 1;
    } while (page <= 50);
    return out;
  }

  async function runLimited(items, limit, fn, onProgress) {
    const results = new Array(items.length);
    let next = 0;
    let done = 0;
    async function worker() {
      for (;;) {
        const index = next;
        next += 1;
        if (index >= items.length) return;
        try {
          results[index] = await fn(items[index], index);
        } catch (err) {
          results[index] = {
            success: false,
            action: "failed",
            email: itemEmail(items[index]),
            credits: items[index] && items[index].credits,
            message: err && err.message ? err.message : String(err || "failed"),
          };
        } finally {
          done += 1;
          if (typeof onProgress === "function") onProgress(done, items.length);
        }
      }
    }
    const workers = [];
    for (let i = 0; i < Math.max(1, Math.min(limit, items.length)); i += 1) {
      workers.push(worker());
    }
    await Promise.all(workers);
    return results;
  }

  function itemEmail(item) {
    return String((item && item.email) || "");
  }

  function listLines(items, limit) {
    const rows = (Array.isArray(items) ? items : []).slice(0, limit).map((item) => {
      const email = itemEmail(item);
      const reason = item && item.reason ? " (" + item.reason + ")" : item && item.action ? " (" + item.action + ")" : "";
      const credits = item && item.credits !== undefined && item.credits !== null ? " [\u4f59\u989d " + item.credits + "]" : "";
      const message = item && item.message ? " - " + item.message : "";
      return "<li>" + escapeHtml(email + credits + reason + message) + "</li>";
    });
    if (!rows.length) return "<li>-</li>";
    if (items.length > limit) rows.push("<li>... +" + (items.length - limit) + "</li>");
    return rows.join("");
  }

  function escapeHtml(value) {
    return String(value).replace(/[&<>"']/g, function (ch) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[ch];
    });
  }

  function showReport(email, preview, result, mode) {
    const existing = document.getElementById(REPORT_ID);
    if (existing) existing.remove();

    const attemptedItems = result.attempted_items || [];
    const removedItems = result.removed_items || [];
    const failedItems = result.failed || [];
    const remoteOnlyItems = preview.remote_only_items || [];
    const localBadItems = preview.local_not_qualified_items || [];
    const remainingCount = Math.max(0, Number(result.cleanup_candidates || 0) - Number(result.removed || 0));

    const overlay = document.createElement("div");
    overlay.id = REPORT_ID;
    overlay.style.cssText = [
      "position:fixed",
      "inset:0",
      "z-index:99999",
      "background:rgba(0,0,0,.35)",
      "display:flex",
      "align-items:center",
      "justify-content:center",
      "padding:24px",
    ].join(";");

    const card = document.createElement("div");
    card.style.cssText = [
      "width:min(760px,96vw)",
      "max-height:82vh",
      "overflow:auto",
      "background:#fff",
      "border-radius:10px",
      "box-shadow:0 18px 60px rgba(0,0,0,.25)",
      "font:14px/1.55 -apple-system,BlinkMacSystemFont,Segoe UI,sans-serif",
      "color:#111827",
    ].join(";");

    card.innerHTML =
      '<div style="padding:18px 22px;border-bottom:1px solid #e5e7eb;font-weight:700;font-size:17px;">' +
      (mode === "missing" ? text.missingTitle : text.reportTitle) +
      "</div>" +
      '<div style="padding:18px 22px;">' +
      '<div style="margin-bottom:12px;">' +
      escapeHtml(email) +
      "</div>" +
      '<div style="display:grid;grid-template-columns:repeat(5,minmax(0,1fr));gap:10px;margin-bottom:16px;">' +
      statBox(text.remoteTotal, preview.remote_total) +
      statBox(text.candidates, preview.cleanup_candidates) +
      statBox(text.remoteOnly, preview.remote_only) +
      statBox(text.localBad, preview.local_not_qualified) +
      statBox(mode === "missing" ? text.remaining : text.removed, mode === "missing" ? preview.cleanup_candidates : result.removed) +
      "</div>" +
      (mode === "missing"
        ? section(text.remoteOnly, listLines(remoteOnlyItems, 80)) +
          section(text.localBad, listLines(localBadItems, 80))
        : '<div style="margin-bottom:14px;color:#6b7280;">' +
          text.remaining +
          ": " +
          remainingCount +
          "</div>" +
          section(text.removed, listLines(removedItems, 40)) +
          section(text.failed, listLines(failedItems, 40)) +
          section(text.attempted, listLines(attemptedItems, 60))) +
      "</div>" +
      '<div style="display:flex;justify-content:flex-end;gap:10px;padding:14px 22px;border-top:1px solid #e5e7eb;">' +
      '<button data-action="close" style="height:34px;padding:0 14px;border:1px solid #d1d5db;border-radius:5px;background:#fff;cursor:pointer;">' +
      text.close +
      "</button>" +
      '<button data-action="refresh" style="height:34px;padding:0 14px;border:1px solid #2563eb;border-radius:5px;background:#2563eb;color:#fff;cursor:pointer;">' +
      text.refresh +
      "</button>" +
      "</div>";

    overlay.appendChild(card);
    document.body.appendChild(overlay);
    overlay.addEventListener("click", (event) => {
      if (event.target === overlay || event.target.dataset.action === "close") overlay.remove();
      if (event.target.dataset.action === "refresh") window.location.reload();
    });
  }

  function showCreditReport(email, result, mode) {
    const existing = document.getElementById(REPORT_ID);
    if (existing) existing.remove();

    const items = result.items || [];
    const refreshed = items.filter((item) => item.success && (item.action === "refreshed" || item.action === "kept"));
    const kept = items.filter((item) => item.action === "kept");
    const removed = items.filter((item) => item.action === "removed");
    const failed = items.filter((item) => !item.success || item.action === "refresh_failed" || item.action === "remove_failed" || item.action === "failed");
    const poolRemoved = removed.filter((item) => item.pool_removed);

    const overlay = document.createElement("div");
    overlay.id = REPORT_ID;
    overlay.style.cssText = [
      "position:fixed",
      "inset:0",
      "z-index:99999",
      "background:rgba(0,0,0,.35)",
      "display:flex",
      "align-items:center",
      "justify-content:center",
      "padding:24px",
    ].join(";");

    const card = document.createElement("div");
    card.style.cssText = [
      "width:min(820px,96vw)",
      "max-height:82vh",
      "overflow:auto",
      "background:#fff",
      "border-radius:10px",
      "box-shadow:0 18px 60px rgba(0,0,0,.25)",
      "font:14px/1.55 -apple-system,BlinkMacSystemFont,Segoe UI,sans-serif",
      "color:#111827",
    ].join(";");

    card.innerHTML =
      '<div style="padding:18px 22px;border-bottom:1px solid #e5e7eb;font-weight:700;font-size:17px;">' +
      (mode === "empty" ? text.emptyTitle : text.creditTitle) +
      "</div>" +
      '<div style="padding:18px 22px;">' +
      '<div style="margin-bottom:12px;">' +
      escapeHtml(email) +
      "</div>" +
      '<div style="display:grid;grid-template-columns:repeat(5,minmax(0,1fr));gap:10px;margin-bottom:16px;">' +
      statBox(text.localTotal, result.total) +
      statBox(text.refreshed, refreshed.length) +
      statBox(text.kept, kept.length) +
      statBox(text.removed, removed.length) +
      statBox(text.failed, failed.length) +
      "</div>" +
      (mode === "empty" ? '<div style="margin-bottom:14px;color:#6b7280;">' + text.poolRemoved + ": " + poolRemoved.length + "</div>" : "") +
      (mode === "empty"
        ? section(text.removed, listLines(removed, 80)) + section(text.kept, listLines(kept, 80)) + section(text.failed, listLines(failed, 80))
        : section(text.refreshed, listLines(refreshed, 120)) + section(text.failed, listLines(failed, 80))) +
      "</div>" +
      '<div style="display:flex;justify-content:flex-end;gap:10px;padding:14px 22px;border-top:1px solid #e5e7eb;">' +
      '<button data-action="close" style="height:34px;padding:0 14px;border:1px solid #d1d5db;border-radius:5px;background:#fff;cursor:pointer;">' +
      text.close +
      "</button>" +
      '<button data-action="refresh" style="height:34px;padding:0 14px;border:1px solid #2563eb;border-radius:5px;background:#2563eb;color:#fff;cursor:pointer;">' +
      text.refresh +
      "</button>" +
      "</div>";

    overlay.appendChild(card);
    document.body.appendChild(overlay);
    overlay.addEventListener("click", (event) => {
      if (event.target === overlay || event.target.dataset.action === "close") overlay.remove();
      if (event.target.dataset.action === "refresh") window.location.reload();
    });
  }

  function statBox(label, value) {
    return (
      '<div style="border:1px solid #e5e7eb;border-radius:8px;padding:10px;background:#f9fafb;">' +
      '<div style="font-size:12px;color:#6b7280;margin-bottom:4px;">' +
      escapeHtml(String(label)).replace(/[:：]\s*$/, "") +
      "</div>" +
      '<div style="font-size:20px;font-weight:700;">' +
      escapeHtml(value == null ? "-" : String(value)) +
      "</div>" +
      "</div>"
    );
  }

  function section(title, body) {
    return (
      '<div style="margin-top:14px;">' +
      '<div style="font-weight:700;margin-bottom:6px;">' +
      escapeHtml(title) +
      "</div>" +
      '<ul style="margin:0;padding-left:20px;max-height:180px;overflow:auto;border:1px solid #eef2f7;border-radius:6px;padding-top:8px;padding-bottom:8px;">' +
      body +
      "</ul>" +
      "</div>"
    );
  }

  function makeButton() {
    const btn = document.createElement("button");
    btn.id = BUTTON_ID;
    btn.type = "button";
    btn.textContent = text.button;
    btn.style.cssText = [
      "height:34px",
      "padding:0 15px",
      "border:1px solid #d97706",
      "border-radius:4px",
      "background:#f59e0b",
      "color:#fff",
      "font-size:14px",
      "line-height:32px",
      "cursor:pointer",
      "white-space:nowrap",
    ].join(";");
    return btn;
  }

  function makeMissingButton() {
    const btn = document.createElement("button");
    btn.id = MISSING_BUTTON_ID;
    btn.type = "button";
    btn.textContent = text.missingButton;
    btn.style.cssText = [
      "height:34px",
      "padding:0 15px",
      "border:1px solid #2563eb",
      "border-radius:4px",
      "background:#fff",
      "color:#2563eb",
      "font-size:14px",
      "line-height:32px",
      "cursor:pointer",
      "white-space:nowrap",
    ].join(";");
    return btn;
  }

  function makeCreditButton() {
    const btn = document.createElement("button");
    btn.id = CREDIT_BUTTON_ID;
    btn.type = "button";
    btn.textContent = text.creditButton;
    btn.style.cssText = [
      "height:34px",
      "padding:0 15px",
      "border:1px solid #059669",
      "border-radius:4px",
      "background:#10b981",
      "color:#fff",
      "font-size:14px",
      "line-height:32px",
      "cursor:pointer",
      "white-space:nowrap",
    ].join(";");
    return btn;
  }

  function makeEmptyButton() {
    const btn = document.createElement("button");
    btn.id = EMPTY_BUTTON_ID;
    btn.type = "button";
    btn.textContent = text.emptyButton;
    btn.style.cssText = [
      "height:34px",
      "padding:0 15px",
      "border:1px solid #dc2626",
      "border-radius:4px",
      "background:#fff",
      "color:#dc2626",
      "font-size:14px",
      "line-height:32px",
      "cursor:pointer",
      "white-space:nowrap",
    ].join(";");
    return btn;
  }

  function makeDangerJobButton(id, label, filled) {
    const btn = document.createElement("button");
    btn.id = id;
    btn.type = "button";
    btn.textContent = label;
    btn.style.cssText = [
      "height:34px",
      "padding:0 15px",
      "border:1px solid #dc2626",
      "border-radius:4px",
      filled ? "background:#dc2626" : "background:#fff",
      filled ? "color:#fff" : "color:#dc2626",
      "font-size:14px",
      "line-height:32px",
      "cursor:pointer",
      "white-space:nowrap",
    ].join(";");
    return btn;
  }

  function setLoading(btn, loading, loadingText) {
    btn.disabled = loading;
    btn.style.opacity = loading ? "0.65" : "1";
    btn.style.cursor = loading ? "not-allowed" : "pointer";
    if (loading) {
      btn.textContent = loadingText || text.loading;
    } else {
      if (btn.id === MISSING_BUTTON_ID) btn.textContent = text.missingButton;
      else if (btn.id === CREDIT_BUTTON_ID) btn.textContent = text.creditButton;
      else if (btn.id === EMPTY_BUTTON_ID) btn.textContent = text.emptyButton;
      else if (btn.id === ALL_CHILDREN_BUTTON_ID) btn.textContent = text.allChildrenButton;
      else if (btn.id === REMOTE_ALL_BUTTON_ID) btn.textContent = text.remoteAllButton;
      else if (btn.id === LOCAL_ALL_BUTTON_ID) btn.textContent = text.localAllButton;
      else if (btn.id === BATCH_LOGIN_BUTTON_ID) btn.textContent = text.batchLoginButton;
      else if (btn.id === SELECTED_ALL_BUTTON_ID) btn.textContent = text.selectedAllButton;
      else if (btn.id === IMPORT_POOL_BUTTON_ID) btn.textContent = text.importPoolButton;
      else btn.textContent = text.button;
    }
  }

  async function handleCleanup(titleEl, btn) {
    const email = parseEmail(titleEl);
    if (!email) {
      notify("error", text.noEmail);
      return;
    }
    setLoading(btn, true);
    try {
      const accountId = await getAccountIdByEmail(email);
      const preview = await api("/adobe-accounts/" + accountId + "/members/remote-preview");
      const candidates = Number(preview.cleanup_candidates || 0);
      const total = Number(preview.remote_total || 0);
      if (!candidates) {
        notify("success", text.noCandidates);
        return;
      }
      const ok = window.confirm(
        text.confirmTitle +
          email +
          "\n" +
          text.remoteTotal +
          total +
          "\n" +
          text.candidates +
          candidates +
          "\n\n" +
          text.confirmBody
      );
      if (!ok) return;
      const result = await api("/adobe-accounts/" + accountId + "/members/cleanup-remote", { method: "POST" });
      notify("success", text.done + ": " + text.removed + " " + Number(result.removed || 0));
      showReport(email, preview, result, "cleanup");
    } catch (err) {
      notify("error", err && err.message ? err.message : text.cleanupFailed);
    } finally {
      setLoading(btn, false);
    }
  }

  async function handleMissing(titleEl, btn) {
    const email = parseEmail(titleEl);
    if (!email) {
      notify("error", text.noEmail);
      return;
    }
    setLoading(btn, true, text.loadingMissing);
    try {
      const accountId = await getAccountIdByEmail(email);
      const preview = await api("/adobe-accounts/" + accountId + "/members/remote-preview");
      showReport(email, preview, { attempted_items: [], removed_items: [], failed: [], removed: 0 }, "missing");
    } catch (err) {
      notify("error", err && err.message ? err.message : text.cleanupFailed);
    } finally {
      setLoading(btn, false);
    }
  }

  async function handleCreditRefresh(titleEl, btn) {
    const email = parseEmail(titleEl);
    if (!email) {
      notify("error", text.noEmail);
      return;
    }
    setLoading(btn, true, text.loadingCredits);
    try {
      const accountId = await getAccountIdByEmail(email);
      const members = await getAllMembers(accountId);
      if (!members.length) {
        notify("warning", text.noMembers);
        return;
      }
      const items = await runLimited(
        members,
        CREDIT_REFRESH_CONCURRENCY,
        (member) => api("/adobe-accounts/" + accountId + "/members/" + member.id + "/refresh-credits", { method: "POST" }),
        (done, total) => {
          btn.textContent = text.loadingCredits + " " + done + "/" + total;
        }
      );
      const failed = items.filter((item) => !item.success).length;
      notify("success", text.creditDone + ": " + (items.length - failed) + "/" + items.length);
      showCreditReport(email, { total: items.length, items: items }, "credit");
    } catch (err) {
      notify("error", err && err.message ? err.message : text.creditFailed);
    } finally {
      setLoading(btn, false);
    }
  }

  async function handleEmptyRemove(titleEl, btn) {
    const email = parseEmail(titleEl);
    if (!email) {
      notify("error", text.noEmail);
      return;
    }
    setLoading(btn, true, text.loadingEmpty);
    try {
      const accountId = await getAccountIdByEmail(email);
      const members = await getAllMembers(accountId);
      if (!members.length) {
        notify("warning", text.noMembers);
        return;
      }
      const ok = window.confirm(
        text.confirmTitle +
          email +
          "\n" +
          text.localTotal +
          members.length +
          "\n\n" +
          text.emptyConfirmBody
      );
      if (!ok) return;

      const items = [];
      for (let i = 0; i < members.length; i += 1) {
        const member = members[i];
        btn.textContent = text.loadingEmpty + " " + (i + 1) + "/" + members.length;
        try {
          const res = await api(
            "/adobe-accounts/" +
              accountId +
              "/members/" +
              member.id +
              "/refresh-and-remove-empty?expected_credits=" +
              EXPECTED_CREDITS +
              "&remove_non_target=true",
            { method: "POST" }
          );
          items.push(res);
        } catch (err) {
          items.push({
            success: false,
            action: "failed",
            email: itemEmail(member),
            credits: member.credits,
            message: err && err.message ? err.message : String(err || "failed"),
          });
        }
      }
      const removed = items.filter((item) => item.action === "removed").length;
      const failed = items.filter((item) => !item.success || item.action === "remove_failed" || item.action === "refresh_failed" || item.action === "failed").length;
      notify("success", text.emptyDone + ": " + text.removed + " " + removed + ", " + text.failed + " " + failed);
      showCreditReport(email, { total: items.length, items: items }, "empty");
    } catch (err) {
      notify("error", err && err.message ? err.message : text.emptyFailed);
    } finally {
      setLoading(btn, false);
    }
  }

  function cleanupConfirmText(mode) {
    if (mode === "remote") return text.remoteAllConfirmBody;
    if (mode === "local") return text.localAllConfirmBody;
    return text.allConfirmBody;
  }

  function navigateToJob(jobId) {
    const target = "/jobs?id=" + encodeURIComponent(String(jobId));
    if (window.location.hash && window.location.hash.startsWith("#/")) {
      window.location.hash = "#" + target;
      return;
    }
    window.location.href = "/#" + target;
  }

  async function handleAllChildrenJob(titleEl, btn, mode) {
    const email = parseEmail(titleEl);
    if (!email) {
      notify("error", text.noEmail);
      return;
    }
    const ok = window.confirm(text.confirmTitle + email + "\n\n" + cleanupConfirmText(mode));
    if (!ok) return;
    setLoading(btn, true, "\u521b\u5efa\u4efb\u52a1\u4e2d...");
    try {
      const accountId = await getAccountIdByEmail(email);
      const job = await api("/adobe-accounts/" + accountId + "/members/cleanup-job", {
        method: "POST",
        body: { mode: mode },
      });
      notify("success", text.jobStarted + " #" + job.id);
      navigateToJob(job.id);
    } catch (err) {
      notify("error", err && err.message ? err.message : text.jobStartFailed);
    } finally {
      setLoading(btn, false);
    }
  }

  function isInDrawer(el) {
    return !!(el && el.closest(".n-drawer, .n-drawer-container, .n-modal"));
  }

  function findMainButtonByText(expected) {
    return Array.from(document.querySelectorAll("button")).find((btn) => {
      if (isInDrawer(btn)) return false;
      const value = (btn.textContent || "").replace(/\s+/g, "");
      return value === expected.replace(/\s+/g, "") || value.startsWith(expected.replace(/\s+/g, ""));
    });
  }

  function selectedAccountIdsFromTable() {
    const ids = [];
    const rows = Array.from(document.querySelectorAll(".n-data-table-tr")).filter((row) => !isInDrawer(row));
    rows.forEach((row) => {
      const checked = row.querySelector(
        "input[type='checkbox']:checked, .n-checkbox--checked, [aria-checked='true']"
      );
      if (!checked) return;
      const cells = Array.from(row.querySelectorAll(".n-data-table-td"));
      for (const cell of cells) {
        const value = (cell.textContent || "").replace(/\s+/g, " ").trim();
        if (/^\d+$/.test(value)) {
          ids.push(Number(value));
          break;
        }
      }
    });
    return Array.from(new Set(ids)).filter(Boolean);
  }

  async function handleSelectedAllChildren(btn) {
    const ids = selectedAccountIdsFromTable();
    if (!ids.length) {
      notify("warning", text.noSelectedAdmin);
      return;
    }
    const ok = window.confirm(
      "\u5df2\u9009\u6bcd\u53f7: " +
        ids.length +
        "\n\n" +
        "\u5c06\u5bf9\u6240\u9009\u6bcd\u53f7\u521b\u5efa\u540e\u53f0\u4efb\u52a1,\u5220\u9664 Adobe \u8fdc\u7a0b\u5b50\u53f7\u5e76\u5728\u6210\u529f\u540e\u5220\u9664\u672c\u5730\u5b50\u53f7\u8bb0\u5f55\u3002\u786e\u8ba4\u6267\u884c\uff1f"
    );
    if (!ok) return;
    setLoading(btn, true, "\u521b\u5efa\u4efb\u52a1\u4e2d...");
    try {
      const job = await api("/adobe-accounts/members/cleanup-job", {
        method: "POST",
        body: { admin_ids: ids, mode: "all" },
      });
      notify("success", text.jobStarted + " #" + job.id);
      navigateToJob(job.id);
    } catch (err) {
      notify("error", err && err.message ? err.message : text.jobStartFailed);
    } finally {
      setLoading(btn, false);
    }
  }

  async function handleBatchLogin(btn) {
    const ids = selectedAccountIdsFromTable();
    if (!ids.length) {
      notify("warning", text.noSelectedLoginAdmin);
      return;
    }
    const ok = window.confirm(
      "\u5df2\u9009\u6bcd\u53f7: " +
        ids.length +
        "\n\n" +
        "\u5c06\u521b\u5efa\u540e\u53f0\u4efb\u52a1:\u5148\u5bf9\u6bcf\u4e2a\u6bcd\u53f7\u505a\u6536\u4ef6\u68c0\u6d4b\u5e76\u66f4\u65b0\u6536\u4ef6\u72b6\u6001,\u7136\u540e\u6267\u884c\u6bcd\u53f7\u767b\u5f55\u3002\u786e\u8ba4\u6267\u884c\uff1f"
    );
    if (!ok) return;
    setLoading(btn, true, "\u521b\u5efa\u4efb\u52a1\u4e2d...");
    try {
      const job = await api("/adobe-accounts/batch-login", {
        method: "POST",
        body: { admin_ids: ids },
      });
      notify("success", "\u5df2\u521b\u5efa\u6279\u91cf\u767b\u5f55\u4efb\u52a1 #" + job.id);
      navigateToJob(job.id);
    } catch (err) {
      notify("error", err && err.message ? err.message : text.batchLoginFailed);
    } finally {
      setLoading(btn, false);
    }
  }

  async function handleImportPool(btn) {
    const ids = selectedAccountIdsFromTable();
    if (!ids.length) {
      notify("warning", text.noSelectedImportAdmin);
      return;
    }
    const ok = window.confirm(
      "\u5df2\u9009\u6bcd\u53f7: " +
        ids.length +
        "\n\n" +
        "\u5c06\u521b\u5efa\u540e\u53f0\u4efb\u52a1:\u53ea\u68c0\u67e5\u672c\u5730\u5b50\u53f7,\u628a\u6bcf\u4e2a\u6bcd\u53f7\u4e0b\u79ef\u5206\u5927\u4e8e 20 \u4e14\u6709 cookie \u7684\u5b50\u53f7\u540c\u6b65\u5230\u81ea\u6709\u53f7\u6c60\u3002\u786e\u8ba4\u6267\u884c\uff1f"
    );
    if (!ok) return;
    setLoading(btn, true, "\u521b\u5efa\u4efb\u52a1\u4e2d...");
    try {
      const job = await api("/adobe-accounts/members/import-pool-job", {
        method: "POST",
        body: { admin_ids: ids },
      });
      notify("success", "\u5df2\u521b\u5efa\u6279\u91cf\u66f4\u65b0\u53f7\u6c60\u4efb\u52a1 #" + job.id);
      navigateToJob(job.id);
    } catch (err) {
      notify("error", err && err.message ? err.message : text.importPoolFailed);
    } finally {
      setLoading(btn, false);
    }
  }

  function installButton() {
    const titleEl = findDrawerTitle();
    if (!titleEl) return;
    const root = findDrawerRoot(titleEl);
    if (
      root.querySelector("#" + BUTTON_ID) &&
      root.querySelector("#" + MISSING_BUTTON_ID) &&
      root.querySelector("#" + CREDIT_BUTTON_ID) &&
      root.querySelector("#" + EMPTY_BUTTON_ID) &&
      root.querySelector("#" + ALL_CHILDREN_BUTTON_ID) &&
      root.querySelector("#" + REMOTE_ALL_BUTTON_ID) &&
      root.querySelector("#" + LOCAL_ALL_BUTTON_ID)
    ) return;
    const bulkRemove = findButtonByText(root, "\u6279\u91cf\u79fb\u9664");
    if (!bulkRemove || !bulkRemove.parentElement) return;

    let anchor = bulkRemove.parentElement;
    if (!root.querySelector("#" + CREDIT_BUTTON_ID)) {
      const creditBtn = makeCreditButton();
      creditBtn.addEventListener("click", () => handleCreditRefresh(titleEl, creditBtn));
      const holder = anchor.classList.contains("n-space-item") ? anchor.cloneNode(false) : null;
      if (holder) {
        holder.appendChild(creditBtn);
        anchor.after(holder);
        anchor = holder;
      } else {
        bulkRemove.after(creditBtn);
      }
    }

    if (!root.querySelector("#" + EMPTY_BUTTON_ID)) {
      const emptyBtn = makeEmptyButton();
      emptyBtn.addEventListener("click", () => handleEmptyRemove(titleEl, emptyBtn));
      const holder = anchor.classList.contains("n-space-item") ? anchor.cloneNode(false) : null;
      if (holder) {
        holder.appendChild(emptyBtn);
        anchor.after(holder);
        anchor = holder;
      } else {
        anchor.after(emptyBtn);
      }
    }

    if (!root.querySelector("#" + MISSING_BUTTON_ID)) {
      const missingBtn = makeMissingButton();
      missingBtn.addEventListener("click", () => handleMissing(titleEl, missingBtn));
      const holder = anchor.classList.contains("n-space-item") ? anchor.cloneNode(false) : null;
      if (holder) {
        holder.appendChild(missingBtn);
        anchor.after(holder);
        anchor = holder;
      } else {
        bulkRemove.after(missingBtn);
      }
    }

    if (!root.querySelector("#" + ALL_CHILDREN_BUTTON_ID)) {
      const allBtn = makeDangerJobButton(ALL_CHILDREN_BUTTON_ID, text.allChildrenButton, true);
      allBtn.addEventListener("click", () => handleAllChildrenJob(titleEl, allBtn, "all"));
      const holder = anchor.classList.contains("n-space-item") ? anchor.cloneNode(false) : null;
      if (holder) {
        holder.appendChild(allBtn);
        anchor.after(holder);
        anchor = holder;
      } else {
        anchor.after(allBtn);
      }
    }

    if (!root.querySelector("#" + REMOTE_ALL_BUTTON_ID)) {
      const remoteAllBtn = makeDangerJobButton(REMOTE_ALL_BUTTON_ID, text.remoteAllButton, false);
      remoteAllBtn.addEventListener("click", () => handleAllChildrenJob(titleEl, remoteAllBtn, "remote"));
      const holder = anchor.classList.contains("n-space-item") ? anchor.cloneNode(false) : null;
      if (holder) {
        holder.appendChild(remoteAllBtn);
        anchor.after(holder);
        anchor = holder;
      } else {
        anchor.after(remoteAllBtn);
      }
    }

    if (!root.querySelector("#" + LOCAL_ALL_BUTTON_ID)) {
      const localAllBtn = makeDangerJobButton(LOCAL_ALL_BUTTON_ID, text.localAllButton, false);
      localAllBtn.addEventListener("click", () => handleAllChildrenJob(titleEl, localAllBtn, "local"));
      const holder = anchor.classList.contains("n-space-item") ? anchor.cloneNode(false) : null;
      if (holder) {
        holder.appendChild(localAllBtn);
        anchor.after(holder);
        anchor = holder;
      } else {
        anchor.after(localAllBtn);
      }
    }

    if (!root.querySelector("#" + BUTTON_ID)) {
      const btn = makeButton();
      btn.addEventListener("click", () => handleCleanup(titleEl, btn));
      const holder = anchor.classList.contains("n-space-item") ? anchor.cloneNode(false) : null;
      if (holder) {
        holder.appendChild(btn);
        anchor.after(holder);
      } else {
        anchor.after(btn);
      }
    }
  }

  function installAccountListButton() {
    const bulkBuild = findMainButtonByText("\u6279\u91cf\u62c9\u53f7");
    if (!bulkBuild) return;
    const bulkDelete = findMainButtonByText("\u6279\u91cf\u5220\u9664");
    const anchorButton = bulkDelete || bulkBuild;
    if (!anchorButton || !anchorButton.parentElement) return;

    let anchor = anchorButton.parentElement;
    if (!document.getElementById(IMPORT_POOL_BUTTON_ID)) {
      const importBtn = makeDangerJobButton(IMPORT_POOL_BUTTON_ID, text.importPoolButton, false);
      importBtn.style.borderColor = "#2563eb";
      importBtn.style.color = "#2563eb";
      importBtn.addEventListener("click", () => handleImportPool(importBtn));
      const holder = anchor.classList.contains("n-space-item") ? anchor.cloneNode(false) : null;
      if (holder) {
        holder.appendChild(importBtn);
        anchor.after(holder);
        anchor = holder;
      } else {
        anchorButton.after(importBtn);
      }
    }

    if (!document.getElementById(SELECTED_ALL_BUTTON_ID)) {
      const btn = makeDangerJobButton(SELECTED_ALL_BUTTON_ID, text.selectedAllButton, true);
      btn.addEventListener("click", () => handleSelectedAllChildren(btn));
      const holder = anchor.classList.contains("n-space-item") ? anchor.cloneNode(false) : null;
      if (holder) {
        holder.appendChild(btn);
        anchor.after(holder);
      } else {
        anchorButton.after(btn);
      }
    }
  }

  function isSettingsPage() {
    return (
      window.location.pathname === "/settings" ||
      window.location.hash === "#/settings" ||
      document.title.indexOf("\u8bbe\u7f6e") >= 0
    );
  }

  function findSettingsAnchor() {
    const cards = Array.from(document.querySelectorAll(".n-card")).filter((card) => {
      return (card.textContent || "").indexOf("\u8fd0\u884c\u8bbe\u7f6e") >= 0;
    });
    return cards[0] || document.querySelector("#app");
  }

  async function installPoolApiSettings() {
    if (!isSettingsPage() || document.getElementById(POOL_API_SETTINGS_ID)) return;
    const anchor = findSettingsAnchor();
    if (!anchor || !anchor.parentElement) return;

    const card = document.createElement("div");
    card.id = POOL_API_SETTINGS_ID;
    card.style.cssText = [
      "background:#fff",
      "border-radius:3px",
      "padding:20px 24px",
      "margin:0 0 20px 0",
      "box-sizing:border-box",
    ].join(";");
    card.innerHTML =
      '<div style="font-weight:600;font-size:18px;margin-bottom:18px;color:#1f2329;">\u81ea\u6709\u53f7\u6c60\u63a5\u53e3</div>' +
      settingsRow(
        "BASE_URL",
        '<input data-field="pool_api_base_url" placeholder="https://your-domain.com" style="' +
          inputStyle() +
          '">'
      ) +
      settingsRow(
        "KEY",
        '<input data-field="pool_api_key" type="password" placeholder="Bearer Token" style="' +
          inputStyle() +
          '">'
      ) +
      '<div style="margin-left:120px;display:flex;align-items:center;gap:10px;">' +
      '<button data-action="save" style="height:34px;padding:0 16px;border:1px solid #18a058;border-radius:3px;background:#18a058;color:#fff;cursor:pointer;">\u4fdd\u5b58\u81ea\u6709\u53f7\u6c60\u8bbe\u7f6e</button>' +
      '<span data-role="status" style="font-size:12px;color:#6b7280;"></span>' +
      "</div>";

    anchor.after(card);
    const baseInput = card.querySelector("[data-field='pool_api_base_url']");
    const keyInput = card.querySelector("[data-field='pool_api_key']");
    const statusEl = card.querySelector("[data-role='status']");
    const saveBtn = card.querySelector("[data-action='save']");
    try {
      const data = await api("/settings");
      baseInput.value = data.pool_api_base_url || "";
      keyInput.value = data.pool_api_key || "";
    } catch (err) {
      statusEl.textContent = err && err.message ? err.message : "\u52a0\u8f7d\u5931\u8d25";
    }
    saveBtn.addEventListener("click", async () => {
      saveBtn.disabled = true;
      saveBtn.style.opacity = "0.65";
      statusEl.textContent = "\u4fdd\u5b58\u4e2d...";
      try {
        await api("/settings", {
          method: "PUT",
          body: {
            pool_api_base_url: baseInput.value.trim(),
            pool_api_key: keyInput.value.trim(),
          },
        });
        statusEl.textContent = "\u5df2\u4fdd\u5b58";
        notify("success", "\u81ea\u6709\u53f7\u6c60\u8bbe\u7f6e\u5df2\u4fdd\u5b58");
      } catch (err) {
        statusEl.textContent = err && err.message ? err.message : "\u4fdd\u5b58\u5931\u8d25";
      } finally {
        saveBtn.disabled = false;
        saveBtn.style.opacity = "1";
      }
    });
  }

  function inputStyle() {
    return [
      "width:420px",
      "max-width:calc(100vw - 220px)",
      "height:34px",
      "border:1px solid #dcdfe6",
      "border-radius:3px",
      "padding:0 10px",
      "font-size:14px",
      "box-sizing:border-box",
    ].join(";");
  }

  function settingsRow(label, controlHtml) {
    return (
      '<div style="display:flex;align-items:center;margin-bottom:18px;">' +
      '<div style="width:120px;text-align:right;padding-right:12px;color:#1f2329;font-size:14px;box-sizing:border-box;">' +
      escapeHtml(label) +
      "</div>" +
      '<div style="flex:1;">' +
      controlHtml +
      "</div>" +
      "</div>"
    );
  }

  function renameJobsText() {
    if (document.title.indexOf("\u62c9\u53f7\u4efb\u52a1") >= 0) {
      document.title = document.title.replace(/\u62c9\u53f7\u4efb\u52a1/g, "\u4efb\u52a1\u5217\u8868");
    }
    const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
    const nodes = [];
    let node = walker.nextNode();
    while (node) {
      if ((node.nodeValue || "").indexOf("\u62c9\u53f7\u4efb\u52a1") >= 0) nodes.push(node);
      node = walker.nextNode();
    }
    nodes.forEach((item) => {
      item.nodeValue = (item.nodeValue || "").replace(/\u62c9\u53f7\u4efb\u52a1/g, "\u4efb\u52a1\u5217\u8868");
    });
  }

  function installAllButtons() {
    renameJobsText();
    installButton();
    installAccountListButton();
  }

  const observer = new MutationObserver(installAllButtons);
  observer.observe(document.documentElement, { childList: true, subtree: true });
  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", installAllButtons);
  } else {
    installAllButtons();
  }
})();
