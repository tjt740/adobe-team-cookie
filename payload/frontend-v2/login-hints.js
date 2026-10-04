/* Login credentials are fetched only when the title's reveal button is clicked. */
(function () {
  'use strict';
  var panel = null, owner = null, request = null;
  var eye = '<svg viewBox="0 0 24 24" width="18" height="18" aria-hidden="true"><path d="M2 12s3.5-7 10-7 10 7 10 7-3.5 7-10 7S2 12 2 12Z" fill="none" stroke="currentColor" stroke-width="1.6"/><circle cx="12" cy="12" r="3" fill="none" stroke="currentColor" stroke-width="1.6"/></svg>';
  var style = document.createElement('style');
  style.textContent = '.logo .okad-login-reveal{flex-shrink:0;display:inline-flex;align-items:center;justify-content:center;border:0;border-radius:5px;background:transparent;color:inherit;padding:3px;cursor:pointer}.logo .okad-login-reveal:hover{background:#2080f01a}.logo .okad-login-reveal:focus-visible{outline:2px solid #2080f0;outline-offset:2px}.n-layout-sider .logo{gap:7px!important;padding-right:8px!important}.n-layout-sider .logo-text{font-size:15px!important}.okad-login-hints{position:fixed;z-index:5000;box-sizing:border-box;width:min(390px,calc(100vw - 24px));padding:16px;border:1px solid var(--ws-line,#e8edf4);border-radius:12px;background:var(--bg-card,#fff);color:var(--text,#273342);box-shadow:0 12px 40px #15253c26;font:13px/1.6 system-ui;max-height:calc(100vh - 24px);overflow:auto}.okad-login-hints header{display:flex;align-items:center;justify-content:space-between;margin-bottom:12px;font-weight:600}.okad-login-hints header button{background:transparent;border:0;font:20px system-ui;color:inherit;cursor:pointer}.okad-login-hints section{padding:12px 0;border-top:1px solid var(--ws-line,#e8edf4)}.okad-login-hints p{margin:7px 0 0;display:flex;gap:10px;align-items:baseline}.okad-login-hints p>span{color:var(--ws-muted,#87909f);min-width:30px}.okad-login-hints code{font:13px/1.6 ui-monospace,monospace;overflow-wrap:anywhere;white-space:pre-wrap}.okad-login-hints a{display:block;color:#2080f0;font-size:12px;overflow-wrap:anywhere}.okad-login-hints [role=status]{font-weight:400;color:var(--ws-muted,#87909f)}';
  document.head.appendChild(style);
  style.textContent += '.okad-login-reveal[hidden]{display:none!important}';

  function close() {
    if (request) request.abort(); request = null;
    if (owner) { owner.setAttribute('aria-expanded', 'false'); owner.title = '显示登录密码'; }
    if (panel) panel.remove(); panel = null; owner = null;
  }
  function position() {
    if (!panel || !owner) return;
    var rect = owner.getBoundingClientRect();
    panel.style.left = Math.max(12, Math.min(rect.left, window.innerWidth - panel.offsetWidth - 12)) + 'px';
    panel.style.top = Math.max(12, Math.min(rect.bottom + 8, window.innerHeight - panel.offsetHeight - 12)) + 'px';
  }
  async function reveal(button) {
    if (owner === button) { close(); return; }
    close(); owner = button; button.setAttribute('aria-expanded', 'true'); button.title = '隐藏登录密码';
    panel = document.createElement('div'); panel.id = 'okad-login-hints'; panel.className = 'okad-login-hints';
    panel.setAttribute('role', 'region'); panel.setAttribute('aria-label', '本地和线上登录密码');
    panel.innerHTML = '<header>登录凭据<button type="button" aria-label="隐藏登录密码">×</button></header><div role="status">正在读取…</div>';
    panel.querySelector('button').onclick = function () { close(); button.focus(); };
    document.body.appendChild(panel); position();
    var current = panel, controller = new AbortController(); request = controller;
    var timer = setTimeout(function () { controller.abort(); }, 15000);
    try {
      var token = localStorage.getItem('okad_token'), headers = token ? {Authorization: 'Bearer ' + token} : {};
      var response = await fetch('/api/auth/login-hints', {headers: headers, cache: 'no-store', signal: controller.signal});
      var data = await response.json();
      if (!response.ok) throw new Error(data.detail || '登录密码读取失败');
      if (panel !== current) return;
      current.querySelector('[role=status]').remove();
      (data.entries || []).forEach(function (entry) {
        var section = document.createElement('section'), label = document.createElement('strong');
        label.textContent = entry.label; section.appendChild(label);
        if (/^https?:\/\//.test(entry.url)) {
          var link = document.createElement('a'); link.href = entry.url; link.target = '_blank'; link.rel = 'noopener noreferrer'; link.textContent = entry.url; section.appendChild(link);
        }
        [['账号', entry.username], ['密码', entry.password || entry.message || '未登记']].forEach(function (item) {
          var line = document.createElement('p'), key = document.createElement('span'), value = document.createElement('code');
          key.textContent = item[0]; value.textContent = item[1]; line.append(key, value); section.appendChild(line);
        });
        current.appendChild(section);
      });
      position();
    } catch (error) {
      if (panel === current) current.querySelector('[role=status]').textContent = error.name === 'AbortError' ? '读取超时，请重试' : error.message;
    } finally { clearTimeout(timer); if (request === controller) request = null; }
  }
  var lastPath = location.pathname;
  function sync() {
    if (lastPath !== location.pathname) { close(); lastPath = location.pathname; }
    if (owner && !owner.isConnected) close();
    document.querySelectorAll('.logo-text').forEach(function (title) {
      if (title.textContent.trim() !== 'okad 管理平台') return;
      var logo = title.parentElement;
      if (getComputedStyle(title).display === 'none') {
        var old = logo.querySelector('.okad-login-reveal'); if (old) old.hidden = true;
        if (old === owner) close();
        return;
      }
      var button = logo.querySelector('.okad-login-reveal');
      if (button) { button.hidden = false; return; }
      button = document.createElement('button'); button.type = 'button'; button.className = 'okad-login-reveal';
      button.title = '显示登录密码'; button.setAttribute('aria-label', '查看本地和线上登录密码');
      button.setAttribute('aria-expanded', 'false'); button.setAttribute('aria-controls', 'okad-login-hints'); button.innerHTML = eye;
      button.onclick = function () { reveal(button); }; title.insertAdjacentElement('afterend', button);
    });
  }
  var queued = false;
  function schedule() { if (queued) return; queued = true; requestAnimationFrame(function () { queued = false; sync(); }); }
  new MutationObserver(schedule).observe(document.documentElement, {childList: true, subtree: true, attributes: true, attributeFilter: ['style']});
  document.addEventListener('click', function (event) { if (panel && !panel.contains(event.target) && !owner.contains(event.target)) close(); });
  document.addEventListener('keydown', function (event) { if (event.key === 'Escape' && panel) { var button = owner; close(); button.focus(); } });
  window.addEventListener('resize', position); window.addEventListener('popstate', close);
  document.addEventListener('visibilitychange', function () { if (document.hidden) close(); }); schedule();
})();
