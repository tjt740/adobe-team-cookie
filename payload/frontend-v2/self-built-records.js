/* Embed the account records in the shared authenticated workspace. */
(function () {
  'use strict';
  var url = 'https://ccni62k80jk3.feishu.cn/wiki/QZyVwaDJWipRyykRKhkcI0Wkndh?table=tbl8ON2stPY5rnag&view=vewJx5qCa3';
  var panel = null;
  var css = document.createElement('style');
  css.textContent = `
    #self-built-records-panel { position:fixed;right:0;bottom:0;z-index:1090;display:flex;flex-direction:column;overflow:hidden;background:var(--ws-paper,#fff);color:var(--ws-text,#273342); }
    #self-built-records-panel .records-toolbar { display:flex;justify-content:flex-end;align-items:center;flex-wrap:wrap;gap:8px;padding:10px 16px;border-bottom:1px solid var(--ws-line,#e5e7eb); }
    #self-built-records-panel .records-toolbar :is(button,a) { display:inline-flex;align-items:center;justify-content:center;box-sizing:border-box;min-height:34px;padding:6px 12px;border:1px solid var(--ws-line,#e5e7eb);border-radius:6px;background:var(--ws-paper,#fff);color:inherit;font:13px/1.5 system-ui,sans-serif;text-decoration:none;cursor:pointer; }
    #self-built-records-panel .records-toolbar :is(button,a):hover { background:var(--ws-soft,#f5f7fb); }
    #self-built-records-panel .records-toolbar :is(button,a):focus-visible { outline:2px solid var(--ws-blue,#2080f0);outline-offset:2px; }
    #self-built-records-panel iframe { display:block;flex:1;width:100%;height:100%;min-height:0;border:0;background:#fff; }
    @media(max-width:800px) {
      #self-built-records-panel .records-toolbar { padding:8px 12px; }
      #self-built-records-panel .records-toolbar :is(button,a) { min-height:44px; }
    }
  `;
  document.head.appendChild(css);

  function build() {
    panel = document.createElement('section');
    panel.id = 'self-built-records-panel';
    panel.setAttribute('aria-label', '自建号记录');
    var toolbar = document.createElement('div');
    toolbar.className = 'records-toolbar';
    var refresh = document.createElement('button');
    refresh.type = 'button';
    refresh.textContent = '刷新';
    var link = document.createElement('a');
    link.href = url;
    link.target = '_blank';
    link.rel = 'noopener noreferrer';
    link.textContent = '在飞书中打开';
    var iframe = document.createElement('iframe');
    iframe.title = '自建号记录';
    iframe.allow = 'clipboard-write; fullscreen';
    iframe.src = url;
    refresh.onclick = function () {
      var next = iframe.cloneNode(false);
      iframe.replaceWith(next);
      iframe = next;
    };
    toolbar.append(refresh, link);
    panel.append(toolbar, iframe);
    var sider = document.querySelector('.n-layout-sider');
    (sider ? sider.parentElement : document.body).appendChild(panel);
  }
  function layout() {
    if (!panel) return;
    var rect = window.OKAD_NAV.rect();
    panel.style.left = rect.left + 'px';
    panel.style.top = rect.top + 'px';
  }
  function open() {
    if (!panel) build();
    layout();
  }
  function close() {
    // Stop the external page when leaving the workspace or signing out.
    if (panel) panel.remove();
    panel = null;
  }
  document.addEventListener('transitionend', function (event) {
    if (event.target.matches('.n-layout-sider')) layout();
  });
  window.OKAD_NAV.register({
    id:'self-built-records-nav', route:'self-built-records', panel:'self-built-records-panel',
    label:'自建号记录', icon:'logs', open:open, close:close, layout:layout
  });
})();
