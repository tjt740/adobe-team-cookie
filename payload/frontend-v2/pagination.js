/* Shared page-size controls for native and Vue lists. */
(function () {
  'use strict';
  const sizes = [50, 100, 200, 300, 400, 500, 1000], max = 10000;
  const valid = value => Number.isInteger(Number(value)) && Number(value) >= 1 && Number(value) <= max;
  const options = size => sizes.includes(size) ? sizes : [...sizes, size];
  const label = size => size + ' 条' + (sizes.includes(size) ? '' : '（自定义）');
  function sizeHTML(id, size) {
    return '<form class="okad-page-size" id="' + id + '-form"><label>每页<select id="' + id + '" aria-label="每页显示条数">' +
      options(size).map(n => '<option value="' + n + '"' + (n === size ? ' selected' : '') + '>' + label(n) + '</option>').join('') +
      '</select></label><label>自定义<input name="pageSize" type="number" min="1" max="' + max + '" step="1" required value="' + size + '" aria-label="自定义每页条数" title="1–10000 条"></label><button type="submit">应用</button></form>';
  }
  function bindSize(id, change, root = document) {
    const select = root.querySelector('#' + id), form = root.querySelector('#' + id + '-form');
    select.onchange = () => { if (valid(select.value)) change(Number(select.value)); };
    form.onsubmit = event => { event.preventDefault(); if (form.reportValidity() && valid(form.elements.pageSize.value)) change(Number(form.elements.pageSize.value)); };
  }
  function syncSize(id, size, disabled, root = document) {
    const select = root.querySelector('#' + id), form = root.querySelector('#' + id + '-form');
    if (!select || !form) return;
    if (!Array.from(select.options).some(option => Number(option.value) === size)) select.add(new Option(label(size), String(size)));
    select.value = String(size);
    const input = form.elements.pageSize;
    if (form.dataset.size !== String(size)) { input.value = String(size); form.dataset.size = String(size); }
    form.querySelectorAll('input,select,button').forEach(node => { node.disabled = !!disabled; });
  }
  function sizeControl(h, {size, onSize, busy = false}) {
    return h('form', {class:'okad-page-size', onSubmit:event => {
      event.preventDefault(); const form = event.currentTarget;
      if (!busy && form.reportValidity() && valid(form.elements.pageSize.value)) onSize(Number(form.elements.pageSize.value));
    }}, [
      h('label', {}, ['每页', h('select', {value:size, disabled:busy, 'aria-label':'每页显示条数', onChange:event => onSize(Number(event.target.value))},
        options(size).map(n => h('option', {value:n}, label(n))))]),
      h('label', {}, ['自定义', h('input', {key:size, name:'pageSize', type:'number', defaultValue:size, min:1, max, step:1, required:true, disabled:busy, 'aria-label':'自定义每页条数', title:'1–10000 条'})]),
      h('button', {type:'submit', disabled:busy}, '应用')
    ]);
  }
  function pager(h, {page, size, total, onPage, onSize, busy = false}) {
    const pages = Math.max(1, Math.ceil(total / size));
    return h('nav', {class:'okad-pagination', 'aria-label':'列表分页'}, [
      h('span', {role:'status'}, `共 ${total} 条 · 第 ${page} / ${pages} 页`), sizeControl(h, {size, onSize, busy}),
      h('button', {disabled:busy || page <= 1, onClick:() => onPage(page - 1)}, '上一页'),
      h('button', {disabled:busy || page >= pages, onClick:() => onPage(page + 1)}, '下一页')
    ]);
  }
  function mountPager(host, {id, state, onPage, onSize}) {
    host.classList.add('okad-pagination'); host.setAttribute('aria-label', '列表分页');
    host.innerHTML = '<span role="status"></span>' + sizeHTML(id, state().size) + '<button type="button" data-prev>上一页</button><button type="button" data-next>下一页</button>';
    bindSize(id, onSize, host);
    host.querySelector('[data-prev]').onclick = () => onPage(state().page - 1);
    host.querySelector('[data-next]').onclick = () => onPage(state().page + 1);
    function update() {
      const {page, size, total, busy} = state(), pages = Math.max(1, Math.ceil(total / size));
      host.querySelector('[role=status]').textContent = `共 ${total} 条 · 第 ${page} / ${pages} 页`;
      syncSize(id, size, busy, host);
      host.querySelector('[data-prev]').disabled = !!busy || page <= 1;
      host.querySelector('[data-next]').disabled = !!busy || page >= pages;
    }
    update(); return update;
  }
  window.OKAD_PAGINATION = {sizes, max, valid, sizeHTML, bindSize, syncSize, sizeControl, pager, mountPager};
})();
