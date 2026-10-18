/* Add mobile labels to the existing rows, preserving selection, sorting and action handlers. */
(function(){
  'use strict';
  const tables='#adobe-workspace .n-data-table,#email-workspace .n-data-table,#pool-workspace .n-data-table,#logs-workspace .n-data-table,.extm-t,.s2-t,#integration-sources,#okad-user-management table', mobile=matchMedia('(max-width:600px)');
  let queued=false;
  function sync(){
    queued=false;
    document.querySelectorAll(tables).forEach(root=>{
      if(root.id==='integration-sources')root=root.closest('table');
      root.classList.add('ws-card-table');
      const headers=Array.from(root.querySelectorAll('thead th'));
      root.querySelectorAll('tbody>tr').forEach(row=>{
        if(row.dataset.wsRow==='record' && row.cells[0]?.hasAttribute('data-ws-cell'))return;
        if(row.hasAttribute('data-detail')){row.dataset.wsRow='detail';return;}
        if(row.cells.length===1 && row.cells[0].colSpan>1){row.dataset.wsRow='empty';return;}
        row.dataset.wsRow='record';
        Array.from(row.cells).forEach((cell,index)=>{
          const title=(headers[index]?.textContent||'').trim();
          const key=cell.dataset.colKey || '';
          const type=cell.querySelector('input[type=checkbox],[role=checkbox]')?'select':cell.querySelector('.extm-toggle')?'toggle':key==='email'||/^(用户名|邮箱|账号)(\s|$|\s*\/)/.test(title)?'primary':/操作/.test(title)?'actions':'field';
          cell.dataset.wsCell=type;cell.dataset.wsLabel=title;
          cell.querySelectorAll('input[type=checkbox],[role=checkbox]').forEach(box=>{if(!box.getAttribute('aria-label'))box.setAttribute('aria-label','选择账号');});
        });
      });
      root.querySelectorAll('thead input[type=checkbox],thead [role=checkbox]').forEach(box=>{if(!box.getAttribute('aria-label'))box.setAttribute('aria-label','全选本页');});
    });
    for(const [selector,count] of [['.extm-batch-row','#extm-selc'],['.s2-tools','#s2-seln']]){
      const bar=document.querySelector(selector),value=document.querySelector(count);
      if(bar&&value)bar.dataset.wsSelected=String(Number(value.textContent)>0);
    }
    document.querySelectorAll('.ws-drawer').forEach(drawer=>{
      const title=drawer.querySelector('.n-card-header__main')?.textContent.trim();
      if(title)drawer.setAttribute('aria-label',title);
    });
  }
  function schedule(){if(!queued){queued=true;requestAnimationFrame(sync);}}
  new MutationObserver(schedule).observe(document.documentElement,{subtree:true,childList:true});
  mobile.addEventListener('change',schedule);schedule();
  window.OKAD_WORKSPACE={bindDrawer(dialog,trigger,close){
    const dismiss=()=>{if(dialog.open){dialog.close();trigger.setAttribute('aria-expanded','false');trigger.focus({preventScroll:true});}};
    trigger.setAttribute('aria-haspopup','dialog');trigger.setAttribute('aria-controls',dialog.id);trigger.setAttribute('aria-expanded','false');
    trigger.onclick=()=>{dialog.showModal();trigger.setAttribute('aria-expanded','true');};
    close.onclick=dismiss;dialog.addEventListener('cancel',event=>{event.preventDefault();dismiss();});
    dialog.addEventListener('close',()=>trigger.setAttribute('aria-expanded','false'));
    dialog.addEventListener('click',event=>{if(event.target===dialog){const r=dialog.getBoundingClientRect();if(event.clientX<r.left||event.clientX>r.right||event.clientY<r.top||event.clientY>r.bottom)dismiss();}});
  }};
})();
