/* Cosmetic layout coordination for legacy settings/dashboard and embedded screens. */
(function(){
  let queued=false;
  function sync(){
    queued=false;
    const path=location.pathname.replace(/\/+$/,'')||'/dashboard';
    const page=path.slice(1);
    if(document.body.dataset.workspace!==page)document.body.dataset.workspace=page;
    if(page!=='settings')return;
    const content=document.querySelector('.n-layout-content.content');
    if(!content)return;
    const cards=Array.from(content.querySelectorAll('.n-card')).filter(c=>c.querySelector('.n-card-header__main'));
    const run=cards.find(c=>c.querySelector('.n-card-header__main').textContent.trim()==='运行设置');
    if(!run)return;
    const scroll=content.querySelector(':scope > .n-layout-scroll-container');
    let root=run;
    while(root.parentElement&&root.parentElement!==scroll&&root.parentElement!==content)root=root.parentElement;
    root.classList.add('ws-settings-page');
    let heading=document.getElementById('ws-settings-heading');
    if(!heading){
      heading=document.createElement('header');heading.id='ws-settings-heading';heading.className='ws-settings-heading';
      heading.innerHTML='<div class="ws-heading"><div><h2>项目设置</h2><p>按用途管理运行参数、服务连接和访问权限</p></div></div><nav class="ws-settings-nav" aria-label="设置分类"></nav>';
      root.prepend(heading);
    }
    const sections=[['网络代理',content.querySelector('#okad-clash-settings')],['运行参数',run],['自建号池',content.querySelector('#okad-local-pool-settings')],['接口访问',content.querySelector('#okad-external-apikey')],['验证码服务',content.querySelector('#okad-captcha-settings')],['管理员密码',cards.find(c=>c.querySelector('.n-card-header__main').textContent.trim()==='修改管理员密码')]].filter(([,el])=>el);
    const nav=heading.querySelector('nav');
    for(const [label,el] of sections){
      if(Array.from(nav.children).some(b=>b.textContent===label))continue;
      const b=document.createElement('button');b.type='button';b.textContent=label;b.onclick=()=>el.scrollIntoView({behavior:'smooth',block:'start'});nav.appendChild(b);
    }
  }
  function schedule(){if(!queued){queued=true;requestAnimationFrame(sync);}}
  new MutationObserver(schedule).observe(document.documentElement,{childList:true,subtree:true});
  window.addEventListener('popstate',schedule);schedule();
})();
