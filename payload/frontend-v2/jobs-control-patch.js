(function () {
  if (window.__okadJobsControlPatch) return;
  window.__okadJobsControlPatch = true;
  var box = null, current = 0, busy = false, loading = false, last = 0, state = null;
  var style = document.createElement('style');
  style.textContent = '#okad-job-controls{display:flex;gap:8px;align-items:center;flex-wrap:wrap;padding:12px 24px;border-top:1px solid var(--n-border-color,#efeff5)}#okad-job-controls button{height:30px;border:1px solid #1890ff;border-radius:4px;padding:0 12px;background:transparent;color:#1890ff;cursor:pointer}#okad-job-controls button.stop{color:#d03050;border-color:#d03050}#okad-job-controls button:disabled{opacity:.5;cursor:not-allowed}#okad-job-controls span{font-size:12px;opacity:.7}';
  document.head.appendChild(style);
  async function request(id, action) {
    var response = await fetch('/api/adobe-accounts/jobs/' + id + (action ? '/' + action : ''), {method:action ? 'POST':'GET', headers:{Authorization:'Bearer ' + (localStorage.getItem('okad_token') || '')}});
    var data = await response.json();
    if (!response.ok || data.success === false) throw new Error(data.detail || data.message || '任务操作失败');
    return data;
  }
  function render() {
    if (!box || !state) return;
    var live = ['running','pausing','paused'].includes(state.status);
    var resume = ['paused','pausing'].includes(state.status);
    var pause = box.querySelector('.pause'), stop = box.querySelector('.stop');
    pause.hidden = state.type !== 'external_login';
    pause.disabled = busy || !live;
    pause.textContent = busy ? '处理中…' : resume ? '继续任务' : '暂停任务';
    pause.dataset.action = resume ? 'resume':'pause';
    stop.disabled = busy || !live;
    stop.textContent = state.status === 'cancelling' ? '终止中…':'终止任务';
    box.querySelector('span').textContent = state.status === 'paused' ? '已暂停，可继续或终止' : state.status === 'pausing' ? '当前账号完成后暂停，排队账号不会启动' : state.status === 'cancelling' ? '等待当前请求返回后退出' : state.status === 'cancelled' ? '已终止，结果和日志已保留' : state.type === 'external_login' && live ? '暂停将等待当前账号完成；终止后不可继续' : '';
  }
  async function refresh(id) {
    if (loading) return;
    loading = true; last = Date.now();
    try { var data = await request(id); if (id === current) {state = data;render();} }
    catch (error) { if (box && id === current) box.querySelector('span').textContent = error.message; }
    finally { loading = false; }
  }
  async function action(name) {
    if (busy || !current) return;
    var id = current;
    if (name === 'cancel' && !confirm('终止任务 #' + id + '？排队账号将取消，当前请求返回后退出；已完成结果和日志会保留。')) return;
    busy = true;render();
    try { await request(id,name); await refresh(id); }
    catch (error) { if (box) box.querySelector('span').textContent = error.message; }
    finally { busy = false;render(); }
  }
  function install() {
    if (location.pathname.replace(/\/+$/, '') !== '/jobs') { if (box) box.remove();box=null;current=0;state=null;return; }
    var card = Array.from(document.querySelectorAll('.n-card')).find(function (c) {var header=c.querySelector('.n-card-header');return header && header.textContent.includes('任务详情');});
    var match = card && card.querySelector('.n-card-header').textContent.match(/#(\d+)/);
    if (!match) {if (box) box.remove();box=null;current=0;state=null;return;}
    var id = Number(match[1]);
    if (!box || !box.isConnected || !card.contains(box)) {
      if (box) box.remove();
      box=document.createElement('div');box.id='okad-job-controls';
      box.innerHTML='<button type="button" class="pause">暂停任务</button><button type="button" class="stop">终止任务</button><span role="status"></span>';
      box.querySelector('.pause').onclick=function(){action(this.dataset.action);};
      box.querySelector('.stop').onclick=function(){action('cancel');};
      card.appendChild(box);last=0;
    }
    if (current !== id) {current=id;state=null;last=0;box.querySelectorAll('button').forEach(function(b){b.disabled=true;});}
    if (!busy && Date.now()-last>2000) refresh(id);
  }
  new MutationObserver(install).observe(document.documentElement,{childList:true,subtree:true});
  setInterval(install,1000);install();
})();
