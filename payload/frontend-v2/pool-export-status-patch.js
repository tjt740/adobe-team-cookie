(function () {
  const SELECT_ID = "okad-pool-export-status";
  const STORAGE_KEY = "okad_pool_export_status";
  const VALID = new Set(["", "unexported", "exported"]);

  function getStatus() {
    const value = String(localStorage.getItem(STORAGE_KEY) || "").trim();
    return VALID.has(value) ? value : "";
  }

  function setStatus(value) {
    const next = VALID.has(value) ? value : "";
    window.__okadPoolExportStatus = next;
    if (next) {
      localStorage.setItem(STORAGE_KEY, next);
    } else {
      localStorage.removeItem(STORAGE_KEY);
    }
  }

  function isPoolPage() {
    return location.pathname.replace(/\/+$/, "") === "/pool";
  }

  function findSearchButton(root) {
    return Array.from(root.querySelectorAll("button")).find((button) => {
      const text = (button.textContent || "").replace(/\s+/g, "");
      return text === "搜索" || text === "鎼滅储";
    });
  }

  function findFilterBar() {
    const inputs = Array.from(document.querySelectorAll("input[placeholder]"));
    const searchInput = inputs.find((input) => {
      const value = input.getAttribute("placeholder") || "";
      return value === "搜索邮箱" || value === "鎼滅储閭";
    });
    if (!searchInput) return null;
    return searchInput.closest(".n-space") || searchInput.parentElement;
  }

  function createFilter(root) {
    const wrap = document.createElement("span");
    wrap.id = SELECT_ID;
    wrap.className = "okad-pool-export-status";
    wrap.style.display = "inline-flex";
    wrap.style.alignItems = "center";
    wrap.style.gap = "6px";

    const label = document.createElement("span");
    label.textContent = "导出";
    label.style.color = "rgba(51,54,57,.65)";
    label.style.fontSize = "13px";

    const select = document.createElement("select");
    select.style.height = "34px";
    select.style.minWidth = "118px";
    select.style.border = "1px solid #dcdfe6";
    select.style.borderRadius = "6px";
    select.style.padding = "0 9px";
    select.style.background = "#fff";
    select.style.color = "#333639";
    select.style.outline = "none";

    [
      ["", "全部导出"],
      ["unexported", "未导出"],
      ["exported", "已导出"],
    ].forEach(([value, text]) => {
      const option = document.createElement("option");
      option.value = value;
      option.textContent = text;
      select.appendChild(option);
    });

    select.value = getStatus();
    select.addEventListener("change", () => {
      setStatus(select.value);
      const button = findSearchButton(root) || findSearchButton(document);
      if (button) {
        button.click();
      } else {
        location.reload();
      }
    });

    wrap.appendChild(label);
    wrap.appendChild(select);
    return wrap;
  }

  function install() {
    setStatus(getStatus());
    if (!isPoolPage()) return;
    if (document.getElementById('pool-workspace')) return;
    if (document.getElementById(SELECT_ID)) return;
    const bar = findFilterBar();
    if (!bar) return;
    const searchButton = findSearchButton(bar);
    const node = createFilter(bar);
    if (searchButton && searchButton.parentElement === bar) {
      bar.insertBefore(node, searchButton);
    } else {
      bar.appendChild(node);
    }
  }

  const originalPushState = history.pushState;
  const originalReplaceState = history.replaceState;
  history.pushState = function () {
    const result = originalPushState.apply(this, arguments);
    setTimeout(install, 80);
    return result;
  };
  history.replaceState = function () {
    const result = originalReplaceState.apply(this, arguments);
    setTimeout(install, 80);
    return result;
  };
  window.addEventListener("popstate", () => setTimeout(install, 80));
  const observer = new MutationObserver(install);
  observer.observe(document.documentElement, { childList: true, subtree: true });
  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", install);
  } else {
    install();
  }
})();
