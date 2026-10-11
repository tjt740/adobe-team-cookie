/* Reliable integration as a page in the existing authenticated Okad workspace. */
(function () {
  'use strict';
  var panel, page = 1, total = 0, active = false, generation = 0;
  var refreshing = false, acting = false, poll = null, reads = new Set();
  var requestID = 0, loaded = false, dirty = false, connected = false, lastChecked = 0, trackedJob = '';
  var labels = {pending:'等待同步', retry:'等待补推或验证', ready:'已验证 · 可调度',
    paused:'已验证 · 保持暂停', attention:'需要处理', blocked:'已停止 · 需要处理',
    queued:'排队', running:'登录中', done:'登录完成', failed:'未完成'};

  function el(id) { return panel.querySelector('#integration-' + id); }
  function esc(value) {
    return String(value == null ? '' : value).replace(/[&<>"']/g, function (c) {
      return {'&':'&amp;', '<':'&lt;', '>':'&gt;', '"':'&quot;', "'":'&#39;'}[c];
    });
  }
  function text(node, value) {
    value = String(value == null ? '' : value);
    if (node.textContent !== value) node.textContent = value;
  }
  function notice(message) { text(el('notice'), message || ''); }
  // Keep existing buttons, focused elements and text selections across polling.
  function patch(node, next) {
    if (node.nodeType !== next.nodeType || node.nodeName !== next.nodeName) {
      node.replaceWith(next.cloneNode(true)); return;
    }
    if (node.nodeType === 3) {
      if (node.nodeValue !== next.nodeValue) node.nodeValue = next.nodeValue;
      return;
    }
    Array.from(node.attributes || []).forEach(function (attr) {
      if (!next.hasAttribute(attr.name) && attr.name !== 'disabled') node.removeAttribute(attr.name);
    });
    Array.from(next.attributes || []).forEach(function (attr) {
      if (node.getAttribute(attr.name) !== attr.value) node.setAttribute(attr.name, attr.value);
    });
    Array.from(next.childNodes).forEach(function (child, index) {
      if (node.childNodes[index]) patch(node.childNodes[index], child);
      else node.appendChild(child.cloneNode(true));
    });
    while (node.childNodes.length > next.childNodes.length) node.lastChild.remove();
  }
  function reconcile(container, items, html, empty) {
    if (!items.length && container._empty === empty && container.firstChild) return;
    var retained = new Set(), cursor = container.firstElementChild;
    items.forEach(function (item) {
      var key = item.job_id || item.source_key, markup = html(item);
      var node = Array.from(container.children).find(function (child) { return child.dataset.key === key; });
      if (!node || node._markup !== markup) {
        var template = document.createElement('template'); template.innerHTML = markup;
        if (node) patch(node, template.content.firstElementChild);
        else node = template.content.firstElementChild;
        node.dataset.key = key; node._markup = markup;
      }
      retained.add(node);
      if (node !== cursor) container.insertBefore(node, cursor);
      cursor = node.nextElementSibling;
    });
    Array.from(container.children).forEach(function (node) { if (!retained.has(node)) node.remove(); });
    if (!items.length && container._empty !== empty) { container.innerHTML = empty; }
    else if (!items.length && !container.firstChild) container.innerHTML = empty;
    container._empty = items.length ? null : empty;
  }
  function cancelReads() {
    requestID++; reads.forEach(function (controller) { controller.abort(); }); reads.clear(); refreshing = false;
  }
  function badge(state) {
    var tone = ['ready','done'].includes(state) ? 'good' : ['attention','blocked','failed'].includes(state) ? 'bad' : 'warn';
    return '<span class="integration-badge ' + tone + '">' + esc(labels[state] || state) + '</span>';
  }
  async function api(path, method, body) {
    var token = localStorage.getItem('okad_token');
    if (!token) throw Error('登录已过期，请重新登录 Okad。');
    var controller = new AbortController(), read = !method || method === 'GET';
    if (read) reads.add(controller);
    var timeout = setTimeout(function () { controller.abort(); }, 30000);
    try {
      var response = await fetch(window.OKAD_ROUTE.href('/api/integration' + path), {
        method:method || 'GET', signal:controller.signal,
        headers:{Authorization:'Bearer ' + token, 'Content-Type':'application/json'},
        body:body ? JSON.stringify(body) : undefined
      });
      if (response.status === 401) throw Error('登录已过期，请重新登录 Okad。');
      var data;
      try { data = await response.json(); } catch (_) { throw Error('服务返回异常（HTTP ' + response.status + '），请稍后重试。'); }
      if (!response.ok) throw Error(typeof data.detail === 'string' ? data.detail : '请求未完成（HTTP ' + response.status + '）');
      return data;
    } catch (error) {
      if (error.name === 'AbortError') throw Error(read ? '请求超时，请稍后刷新重试。' : '提交结果尚未确认，请刷新状态核对后再操作。');
      throw error;
    } finally {
      clearTimeout(timeout);
      reads.delete(controller);
    }
  }
  function controls() {
    el('refresh').disabled = acting;
    el('prev').disabled = acting || page <= 1;
    el('next').disabled = acting || page * 100 >= total;
    el('config').querySelectorAll('button,input').forEach(function (input) { input.disabled = acting; });
    panel.querySelectorAll('button[data-action]').forEach(function (button) {
      button.disabled = acting || !connected || button.dataset.unavailable === 'true';
    });
    text(el('activity'), acting ? '正在提交…' : refreshing && !loaded ? '正在读取状态…' :
      lastChecked ? '更新于 ' + new Date(lastChecked * 1000).toLocaleTimeString() + ' · 自动更新' : '等待读取状态');
  }
  function render(status, sources) {
    total = sources.total;
    if (!dirty && !acting) {
      if (el('base').value !== status.config.base_url) el('base').value = status.config.base_url;
      el('enabled').checked = status.config.enabled;
    }
    connected = !!(status.config.enabled && status.config.key_configured && status.config.site_id);
    text(el('connection'), connected ? '已启用 · ' + status.config.site_id : '尚未启用');
    el('setup').hidden = connected;
    lastChecked = status.checked_at || Date.now() / 1000;
    text(el('queued'), (status.counts.pending || 0) + (status.counts.retry || 0));
    text(el('ready'), status.counts.ready || 0);
    text(el('attention'), (status.counts.attention || 0) + (status.counts.blocked || 0) + (status.counts.paused || 0));
    text(el('running'), status.active_jobs || 0);
    reconcile(el('sources'), sources.items, function (row) {
      var delivery = row.delivery;
      return '<tr><td><span class="integration-email">' + esc(row.email) + '</span><small>' + esc(row.source) + ' · ' + esc(row.source_key) +
        (delivery && delivery.account_id ? ' · Sub2 #' + esc(delivery.account_id) : '') + '</small></td><td>' +
        '<span class="integration-badge ' + (row.auto_recovery ? 'good' : 'warn') + '">' + (row.auto_recovery ? '可自动恢复' : row.recovery_code === 'configuration' ? '等待连接配置' : '需要处理') + '</span><small>' + esc(row.recovery_message) + '</small></td><td>' +
        (row.has_cookie ? (row.version ? 'v' + esc(row.version) : '待编号') : '尚无 Cookie') + '</td><td>' +
        (delivery ? badge(delivery.state) + '<small>' + esc(delivery.message) + (delivery.next_at ? ' · 下次 ' + new Date(delivery.next_at * 1000).toLocaleTimeString() : '') + (delivery.updated_at ? '<br>更新于 ' + new Date(delivery.updated_at * 1000).toLocaleString() : '') + '</small>' : '<span class="integration-muted">尚未登记可靠同步</span>') +
        '</td><td><div class="integration-actions"><button data-action="' + (delivery ? 'retry-sync' : 'push') + '" data-source="' + esc(row.source_key) + '" data-unavailable="' + !row.has_cookie + '">' +
        (delivery ? '同步与验证' : '推送入库') + '</button>' + (row.recovery_code === 'needs_manual' ?
          '<a data-route href="' + window.OKAD_ROUTE.href('/external-members') + '">手动验证码登录</a>' :
          '<button class="secondary" data-action="login" data-source="' + esc(row.source_key) + '" data-unavailable="' + !row.auto_recovery + '" title="' + esc(row.recovery_message || '重新登录并获取 Cookie') + '">重新授权</button>') + '</div></td></tr>';
    }, '<tr><td colspan="5" class="integration-empty">暂无账号，请先在 Okad 导入账号。</td></tr>');
    text(el('page'), page + ' / ' + Math.max(1, Math.ceil(total / 100)) + ' · ' + total + ' 个账号');
    reconcile(el('jobs'), status.jobs.slice(0,20), function (job) {
      return '<div class="integration-job">' + badge(job.state) + '<span>' + esc(job.email) + '<small>' + esc(job.message) + '</small></span><small>' + new Date(job.created_at * 1000).toLocaleString() + '</small></div>';
    }, '<div class="integration-empty">暂无恢复任务</div>');
    if (trackedJob) {
      var job = status.jobs.find(function (item) { return item.job_id === trackedJob; });
      if (job) {
        notice((labels[job.state] || job.state) + '：' + (job.message || job.email));
        if (['done','failed'].includes(job.state)) trackedJob = '';
      }
    }
    loaded = true;
  }
  async function refresh(targetPage, manual) {
    if (!active || acting || (refreshing && !manual)) return;
    if (manual) cancelReads();
    var current = generation, id = ++requestID, requestedPage = targetPage || page;
    refreshing = true; controls();
    try {
      var results = await Promise.all([api('/status'), api('/sources?page=' + requestedPage)]);
      if (active && current === generation && id === requestID) {
        var changedPage = page !== (results[1].page || requestedPage);
        page = results[1].page || requestedPage;
        render(results[0], results[1]);
        if (changedPage) panel.querySelector('.integration-scroll').scrollTop = 0;
      }
    } catch (error) {
      if (active && current === generation && id === requestID) notice('状态更新失败，保留上次结果。' + error.message);
    } finally {
      if (current === generation && id === requestID) { refreshing = false; controls(); }
    }
  }
  async function mutate(path, method, body, configuration) {
    if (acting) return;
    cancelReads();
    var current = generation;
    acting = true; trackedJob = ''; controls(); notice('');
    try {
      var result = await api(path, method, body);
      if (result.job_id) trackedJob = result.job_id;
      if (configuration) {
        el('key').value = ''; dirty = false;
        el('base').value = result.base_url;
        el('enabled').checked = result.enabled;
      }
      if (active && current === generation) {
        notice(configuration ? (result.enabled ? '连接已核验，配置已保存。' : '已停用可靠联动，原有推送和登录入口仍可使用。') : result.message || '任务已提交，处理进度见下方任务列表。');
      }
    } catch (error) {
      if (active && current === generation) notice(error.message);
    } finally {
      // A write continues after navigation; never allow a second submission until it ends.
      acting = false; controls();
      if (active) refresh();
    }
  }
  function build() {
    if (panel) return;
    panel = document.createElement('section');
    panel.id = 'integration-panel';
    panel.setAttribute('aria-label', '联动中心');
    panel.hidden = true;
    panel.innerHTML = `
      <div class="integration-workspace ws-page">
        <header class="ws-heading"><div><h2>联动中心</h2><p>查看 Okad 与 Sub2 之间的账号登录、同步和验证状态。</p></div>
          <div class="integration-refresh"><small id="integration-activity" role="status">正在读取状态…</small><button id="integration-refresh" class="secondary">刷新状态</button></div></header>
        <div id="integration-notice" role="status" aria-live="polite"></div>
        <div id="integration-setup" class="integration-setup" hidden>可靠联动尚未启用，请先展开连接配置并测试保存。原有账号的推送和登录仍可在 <a data-route href="${window.OKAD_ROUTE.href('/external-members')}">外部子号</a> 操作；本页未登记不代表 Sub2 中没有该账号。</div>
        <div class="integration-metrics">
          <article><small>等待同步 / 重试</small><strong id="integration-queued">—</strong></article>
          <article><small>已验证并可调度</small><strong id="integration-ready">—</strong></article>
          <article><small>需要处理 / 已暂停</small><strong id="integration-attention">—</strong></article>
          <article><small>登录任务进行中</small><strong id="integration-running">—</strong></article>
        </div>
        <details class="integration-config"><summary>连接配置 <span id="integration-connection">正在读取</span></summary>
          <form id="integration-config">
            <label>Sub2 地址<input id="integration-base" type="url" required placeholder="http://127.0.0.1:18080"></label>
            <label>专用联动密钥<input id="integration-key" type="password" autocomplete="new-password" placeholder="已配置时留空保留"></label>
            <label class="integration-check"><input id="integration-enabled" type="checkbox">启用可靠联动</label>
            <button>测试连接并保存</button>
          </form>
          <p class="integration-muted">首次入库使用 <a data-route href="${window.OKAD_ROUTE.href('/sub2')}">Sub2 管理</a> 中的管理员配置和 Adobe 分组。</p>
        </details>
        <section class="integration-section"><div class="integration-section-heading"><h3>账号联动状态</h3>
          <p class="integration-muted">同步与验证不会重新登录，人工暂停会保留；远端状态约每 30 秒核对一次。</p></div>
          <div class="integration-scroll"><table><thead><tr><th>账号 / 来源</th><th>自动恢复</th><th>凭据版本</th><th>同步与验证</th><th>操作</th></tr></thead><tbody id="integration-sources"><tr><td colspan="5" class="integration-empty">正在读取账号状态…</td></tr></tbody></table></div>
          <footer><button id="integration-prev" class="secondary">上一页</button><span id="integration-page">—</span><button id="integration-next" class="secondary">下一页</button></footer>
        </section>
        <section class="integration-section"><div class="integration-section-heading"><h3>最近恢复任务</h3><p class="integration-muted">同一账号的并发登录会合并。</p></div><div id="integration-jobs"></div></section>
        <p class="integration-footnote integration-muted">凭据验证检查实时 Token 与额度，模型出图能力仍需在 Sub2 实际测试。</p>
      </div>`;
    document.body.appendChild(panel);
    el('config').addEventListener('input', function () { dirty = true; });
    el('config').onsubmit = function (event) {
      event.preventDefault();
      mutate('/config', 'PUT', {enabled:el('enabled').checked, base_url:el('base').value, integration_key:el('key').value}, true);
    };
    el('sources').onclick = function (event) {
      var button = event.target.closest('button[data-action]');
      if (button && !button.disabled) mutate('/' + button.dataset.action, 'POST', {source_key:button.dataset.source}, false);
    };
    panel.addEventListener('click', function (event) {
      var link = event.target.closest('a[data-route]');
      if (!link || event.button !== 0 || event.ctrlKey || event.metaKey || event.shiftKey || event.altKey) return;
      event.preventDefault();
      window.OKAD_NAV.navigate(link.getAttribute('href'));
    });
    el('refresh').onclick = function () { refresh(page, true); };
    el('prev').onclick = function () { refresh(page - 1, true); };
    el('next').onclick = function () { refresh(page + 1, true); };
  }
  function layout() {
    if (!panel) return;
    var rect = window.OKAD_NAV.rect();
    if (panel.style.left !== rect.left + 'px') panel.style.left = rect.left + 'px';
    if (panel.style.top !== rect.top + 'px') panel.style.top = rect.top + 'px';
  }
  function close() {
    active = false;
    generation++;
    clearInterval(poll);
    poll = null;
    cancelReads();
    if (panel) { panel.hidden = true; el('key').value = ''; }
  }
  function open() {
    if (active) return;
    build();
    generation++;
    active = true;
    panel.hidden = false;
    layout();
    notice('');
    refresh();
    poll = setInterval(function () { if (!document.hidden) refresh(); }, 5000);
  }
  window.OKAD_INTEGRATION = {open:open, close:close, layout:layout};
})();
