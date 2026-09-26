/* Native Vue integration for the prebuilt pool page. No external-account data. */
export function createPoolSub2({ref, h, Button, Tooltip, selected, selectedRows, refresh}) {
  const busy = ref(false), current = ref(null), error = ref('');
  const expanded = ref(true), config = ref(null), configError = ref(''), configLoading = ref(true);
  const key = 'okad_pool_cookie_sub2_job';
  let timer, disposed = false, refreshing = false, submitting = false;
  const active = job => ['running', 'pausing', 'paused', 'cancelling'].includes(job?.status);

  function configReason() {
    if (configLoading.value) return '正在检查 Sub2 配置';
    if (configError.value) return '无法读取 Sub2 配置，请刷新后重试';
    if (!config.value?.admin_token_set) return '尚未配置 Sub2 管理员密钥';
    if (!config.value?.base_url?.trim()) return '尚未配置 Sub2 服务地址';
    if (config.value.platform !== 'adobe') return '请在 Sub2 管理选择 Adobe Firefly 平台';
    if (!String(config.value.group_ids || '').match(/[1-9]\d*/)) return '请在 Sub2 管理选择并保存目标分组';
    return '';
  }

  async function refreshConfig() {
    configLoading.value = true;
    try { config.value = await api('/sub2/config'); configError.value = ''; }
    catch (e) { config.value = null; configError.value = e.message; }
    finally { configLoading.value = false; }
  }

  function openConfig() { document.getElementById('sub2-nav-mng')?.click(); }

  async function api(path, body) {
    const res = await fetch('/api' + path, {
      method: body === undefined ? 'GET' : 'POST',
      headers: {'Content-Type': 'application/json',
        Authorization: 'Bearer ' + (localStorage.getItem('okad_token') || '')},
      ...(body === undefined ? {} : {body: JSON.stringify(body)})
    });
    const data = await res.json();
    if (!res.ok) {
      const error = new Error(typeof data.detail === 'string' ? data.detail : '请求失败，请刷新后重试');
      error.status = res.status;
      throw error;
    }
    return data;
  }

  function schedule() {
    clearTimeout(timer);
    if (!disposed) timer = setTimeout(poll, 2500);
  }

  async function poll() {
    if (!current.value?.id || disposed) return;
    try {
      const job = await api('/adobe-accounts/jobs/' + current.value.id);
      if (disposed) return;
      current.value = job;
      busy.value = active(job);
      error.value = '';
      if (active(job)) schedule();
      else if (!refreshing) {
        refreshing = true;
        window.dispatchEvent(new Event('okad:sub2-stock-changed'));
        try { await refresh(); } finally { refreshing = false; }
      }
    } catch (e) {
      if (disposed) return;
      if (e.status === 404) {
        localStorage.removeItem(key);
        current.value = null;
        busy.value = false;
        error.value = '上次任务已不存在，可重新勾选账号操作。';
        return;
      }
      error.value = e.message + '；可前往任务列表查看，正在重试读取进度。';
      schedule();
    }
  }

  async function start() {
    if (busy.value || submitting || configReason()) return;
    const ids = [...new Set(selected())];
    if (!ids.length) return;
    submitting = true;
    busy.value = true;
    error.value = '';
    try {
      await refreshConfig();
      if (configReason()) throw new Error(configReason());
      const job = await api('/pool/login-push-sub2', {ids});
      localStorage.setItem(key, String(job.id));
      if (disposed) return;
      current.value = job;
      expanded.value = true;
      await poll();
    } catch (e) {
      error.value = e.message;
      busy.value = false;
    } finally { submitting = false; }
  }

  async function cancel() {
    try {
      await api('/adobe-accounts/jobs/' + current.value.id + '/cancel', {});
      await poll();
    } catch (e) { error.value = e.message; }
  }

  return {
    button: () => h('div', {class: 'pool-sub2-control'}, [
      h(Button, {
        id: 'pool-sub2-push', type: 'primary', loading: busy.value,
        disabled: busy.value || !!configReason() || !selected().length || selectedRows?.().some(row => row.is_admin),
        onClick: start, title: configReason() || (selectedRows?.().some(row => row.is_admin)
          ? '请选择子号或导入账号，不能选择母号自身' : '获取所选账号的 Cookie 并导入 Sub2')
      }, () => '导入 Sub2'),
      h(Tooltip, {trigger: 'click', placement: 'bottom-end', style: {maxWidth: '290px'}}, {
        trigger: () => h('button', {id: 'pool-sub2-help', type: 'button', class: 'pool-help',
          'aria-label': 'Sub2 导入说明', title: '只有配置 Sub2 管理员密钥后才能导入。点击查看说明。'}, '?'),
        default: () => h('div', {id: 'pool-sub2-help-content', style: {lineHeight: '1.8'}}, [
          h('strong', {}, '导入 Sub2 前需要完成配置'),
          h('p', {style: {margin: '6px 0'}}, '必须先在「Sub2 管理」保存服务地址、管理员密钥，并选择 Adobe Firefly 平台和目标分组。未配置密钥时无法导入。'),
          h('p', {style: {margin: '6px 0'}}, '仅处理勾选的子号或导入账号。缺 Cookie 时自动登录，积分需达到 4000；已在库账号跳过。'),
          h(Button, {size: 'small', onClick: openConfig}, () => '去配置 Sub2')
        ])
      })
    ]),
    notice: () => !configLoading.value && configReason() ? h('div', {class: 'pool-sub2-notice'}, [
      h('span', {}, configReason() + '，配置完成后才能导入。'),
      h(Button, {text: true, size: 'small', type: 'primary', onClick: openConfig}, () => '去配置')
    ]) : null,
    panel: () => {
      const job = current.value;
      if (!job && !error.value) return null;
      const items = job?.extra?.items || job?.result?.items || [];
      const state = job?.status === 'error' ? '任务失败' : job?.status === 'cancelled' ? '已终止' :
        active(job) ? '处理中' : '已完成';
      return h('section', {id: 'pool-sub2-progress', class: 'pool-job', 'aria-live': 'polite'}, [
        h('div', {class: 'pool-job-summary'}, [
          h('strong', {}, job ? `号池推送任务 #${job.id} · ${state}` : '号池推送'),
          job ? h('span', {class: 'pool-job-stats'}, `完成 ${job.success || 0} · 失败 ${job.fail || 0} · 共 ${job.target || 0}`) : null,
          items.length ? h(Button, {class: 'pool-job-toggle', text: true, size: 'small',
            'aria-expanded': expanded.value, onClick: () => expanded.value = !expanded.value},
          () => expanded.value ? '收起明细' : '展开明细') : null,
          job ? h('a', {href: '/jobs?id=' + job.id}, '查看任务') : null,
          active(job) ? h(Button, {size: 'small', disabled: job.status === 'cancelling', onClick: cancel},
            () => job.status === 'cancelling' ? '终止中…' : '终止任务') : null
        ]),
        error.value || job?.error ? h('p', {class: 'pool-job-error', role: 'alert'}, error.value || job.error) : null,
        expanded.value ? h('div', {class: 'pool-job-items'}, items.map(item =>
          h('div', {'data-pool-sub2-id': item.id, class: 'pool-job-item'}, [
            h('span', {translate: 'no'}, item.email || '账号 #' + item.id),
            h('span', {style: {color: item.status === 'failed' ? '#d03050' :
              ['pushed', 'existing'].includes(item.status) ? '#18a058' : 'inherit'}}, item.message)
          ]))) : null
      ]);
    },
    async mount() {
      refreshConfig();
      window.addEventListener('okad:sub2-config-changed', refreshConfig);
      window.addEventListener('focus', refreshConfig);
      const id = Number(localStorage.getItem(key));
      if (id > 0) { current.value = {id, status: 'running'}; expanded.value = true; busy.value = true; poll(); }
      else {
        // Also show tasks started in another tab or through the API.
        try {
          const jobs = await api('/adobe-accounts/jobs?limit=100');
          if (disposed || current.value || submitting) return;
          const job = Array.isArray(jobs) && jobs.find(j => j.type === 'pool_cookie_sub2');
          if (job) {
            localStorage.setItem(key, String(job.id));
            current.value = job;
            expanded.value = true;
            busy.value = active(job);
            poll();
          }
        } catch (_) { /* The account list and manual submission remain available. */ }
      }
    },
    dispose() {
      disposed = true; clearTimeout(timer);
      window.removeEventListener('okad:sub2-config-changed', refreshConfig);
      window.removeEventListener('focus', refreshConfig);
    }
  };
}
