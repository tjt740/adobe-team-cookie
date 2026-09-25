(function () {
  'use strict';
  if (window.__clashSettings) return;
  window.__clashSettings = true;
  var ID = 'okad-clash-settings';
  var style = document.createElement('style');
  style.textContent = `
    #${ID}{background:var(--n-color,#fff);border:1px solid var(--n-border-color,#efeff5);border-radius:var(--n-border-radius,6px);padding:20px 24px;margin-bottom:20px;width:100%;min-width:0;box-sizing:border-box;color:var(--n-text-color,#333639);font-size:14px;line-height:1.6}
    #${ID} h3{margin:0;font-size:var(--n-title-font-size,18px);font-weight:var(--n-title-font-weight,500);color:var(--n-title-text-color,#1f2225)}
    #${ID} .cl-head,#${ID} .cl-actions{display:flex;align-items:center;gap:10px;flex-wrap:wrap}
    #${ID} .cl-head{justify-content:space-between;margin-bottom:12px}
    #${ID} .cl-power-group{display:flex;align-items:center;gap:10px}
    #${ID} button.cl-power{position:relative;width:42px;height:24px;padding:0;border:0;border-radius:12px;background:#b8bec7;transition:background .2s;flex:none}
    #${ID} button.cl-power[aria-checked="true"]{background:#1890ff}
    #${ID} button.cl-power:after{content:"";position:absolute;left:3px;top:3px;width:18px;height:18px;border-radius:50%;background:#fff;box-shadow:0 1px 3px #0002;transition:transform .2s}
    #${ID} button.cl-power[aria-checked="true"]:after{transform:translateX(18px)}
    #${ID} button.cl-power.loading:before{position:absolute;z-index:1;left:6px;top:6px;width:8px;height:8px;margin:0;color:#1890ff}
    #${ID} button.cl-power.loading[aria-checked="true"]:before{left:24px}
    #${ID} button.cl-power:focus-visible{outline:2px solid #1890ff;outline-offset:3px}
    #${ID} .cl-badge{padding:3px 9px;border-radius:4px;font-size:12px;background:rgba(24,160,88,.1);color:#18a058}
    #${ID} .cl-badge.off{background:rgba(128,128,128,.1);color:inherit;opacity:.7}
    #${ID} .cl-help,#${ID} .cl-meta{font-size:13px;color:inherit;opacity:.65;line-height:1.7;margin:8px 0}
    #${ID} .cl-meta{display:flex;gap:8px 24px;flex-wrap:wrap}
    #${ID} .cl-row{display:grid;grid-template-columns:120px minmax(0,740px);align-items:start;margin-top:20px}
    #${ID} .cl-field{display:block;font-size:14px;margin:0;padding-right:12px;line-height:34px;text-align:right}
    #${ID} .cl-body{min-width:0}
    #${ID} select,#${ID} input{box-sizing:border-box;min-width:0;width:100%;height:34px;border:1px solid var(--n-border-color,#dcdfe6);border-radius:3px;padding:0 10px;font:14px system-ui;color:inherit;background:var(--n-color,#fff)}
    #${ID} input:focus,#${ID} select:focus{outline:2px solid #1890ff33;border-color:#1890ff}
    #${ID} select{flex:1;min-width:0}
    #${ID} button{border:1px solid var(--n-border-color,#dcdfe6);border-radius:3px;background:transparent;color:inherit;padding:0 14px;height:34px;cursor:pointer;font:14px system-ui;white-space:nowrap}
    #${ID} button.primary{background:#1890ff;border-color:#1890ff;color:#fff}
    #${ID} button:hover{filter:brightness(.97)}
    #${ID} button:disabled{opacity:.5;cursor:not-allowed}
    #${ID} button.loading:before{content:'';display:inline-block;width:11px;height:11px;border:2px solid currentColor;border-right-color:transparent;border-radius:50%;margin-right:7px;vertical-align:-2px;animation:cl-spin .7s linear infinite}
    #${ID} .cl-edit{border-top:1px solid var(--n-border-color,#efeff5);margin-top:20px;padding-top:0}
    #${ID} [hidden]{display:none!important}
    #${ID} .cl-message{font-size:13px;line-height:1.6;margin-top:12px;color:#15934e;overflow-wrap:anywhere}
    #${ID} .cl-message.error{color:#d03050}
    #${ID} .cl-message:empty{display:none}
    .okad-panel-active #${ID}{display:none!important}
    @keyframes cl-spin{to{transform:rotate(360deg)}}
    @media(max-width:760px){#${ID}{padding:20px}#${ID} .cl-row{grid-template-columns:minmax(0,1fr);gap:6px}#${ID} .cl-field{text-align:left;padding:0}#${ID} select{flex-basis:100%}}
    @media(prefers-reduced-motion:reduce){#${ID} button.loading:before{animation:none}}
  `;
  document.head.appendChild(style);

  async function request(path, method, body) {
    var response = await fetch('/api/settings/clash' + path, {
      method: method || 'GET',
      headers: { 'Content-Type':'application/json', Authorization:'Bearer ' + (localStorage.getItem('okad_token') || '') },
      body: body ? JSON.stringify(body) : undefined
    });
    var data = await response.json();
    if (!response.ok) throw new Error(typeof data.detail === 'string' ? data.detail : '操作失败，请稍后重试');
    return data;
  }

  function create() {
    var card = document.createElement('section');
    card.id = ID;
    card.innerHTML = `
      <div class="cl-head"><h3>Clash 订阅代理</h3><div class="cl-power-group"><span class="cl-badge off">加载中</span><button class="cl-power" type="button" role="switch" aria-label="启用 Clash 订阅代理" aria-checked="false" disabled hidden></button></div></div>
      <p class="cl-help cl-description">直接在这里更换订阅和节点，无需修改项目代理地址。</p>
      <div class="cl-controls" hidden>
        <div class="cl-row"><label class="cl-field" for="cl-node">当前节点</label><div class="cl-body">
          <div class="cl-actions"><select id="cl-node" aria-label="当前节点"></select><button class="primary cl-select" type="button">切换节点</button></div>
          <div class="cl-meta"><span class="cl-traffic"></span><span class="cl-expiry"></span></div>
          <p class="cl-help cl-updated"></p>
          <div class="cl-actions"><button class="cl-toggle" type="button" aria-expanded="false">更换订阅</button><button class="cl-refresh" type="button">更新节点</button></div>
        </div></div>
        <form class="cl-edit" hidden>
          <div class="cl-row"><label class="cl-field" for="cl-url">订阅链接</label><div class="cl-body">
          <input id="cl-url" type="password" autocomplete="off" spellcheck="false" placeholder="粘贴 https:// 开头的 Clash 订阅链接" required>
          <p class="cl-help">保存后自动更新节点；原节点仍存在时会保留选择。请等正在运行的任务结束后操作。</p>
          <div class="cl-actions"><button class="primary cl-save" type="submit">保存并更新</button><button class="cl-cancel" type="button">取消</button></div>
          </div></div>
        </form>
      </div>
      <div class="cl-message" role="status" aria-live="polite"></div>
      <button class="cl-retry" type="button" hidden>重新加载</button>
    `;
    var q = function (s) { return card.querySelector(s); };
    var selected = '', busy = false, data = null;
    function message(text, error) {
      q('.cl-message').textContent = text;
      q('.cl-message').classList.toggle('error', !!error);
    }
    function controls() {
      card.querySelectorAll('button,input,select').forEach(function (el) { el.disabled = busy; });
      q('.cl-power').disabled = busy || !data;
      q('.cl-select').disabled = busy || !q('#cl-node').value || q('#cl-node').value === selected;
    }
    function edit(open) {
      q('.cl-edit').hidden = !open;
      q('.cl-toggle').setAttribute('aria-expanded', String(open));
      if (open) q('#cl-url').focus(); else q('#cl-url').value = '';
    }
    function render(value) {
      data = Object.assign({}, data || {}, value);
      q('.cl-retry').hidden = true;
      q('.cl-controls').hidden = !data.available;
      q('.cl-power').hidden = !data.available;
      q('.cl-power').setAttribute('aria-checked', String(!!data.clash_enabled));
      q('.cl-badge').textContent = data.available ? (data.clash_enabled ? '已开启' : '已关闭') : '客户端管理';
      q('.cl-badge').classList.toggle('off', !data.available || !data.clash_enabled);
      q('.cl-description').textContent = data.available ?
        (data.clash_enabled ? '项目请求使用下方所选节点。关闭后恢复本机原有网络，订阅和节点会保留。' : (data.proxy_enabled ? '当前使用其他手动代理。开启后将切换到下方 Clash 节点。' : '已恢复项目所在机器原有网络（如有环境代理则沿用）。订阅和节点已保留，开启即可恢复。')) :
        '此环境未启用项目内订阅管理，可在下方运行设置中配置已有的 HTTP / SOCKS 代理。';
      if (!data.available && ['127.0.0.1', 'localhost', '[::1]'].includes(location.hostname)) {
        q('.cl-description').textContent = '本地可以直接使用电脑上的 Clash，在 Clash 客户端中更换订阅或节点；线上代理需要在线上设置页单独修改。';
      }
      if (!data.available && data.proxy_endpoint) {
        q('.cl-description').textContent += (data.proxy_source === 'environment' ? ' 检测到环境代理：' : ' 项目已配置代理：') + data.proxy_endpoint + '。';
      }
      if (!data.available) return;
      selected = data.selected || '';
      q('.cl-retry').hidden = data.connected !== false;
      q('#cl-node').replaceChildren();
      (data.nodes || []).forEach(function (name) {
        var option = document.createElement('option');
        option.value = name; option.textContent = name;
        q('#cl-node').appendChild(option);
      });
      q('#cl-node').value = selected;
      var gib = function (n) { return (n / Math.pow(1024, 3)).toFixed(1); };
      q('.cl-traffic').textContent = data.total_bytes ? '剩余流量 ' + gib(Math.max(0, data.total_bytes - data.used_bytes)) + ' / ' + gib(data.total_bytes) + ' GB' : '订阅未提供流量信息';
      q('.cl-expiry').textContent = data.expires_at ? '到期 ' + new Date(data.expires_at * 1000).toLocaleString('zh-CN', {hour12:false}) : '订阅未提供到期时间';
      q('.cl-updated').textContent = (data.nodes || []).length + ' 个节点 · 每小时自动更新' + (data.updated_at ? ' · 最近更新 ' + new Date(data.updated_at).toLocaleString('zh-CN', {hour12:false}) : '');
      controls();
    }
    async function run(button, operation, success) {
      if (busy) return;
      busy = true; controls(); button.classList.add('loading'); card.setAttribute('aria-busy', 'true'); message('');
      try {
        var next = await operation();
        if (!card.isConnected) return;
        render(next); message(next.message || success || '');
      } catch (error) {
        if (card.isConnected) message(error.message, true);
      } finally {
        busy = false; button.classList.remove('loading'); card.setAttribute('aria-busy', 'false'); controls();
      }
    }
    async function load() {
      await run(q('.cl-retry'), function () { return request(''); });
      if (!data) { q('.cl-badge').textContent = '暂不可用'; q('.cl-retry').hidden = false; }
    }
    q('.cl-power').onclick = function () {
      var enabled = !data.clash_enabled;
      run(this, async function () {
        var next = await request('/enabled', 'PUT', {enabled:enabled});
        var anchor = Array.from(card.parentElement.querySelectorAll('.n-card')).find(function (el) { var title = el.querySelector('.n-card-header__main'); return title && title.textContent.trim() === '运行设置'; });
        if (anchor) anchor.dispatchEvent(new CustomEvent('okad-proxy-changed'));
        return next;
      }, enabled ? 'Clash 代理已开启' : 'Clash 代理已关闭，已恢复本机原有网络');
    };
    card.addEventListener('okad-settings-saved', load);
    q('.cl-toggle').onclick = function () { edit(q('.cl-edit').hidden); };
    q('.cl-cancel').onclick = function () { edit(false); };
    q('#cl-node').onchange = controls;
    q('.cl-select').onclick = function () {
      run(this, function () { return request('/node', 'PUT', {node:q('#cl-node').value}); }, '节点已切换，建议先用一个账号验证登录和额度');
    };
    q('.cl-refresh').onclick = function () {
      run(this, function () { return request('/refresh', 'POST'); }, '节点已更新');
    };
    q('.cl-edit').onsubmit = function (event) {
      event.preventDefault();
      var url = q('#cl-url').value.trim();
      if (!url.startsWith('https://')) { message('请粘贴 HTTPS Clash 订阅链接', true); return; }
      run(q('.cl-save'), async function () {
        var next = await request('/subscription', 'PUT', {url:url});
        edit(false); return next;
      });
    };
    q('.cl-retry').onclick = load;
    // Start after the card is attached so response handling can detect navigation.
    setTimeout(load, 0);
    return card;
  }

  function install() {
    if (location.pathname.replace(/\/+$/, '') !== '/settings') {
      var old = document.getElementById(ID); if (old) old.remove();
      return;
    }
    var content = document.querySelector('#app .n-layout-content.content');
    if (!content) return;
    var anchor = Array.from(content.querySelectorAll('.n-card')).find(function (card) {
      var title = card.querySelector('.n-card-header__main');
      return title && title.textContent.trim() === '运行设置';
    });
    if (!anchor) return;
    var card = document.getElementById(ID);
    if (!card) { card = create(); anchor.insertAdjacentElement('beforebegin', card); }
    // Follow the native card's theme variables, including live dark-mode changes.
    var theme = anchor.getAttribute('style') || '';
    if (card.getAttribute('style') !== theme) card.setAttribute('style', theme);
  }
  new MutationObserver(install).observe(document.documentElement, { childList:true, subtree:true });
  window.addEventListener('popstate', install);
  window.setInterval(install, 1000);
  install();
})();
