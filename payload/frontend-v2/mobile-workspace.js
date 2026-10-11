/* Mobile shell for the existing Vue/Naive UI application. No duplicate routes or actions. */
(function () {
  'use strict';
  var mobile = window.matchMedia('(max-width: 800px)');
  var sider, toggle, backdrop, closeButton, open = false, queued = false;
  var lastPath = location.pathname + location.search;
  var inertElements = new Map();
  var floating = new Set();
  function clampFloating() {
    floating.forEach(function (element) {
      if (!element.isConnected) {
        floatingSizes.unobserve(element); floating.delete(element); return;
      }
      var previous = Number(element.dataset.okadShift || 0), shift = 0;
      if (mobile.matches) {
        var rect = element.getBoundingClientRect();
        if (!rect.width) return;
        // The independent CSS translate leaves Naive UI's anchor/vertical transform intact.
        var left = rect.left - previous;
        shift = Math.max(12 - left, Math.min(0, innerWidth - 12 - left - rect.width));
      }
      if (Math.abs(previous - shift) > 0.5) {
        element.dataset.okadShift = shift;
        element.style.setProperty('--okad-float-x', shift + 'px');
      }
    });
  }
  var floatingSizes = new ResizeObserver(clampFloating);
  var floatingPosition = new MutationObserver(clampFloating);

  function visualViewportSize() {
    var viewport = window.visualViewport;
    if (!viewport) return;
    // Mobile keyboards resize the visual viewport without necessarily changing 100dvh.
    document.documentElement.style.setProperty('--okad-visual-height', viewport.height + 'px');
    document.documentElement.style.setProperty('--okad-visual-top', viewport.offsetTop + 'px');
  }

  function trackFloating() {
    document.querySelectorAll('.v-binder-follower-content').forEach(function (element) {
      if (floating.has(element)) return;
      floating.add(element); floatingSizes.observe(element);
    });
    // Disconnect removed popovers so repeated navigation does not retain detached nodes.
    floatingPosition.disconnect();
    clampFloating();
    floating.forEach(function (element) {
      floatingPosition.observe(element, {attributes:true, attributeFilter:['style']});
    });
  }

  function isolateBackground() {
    if (!sider || !open) return;
    Array.from(sider.parentElement.children).forEach(function (element) {
      if (element === sider || element === backdrop || inertElements.has(element)) return;
      inertElements.set(element, element.inert);
      element.inert = true;
    });
  }

  function setOpen(value, restoreFocus) {
    open = !!(value && mobile.matches && sider);
    document.body.classList.toggle('okad-mobile-nav-open', open);
    if (toggle) toggle.setAttribute('aria-expanded', String(open));
    if (backdrop) backdrop.hidden = !open;
    if (sider) {
      sider.inert = mobile.matches && !open;
      if (open) {
        sider.setAttribute('role', 'dialog');
        sider.setAttribute('aria-modal', 'true');
        sider.setAttribute('aria-label', '页面导航');
      } else {
        sider.removeAttribute('role');
        sider.removeAttribute('aria-modal');
        sider.removeAttribute('aria-label');
      }
    }
    if (open) {
      isolateBackground();
      closeButton.focus();
    } else {
      inertElements.forEach(function (previous, element) { element.inert = previous; });
      inertElements.clear();
      if (restoreFocus && toggle && toggle.isConnected && mobile.matches) toggle.focus();
    }
  }

  function sync() {
    queued = false;
    trackFloating();
    var nextSider = document.querySelector('.n-layout-sider');
    var header = document.querySelector('.n-layout-header');
    var path = location.pathname + location.search;
    if (path !== lastPath || nextSider !== sider || !mobile.matches) setOpen(false, open);
    lastPath = path;
    if (!nextSider || !header) {
      if (backdrop) backdrop.remove();
      sider = toggle = backdrop = closeButton = null;
      return;
    }
    if (nextSider !== sider) {
      sider = nextSider;
      sider.id = 'okad-mobile-navigation';
      sider.parentElement.parentElement.classList.add('okad-shell');
      var heading = document.createElement('div');
      heading.className = 'okad-mobile-drawer-heading';
      heading.innerHTML = '<strong>页面导航</strong><button type="button" aria-label="关闭导航">×</button>';
      closeButton = heading.querySelector('button');
      closeButton.onclick = function () { setOpen(false, true); };
      sider.querySelector('.n-layout-sider-scroll-container').prepend(heading);
      backdrop = document.createElement('div');
      backdrop.id = 'okad-mobile-backdrop';
      backdrop.hidden = true;
      backdrop.setAttribute('aria-hidden', 'true');
      backdrop.onclick = function () { setOpen(false, true); };
      sider.parentElement.appendChild(backdrop);
    }
    if (!toggle || toggle.parentElement !== header) {
      if (toggle) toggle.remove();
      toggle = document.createElement('button');
      toggle.type = 'button';
      toggle.id = 'okad-mobile-menu';
      toggle.setAttribute('aria-label', '打开导航');
      toggle.setAttribute('aria-controls', sider.id);
      toggle.setAttribute('aria-expanded', 'false');
      toggle.innerHTML = '<svg viewBox="0 0 24 24" width="22" height="22" aria-hidden="true"><path d="M4 6h16M4 12h16M4 18h16" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"/></svg>';
      toggle.onclick = function () { setOpen(!open, true); };
      header.prepend(toggle);
    }
    sider.inert = mobile.matches && !open;
    isolateBackground();
  }

  function schedule() {
    if (!queued) { queued = true; requestAnimationFrame(sync); }
  }
  document.addEventListener('keydown', function (event) {
    if (!open) return;
    if (event.key === 'Escape') {
      event.preventDefault(); setOpen(false, true);
    } else if (event.key === 'Tab') {
      var focusable = Array.from(sider.querySelectorAll('button,a[href],[tabindex="0"]')).filter(function (el) {
        return !el.disabled && el.getClientRects().length && getComputedStyle(el).visibility !== 'hidden';
      });
      var first = focusable[0], last = focusable[focusable.length - 1];
      if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last.focus(); }
      else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first.focus(); }
    }
  });
  // Navigation to the already active item does not change the URL.
  window.OKAD_MOBILE = { close: function () { if (open) setOpen(false, true); } };
  mobile.addEventListener('change', function () { setOpen(false, open); schedule(); });
  window.addEventListener('resize', schedule);
  if (window.visualViewport) {
    window.visualViewport.addEventListener('resize', visualViewportSize);
    window.visualViewport.addEventListener('scroll', visualViewportSize);
    visualViewportSize();
  }
  window.addEventListener('popstate', schedule);
  new MutationObserver(schedule).observe(document.documentElement, {childList:true, subtree:true});
  schedule();
})();
