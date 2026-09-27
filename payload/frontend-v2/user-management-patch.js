/* Login administrators share this site's account pool, tasks and settings. */
(function () {
  if (window.__userManagementPatch) return;
  window.__userManagementPatch = true;
  const ID = 'okad-user-management';
  function element(tag, text, cls) {
    const el = document.createElement(tag);
    if (text !== undefined) el.textContent = text;
    if (cls) el.className = cls;
    return el;
  }
  function button(text, action, cls) {
    const el = element('button', text, cls || 'um-btn'); el.type = 'button'; el.onclick = action; return el;
  }
  async function request(path, method, body) {
    const res = await fetch('/api' + path, { method: method || 'GET',
      headers: { 'Content-Type': 'application/json', Authorization: 'Bearer ' + (localStorage.getItem('okad_token') || '') },
      body: body === undefined ? undefined : JSON.stringify(body) });
    const data = await res.json().catch(() => ({}));
    if (!res.ok) throw new Error(typeof data.detail === 'string' ? data.detail : '请求失败（HTTP ' + res.status + '）');
    return data;
  }
  function styles() {
    if (document.getElementById(ID + '-style')) return;
    const style = element('style'); style.id = ID + '-style';
    style.textContent = `
      #${ID}{background:#fff;border:1px solid #e4eaf2;border-radius:14px;padding:24px;margin-top:20px;box-sizing:border-box;scroll-margin-top:20px}
      #${ID} .um-head{display:flex;justify-content:space-between;align-items:center;gap:16px;flex-wrap:wrap}
      #${ID} h3{font-size:17px;margin:0;color:#273348} #${ID} .um-lead{color:#69778c;line-height:1.7;font-size:13px;margin:12px 0 18px}
      #${ID} .um-scroll{overflow:auto} #${ID} table{width:100%;border-collapse:collapse;white-space:nowrap;font-size:13px}
      #${ID} th,#${ID} td{text-align:left;padding:12px;border-bottom:1px solid #edf0f5} #${ID} th{background:#f7f9fc;color:#6b7890;font-weight:500}
      #${ID} .um-actions{display:flex;gap:8px} .um-btn{background:#fff;border:1px solid #d7dfeb;border-radius:7px;color:#34445c;padding:7px 12px;cursor:pointer;font:inherit}
      .um-btn.um-primary{background:#2580f4;color:white;border-color:#2580f4} .um-btn.um-danger{color:#c43838}
      .um-btn:disabled{opacity:.5;cursor:not-allowed} #${ID} .um-note{font-size:13px;color:#69778c;margin-top:12px}
      #${ID} .um-error,.um-dialog .um-error{color:#c43838;font-size:13px;line-height:1.6} #${ID} .um-active{color:#18965b}
      .um-dialog{border:1px solid #e4eaf2;border-radius:16px;width:min(430px,calc(100vw - 56px));padding:24px;color:#273348;box-shadow:0 20px 80px #18294533}
      .um-dialog::backdrop{background:#17263d66} .um-dialog h3{margin:0 0 10px;font-size:18px} .um-dialog p{font-size:13px;color:#69778c;line-height:1.7}
      .um-dialog label{display:flex;flex-direction:column;gap:7px;margin:16px 0;font-size:14px}
      .um-dialog input{box-sizing:border-box;width:100%;height:38px;padding:0 10px;border:1px solid #d7dfeb;border-radius:7px;font:inherit;color:inherit}
      .um-dialog input:focus{outline:2px solid #2580f444;border-color:#2580f4} .um-dialog footer{display:flex;gap:10px;justify-content:flex-end;margin-top:22px}
      @media(max-width:720px){#${ID}{padding:18px}#${ID} th,#${ID} td{padding:10px}}
    `;
    document.head.appendChild(style);
  }
  function createCard() {
    styles();
    const card = element('section'); card.id = ID;
    const head = element('div', undefined, 'um-head');
    head.appendChild(element('h3', '管理员管理'));
    const add = button('新增管理员', () => edit('create'), 'um-btn um-primary'); add.disabled = true; head.appendChild(add);
    card.appendChild(head);
    card.appendChild(element('p', '每人使用独立账号登录。所有管理员均可管理全部账号、任务、系统设置及其他登录用户，数据和 Sub2 连接配置共享。仅为可信任的同事开通管理员。', 'um-lead'));
    const scroll = element('div', undefined, 'um-scroll'); card.appendChild(scroll);
    const note = element('div', '加载中…', 'um-note'); note.setAttribute('role', 'status'); card.appendChild(note);
    let me = null;
    async function load() {
      try {
        me = await request('/auth/me');
        if (!me.is_superuser) { add.hidden = true; note.textContent = '仅管理员可以管理登录用户。'; return; }
        const users = await request('/admin/users');
        if (!Array.isArray(users)) throw new Error('登录用户列表格式异常');
        scroll.replaceChildren();
        const table = element('table'); table.setAttribute('aria-label', '登录用户');
        const header = element('tr');
        ['用户名', '昵称', '权限', '状态', '创建时间', '操作'].forEach(t => header.appendChild(element('th', t)));
        const thead = element('thead'); thead.appendChild(header); table.appendChild(thead);
        const body = element('tbody');
        users.forEach(user => {
          const row = element('tr'); row.dataset.userId = user.id;
          [user.username + (user.id === me.id ? '（当前）' : ''), user.nickname || '—', user.is_superuser ? '管理员' : '普通用户'].forEach(t => row.appendChild(element('td', t)));
          row.appendChild(element('td', user.is_active ? '启用' : '停用', user.is_active ? 'um-active' : ''));
          row.appendChild(element('td', user.created_at ? new Date(user.created_at).toLocaleString('zh-CN', { hour12: false }) : '—'));
          const cell = element('td'), actions = element('div', undefined, 'um-actions');
          actions.appendChild(button('编辑昵称', () => edit('nickname', user)));
          const reset = button('重置密码', () => edit('password', user));
          const toggle = button(user.is_active ? '停用' : '启用', () => edit('toggle', user), 'um-btn' + (user.is_active ? ' um-danger' : ''));
          if (user.id === me.id) {
            reset.disabled = toggle.disabled = true;
            reset.title = '请在「管理员密码」中修改自己的密码'; toggle.title = '不能停用当前登录账号';
          }
          actions.append(reset, toggle); cell.appendChild(actions); row.appendChild(cell); body.appendChild(row);
        });
        table.appendChild(body); scroll.appendChild(table); add.disabled = false;
        note.className = 'um-note'; note.textContent = '共 ' + users.length + ' 个登录用户。停用或重置密码会立即使该用户的旧登录会话失效；已提交的后台任务继续运行。';
      } catch (err) { note.className = 'um-note um-error'; note.textContent = err.message; }
    }
    function edit(mode, user) {
      if (card.querySelector('dialog')) return;
      const dialog = element('dialog', undefined, 'um-dialog'), form = element('form');
      const title = mode === 'create' ? '新增管理员' : mode === 'nickname' ? '编辑昵称' : mode === 'password' ? '重置密码' : user.is_active ? '停用登录用户' : '启用登录用户';
      const heading = element('h3', title); heading.id = 'um-dialog-title'; form.appendChild(heading); dialog.setAttribute('aria-labelledby', heading.id);
      const description = mode === 'create' ? '新管理员将拥有全部管理权限。用户名创建后不可修改。' : '登录用户：' + user.username;
      form.appendChild(element('p', description));
      const inputs = {};
      function input(name, label, type, value) {
        const wrap = element('label', label), field = element('input'); field.name = name; field.type = type || 'text'; field.value = value || '';
        field.autocomplete = type === 'password' ? 'new-password' : 'off';
        field.required = name !== 'nickname'; field.maxLength = name === 'password' || name === 'confirm' ? 72 : 50;
        if (name === 'username') { field.minLength = 3; field.pattern = '[A-Za-z0-9_.-]{3,50}'; }
        if (type === 'password') field.minLength = 10;
        wrap.appendChild(field); form.appendChild(wrap); inputs[name] = field;
      }
      if (mode === 'create') input('username', '用户名（3～50 位字母、数字或 ._-）');
      if (mode === 'create' || mode === 'nickname') input('nickname', '昵称', 'text', user && user.nickname);
      if (mode === 'create' || mode === 'password') {
        input('password', '新密码（至少 10 个字符，不超过 72 字节）', 'password'); input('confirm', '确认密码', 'password');
        if (mode === 'password') form.appendChild(element('p', '保存后，该用户需要使用新密码重新登录。'));
      }
      if (mode === 'toggle') form.appendChild(element('p', user.is_active ? '停用后，该用户会退出登录且无法重新登录。其已提交的后台任务会继续运行，账号数据保留。' : '启用后，该用户可以使用现有密码重新登录。'));
      const error = element('div', '', 'um-error'); error.setAttribute('role', 'alert'); form.appendChild(error);
      const footer = element('footer'); let busy = false;
      function close() { if (busy) return; form.reset(); Object.values(inputs).forEach(i => { i.value = ''; }); dialog.close(); dialog.remove(); }
      const cancel = button('取消', close), save = element('button', mode === 'toggle' ? (user.is_active ? '确认停用' : '确认启用') : '保存', 'um-btn um-primary'); save.type = 'submit';
      footer.append(cancel, save); form.appendChild(footer); dialog.appendChild(form); card.appendChild(dialog);
      dialog.addEventListener('cancel', e => { e.preventDefault(); close(); });
      form.onsubmit = async e => {
        e.preventDefault(); if (busy) return; error.textContent = '';
        if (inputs.password && inputs.password.value !== inputs.confirm.value) { error.textContent = '两次输入的密码不一致'; return; }
        if (inputs.password && (Array.from(inputs.password.value).length < 10 || new TextEncoder().encode(inputs.password.value).length > 72)) { error.textContent = '密码至少 10 个字符，且不超过 72 字节'; return; }
        busy = true; save.disabled = cancel.disabled = true;
        try {
          if (mode === 'create') await request('/admin/users', 'POST', { username: inputs.username.value, nickname: inputs.nickname.value, password: inputs.password.value });
          else if (mode === 'password') await request('/admin/users/' + user.id + '/reset-password', 'POST', { password: inputs.password.value });
          else await request('/admin/users/' + user.id, 'PATCH', mode === 'nickname' ? { nickname: inputs.nickname.value } : { is_active: !user.is_active });
          busy = false; close(); await load();
        } catch (err) { error.textContent = err.message; }
        finally { busy = false; save.disabled = cancel.disabled = false; }
      };
      dialog.showModal();
    }
    load(); return card;
  }
  function install() {
    if (location.pathname.replace(/\/+$/, '') !== '/settings') { const old = document.getElementById(ID); if (old) old.remove(); return; }
    if (document.getElementById(ID)) return;
    const content = document.querySelector('#app .n-layout-content.content'); if (!content) return;
    const mount = Array.from(content.querySelectorAll('.n-card')).find(card => {
      const title = card.querySelector('.n-card-header__main'); return title && title.textContent.trim() === '修改管理员密码';
    });
    if (mount) mount.insertAdjacentElement('beforebegin', createCard());
  }
  new MutationObserver(install).observe(document.documentElement, { childList: true, subtree: true });
  window.addEventListener('popstate', install); window.setInterval(install, 800); install();
})();
