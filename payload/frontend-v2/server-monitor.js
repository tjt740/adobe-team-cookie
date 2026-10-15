/* Read-only telemetry, integrated into the authenticated workspace router. */
(function () {
  'use strict';
  function valid(value) { return typeof value === 'number' && Number.isFinite(value) && value >= 0; }
  function tone(value, warn, bad) { return !valid(value) ? 'unknown' : value >= (bad == null ? 90 : bad) ? 'bad' : value >= (warn == null ? 80 : warn) ? 'warn' : 'good'; }
  var toneLabels = {good:'正常', warn:'关注', bad:'高压', unknown:'暂无数据', info:'参考指标'};
  function resourceScore(value, warn, bad) {
    if (!valid(value) || value > 100) return null;
    if (value < warn * .75) return 100;
    if (value < warn) return 100 - 20 * (value - warn * .75) / (warn * .25);
    if (value < bad) return 79 - 19 * (value - warn) / (bad - warn);
    return Math.max(0, 59 * (100 - value) / (100 - bad));
  }
  // A transparent resource-pressure heuristic, not an availability or Adobe-account score.
  function health(data, suspended) {
    var c = data && data.current;
    if (!c || data.stale || suspended) return {score:null, tone:'unknown', items:[], reason:!c ? '等待第一条资源采样。' : suspended ? '刷新已暂停或连接中断，恢复采样后重新评分。' : '采样已过期，恢复采样后重新评分。'};
    var h = c.host || {}, a = c.application || {}, disk = c.disk || {};
    var items = [
      {label:'整机 CPU', value:h.cpu_percent, weight:20, warn:80, bad:90},
      {label:'整机内存', value:h.memory_percent, weight:25, warn:80, bad:90},
      {label:'数据盘', value:disk.percent, weight:20, warn:80, bad:90},
      {label:'I/O 等待', value:h.io_wait_percent, weight:10, warn:10, bad:20}
    ];
    if (data.container) {
      items.push({label:'Okad CPU', value:a.cpu_percent, weight:10, warn:80, bad:90});
      if (valid(a.memory_limit) && a.memory_limit > 0) items.push({label:'Okad 内存', value:a.memory_percent, weight:15, warn:80, bad:90});
    }
    items.forEach(function (item) { item.score = resourceScore(item.value, item.warn, item.bad); item.tone = item.score == null ? 'unknown' : tone(item.value, item.warn, item.bad); });
    var missing = items.filter(function (item) { return item.score == null; });
    if (missing.length) return {score:null, tone:'unknown', items:items, reason:'缺少 ' + missing.map(function (item) { return item.label; }).join('、') + '，暂不计算总分。'};
    var weight = items.reduce(function (sum, item) { return sum + item.weight; }, 0);
    var score = Math.round(items.reduce(function (sum, item) { return sum + item.score * item.weight; }, 0) / weight);
    var bad = items.some(function (item) { return item.tone === 'bad'; });
    var warn = items.some(function (item) { return item.tone === 'warn'; });
    score = Math.min(score, bad ? 59 : warn ? 79 : 100);
    return {score:score, tone:score >= 80 ? 'good' : score >= 60 ? 'warn' : 'bad', items:items,
      reason:bad ? '存在高压指标，优先检查下方红色项目。' : warn ? '部分资源接近上限，结合趋势检查并发和任务。' : '已采集的资源指标处于正常区间。',
      excluded:data.container && !(valid(a.memory_limit) && a.memory_limit > 0) ? 'Okad 未提供有效内存上限，内存用量只作参考，其余权重归一化。' : !data.container ? '当前非容器环境，仅按整机资源评分，其余权重归一化。' : ''};
  }
  if (typeof window === 'undefined') { module.exports = {health:health, tone:tone, resourceScore:resourceScore}; return; }
  var panel, active = false, paused = false, generation = 0, controller = null;
  var timer = null, minutes = 15, last = null;
  var colors = ['#3b82f6', '#a78bfa'];
  var disconnected = false;
  var businessMinutes = 15, businessController = null, businessNext = 0, businessLast = null;
  function el(id) { return panel.querySelector('#monitor-' + id); }
  function esc(value) {
    return String(value == null ? '' : value).replace(/[&<>"']/g, function (c) {
      return {'&':'&amp;', '<':'&lt;', '>':'&gt;', '"':'&quot;', "'":'&#39;'}[c];
    });
  }
  function number(value, unit) { return !valid(value) ? '—' : Number(value).toLocaleString('zh-CN', {maximumFractionDigits:1}) + (unit || ''); }
  function percent(value) { return number(value, '%'); }
  function bytes(value) {
    if (!valid(value)) return '—';
    var index = 0, units = ['B', 'KiB', 'MiB', 'GiB', 'TiB'];
    while (value >= 1024 && index < units.length - 1) { value /= 1024; index++; }
    return number(value) + ' ' + units[index];
  }
  function duration(value) {
    if (!valid(value)) return '—';
    if (value < 60) return Math.floor(value) + ' 秒';
    if (value < 3600) return Math.floor(value / 60) + ' 分钟';
    if (value < 86400) return Math.floor(value / 3600) + ' 小时 ' + Math.floor(value % 3600 / 60) + ' 分钟';
    return Math.floor(value / 86400) + ' 天 ' + Math.floor(value % 86400 / 3600) + ' 小时';
  }
  function time(ts) { return new Date(ts * 1000).toLocaleTimeString('zh-CN', {hour12:false}); }
  function badge(state, label) { return '<span class="monitor-badge" data-tone="' + state + '">' + esc(label || toneLabels[state]) + '</span>'; }
  function card(id, value, detail, warn, bad) {
    el(id + '-value').textContent = percent(value);
    el(id + '-detail').textContent = detail;
    el(id + '-bar').style.width = (value == null ? 0 : Math.min(100, value)) + '%';
    var state = valid(value) && value <= 100 ? tone(value, warn, bad) : 'unknown';
    el(id + '-card').dataset.tone = state;
    el(id + '-state').innerHTML = badge(state);
    el(id + '-bar').dataset.tone = state;
  }
  function chart(id, title, rows, series, format, fixedMax, options) {
    options = options || {};
    var chartMinutes = options.minutes || minutes;
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
    var end = options.end || rows[rows.length - 1].ts, start = options.start || end - chartMinutes * 60;
    var x = function (ts) { return 65 + (ts - start) / (end - start) * 615; };
    var y = function (value) { return 170 - Math.min(max, Math.max(0, value)) / max * 150; };
    var svg = '<svg viewBox="0 0 700 205" role="img" aria-label="' + esc(title + '，最近 ' + chartMinutes + ' 分钟') + '"><title>' + esc(title) + '</title>';
    [0, .5, 1].forEach(function (fraction) {
      var level = max * fraction, yy = y(level);
      svg += '<line class="monitor-gridline" x1="65" x2="680" y1="' + yy + '" y2="' + yy + '"/><text x="55" y="' + (yy + 4) + '" text-anchor="end">' + esc(format(level)) + '</text>';
    });
    series.forEach(function (s, i) {
      var path = '', previous = null, dots = '';
      rows.forEach(function (row) {
        var value = row[s.key];
        if (value == null || row.ts < start || row.ts > end) { previous = null; return; }
        var xx = x(row.ts).toFixed(1), yy = y(value).toFixed(1);
        path += (previous != null && row.ts - previous <= (options.maxGap || 15) ? 'L' : 'M') + xx + ',' + yy;
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
  function metric(label, value, note, state) {
    state = value === '—' ? 'unknown' : state || 'info';
    return '<article data-tone="' + state + '"><div class="monitor-metric-heading"><span>' + esc(label) + '</span>' + badge(state, state === 'bad' ? '异常' : undefined) + '</div><strong>' + esc(value) + '</strong><small>' + esc(note) + '</small></article>';
  }
  function renderHealth(data) {
    var result = health(data, paused || disconnected);
    el('health').dataset.tone = result.tone;
    el('score').textContent = result.score == null ? '—' : result.score;
    el('health-state').innerHTML = badge(result.tone, result.score == null ? '暂不评分' : toneLabels[result.tone]);
    el('health-reason').textContent = result.reason;
    el('health-excluded').textContent = result.excluded || '';
    el('score-items').innerHTML = result.items.map(function (item) {
      return '<li><div><span>' + esc(item.label) + '</span>' + badge(item.tone) + '</div><strong>' + percent(item.value) + '</strong><small>单项 ' + (item.score == null ? '—' : Math.round(item.score)) + ' 分 · 基础权重 ' + item.weight + '%</small></li>';
    }).join('');
    panel.dataset.outdated = String(!!(data.stale || paused || disconnected || !data.current));
  }
  function render(data) {
    last = data;
    renderHealth(data);
    var c = data.current;
    if (!c) {
      ['cpu','memory','app','disk','app-cpu','io'].forEach(function (id) { card(id, null, '等待采样'); });
      ['cpu-chart','memory-chart','network-chart','latency-chart'].forEach(function (id) {
        el(id).innerHTML = '<div class="monitor-chart-empty">等待采样</div>';
      });
      ['http','jobs','details','alerts','network'].forEach(function (id) { el(id).replaceChildren(); });
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
    card('cpu', h.cpu_percent, number(h.cores) + ' 个逻辑核心 · 整台服务器');
    card('app-cpu', a.cpu_percent, 'Okad 可用额度 ' + number(a.cpu_capacity, ' 核'));
    card('io', h.io_wait_percent, '最近两次采样之间的 CPU 等待占比', 10, 20);
    card('memory', h.memory_percent, bytes(h.memory_used) + ' / ' + bytes(h.memory_total) + ' · 整机');
    card('app', a.memory_percent, a.available ? bytes(a.memory_used) + (a.memory_limit ? ' / ' + bytes(a.memory_limit) + ' · 含缓存' : ' · 未设置可见内存上限') : '当前环境不提供资源组计数');
    if (a.available && a.memory_limit == null) { el('app-value').textContent = bytes(a.memory_used); el('app-state').innerHTML = badge('info', '未设上限'); }
    card('disk', disk.percent, '可用 ' + bytes(disk.free) + ' / ' + bytes(disk.total));
    var result = health(data, paused || disconnected);
    var alerts = result.items.filter(function (item) { return item.tone === 'warn' || item.tone === 'bad'; });
    el('alerts').innerHTML = alerts.map(function (item) {
      return '<p class="monitor-alert" data-tone="' + item.tone + '">' + badge(item.tone) + ' ' + esc(item.label) + ' ' + percent(item.value) + '，达到' + (item.tone === 'bad' ? '高压' : '关注') + '阈值，请结合持续时间检查。</p>';
    }).join('');
    var errorTone = http.server_errors > 0 ? (http.server_errors >= 5 && http.error_percent >= 5 ? 'bad' : 'warn') : valid(http.count) && http.count > 0 ? 'good' : 'unknown';
    el('http').innerHTML = metric('请求速率', number(http.rps, ' 次/秒'), '最近 60 秒完成请求数 ÷ 60；流量大小本身不代表过载。') +
      metric('完成请求', number(http.count, ' 次'), '最近 60 秒已结束的 API 请求，包含成功和失败。') +
      metric('P95 耗时', number(http.p95_ms, ' ms'), '95% 的耗时样本不超过此值；' + number(http.latency_samples) + ' 条样本。接口不同，需结合平时耗时判断。') +
      metric('平均耗时', number(http.average_ms, ' ms'), '最近 60 秒完成请求的平均时长，可能被少量慢请求拉高。') +
      metric('服务端错误 · 5xx', number(http.server_errors, ' 次'), '5xx 占比 ' + percent(http.error_percent) + '；有错误标黄，至少 5 次且占比 ≥5% 标红。', errorTone) +
      metric('客户端错误 · 4xx', number(http.client_errors, ' 次'), '鉴权、参数、权限等响应；可能是调用问题，不能直接认定服务器过载。', http.client_errors > 0 ? 'warn' : 'info') +
      metric('正在处理', number(http.active, ' 个'), '当前尚未结束的 Okad API 请求；不等于后台登录并发数。') +
      metric('统计窗口', '60 秒', '随每轮采样滚动更新；请求耗时最多保留最近 10,000 个样本。');
    el('network').innerHTML = metric('网络接收', bytes(c.network.receive_bps) + (valid(c.network.receive_bps) ? '/s' : ''), '当前容器每秒收到的字节，不包含其他容器；无链路带宽上限，不能推算使用率。') +
      metric('网络发送', bytes(c.network.transmit_bps) + (valid(c.network.transmit_bps) ? '/s' : ''), '当前容器每秒发出的字节；速率升高需要结合响应耗时判断。');
    chart('cpu-chart', 'CPU 使用率', data.history, [{key:'cpu', label:'整机'}, {key:'app_cpu', label:'应用 / 可用 CPU 额度'}], percent, 100);
    chart('memory-chart', '内存使用率', data.history, [{key:'memory', label:'整机'}, {key:'app_memory', label:'应用 / 内存上限'}], percent, 100);
    chart('network-chart', '网络吞吐', data.history, [{key:'rx', label:'接收'}, {key:'tx', label:'发送'}], function (v) { return v == null ? '—' : bytes(v) + '/s'; });
    chart('latency-chart', 'API P95 耗时', data.history, [{key:'p95', label:'P95 耗时'}], function (v) { return number(v, ' ms'); });
    el('jobs').innerHTML = metric('运行中', number(jobs.running), '正在运行的任务数量，一个任务可能处理多个账号。') +
      metric('已暂停', number(jobs.paused), '已进入暂停状态的任务，不表示任务失败。') +
      metric('暂停中', number(jobs.pausing), '已收到暂停指令，等待当前步骤结束。') +
      metric('正在停止', number(jobs.cancelling), '已收到停止指令，等待当前操作安全结束。');
    var rows = [
      ['整机负载 · 1 / 5 / 15 分钟', h.load ? h.load.map(function (v) { return number(v); }).join(' / ') : '—', '等待 CPU 或部分 I/O 的平均任务数，不是百分比。持续接近或超过 ' + number(h.cores) + ' 核时，结合 CPU 和 I/O 等待检查。'],
      ['应用可用 CPU 额度', number(a.cpu_capacity, ' 核'), 'Okad 当前资源组可用的 CPU 配额/亲和性上限，应用 CPU 百分比以它为分母。'],
      ['应用主进程内存 RSS', bytes(c.process.memory_rss), '仅 Okad 主进程当前驻留物理内存，不包含全部子进程；与含缓存的资源组内存口径不同。'],
      ['应用主进程线程', number(c.process.threads, ' 个'), '当前主进程线程数。没有统一安全上限，应结合平时水平与请求耗时判断。'],
      ['交换分区用量', bytes(h.swap_used) + ' / ' + bytes(h.swap_total), '磁盘充当内存的使用量 / 总量；总量为 0 表示没有可用 swap。已有占用不等于正在频繁换页。'],
      ['资源组 OOM 终止累计', number(a.oom_kills, ' 次'), 'Okad 资源组生命周期内因内存不足被终止的累计次数。历史累计不代表当前仍在 OOM，也不覆盖 Sub2。'],
      ['服务器运行时间', duration(h.uptime_seconds), '宿主机从上次启动至今的时间。'],
      ['本次服务运行时间', duration(c.service_uptime_seconds), 'Okad 监控服务本次启动后的运行时长；重启会重新积累一小时趋势。']
    ];
    el('details').innerHTML = rows.map(function (row) { return '<div><dt>' + esc(row[0]) + '</dt><dd>' + esc(row[1]) + '</dd><p>' + esc(row[2]) + '</p></div>'; }).join('');
  }

  function renderBusiness(data) {
    businessLast = data;
    var request = data.requests, memory = data.memory || {}, current = memory.current;
    var usable = data.status === 'ok' && request;
    var status = {loading:'正在读取 Sub2 业务记录', unconfigured:'请先在 Sub2 设置中配置联动地址与管理员授权', unavailable:'Sub2 统计暂不可用，请检查联动授权和运维监控开关', stale:'统计已过期，请稍后刷新', forbidden:'仅管理员可查看全站业务统计', offline:'读取失败，请稍后刷新'};
    el('business-status').textContent = paused ? '已暂停刷新' : usable ? '业务统计每 30 秒更新 · 内存约每分钟采样' : status[data.status] || '统计暂不可用';
    el('business').dataset.outdated = String(!usable || paused);
    var counts = usable ? request.counts : {};
    el('business-window').textContent = usable ? '统计区间：' + time(request.start) + ' – ' + time(request.end) + '（最近 ' + businessMinutes + ' 分钟，按记录入库时间）' : '最近 ' + businessMinutes + ' 分钟 · 暂无有效统计，未按 0 次处理';
    el('business-counts').innerHTML = metric('用户业务请求 · 已记录', number(counts.request_count_total, ' 次'), '成功 + 全部失败；平均 ' + number(usable ? request.average_rps : null, ' 次/秒') + '。请求次数不是独立用户数。') +
      metric('成功请求', number(counts.success_count, ' 次'), '已写入用量日志的真实成功请求；未使用模拟 Token 数量推算。', usable && counts.success_count > 0 ? 'good' : 'info') +
      metric('业务限制 / 限流', number(counts.business_limited_count, ' 次'), '属于失败请求，包括服务记录的容量、并发、额度等业务限制；不能全部认定为内存不足。', usable && counts.business_limited_count > 0 ? 'warn' : 'info') +
      metric('其他失败请求', number(usable ? counts.error_count_total - counts.business_limited_count : null, ' 次'), '失败总数 ' + number(counts.error_count_total, ' 次') + '，扣除左侧业务限制；包括已有记录中的鉴权、上游和服务错误。', usable && counts.error_count_total > counts.business_limited_count ? 'bad' : 'info');
    var memoryFresh = current && !memory.stale && usable;
    var change = memory.change;
    var signed = typeof change === 'number' && Number.isFinite(change) ? (change > 0 ? '+' : change < 0 ? '−' : '') + bytes(Math.abs(change)) : '—';
    el('business-memory').innerHTML = metric('Sub2 上报内存', memoryFresh ? bytes(current.used) : '—', current ? '采样于 ' + time(current.ts) + '；用量 / 上报总量 ' + bytes(current.used) + ' / ' + bytes(current.total) + '（' + percent(current.percent) + '）' + (memoryFresh ? '。' : '，当前不可确认。') : '等待 Sub2 内存采样；不使用容量预留预算代替实测。', memoryFresh ? tone(current.percent) : 'unknown') +
      metric('区间采样峰值', usable ? bytes(memory.peak) : '—', '已获得内存样本中的最大值；约 1 分钟采样可能漏过短时尖峰，不等于该区间真实瞬时峰值。') +
      metric('区间样本平均', usable ? bytes(memory.average) : '—', '已获得内存样本的算术平均；不是每个请求的平均占用。') +
      metric('首末样本净变化', usable ? signed : '—', '末次减首次；包含请求、后台任务、缓存和回收的共同变化，不能作为请求独占内存。');
    el('business-coverage').textContent = memory.samples ? '内存样本覆盖：' + time(memory.observed_from) + ' – ' + time(memory.observed_to) + '，共 ' + memory.samples + ' 个样本。仅展示实际采集部分，缺口不补零；Okad 重启后重新积累，最多保留 1 小时。' : '尚未积累内存历史；启动后开始采集，不能回填发布前的占用。';
    var options = {minutes:businessMinutes, start:usable ? request.start : Date.now()/1000-businessMinutes*60, end:usable ? request.end : Date.now()/1000, maxGap:90};
    chart('business-request-chart', '真实业务请求数量', usable ? request.history : [], [{key:'count',label:'已记录请求'}], function(v) { return number(v, ' 次'); }, null, Object.assign({}, options, {maxGap:(request && request.bucket_seconds || 60)*1.5}));
    el('business-bucket').textContent = usable && request.bucket_seconds ? '每点汇总 ' + request.bucket_seconds / 60 + ' 分钟；首尾可能为部分区间。入库延迟可能使曲线与总数有短暂差异。' : '等待请求记录';
    chart('business-memory-chart', '同期 Sub2 内存用量', usable ? memory.history || [] : [], [{key:'used',label:'实测内存'}], bytes, null, options);
  }
  async function refreshBusiness(force) {
    if (!active || businessController || document.hidden || !force && Date.now() < businessNext) return;
    var request = new AbortController(), current = generation;
    businessController = request;
    var timeout = setTimeout(function () { request.abort(); }, 12000);
    try {
      var response = await fetch(window.OKAD_ROUTE.href('/api/monitor/user-requests?minutes=' + businessMinutes), {
        headers:{Authorization:'Bearer ' + localStorage.getItem('okad_token')}, signal:request.signal, cache:'no-store'
      });
      var data = response.ok ? await response.json() : {status:response.status === 403 ? 'forbidden' : 'offline'};
      if (active && current === generation && businessController === request) {
        renderBusiness(data);
        businessNext = Date.now() + (data.status === 'loading' ? 5000 : 30000);
      }
    } catch (error) {
      if (active && current === generation && businessController === request) { renderBusiness({status:'offline'}); businessNext = Date.now() + 30000; }
    } finally {
      clearTimeout(timeout);
      if (businessController === request) businessController = null;
    }
  }
  function stopBusiness() {
    if (businessController) { businessController.abort(); businessController = null; }
    businessNext = 0;
  }

  function schedule() {
    clearTimeout(timer);
    if (active && !paused && !document.hidden) timer = setTimeout(refresh, 5000);
  }
  async function refresh() {
    if (!active || controller || document.hidden) return;
    clearTimeout(timer);
    refreshBusiness(false);
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
      if (active && current === generation) { disconnected = false; render(data); }
    } catch (error) {
      if (active && current === generation) {
        disconnected = true;
        renderHealth(last || {current:null});
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
    var cards = [
      ['cpu','整机 CPU','整台服务器忙于计算的比例，涵盖 Sub2、Okad 及其他进程；≥80% 关注，≥90% 高压。'],
      ['memory','整机内存','已用 = 总量 − 可用内存；反映整机剩余余量。≥80% 关注，≥90% 高压。'],
      ['disk','数据所在磁盘','Okad 数据目录所在文件系统的已用比例，不是数据库文件大小。≥80% 关注，≥90% 高压。'],
      ['app-cpu','Okad CPU','Okad 容器及其子进程占可用 CPU 额度的比例。≥80% 关注，≥90% 高压。'],
      ['app','Okad 资源组内存','容器及子进程的内存，包含文件缓存；按容器上限计算。≥80% 关注，≥90% 高压。'],
      ['io','I/O 等待','CPU 等待磁盘等 I/O 完成的时间占比；≥10% 关注，≥20% 高压，不等同于磁盘使用率。']
    ];
    panel.innerHTML = '<div class="monitor-workspace ws-page">' +
      '<header class="ws-heading"><div><h2>服务器监控 <span id="monitor-status" data-tone="unknown">正在连接</span></h2><p id="monitor-scope">查看资源压力、请求表现与后台任务</p></div><div class="monitor-actions"><span id="monitor-updated"></span><button id="monitor-pause">暂停刷新</button><button id="monitor-refresh">立即刷新</button></div></header>' +
      '<div id="monitor-notice" role="status" aria-live="polite"></div>' +
      '<section class="monitor-health" id="monitor-health" data-tone="unknown" aria-label="服务器资源健康评分"><div class="monitor-health-overview"><div class="monitor-score"><strong id="monitor-score">—</strong><span>/ 100</span></div><div><div class="monitor-health-title"><h3>服务器资源健康值</h3><span id="monitor-health-state"></span></div><p id="monitor-health-reason">等待资源采样。</p><p class="monitor-scope-note">范围：整机资源 + Okad 容器资源。分数是压力参考；Sub2 容器是否健康、Adobe 账号是否可用需查看各自监控。</p><a href="/admin/ops" target="_blank" rel="noopener">查看 Sub2 并发、排队与业务错误 ↗</a></div></div>' +
      '<div class="monitor-color-key">' + badge('good','80–100 分 · 正常') + badge('warn','60–79 分 · 关注') + badge('bad','0–59 分 · 高压') + badge('unknown','缺失 / 过期 · 暂不评分') + '</div>' +
      '<details class="monitor-score-method"><summary>评分依据与各项得分</summary><p>按下方权重加权，任一资源到达关注阈值，总分最高 79；任一资源到达高压阈值，总分最高 59。单项评分随用量升高而降低：低于关注阈值的 75% 为 100 分，之后降至 80；关注区间为 79–60，高压区间为 59–0。CPU、内存、磁盘采用 80% / 90%；I/O 等待采用 10% / 20%。这些是本看板的参考规则，不代表服务可用率。</p><ul id="monitor-score-items"></ul><p id="monitor-health-excluded"></p><p>请求速率、耗时、4xx/5xx、任务数、负载、网络和历史 OOM 单独展示，不参与资源评分；没有请求不等于业务已验证正常。</p></details></section>' +
      '<section id="monitor-business" class="monitor-box monitor-business" aria-label="用户请求与 Sub2 内存"><div class="monitor-section-heading"><div><h3>用户请求与 Sub2 内存</h3><p id="monitor-business-status" class="monitor-section-note">正在读取 Sub2 业务记录</p></div><label>业务时间范围 <select id="monitor-business-range" aria-label="用户请求时间范围"><option value="5">最近 5 分钟</option><option value="15" selected>最近 15 分钟</option><option value="30">最近 30 分钟</option><option value="60">最近 1 小时</option></select></label></div><p id="monitor-business-window"></p><div id="monitor-business-counts" class="monitor-stats"></div><p>范围：Sub2 全平台客户业务的已入库记录，包含失败和业务限流。正在执行、尚未入库、未记录的入口拒绝不计入；管理页面、健康检查和本页轮询不计入，客户端重试会形成新的请求记录。</p><div id="monitor-business-memory" class="monitor-stats"></div><p>内存口径：Sub2 运维采集器优先上报容器用量（含缓存）及容器上限，无有效容器上限时回退宿主机；接口未提供来源标签。它包含后台任务，无法精确归因到每个用户请求，也不代表本区间产生的累计分配量。</p><p id="monitor-business-coverage"></p><div class="monitor-charts"><section class="monitor-business-chart"><h3>真实业务请求数量</h3><p id="monitor-business-bucket" class="monitor-section-note"></p><div id="monitor-business-request-chart"></div></section><section class="monitor-business-chart"><h3>同期 Sub2 内存用量</h3><p class="monitor-section-note">与左侧使用相同时间轴；断点表示未采集，变化不直接证明因果关系。</p><div id="monitor-business-memory-chart"></div></section></div></section>' +
      '<div class="monitor-section-heading"><h3>资源使用与余量</h3><span class="monitor-section-note">每个指标均附口径与判断说明</span></div>' +
      '<div class="monitor-cards">' + cards.map(function (item) { return '<article id="monitor-' + item[0] + '-card" data-tone="unknown"><div class="monitor-metric-heading"><span>' + item[1] + '</span><span id="monitor-' + item[0] + '-state">' + badge('unknown') + '</span></div><strong id="monitor-' + item[0] + '-value">—</strong><div class="monitor-track"><i id="monitor-' + item[0] + '-bar"></i></div><small id="monitor-' + item[0] + '-detail">等待采样</small><p class="monitor-explanation">' + item[2] + '</p></article>'; }).join('') + '</div>' +
      '<div id="monitor-alerts"></div><div class="monitor-section-heading"><h3>资源趋势</h3><label>时间范围 <select id="monitor-range" aria-label="趋势时间范围"><option value="5">最近 5 分钟</option><option value="15" selected>最近 15 分钟</option><option value="60">最近 1 小时</option></select></label></div>' +
      '<p class="monitor-section-note">曲线颜色用于区分数据序列，不表示健康等级。每 5 秒采样，历史保留 1 小时，服务重启后重新积累。</p>' +
      '<div class="monitor-charts">' + [['cpu-chart','CPU 使用率','整机以全部逻辑核心为分母；Okad 以可用 CPU 额度为分母。'], ['memory-chart','内存使用率','整机按可用内存计算；Okad 按资源组上限计算，应用用量包含缓存。'], ['network-chart','网络吞吐','接收 / 发送：当前容器每秒收发字节，非服务器全部流量。'], ['latency-chart','API 响应耗时','P95：95% 的样本不超过该值；每个点统计此前 60 秒的 Okad 请求。']].map(function (c) {
        return '<section class="monitor-box"><h3>' + c[1] + '</h3><p>' + c[2] + '</p><div id="monitor-' + c[0] + '"><div class="monitor-chart-empty">等待采样</div></div></section>';
      }).join('') + '</div>' +
      '<section class="monitor-box"><h3>当前网络速率</h3><div class="monitor-stats monitor-network-stats" id="monitor-network"></div></section>' +
      '<section class="monitor-box monitor-request-box"><div class="monitor-section-heading"><h3>Okad 应用请求 · 最近 60 秒</h3><a data-route href="' + window.OKAD_ROUTE.href('/logs') + '">查看日志 →</a></div><div class="monitor-stats" id="monitor-http"></div><p>仅统计当前 Okad 进程的 API，排除健康检查和监控轮询。Sub2 客户业务请求见上方独立统计。</p></section>' +
      '<div class="monitor-bottom"><section class="monitor-box"><div class="monitor-section-heading"><h3>后台任务</h3><a data-route href="' + window.OKAD_ROUTE.href('/jobs') + '">任务中心 →</a></div><div class="monitor-stats monitor-job-stats" id="monitor-jobs"></div><p>当前进程任务管理器中的任务，不含联动中心的独立恢复队列；任务数不等于正在登录的账号数。</p></section>' +
      '<section class="monitor-box"><h3>运行信息与参数说明</h3><dl id="monitor-details"></dl></section></div>' +
      '<details class="monitor-help"><summary>采集范围与刷新说明</summary><p>整机指标来自 Linux 内核可见的主机计数；应用指标来自 Okad 当前资源组，不能用于推断 Sub2 容器上限。网络覆盖当前网络命名空间，磁盘对应应用数据目录所在文件系统。</p><p>采集每 5 秒进行，最多保留 1 小时。暂停刷新、采样过期或读取失败时暂不显示健康分，旧指标仍保留供对照；缺失值显示 —。没有请求时耗时及错误比例没有样本。</p><p>非 Linux 环境可能缺少部分资源指标。默认单进程部署，多 worker 的请求和任务统计仅代表返回数据的进程。</p></details>' +
      '<p class="monitor-footnote">只读监控 · 不会触发登录、推送或外部健康探测</p></div>';
    document.body.appendChild(panel);
    el('refresh').onclick = function () { businessNext = 0; refresh(); };
    el('business-range').onchange = function () {
      businessMinutes = Number(el('business-range').value);
      stopBusiness(); renderBusiness({status:'loading'}); refreshBusiness(true);
    };
    el('pause').onclick = function () {
      paused = !paused;
      el('pause').textContent = paused ? '继续刷新' : '暂停刷新';
      clearTimeout(timer);
      if (last) render(last);
      stopBusiness();
      if (businessLast) renderBusiness(businessLast);
      if (!paused) refresh();
    };
    el('range').onchange = function () {
      minutes = Number(el('range').value);
      generation++; stopBusiness();
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
    build(); businessNext = 0; active = true; generation++; panel.hidden = false;
    el('notice').textContent = ''; el('status').textContent = '正在连接'; el('status').dataset.tone = 'unknown';
    layout(); refresh();
  }
  function close() {
    active = false; generation++; clearTimeout(timer); stopBusiness();
    if (controller) { controller.abort(); controller = null; }
    if (panel) panel.hidden = true;
  }
  document.addEventListener('transitionend', function (event) {
    if (event.target.matches('.n-layout-sider')) layout();
  });
  document.addEventListener('visibilitychange', function () {
    if (!active) return;
    clearTimeout(timer);
    if (document.hidden) {
      generation++; stopBusiness();
      if (controller) { controller.abort(); controller = null; }
    } else if (!paused) refresh();
  });
  window.OKAD_NAV.register({id:'server-monitor-nav', route:'server-monitor', panel:'server-monitor-panel',
    label:'服务器监控', icon:'monitor', open:open, close:close, layout:layout});
})();
