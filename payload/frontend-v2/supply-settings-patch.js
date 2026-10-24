/* Project-wide supply.ink mail credentials; shared with external member imports. */
(function () {
  'use strict';
  if (window.__supplySettings) return;
  window.__supplySettings = true;
  var ID = 'okad-supply-mail-settings';
  var style = document.createElement('style');
  style.textContent = `
    #${ID}{--sm-accent:#2080f0;--sm-line:var(--ws-line,#e8edf4);--sm-bg:var(--ws-paper,#fff);--sm-input:var(--ws-paper,#fff);box-sizing:border-box;position:relative;isolation:isolate;width:100%;min-width:0;padding:22px 24px;margin-bottom:20px;border:2px solid var(--sm-line);border-radius:12px;background:var(--sm-bg);color:var(--ws-text,#273342);font:14px/1.6 system-ui,-apple-system,'PingFang SC',sans-serif;scroll-margin-top:20px}
    #${ID}[data-health="ok"]{--sm-accent:#168252;--sm-line:#70c59c;--sm-bg:#f0fbf5}
    #${ID}[data-health="error"]{--sm-accent:#c9344d;--sm-line:#e58c9d;--sm-bg:#fff5f5}
    #${ID} .sm-head,#${ID} form{position:relative;z-index:1}
    #${ID} .sm-head{display:flex;justify-content:space-between;align-items:center;gap:12px;flex-wrap:wrap}
    #${ID} h3{margin:0;color:inherit;font-size:18px;font-weight:600}
    #${ID} .sm-state{padding:3px 10px;border-radius:5px;background:var(--sm-input);border:1px solid var(--sm-line);color:var(--sm-accent);font-size:12px}
    #${ID} .sm-watermark{position:relative;z-index:0;display:flex;align-items:center;gap:8px;width:max-content;max-width:100%;margin:16px 4px 0 auto;transform:rotate(-8deg);color:var(--sm-accent);font-size:32px;font-weight:800;letter-spacing:1px;opacity:.3;pointer-events:none;user-select:none;white-space:nowrap}
    #${ID} .sm-watermark .okad-icon{width:1.1em;height:1.1em}
    #${ID} form{display:grid;grid-template-columns:116px minmax(0,740px);gap:8px 12px;margin-top:18px;align-items:start}
    #${ID} label{line-height:36px;text-align:right}
    #${ID} .sm-field{min-width:0}
    #${ID} input{box-sizing:border-box;width:100%;min-width:0;height:36px;border:1px solid var(--sm-line);border-radius:6px;padding:0 11px;background:var(--sm-input);color:inherit;font:14px system-ui}
    #${ID} .sm-actions{display:flex;gap:10px;flex-wrap:wrap;margin-top:14px}
    #${ID} button{height:36px;padding:0 16px;border:1px solid var(--sm-line);border-radius:6px;background:var(--sm-input);color:var(--sm-accent);font:14px system-ui;cursor:pointer}
    #${ID} .sm-save{background:var(--sm-accent);border-color:var(--sm-accent);color:#fff}
    #${ID} .sm-clear{color:var(--ws-muted,#87909f)}
    #${ID} button:disabled,#${ID} input:disabled{opacity:.55;cursor:not-allowed}
    #${ID} button:focus-visible,#${ID} input:focus{outline:2px solid var(--sm-accent);outline-offset:2px}
    #${ID} .sm-result{margin-top:12px;font-size:13px;color:#168252;overflow-wrap:anywhere}
    #${ID} .sm-result.error{color:#c9344d}
    #${ID} .sm-result:empty,#${ID} [hidden]{display:none!important}
    .okad-panel-active #${ID}{display:none!important}
    html.dark #${ID}[data-health="ok"]{--sm-accent:#70d6a2;--sm-line:#357e5b;--sm-bg:#20362b}
    html.dark #${ID}[data-health="error"]{--sm-accent:#f18da0;--sm-line:#a64b60;--sm-bg:#33252b}
    html.dark #${ID}[data-health="ok"] .sm-save{background:#168252;border-color:#168252;color:#fff}
    html.dark #${ID}[data-health="error"] .sm-save{background:#bd3650;border-color:#bd3650;color:#fff}
    html.dark #${ID} .sm-result:not(.error){color:#70d6a2}
    @media(max-width:800px){#${ID}{padding:18px 16px}#${ID} form{grid-template-columns:minmax(0,1fr);gap:6px}#${ID} label{text-align:left;line-height:1.6}#${ID} input,#${ID} button{min-height:44px}#${ID} input{font-size:16px}#${ID} .sm-watermark{font-size:28px}}
  `;
  document.head.appendChild(style);

  async function request(path, method, body) {
    var response = await fetch('/api/external/mail/' + path, {
      method:method || 'GET',
      headers:{'Content-Type':'application/json', Authorization:'Bearer ' + (localStorage.getItem('okad_token') || '')},
      body:body ? JSON.stringify(body) : undefined
    });
    var data = await response.json().catch(function () { return {}; });
    if (!response.ok) throw new Error(typeof data.detail === 'string' ? data.detail : '操作失败，请稍后重试');
    return data;
  }

  function create() {
    var card = document.createElement('section');
    card.id = ID;
    card.dataset.health = 'neutral';
    card.setAttribute('aria-labelledby', 'sm-title');
    card.innerHTML = `
      <div class="sm-head"><h3 id="sm-title">Supply 邮件 Token</h3><span class="sm-state">读取中…</span></div>
      <form>
        <label for="sm-token">Supply Token</label>
        <div class="sm-field">
          <input id="sm-token" type="text" autocomplete="off" spellcheck="false" maxlength="512" placeholder="粘贴 supply.ink Token" disabled>
          <div class="sm-actions"><button class="sm-save" type="submit" disabled>保存 Token</button><button class="sm-test" type="button" disabled>测试连接</button><button class="sm-clear" type="button" disabled>清除 Token</button><button class="sm-retry" type="button" hidden>重新加载</button></div>
          <div class="sm-result" role="status" aria-live="polite"></div>
        </div>
      </form>
      <div class="sm-watermark" role="status" aria-live="polite" hidden><span data-sm-status="ok" hidden>${window.OKAD_ICONS.svg('check', 36)}</span><span data-sm-status="error" hidden>${window.OKAD_ICONS.svg('error', 36)}</span><span class="sm-watermark-label"></span></div>
    `;
    var q = function (selector) { return card.querySelector(selector); };
    var configured = null, savedToken = '', health = 'untested', busy = false;
    function message(value, error) {
      q('.sm-result').textContent = value;
      q('.sm-result').classList.toggle('error', !!error);
    }
    function controls() {
      var dirty = q('#sm-token').value.trim() !== savedToken;
      q('#sm-token').disabled = busy || configured === null;
      q('.sm-save').disabled = busy || configured === null;
      q('.sm-test').disabled = busy || !configured || dirty;
      q('.sm-clear').disabled = busy || !configured;
      q('.sm-retry').disabled = busy;
      var tone = !dirty && configured && (health === 'ok' || health === 'error') ? health : 'neutral';
      card.dataset.health = tone;
      q('.sm-watermark').hidden = tone === 'neutral';
      q('[data-sm-status="ok"]').hidden = tone !== 'ok';
      q('[data-sm-status="error"]').hidden = tone !== 'error';
      q('.sm-watermark-label').textContent = tone === 'ok' ? 'token 正常' : tone === 'error' ? 'token 异常' : '';
    }
    function render(config, replaceInput) {
      var dirty = configured !== null && q('#sm-token').value.trim() !== savedToken;
      savedToken = config.token || '';
      configured = !!config.configured;
      health = config.health && config.health.status || 'untested';
      if (replaceInput || !dirty) q('#sm-token').value = savedToken;
      q('.sm-state').textContent = configured ? '已配置' : '未配置';
      q('.sm-save').textContent = configured ? '更新 Token' : '保存 Token';
      q('.sm-retry').hidden = true;
      controls();
    }
    async function run(button, pending, operation) {
      if (busy) return;
      busy = true; controls(); card.setAttribute('aria-busy', 'true');
      var label = button.textContent;
      button.textContent = pending; message('');
      try {
        await operation();
      } catch (error) {
        if (card.isConnected) message(error.message || '操作失败，请稍后重试', true);
      } finally {
        busy = false; button.textContent = label;
        q('.sm-save').textContent = configured ? '更新 Token' : '保存 Token';
        card.setAttribute('aria-busy', 'false'); controls();
      }
    }
    function load() {
      return run(q('.sm-retry'), '读取中…', async function () {
        try {
          var config = await request('config');
          if (card.isConnected) render(config);
        } catch (error) {
          q('.sm-state').textContent = '配置读取失败'; q('.sm-retry').hidden = false;
          throw error;
        }
      });
    }
    q('#sm-token').oninput = controls;
    q('form').onsubmit = function (event) {
      event.preventDefault();
      var token = q('#sm-token').value.trim();
      if (!token) { message('请先粘贴 supply.ink Token', true); q('#sm-token').focus(); return; }
      run(q('.sm-save'), '保存中…', async function () {
        var replacing = configured;
        var config = await request('config', 'PUT', {token:token});
        if (card.isConnected) { render(config, true); message(replacing ? '已更新' : '已保存'); }
      });
    };
    q('.sm-test').onclick = function () {
      run(this, '测试中…', async function () {
        try {
          var result = await request('test', 'POST');
          health = result.ok ? 'ok' : 'error';
          if (card.isConnected) controls();
        } catch (error) {
          health = 'error';
          if (card.isConnected) controls();
          throw error;
        }
      });
    };
    q('.sm-clear').onclick = function () {
      run(this, '清除中…', async function () {
        var config = await request('config', 'PUT', {clear_token:true});
        if (card.isConnected) { render(config, true); message('已清除'); }
      });
    };
    q('.sm-retry').onclick = load;
    card.addEventListener('okad-supply-refresh', function () { if (!busy) load(); });
    setTimeout(load, 0);
    return card;
  }

  function install() {
    var card = document.getElementById(ID);
    if (window.OKAD_ROUTE.path().replace(/\/+$/, '') !== '/settings') {
      if (card) card.remove();
      return;
    }
    var anchor = document.querySelector('#app .n-layout-content.content #okad-clash-settings');
    if (!anchor) return;
    if (!card) anchor.insertAdjacentElement('beforebegin', create());
    else if (card.nextElementSibling !== anchor) anchor.insertAdjacentElement('beforebegin', card);
  }
  new MutationObserver(install).observe(document.documentElement, {childList:true, subtree:true});
  window.addEventListener('popstate', install);
  window.setInterval(install, 1000);
  function refresh() {
    var card = document.getElementById(ID);
    if (card && !document.hidden) card.dispatchEvent(new Event('okad-supply-refresh'));
  }
  window.setInterval(refresh, 60000);
  document.addEventListener('visibilitychange', refresh);
  install();
})();
