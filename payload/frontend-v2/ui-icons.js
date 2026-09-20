/* Shared outline SVG icons for navigation and status tags. */
(function () {
  "use strict";
  var shapes = {
    external: '<circle cx="9" cy="8" r="3"/><path d="M3 21v-2a6 6 0 0 1 12 0v2M16 5a3 3 0 0 1 0 6M18 15a5 5 0 0 1 3 4v2"/>',
    dashboard: '<rect x="3" y="3" width="7" height="7" rx="1.5"/><rect x="14" y="3" width="7" height="7" rx="1.5"/><rect x="3" y="14" width="7" height="7" rx="1.5"/><rect x="14" y="14" width="7" height="7" rx="1.5"/>',
    adobe: '<rect x="4" y="3" width="16" height="18" rx="2"/><path d="M9 21v-5h6v5M8 7h1m6 0h1M8 11h1m6 0h1"/>',
    pool: '<path d="m12 3 9 5-9 5-9-5 9-5Zm-9 9 9 5 9-5M3 16l9 5 9-5"/>',
    jobs: '<rect x="5" y="4" width="14" height="17" rx="2"/><rect x="9" y="2" width="6" height="4" rx="1" fill="var(--okad-icon-bg, none)"/><path d="m8 11 1 1 2-2m-3 7 1 1 2-2m3-5h2m-2 6h2"/>',
    email: '<rect x="3" y="5" width="18" height="14" rx="2"/><path d="m3 6 9 7 9-7"/>',
    logs: '<path d="M14 3H6a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V9l-6-6Zm0 0v6h6M8 13h8M8 17h6"/>',
    settings: '<path d="M4 3v4m0 6v8M12 3v10m0 6v2M20 3v4m0 6v8M1 7h6v6H1V7Zm8 6h6v6H9v-6Zm8-6h6v6h-6V7Z"/>',
    sub2: '<rect x="9" y="3" width="6" height="6" rx="1.5"/><rect x="2" y="16" width="6" height="5" rx="1.5"/><rect x="16" y="16" width="6" height="5" rx="1.5"/><path d="M12 9v4M5 16v-3h14v3"/>',
    chevron: '<path d="m9 5 7 7-7 7"/>',
    check: '<circle cx="12" cy="12" r="9"/><path d="m8 12 3 3 5-6"/>'
  };
  function svg(name, size) {
    if (!shapes[name]) return "";
    size = Number(size) || 18;
    return '<svg class="okad-icon" data-okad-icon="' + name + '" width="' + size + '" height="' + size + '" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" focusable="false">' + shapes[name] + '</svg>';
  }
  window.OKAD_ICONS = { svg: svg };
  var style = document.createElement("style");
  style.textContent = '.okad-icon{display:inline-block;vertical-align:middle;flex-shrink:0}.n-menu-item-content__icon>.okad-icon{width:18px;height:18px}';
  document.head.appendChild(style);

  var labels = { "外部子号": "external", "运营驾驶舱": "dashboard", "母号管理": "adobe", "号池管理": "pool", "任务列表": "jobs", "拉号任务": "jobs", "邮箱管理": "email", "日志管理": "logs", "设置": "settings", "Sub2 管理": "sub2" };
  function updateMenuIcons() {
    document.querySelectorAll('.n-layout-sider .n-menu-item').forEach(function (item) {
      var header = item.querySelector('.n-menu-item-content-header');
      var name = header && labels[header.textContent.trim()];
      var icon = item.querySelector('.n-menu-item-content__icon');
      if (!name || !icon) return;
      if (icon.children.length === 1 && icon.firstElementChild.dataset.okadIcon === name && !icon.textContent.trim()) return;
      icon.innerHTML = svg(name);
    });
  }
  var scheduled = false;
  function schedule() {
    if (scheduled) return;
    scheduled = true;
    requestAnimationFrame(function () { scheduled = false; updateMenuIcons(); });
  }
  new MutationObserver(schedule).observe(document.documentElement, { childList: true, subtree: true });
  schedule();
})();
