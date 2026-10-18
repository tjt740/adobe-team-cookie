/* Read-only telemetry, integrated into the authenticated workspace router. */
(function () {
  'use strict';
  var panel, active = false, paused = false, generation = 0, controller = null;
  var timer = null, minutes = 15, last = null;
  var colors = ['#4384ed', '#27ad91'];
  function el(id) { return panel.querySelector('#monitor-' + id); }
  function esc(value) {
    return String(value == null ? '' : value).replace(/[&<>"']/g, function (c) {
      return {'&':'&amp;', '<':'&lt;', '>':'&gt;', '"':'&quot;', "'":'&#39;'}[c];
    });
  }
  function number(value, unit) { return value == null ? '—' : Number(value).toLocaleString('zh-CN', {maximumFractionDigits:1}) + (unit || ''); }
  function percent(value) { return number(value, '%'); }
  function bytes(value) {
    if (value == null) return '—';
    var index = 0, units = ['B', 'KiB', 'MiB', 'GiB', 'TiB'];
    while (value >= 1024 && index < units.length - 1) { value /= 1024; index++; }
    return number(value) + ' ' + units[index];
  }
  function duration(value) {
    if (value == null) return '—';
    if (value < 60) return Math.floor(value) + ' 秒';
    if (value < 3600) return Math.floor(value / 60) + ' 分钟';
    if (value < 86400) return Math.floor(value / 3600) + ' 小时 ' + Math.floor(value % 3600 / 60) + ' 分钟';
    return Math.floor(value / 86400) + ' 天 ' + Math.floor(value % 86400 / 3600) + ' 小时';
  }
  function time(ts) { return new Date(ts * 1000).toLocaleTimeString('zh-CN', {hour12:false}); }
  function card(id, value, detail) {
    el(id + '-value').textContent = percent(value);
    el(id + '-detail').textContent = detail;
    el(id + '-bar').style.width = (value == null ? 0 : Math.min(100, value)) + '%';
    el(id + '-bar').dataset.tone = value == null ? 'unknown' : value >= 90 ? 'bad' : value >= 80 ? 'warn' : 'good';
  }
  function chart(id, title, rows, series, format, fixedMax) {
    var host = el(id), values = rows.flatMap(function (row) { return series.map(function (s) { return row[s.key]; }); }).filter(function (v) { return v != null; });
    var legend = series.map(function (s, i) {
      var latest = rows.length ? rows[rows.length - 1][s.key] : null;
      return '<span><i style="background:' + colors[i] + '"></i>' + esc(s.label) + ' <b>' + esc(format(latest)) + '</b></span>';
    }).join('');
    if (!values.length) {
      host.innerHTML = '<div class="monitor-chart-empty">暂无可用采样，等待数据</div><div class="monitor-legend">' + legend + '</div>';
      return;
    }
    var max = fixedMax || Math.max(1, Math.max.apply(null, values) * 1.2);
    var end = rows[rows.length - 1].ts, start = end - minutes * 60;
    var x = function (ts) { return 65 + (ts - start) / (end - start) * 615; };
    var y = function (value) { return 170 - Math.min(max, Math.max(0, value)) / max * 150; };
    var svg = '<svg viewBox="0 0 700 205" role="img" aria-label="' + esc(title + '，最近 ' + minutes + ' 分钟') + '"><title>' + esc(title) + '</title>';
    [0, .5, 1].forEach(function (fraction) {
      var level = max * fraction, yy = y(level);
      svg += '<line class="monitor-gridline" x1="65" x2="680" y1="' + yy + '" y2="' + yy + '"/><text x="55" y="' + (yy + 4) + '" text-anchor="end">' + esc(format(level)) + '</text>';
    });
    series.forEach(function (s, i) {
      var path = '', previous = null, dots = '';
      rows.forEach(function (row) {
        var value = row[s.key];
        if (value == null) { previous = null; return; }
        var xx = x(row.ts).toFixed(1), yy = y(value).toFixed(1);
        path += (previous != null && row.ts - previous <= 15 ? 'L' : 'M') + xx + ',' + yy;
        dots += '<circle cx="' + xx + '" cy="' + yy + '" r="2" fill="' + colors[i] + '"><title>' + esc(time(row.ts) + ' · ' + s.label + ' ' + format(value)) + '</title></circle>';
        previous = row.ts;
      });
      svg += '<path d="' + path + '" fill="none" stroke="' + colors[i] + '" stroke-width="2.5" stroke-linejoin="round"/>' + dots;
    });
    [start, (start + end) / 2, end].forEach(function (ts, i) {
      svg += '<text x="' + x(ts) + '" y="196" text-anchor="' + (i === 0 ? 'start' : i === 2 ? 'end' : 'middle') + '">' + esc(time(ts)) + '</text>';
    });
    host.innerHTML = svg + '</svg><div class="monitor-legend">' + legend + '</div>';
  }
  function metric(label, value, note) {
    return '<article><span>' + esc(label) + '</span><strong>' + esc(value) + '</strong><small>' + esc(note) + '</small></article>';
  }
  function render(data) {
    last = data;
    var c = data.current;
    if (!c) {
      ['cpu','memory','app','disk'].forEach(function (id) { card(id, null, '等待采样'); });
      ['cpu-chart','memory-chart','network-chart','latency-chart'].forEach(function (id) {
        el(id).innerHTML = '<div class="monitor-chart-empty">等待采样</div>';
      });
      ['http','jobs','details','alerts'].forEach(function (id) { el(id).replaceChildren(); });
      el('updated').textContent = '';
      el('status').textContent = '等待第一条采样';
      el('status').dataset.tone = 'unknown';
      el('notice').textContent = '采集器尚未返回数据；启动后约 5 秒出现 CPU 与网络速率。';
      return;
    }
    var h = c.host, a = c.application, http = c.http, disk = c.disk, jobs = c.jobs;
    el('status').textContent = data.stale ? '数据已过期' : paused ? '已暂停刷新' : '实时采集中';
    el('status').dataset.tone = data.stale || paused ? 'warn' : 'good';
    el('updated').textContent = '采样于 ' + time(c.ts);
    el('notice').textContent = data.stale ? '最近采样未更新，下方保留上次数据。请检查服务或稍后刷新。' : '';
    el('scope').textContent = '当前环境：' + (data.container ? '应用容器' : data.platform) + ' · 每 ' + data.interval_seconds + ' 秒采样 · ' + h.cores + ' 个逻辑核心';
    card('cpu', h.cpu_percent, '整台服务器 · I/O 等待 ' + percent(h.io_wait_percent));
    card('memory', h.memory_percent, bytes(h.memory_used) + ' / ' + bytes(h.memory_total) + ' · 整机');
    card('app', a.memory_percent, a.available ? bytes(a.memory_used) + (a.memory_limit ? ' / ' + bytes(a.memory_limit) + ' · 含缓存' : ' · 未设置可见内存上限') : '当前环境不提供资源组计数');
    if (a.available && a.memory_limit == null) el('app-value').textContent = bytes(a.memory_used);
    card('disk', disk.percent, '可用 ' + bytes(disk.free) + ' / ' + bytes(disk.total));
    var alerts = c.alerts || [];
    el('alerts').innerHTML = alerts.length ? alerts.map(function (item) {
      return '<p class="monitor-alert ' + esc(item.level) + '">' + esc(item.message) + '</p>';
    }).join('') : '<p class="monitor-alert neutral">' + (data.stale ? '等待恢复采样后判断资源状态。' : h.cpu_percent == null || h.memory_percent == null || !a.available || disk.percent == null ? '部分指标尚不可用；已有指标未触及提醒阈值。' : '当前资源未触及提醒阈值。持续高于 80% 时，建议检查并发和任务积压。') + '</p>';
    el('http').innerHTML = metric('请求速率', number(http.rps, ' 次/秒'), '最近 60 秒 · ' + http.count + ' 次请求') +
      metric('P95 耗时', number(http.p95_ms, ' ms'), http.latency_samples ? http.latency_samples + ' 条耗时样本' : '暂无请求，等待样本') +
      metric('服务端错误', number(http.server_errors), '5xx 比例 ' + percent(http.error_percent)) +
      metric('正在处理', number(http.active), '当前应用内的 API 请求');
    chart('cpu-chart', 'CPU 使用率', data.history, [{key:'cpu', label:'整机'}, {key:'app_cpu', label:'应用 / 可用 CPU 额度'}], percent, 100);
    chart('memory-chart', '内存使用率', data.history, [{key:'memory', label:'整机'}, {key:'app_memory', label:'应用 / 内存上限'}], percent, 100);
    chart('network-chart', '网络吞吐', data.history, [{key:'rx', label:'接收'}, {key:'tx', label:'发送'}], function (v) { return v == null ? '—' : bytes(v) + '/s'; });
    chart('latency-chart', 'API P95 耗时', data.history, [{key:'p95', label:'P95 耗时'}], function (v) { return number(v, ' ms'); });
    el('jobs').innerHTML = metric('运行中', number(jobs.running), '后台任务') + metric('暂停 / 暂停中', number(jobs.paused + jobs.pausing), '后台任务') + metric('正在停止', number(jobs.cancelling), '等待当前操作结束');
    var rows = [
      ['整机负载 · 1 / 5 / 15 分钟', h.load ? h.load.map(function (v) { return number(v); }).join(' / ') : '—'],
      ['应用可用 CPU 额度', number(a.cpu_capacity, ' 核')],
      ['应用主进程内存 / 线程', bytes(c.process.memory_rss) + ' / ' + number(c.process.threads)],
      ['交换分区用量', bytes(h.swap_used) + ' / ' + bytes(h.swap_total)],
      ['资源组 OOM 终止累计', number(a.oom_kills)],
      ['最近 60 秒 · 4xx / 平均耗时', number(http.client_errors) + ' / ' + number(http.average_ms, ' ms')],
      ['服务器运行时间', duration(h.uptime_seconds)],
      ['本次服务运行时间', duration(c.service_uptime_seconds)]
    ];
    el('details').innerHTML = rows.map(function (row) { return '<div><dt>' + esc(row[0]) + '</dt><dd>' + esc(row[1]) + '</dd></div>'; }).join('');
  }
  function schedule() {
    clearTimeout(timer);
    if (active && !paused && !document.hidden) timer = setTimeout(refresh, 5000);
  }
  async function refresh() {
    if (!active || controller || document.hidden) return;
    clearTimeout(timer);
    var current = generation, request = new AbortController();
    controller = request;
    el('refresh').disabled = true;
    var timeout = setTimeout(function () { request.abort(); }, 10000);
    try {
      var response = await fetch(window.OKAD_ROUTE.href('/api/monitor/snapshot?minutes=' + minutes), {
        headers:{Authorization:'Bearer ' + localStorage.getItem('okad_token')}, signal:request.signal, cache:'no-store'
      });
      if (!response.ok) throw Error(response.status === 401 || response.status === 403 ? '登录已过期，请重新登录后查看。' : '读取监控失败（HTTP ' + response.status + '），请稍后重试。');
      var data = await response.json();
      if (active && current === generation) render(data);
    } catch (error) {
      if (active && current === generation) {
        el('notice').textContent = error.name === 'AbortError' ? '读取超时，下方可能仍是上次采样。' : error.message;
        el('status').textContent = '连接中断';
        el('status').dataset.tone = 'warn';
      }
    } finally {
      clearTimeout(timeout);
      if (controller === request) controller = null;
      if (active && current === generation) { el('refresh').disabled = false; schedule(); }
    }
  }
  function build() {
    if (panel) return;
    panel = document.createElement('section'); panel.id = 'server-monitor-panel';
    panel.setAttribute('aria-label', '服务器监控'); panel.hidden = true;
    var cards = [['cpu','整机 CPU'], ['memory','整机内存'], ['app','应用资源组内存'], ['disk','数据所在磁盘']];
    panel.innerHTML = '<div class="monitor-workspace ws-page">' +
      '<header class="ws-heading"><div><h2>服务器监控 <span id="monitor-status" data-tone="unknown">正在连接</span></h2><p id="monitor-scope">查看资源压力、请求表现与后台任务</p></div><div class="monitor-actions"><span id="monitor-updated"></span><button id="monitor-pause">暂停刷新</button><button id="monitor-refresh">立即刷新</button></div></header>' +
      '<div id="monitor-notice" role="status" aria-live="polite"></div>' +
      '<div class="monitor-cards">' + cards.map(function (item) { return '<article><span>' + item[1] + '</span><strong id="monitor-' + item[0] + '-value">—</strong><div class="monitor-track"><i id="monitor-' + item[0] + '-bar"></i></div><small id="monitor-' + item[0] + '-detail">等待采样</small></article>'; }).join('') + '</div>' +
      '<div id="monitor-alerts"></div><div class="monitor-section-heading"><h3>资源趋势</h3><label>时间范围 <select id="monitor-range" aria-label="趋势时间范围"><option value="5">最近 5 分钟</option><option value="15" selected>最近 15 分钟</option><option value="60">最近 1 小时</option></select></label></div>' +
      '<div class="monitor-charts">' + [['cpu-chart','CPU 使用率','整机与应用可用额度分别计算'], ['memory-chart','内存使用率','应用用量包含文件缓存'], ['network-chart','网络吞吐','当前网络命名空间 · 容器内为容器流量'], ['latency-chart','API 响应耗时','每个点统计此前 60 秒的请求']].map(function (c) {
        return '<section class="monitor-box"><h3>' + c[1] + '</h3><p>' + c[2] + '</p><div id="monitor-' + c[0] + '"><div class="monitor-chart-empty">等待采样</div></div></section>';
      }).join('') + '</div>' +
      '<section class="monitor-box"><div class="monitor-section-heading"><h3>应用请求 · 最近 60 秒</h3><a data-route href="' + window.OKAD_ROUTE.href('/logs') + '">查看日志 →</a></div><div class="monitor-stats" id="monitor-http"></div><p>仅统计此 Okad 服务的 API；不含健康检查、监控轮询和 Sub2 自身接口。P95 表示 95% 的耗时样本不超过该值，最多保留最近 10,000 条样本。</p></section>' +
      '<div class="monitor-bottom"><section class="monitor-box"><div class="monitor-section-heading"><h3>后台任务</h3><a data-route href="' + window.OKAD_ROUTE.href('/jobs') + '">任务中心 →</a></div><div class="monitor-stats monitor-job-stats" id="monitor-jobs"></div><p>当前进程任务管理器中的任务，不含联动中心的独立恢复队列。任务数量不等于正在登录的账号数量。</p></section>' +
      '<section class="monitor-box"><h3>运行信息</h3><dl id="monitor-details"></dl></section></div>' +
      '<details class="monitor-help"><summary>如何判断压力和理解数据范围</summary><p>CPU、内存或数据盘达到 80% 会提醒，90% 会标红。这是单次采样提示，是否扩容应结合持续时间、接口耗时与错误一起判断。整机负载包含等待 CPU 和部分 I/O 的任务，需结合逻辑核心数量观察。</p><p>整机指标读取 Linux 内核可见的主机计数。应用指标读取当前资源组（Docker 部署时为应用容器），可用 CPU 额度同时考虑可见配额和 CPU 亲和性；内存上限考虑可见父组限制。网络仅覆盖当前网络命名空间，磁盘容量对应应用数据库所在文件系统。</p><p>采样不依赖页面打开。历史保留最近 1 小时，服务重启后重新积累；缺失数据以 — 或图表空缺表示。应用未设置可见内存上限时只显示用量。非 Linux 环境可能仅提供磁盘、负载与请求数据。默认单进程部署；多 worker 的请求和任务指标为当前 worker。</p></details>' +
      '<p class="monitor-footnote">只读监控 · 不会触发登录、推送或外部健康探测</p></div>';
    document.body.appendChild(panel);
    el('refresh').onclick = refresh;
    el('pause').onclick = function () {
      paused = !paused;
      el('pause').textContent = paused ? '继续刷新' : '暂停刷新';
      clearTimeout(timer);
      if (last) render(last);
      if (!paused) refresh();
    };
    el('range').onchange = function () {
      minutes = Number(el('range').value);
      generation++;
      if (controller) { controller.abort(); controller = null; }
      refresh();
    };
    panel.addEventListener('click', function (event) {
      var link = event.target.closest('a[data-route]');
      if (link && event.button === 0 && !event.ctrlKey && !event.metaKey && !event.shiftKey && !event.altKey) {
        event.preventDefault(); window.OKAD_NAV.navigate(link.getAttribute('href'));
      }
    });
  }
  function layout() {
    if (!panel || panel.hidden) return;
    var rect = window.OKAD_NAV.rect();
    panel.style.left = rect.left + 'px'; panel.style.top = rect.top + 'px';
  }
  function open() {
    build(); active = true; generation++; panel.hidden = false;
    el('notice').textContent = ''; el('status').textContent = '正在连接'; el('status').dataset.tone = 'unknown';
    layout(); refresh();
  }
  function close() {
    active = false; generation++; clearTimeout(timer);
    if (controller) { controller.abort(); controller = null; }
    if (panel) panel.hidden = true;
  }
  document.addEventListener('visibilitychange', function () {
    if (!active) return;
    clearTimeout(timer);
    if (document.hidden) {
      generation++;
      if (controller) { controller.abort(); controller = null; }
    } else if (!paused) refresh();
  });
  window.OKAD_NAV.register({id:'server-monitor-nav', route:'server-monitor', panel:'server-monitor-panel',
    label:'服务器监控', icon:'monitor', open:open, close:close, layout:layout});
})();
