/* Shared navigation for pages added alongside the compiled application. */
(function () {
  'use strict';
  var pages = {}, active = null, frame = 0, sider = null, header = null, menu = null;
  var tip = null, title = null;
  var css = document.createElement('style');
  css.textContent = `
    .n-layout-sider .n-menu.okad-nav-managed .n-menu-item-content { padding-left:32px!important; }
    .n-layout-sider .n-menu.okad-nav-managed .n-menu-item-content__icon { width:24px!important;height:24px!important;margin-right:8px!important;display:flex;align-items:center;justify-content:center; }
    .n-layout-sider .n-menu.okad-nav-managed.n-menu--collapsed .n-menu-item-content { display:flex!important;padding-left:0!important;padding-right:0!important;justify-content:center; }
    .n-layout-sider .n-menu.okad-nav-managed.n-menu--collapsed .n-menu-item-content__icon { margin:0!important; }
    .n-layout-sider .n-menu.okad-nav-managed.n-menu--collapsed .n-menu-item-content-header { display:none!important; }
    .n-layout-sider .n-menu.okad-nav-managed .n-menu-item-content::before { background:transparent!important; }
    .n-layout-sider .n-menu.okad-nav-managed .n-menu-item-content:hover::before { background:var(--n-item-color-hover)!important; }
    .n-layout-sider .n-menu.okad-nav-managed .n-menu-item-content .n-menu-item-content-header,
    .n-layout-sider .n-menu.okad-nav-managed .n-menu-item-content .n-menu-item-content-header a { color:var(--n-item-text-color)!important; }
    .n-layout-sider .n-menu.okad-nav-managed .n-menu-item-content .n-menu-item-content__icon { color:var(--n-item-icon-color)!important; }
    .n-layout-sider .n-menu.okad-nav-managed .okad-current-item .n-menu-item-content::before { background:var(--n-item-color-active)!important; }
    .n-layout-sider .n-menu.okad-nav-managed .okad-current-item .n-menu-item-content .n-menu-item-content-header,
    .n-layout-sider .n-menu.okad-nav-managed .okad-current-item .n-menu-item-content .n-menu-item-content-header a { color:var(--n-item-text-color-active)!important; }
    .n-layout-sider .n-menu.okad-nav-managed .okad-current-item .n-menu-item-content .n-menu-item-content__icon { color:var(--n-item-icon-color-active)!important; }
    .n-layout-sider .n-menu.okad-nav-managed .n-menu-item:focus-visible { outline:2px solid var(--n-item-text-color-active);outline-offset:-4px;border-radius:6px; }
    .okad-nav-custom { cursor:pointer; }
    .okad-panel-active .n-layout-sider { z-index:1100; }
    .okad-panel-active .n-layout-toggle-button { z-index:1101; }
    .okad-panel-active .header-title { display:none; }
    .okad-panel-active .n-layout-content.content { visibility:hidden; }
    .okad-page-title { font-size:18px;font-weight:600;color:var(--text); }
    #okad-nav-tooltip { position:fixed;z-index:4000;padding:7px 11px;border-radius:6px;background:#262a30;color:#fff;font:14px/1.5 system-ui,sans-serif;box-shadow:0 3px 12px #0002;pointer-events:none;white-space:nowrap; }
  `;
  document.head.appendChild(css);

  function schedule() { if (!frame) frame = requestAnimationFrame(sync); }
  function collapsed() { return sider && sider.classList.contains('n-layout-sider--collapsed'); }
  function hideTip() {
    if (tip) tip.hidden = true;
    document.querySelectorAll('.okad-nav-custom[aria-describedby]').forEach(function (it) { it.removeAttribute('aria-describedby'); });
  }
  function showTip(it) {
    if (!collapsed()) return;
    if (!tip) {
      tip = document.createElement('div'); tip.id = 'okad-nav-tooltip'; tip.setAttribute('role', 'tooltip');
      document.body.appendChild(tip);
    }
    tip.textContent = pages[it.id].label; tip.hidden = false;
    var r = it.getBoundingClientRect();
    tip.style.left = Math.round(sider.getBoundingClientRect().right + 10) + 'px';
    tip.style.top = Math.max(4, Math.round(r.top + (r.height - tip.offsetHeight) / 2)) + 'px';
    it.setAttribute('aria-describedby', tip.id);
  }
  function deactivate() {
    if (active) { var old = active; active = null; pages[old].close(); }
    hideTip(); schedule();
  }
  function activate(id) {
    if (active === id) return;
    deactivate(); active = id; pages[id].open(); layout(); sync();
  }
  function createItem(page) {
    var it = document.createElement('div'); it.id = page.id;
    it.className = 'n-menu-item okad-nav-custom'; it.setAttribute('role', 'menuitem');
    it.tabIndex = 0; it.setAttribute('aria-label', page.label);
    var content = document.createElement('div'); content.className = 'n-menu-item-content';
    var icon = document.createElement('div'); icon.className = 'n-menu-item-content__icon';
    icon.innerHTML = window.OKAD_ICONS.svg(page.icon);
    var label = document.createElement('div'); label.className = 'n-menu-item-content-header'; label.textContent = page.label;
    content.append(icon, label); it.appendChild(content);
    it.addEventListener('click', function (e) { e.preventDefault(); e.stopPropagation(); hideTip(); activate(page.id); });
    it.addEventListener('keydown', function (e) {
      if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); e.stopPropagation(); activate(page.id); }
      if (e.key === 'Escape') hideTip();
    });
    it.addEventListener('mouseenter', function () { showTip(it); });
    it.addEventListener('mouseleave', hideTip);
    it.addEventListener('focus', function () { showTip(it); });
    it.addEventListener('blur', hideTip);
    return it;
  }
  function layout() {
    if (!active) return;
    // Keep overlays in the sidebar's stacking context so its toggle stays clickable.
    var panel = document.getElementById(pages[active].panel);
    var host = sider && sider.parentElement;
    if (panel && host && panel.parentElement !== host) host.appendChild(panel);
    if (pages[active].layout) pages[active].layout();
  }
  var sizes = new ResizeObserver(function () { layout(); hideTip(); });
  var sideState = new MutationObserver(function () { hideTip(); schedule(); });
  function sync() {
    frame = 0;
    var nextSider = document.querySelector('.n-layout-sider');
    var nextHeader = document.querySelector('.n-layout-header');
    if (nextSider !== sider || nextHeader !== header) {
      sizes.disconnect(); sideState.disconnect(); sider = nextSider; header = nextHeader;
      if (sider) { sizes.observe(sider); sideState.observe(sider, { attributes:true, attributeFilter:['class', 'style'] }); }
      if (header) sizes.observe(header);
    }
    menu = sider && sider.querySelector('.n-menu');
    if (!menu || location.pathname === '/login' || !localStorage.getItem('okad_token')) {
      if (active) deactivate();
      Object.keys(pages).forEach(function (id) { var it = document.getElementById(id); if (it) it.remove(); });
      document.body.classList.remove('okad-panel-active');
      if (title) title.remove();
      return;
    }
    menu.classList.add('okad-nav-managed');
    Object.keys(pages).forEach(function (id) {
      if (!menu.querySelector('#' + id)) menu.appendChild(createItem(pages[id]));
    });
    var first = Object.keys(pages).filter(function (id) { return pages[id].first; })[0];
    if (first) {
      var entry = document.getElementById(first);
      if (menu.firstElementChild !== entry) menu.insertBefore(entry, menu.firstElementChild);
      var settings = menu.querySelector('a[href="/settings"]');
      var settingsItem = settings && settings.closest('.n-menu-item');
      if (settingsItem && entry.nextElementSibling !== settingsItem) menu.insertBefore(settingsItem, entry.nextElementSibling);
    }
    menu.querySelectorAll('.n-menu-item').forEach(function (it) {
      var link = it.querySelector('a[href]');
      if (link) { it.tabIndex = 0; it.setAttribute('aria-label', link.textContent.trim()); }
      var current = active ? it.id === active : !!(link && new URL(link.href).pathname === location.pathname);
      it.classList.toggle('okad-current-item', current);
      var target = link || it;
      if (current) { if (target.getAttribute('aria-current') !== 'page') target.setAttribute('aria-current', 'page'); }
      else target.removeAttribute('aria-current');
    });
    document.body.classList.toggle('okad-panel-active', !!active);
    if (active && header) {
      if (!title) { title = document.createElement('span'); title.className = 'okad-page-title'; }
      if (title.parentNode !== header) header.insertBefore(title, header.firstChild);
      if (title.textContent !== pages[active].label) title.textContent = pages[active].label;
    } else if (title) title.remove();
    layout();
  }
  document.addEventListener('click', function (e) {
    var it = e.target.closest && e.target.closest('.n-layout-sider .n-menu-item');
    if (it && !pages[it.id]) {
      deactivate();
      // Native routes live on label links; forward icon/row clicks when labels are hidden.
      var link = it.querySelector('a[href]');
      if (link && !e.target.closest('a') && e.button === 0) {
        e.preventDefault(); e.stopPropagation();
        link.dispatchEvent(new MouseEvent('click', { bubbles:true, cancelable:true,
          ctrlKey:e.ctrlKey, metaKey:e.metaKey, shiftKey:e.shiftKey, altKey:e.altKey }));
      }
    }
  }, true);
  document.addEventListener('keydown', function (e) {
    var it = e.target.closest && e.target.closest('.n-layout-sider .n-menu-item');
    if (!it || pages[it.id] || e.target.closest('a') || (e.key !== 'Enter' && e.key !== ' ')) return;
    var link = it.querySelector('a[href]');
    if (link) { e.preventDefault(); e.stopPropagation(); link.click(); }
  }, true);
  ['pushState', 'replaceState'].forEach(function (name) {
    var original = history[name];
    history[name] = function () { var result = original.apply(this, arguments); deactivate(); return result; };
  });
  window.addEventListener('popstate', deactivate);
  window.addEventListener('resize', function () { hideTip(); layout(); });
  document.addEventListener('scroll', hideTip, true);
  new MutationObserver(schedule).observe(document.documentElement, { childList:true, subtree:true });
  window.OKAD_NAV = {
    register: function (page) { pages[page.id] = page; schedule(); },
    close: deactivate,
    rect: function () {
      var s = document.querySelector('.n-layout-sider'), h = document.querySelector('.n-layout-header');
      return { left:s ? Math.max(0, Math.round(s.getBoundingClientRect().right)) : 0,
        top:h ? Math.max(0, Math.round(h.getBoundingClientRect().bottom)) : 0 };
    }
  };
})();
