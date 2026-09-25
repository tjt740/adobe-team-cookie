/* Readable view layer for the prebuilt pool page; existing API actions are reused. */
export function createPoolWorkspace({h, ref, Button, Select, Input, Switch, Table, Tag,
  Dropdown, Popconfirm, Stats, state: s, actions: a, sub2}) {
  const exporting = ref('');
  const call = fn => (...args) => Promise.resolve(fn(...args)).catch(() => {});
  const button = (label, props = {}) => h(Button, props, () => label);
  const tag = (label, type = 'default') => h(Tag, {size: 'small', round: true, bordered: false, type}, () => label);
  const field = (label, control) => h('div', {class: 'pool-field'}, [h('label', {}, label), control]);
  const select = (value, options, update) => h(Select, {value: value.value, options, 'onUpdate:value': update});
  const date = (timestamp, seconds = false) => {
    if (!timestamp) return '—';
    const d = new Date(seconds ? timestamp * 1000 : timestamp);
    return Number.isNaN(d.getTime()) ? '—' : d.toLocaleString('zh-CN',
      {month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit', hour12: false});
  };
  const setExport = value => {
    s.exportStatus.value = value;
    if (value) localStorage.setItem('okad_pool_export_status', value);
    else localStorage.removeItem('okad_pool_export_status');
    a.search();
  };
  const reset = () => {
    s.keyword.value = '';
    s.exportStatus.value = '';
    localStorage.removeItem('okad_pool_export_status');
    a.reset('reset');
  };
  function menu(label, options, handler, props = {}) {
    return h(Dropdown, {trigger: 'click', options, onSelect: call(handler), placement: 'bottom-end'},
      {default: () => button(label + ' ▾', props)});
  }
  function columns() {
    return [
      {type: 'selection', width: 42},
      {title: '账号', key: 'email', minWidth: 250, render: row => h('div', {class: 'pool-account', translate: 'no'}, [
        h('div', {class: 'pool-email', title: row.email, 'data-pool-email': row.email}, row.email),
        h('div', {class: 'pool-account-meta'}, [
          h('span', {class: 'pool-name', title: [row.display_name, row.admin_email].filter(Boolean).join(' · ')},
            row.display_name || (row.is_admin ? '母号自身' : row.admin_email || '独立账号')),
          h('span', {'data-pool-stock': ''})
        ])
      ])},
      {title: '类型', key: 'type', width: 76, render: row =>
        tag(row.is_admin ? '母号' : row.is_imported ? '导入' : '子号', row.is_admin ? 'warning' : 'info')},
      {title: '状态', key: 'status', width: 108, render: row => row.has_token
        ? tag(row.credits == null || row.credits < 0 ? '额度未知' : '已拿 Token',
          row.credits == null || row.credits < 0 ? 'warning' : 'success')
        : tag(row.status === 'failed' ? '登录失败' : '待登录', row.status === 'failed' ? 'error' : 'default')},
      {title: '可用积分', key: 'credits', width: 100, render: row => row.credits == null || row.credits < 0 ? '—'
        : h('div', {class: 'pool-credits'}, [h('span', {}, String(row.credits)),
          h('div', {class: 'pool-credit-track'}, [h('i', {style: {width: Math.max(0, Math.min(100, row.credits / 40)) + '%'}})])])},
      {title: '登录凭证', key: 'credentials', width: 158, render: row => h('div', {class: 'pool-credentials', translate: 'no'},
        [['Cookie', row.has_cookie], ['Token', row.has_token], ['ARP', row.has_arp]].map(([label, available]) =>
          h('span', {class: available ? 'available' : '', title: available ? '已获取 ' + label : '暂无 ' + label}, label)))},
      {title: 'Token 到期 / 入池', key: 'time', width: 158, render: row => h('div', {class: 'pool-time'}, [
        h('span', {class: row.expires_at && row.expires_at * 1000 < Date.now() ? 'expired' : '',
          title: row.expires_at ? new Date(row.expires_at * 1000).toLocaleString() : '暂无到期时间'}, date(row.expires_at, true)),
        h('small', {title: row.created_at ? new Date(row.created_at).toLocaleString() : ''}, '入池 ' + date(row.created_at))
      ])},
      {title: '操作', key: 'actions', width: 132, fixed: 'right', render: row => h('div', {class: 'pool-row-actions'}, [
        button('编辑', {size: 'small', text: true, type: 'primary', onClick: call(() => a.edit(row))}),
        menu('更多', [
          {label: s.mailBusy.value === row.id ? '测试收件中…' : '测试收件', key: 'testMail', disabled: s.mailBusy.value !== null},
          {label: s.tokenBusy.value === row.id ? '刷新 Token 中…' : '刷新 AT', key: 'refreshToken', disabled: s.tokenBusy.value !== null},
          {label: s.arpBusy.value === row.id ? '刷新 ARP 中…' : '刷新 ARP', key: 'refreshARP', disabled: s.arpBusy.value !== null || !row.has_cookie},
          {label: '测试出图', key: 'testImage', disabled: !row.has_token}
        ], key => a[key](row), {size: 'small', text: true})
      ])}
    ];
  }
  return () => h('div', {id: 'pool-workspace', class: 'notranslate', translate: 'no'}, [
    s.stats().length ? h(Stats, {items: s.stats(), onPick: key => key === 'reset' ? reset() : a.reset(key)}) : null,
    h('div', {class: 'pool-heading'}, [
      h('div', {}, [h('h2', {}, '账号列表'), h('p', {}, `共 ${s.pagination.itemCount} 个账号 · 管理登录凭证与 Sub2 入库`)]),
      h('div', {class: 'pool-heading-actions'}, [
        button('导入邮箱', {type: 'primary', onClick: a.importEmails}),
        button('创建 MoeMail', {onClick: a.createMail}),
        menu('导出', [
          {label: '按设置导出', key: 'default'}, {label: '导出 Cookie', key: 'cookies'},
          {label: '导出 Token', key: 'tokens'}, {label: 'newbanana (JSON)', key: 'json'}
        ], async key => { exporting.value = key; try { await a.export(key); } finally { exporting.value = ''; } },
        {loading: !!exporting.value, disabled: s.exportBusy.value || !s.pagination.itemCount, title: '按当前筛选条件导出'})
      ])
    ]),
    h('section', {class: 'pool-filter-box', 'aria-label': '筛选账号'}, [
      h('div', {class: 'pool-filter-grid'}, [
        field('搜索账号', h(Input, {value: s.keyword.value, 'onUpdate:value': v => s.keyword.value = v,
          placeholder: '搜索邮箱', clearable: true, onKeyup: e => e.key === 'Enter' && a.search()})),
        field('类型', select(s.type, s.typeOptions, v => { s.type.value = v; a.search(); })),
        field('Token', select(s.token, s.tokenOptions, v => { s.token.value = v; a.search(); })),
        field('额度', select(s.credit, s.creditOptions, v => { s.credit.value = v; a.creditChanged(v); })),
        field('状态', select(s.status, s.statusOptions, v => { s.status.value = v; a.search(); })),
        field('导出状态', select(s.exportStatus,
          [{label: '全部', value: ''}, {label: '未导出', value: 'unexported'}, {label: '已导出', value: 'exported'}], setExport))
      ]),
      h('div', {class: 'pool-filter-bottom'}, [
        h('label', {class: 'pool-registered'}, [h(Switch, {size: 'small', value: s.registered.value,
          'onUpdate:value': v => { s.registered.value = v; a.search(); }}), '只看已注册']),
        h('div', {class: 'pool-filter-buttons'}, [button('重置', {onClick: reset}), button('搜索', {onClick: a.search, secondary: true, type: 'primary'})])
      ])
    ]),
    h('div', {class: 'pool-batch-bar'}, [
      h('div', {class: 'pool-selection'}, ['已选 ', h('b', {}, String(s.selected.value.length)), ' 个',
        s.selected.value.length ? button('清空', {text: true, type: 'primary', size: 'small', onClick: () => s.selected.value = []}) : null]),
      h('div', {class: 'pool-batch-actions'}, [
        button('登录选中', {loading: s.loginBusy.value, disabled: !s.selected.value.length || s.loginBusy.value,
          onClick: call(a.loginSelected), title: '刷新所选账号的 Token 和额度'}),
        h(Popconfirm, {onPositiveClick: a.loginFiltered}, {
          trigger: () => button('登录筛选结果', {disabled: !s.pagination.itemCount || s.loginBusy.value, loading: s.loginBusy.value}),
          default: () => h('div', {}, [h('p', {}, `登录当前筛选的 ${s.pagination.itemCount} 个账号？`),
            h('label', {class: 'pool-registered'}, [h(Switch, {size: 'small', value: s.autoRetry.value,
              'onUpdate:value': v => s.autoRetry.value = v}), `失败自动重试（最多 ${s.maxRetries.value} 轮）`])])
        }),
        sub2.button(),
        h('span', {class: 'pool-action-divider'}),
        h(Popconfirm, {onPositiveClick: a.deleteSelected}, {
          trigger: () => button('批量删除', {type: 'error', text: true, loading: s.deleteBusy.value,
            disabled: !s.selected.value.length || s.deleteBusy.value}),
          default: () => `将从号池移除选中的 ${s.selected.value.length} 条记录；母号仅移除号池记录，子号同时尝试从 Adobe 组织移除。确认？`
        })
      ])
    ]),
    sub2.notice(), sub2.panel(),
    h(Table, {class: 'pool-table', columns: columns(), data: s.rows.value, loading: s.loading.value,
      rowKey: row => row.id, checkedRowKeys: s.selected.value, 'onUpdate:checkedRowKeys': v => s.selected.value = v,
      scrollX: 1124, remote: true, pagination: {page: s.pagination.page, pageSize: s.pagination.pageSize,
        itemCount: s.pagination.itemCount, pageSizes: [50, 100, 200, 500], showSizePicker: true,
        prefix: p => `共 ${p.itemCount} 个账号`, onUpdatePage: a.pageChanged, onUpdatePageSize: a.pageSizeChanged}},
      {empty: () => h('div', {class: 'pool-empty'}, ['暂无匹配账号', h('small', {}, '导入邮箱，或调整筛选条件后查看。')])})
  ]);
}
