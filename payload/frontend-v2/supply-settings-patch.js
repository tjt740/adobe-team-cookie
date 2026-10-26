/* Project-wide supply.ink mail credentials; shared with external member imports. */
(function () {
  'use strict';
  if (window.__supplySettings) return;
  window.__supplySettings = true;
  var ID = 'okad-supply-mail-settings';
  var style = document.createElement('style');
  style.textContent = `
    #${ID} .sm-token-card{--sm-accent:#2080f0;--sm-line:var(--ws-line,#e8edf4);--sm-bg:var(--ws-paper,#fff);--sm-input:var(--ws-paper,#fff);box-sizing:border-box;position:relative;isolation:isolate;width:100%;min-width:0;padding:22px 24px;margin-bottom:20px;border:2px solid var(--sm-line);border-radius:12px;background:var(--sm-bg);color:var(--ws-text,#273342);font:14px/1.6 system-ui,-apple-system,'PingFang SC',sans-serif;scroll-margin-top:20px}
    #${ID} .sm-token-card[data-health="ok"]{--sm-accent:#168252;--sm-line:#70c59c;--sm-bg:#f0fbf5}
    #${ID} .sm-token-card[data-health="error"]{--sm-accent:#c9344d;--sm-line:#e58c9d;--sm-bg:#fff5f5}
    #${ID}{--sm-accent:#2080f0;--sm-line:var(--ws-line,#e8edf4);--sm-input:var(--ws-paper,#fff);width:100%;min-width:0;margin-bottom:20px}#${ID} .sm-titlebar .sm-actions{margin-top:0}#${ID} .sm-titlebar{display:flex;align-items:center;justify-content:space-between;gap:12px;margin-bottom:14px}#${ID} .sm-titlebar h3{font-size:18px}#${ID} .sm-token-card{margin-bottom:14px}#${ID} .sm-name{margin-bottom:10px}#${ID} .sm-load-result{color:#c9344d;font-size:13px;margin:10px 0}#${ID} .sm-load-result:empty{display:none}
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
    html.dark #${ID} .sm-token-card[data-health="ok"]{--sm-accent:#70d6a2;--sm-line:#357e5b;--sm-bg:#20362b}
    html.dark #${ID} .sm-token-card[data-health="error"]{--sm-accent:#f18da0;--sm-line:#a64b60;--sm-bg:#33252b}
    html.dark #${ID} .sm-token-card[data-health="ok"] .sm-save{background:#168252;border-color:#168252;color:#fff}
    html.dark #${ID} .sm-token-card[data-health="error"] .sm-save{background:#bd3650;border-color:#bd3650;color:#fff}
    html.dark #${ID} .sm-result:not(.error){color:#70d6a2}
    @media(max-width:800px){#${ID} .sm-token-card{padding:18px 16px}#${ID} form{grid-template-columns:minmax(0,1fr);gap:6px}#${ID} label{text-align:left;line-height:1.6}#${ID} input,#${ID} button{min-height:44px}#${ID} input{font-size:16px}#${ID} .sm-watermark{font-size:28px}}
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
    var root = document.createElement('section');
    root.id = ID;
    root.setAttribute('aria-labelledby', 'sm-title');
    root.innerHTML = '<div class="sm-titlebar"><h3 id="sm-title">Supply 邮件 Token</h3><div class="sm-actions"><button class="sm-add" type="button" disabled>添加 Token</button><button class="sm-retry" type="button" hidden>重新加载</button></div></div><div class="sm-load-result" role="status" aria-live="polite"></div><div class="sm-list"></div>';
    var rows = new Map(), draftCount = 0, loading = false;
    function dirty(row) {
      return row.token.value.trim() !== (row.config.token || '') || row.name.value.trim() !== (row.config.name || '');
    }
    function message(row, value, error) {
      row.result.textContent = value;
      row.result.classList.toggle('error', !!error);
    }
    function controls(row) {
      var editedToken = row.token.value.trim() !== (row.config.token || '');
      var configured = !!row.config.token;
      row.el.querySelectorAll('input,button').forEach(function (el) { el.disabled = row.busy; });
      row.test.disabled = row.busy || row.draft || !configured || editedToken;
      row.clear.disabled = row.busy || !configured;
      row.toggle.disabled = row.busy || row.draft;
      row.save.textContent = row.busy && row.action === 'save' ? '保存中…' : row.draft || !configured ? '保存 Token' : '更新 Token';
      row.test.textContent = row.busy && row.action === 'test' ? '测试中…' : '测试连接';
      row.toggle.textContent = row.config.enabled === false ? '启用' : '停用';
      row.el.querySelector('.sm-state').textContent = row.draft ? '未保存' : row.config.enabled === false ? '已停用' : configured ? '已配置' : '未配置';
      var health = row.config.health && row.config.health.status;
      var tone = configured && !editedToken && row.config.enabled !== false && (health === 'ok' || health === 'error') ? health : 'neutral';
      row.el.dataset.health = tone;
      row.el.setAttribute('aria-busy', String(row.busy));
      row.el.querySelector('.sm-watermark').hidden = tone === 'neutral';
      row.el.querySelector('[data-sm-status="ok"]').hidden = tone !== 'ok';
      row.el.querySelector('[data-sm-status="error"]').hidden = tone !== 'error';
      row.el.querySelector('.sm-watermark-label').textContent = tone === 'ok' ? 'token 正常' : tone === 'error' ? 'token 异常' : '';
    }
    function apply(row, config, force) {
      var editToken = row.token.value.trim() !== (row.config.token || '');
      var editName = row.name.value.trim() !== (row.config.name || '');
      if (!row.busy && row.errorAction === 'test' && config.health && config.health.status === 'ok') message(row,'');
      row.config = config;
      if (force || !editToken) row.token.value = config.token || '';
      if (force || !editName) row.name.value = config.name || '';
      row.el.querySelector('h4').textContent = config.name || 'Supply Token';
      controls(row);
    }
    function render(data, forceId, replaceInputs) {
      if (!root.isConnected) return;
      var list = data.tokens || [{id:'default', name:'默认 Token', token:data.token || '', configured:data.configured, enabled:true, health:data.health}];
      var seen = new Set();
      list.forEach(function (config) {
        seen.add(config.id);
        var row = rows.get(config.id);
        if (!row) row = createRow(config, false);
        if (!row.busy || config.id === forceId) apply(row, config, config.id === forceId && replaceInputs !== false);
      });
      rows.forEach(function (row, key) {
        if (!seen.has(key) && !row.draft && !row.busy) {
          if (dirty(row)) { message(row, '配置已在其他页面删除，请重新添加', true); return; }
          row.el.remove(); rows.delete(key);
        }
      });
      root.querySelector('.sm-add').disabled = false;
      root.querySelector('.sm-retry').hidden = true;
      root.querySelector('.sm-load-result').textContent = '';
    }
    function createRow(config, draft) {
      var card = document.createElement('article');
      card.className = 'sm-token-card'; card.dataset.tokenId = config.id;
      var suffix = config.id === 'default' ? '' : '-' + config.id;
      card.innerHTML = '<div class="sm-head"><h4 style="margin:0;font-size:16px"></h4><span class="sm-state"></span></div><form><label for="sm-name' + suffix + '">名称</label><div class="sm-field sm-name"><input id="sm-name' + suffix + '" type="text" maxlength="80" autocomplete="off"></div><label for="sm-token' + suffix + '">Supply Token</label><div class="sm-field"><input id="sm-token' + suffix + '" type="text" autocomplete="off" spellcheck="false" maxlength="512" placeholder="粘贴 supply.ink Token"><div class="sm-actions"><button class="sm-save" type="submit">保存 Token</button><button class="sm-test" type="button">测试连接</button><button class="sm-toggle" type="button">停用</button><button class="sm-clear" type="button">清除 Token</button>' + (config.id !== 'default' ? '<button class="sm-remove" type="button">删除</button>' : '') + '</div><div class="sm-result" role="status" aria-live="polite"></div></div></form><div class="sm-watermark" role="status" aria-live="polite" hidden><span data-sm-status="ok" hidden>' + window.OKAD_ICONS.svg('check',36) + '</span><span data-sm-status="error" hidden>' + window.OKAD_ICONS.svg('error',36) + '</span><span class="sm-watermark-label"></span></div>';
      var row = {el:card, config:{}, draft:draft, busy:false, action:'', token:card.querySelector('[id^="sm-token"]'), name:card.querySelector('[id^="sm-name"]'), result:card.querySelector('.sm-result'), save:card.querySelector('.sm-save'), test:card.querySelector('.sm-test'), toggle:card.querySelector('.sm-toggle'), clear:card.querySelector('.sm-clear')};
      rows.set(config.id, row); root.querySelector('.sm-list').appendChild(card); apply(row,config,true);
      row.token.oninput = row.name.oninput = function () { controls(row); };
      async function run(action, operation) {
        if (row.busy) return;
        row.busy = true; row.action = action; message(row,''); controls(row);
        try { await operation(); }
        catch (error) { row.errorAction = action; if (root.isConnected) message(row,error.message || '操作失败，请稍后重试',true); }
        finally { row.busy = false; row.action = ''; controls(row); }
      }
      card.querySelector('form').onsubmit = function (event) {
        event.preventDefault();
        if (!row.token.value.trim()) { message(row,'请先粘贴 supply.ink Token',true); row.token.focus(); return; }
        run('save',async function () {
          var payload = {token:row.token.value.trim(), name:row.name.value.trim()};
          var data = await request(row.draft ? 'tokens' : 'tokens/' + row.config.id, row.draft ? 'POST' : 'PUT', payload);
          if (row.draft) {
            rows.delete(row.config.id); row.config.id = data.created_id; row.draft = false;
            card.dataset.tokenId = data.created_id; rows.set(data.created_id,row);
          }
          render(data,row.config.id); message(row,'已保存');
        });
      };
      row.test.onclick = function () {
        run('test',async function () {
          try {
            var result = await request('tokens/' + row.config.id + '/test','POST');
            row.config.health = result.health || {status:result.ok ? 'ok' : 'error'};
          } catch (error) { row.config.health = {status:'error'}; throw error; }
        });
      };
      row.clear.onclick = function () {
        run('clear',async function () { render(await request('tokens/' + row.config.id,'PUT',{clear_token:true}),row.config.id); message(row,'已清除'); });
      };
      row.toggle.onclick = function () {
        run('toggle',async function () { render(await request('tokens/' + row.config.id,'PUT',{enabled:row.config.enabled === false}),row.config.id,false); });
      };
      var remove = card.querySelector('.sm-remove');
      if (remove) remove.onclick = function () {
        if (row.draft) { rows.delete(row.config.id); card.remove(); return; }
        run('remove',async function () {
          var data = await request('tokens/' + row.config.id,'DELETE');
          rows.delete(row.config.id); card.remove(); render(data);
        });
      };
      return row;
    }
    async function load() {
      if (loading) return;
      loading = true;
      try { render(await request('config')); }
      catch (error) {
        root.querySelector('.sm-load-result').textContent = error.message || '配置读取失败';
        root.querySelector('.sm-retry').hidden = false;
      } finally { loading = false; }
    }
    root.querySelector('.sm-add').onclick = function () {
      var row = createRow({id:'draft-' + (++draftCount), name:'Token ' + (rows.size + 1), token:'', enabled:true},true);
      row.token.focus();
    };
    root.querySelector('.sm-retry').onclick = load;
    root.addEventListener('okad-supply-refresh',load);
    setTimeout(load,0);
    return root;
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
