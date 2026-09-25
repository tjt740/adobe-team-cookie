import {d as defineComponent,k as h,r as ref,m as computed,J as onMounted,L as onUnmounted,l as watch,g as useRouter,h as useRoute,B as Button} from './assets/index-CrrzYg-U.js';
import {N as Input} from './assets/Input-fL4pqH-9.js';
import {b as Select} from './assets/text-C52gYURp.js';
import {N as Switch} from './assets/Switch-DPOdd19W.js';
import {N as Popconfirm} from './assets/Popconfirm-ATXmzMdR.js';

const ACTIVE = ['running','pausing','paused','cancelling'];
const TYPES = {
  external_login:['外部子号登录','外部子号','external','登录 Adobe，保存 Cookie 并查询额度'],
  pool_login:['号池账号登录','号池管理','/pool','刷新账号 Token 与额度'],
  pool_cookie_sub2:['账号导入 Sub2','号池管理','/pool','获取 Cookie，将符合条件的账号导入 Sub2'],
  admin_login:['母号登录','母号管理','/adobe','登录并获取组织管理权限'],
  build_team:['创建团队子号','母号管理','/adobe','为母号创建并注册团队子号'],
  build_team_batch:['批量创建团队子号','母号管理','/adobe','为多个母号创建并注册团队子号'],
  '子号清退':['清退团队子号','母号管理','/adobe','清理指定组织中的子号'],
  '批量更新号池':['同步成员到号池','母号管理','/adobe','读取母号成员并更新本地号池']
};
const active = job => ACTIVE.includes(job?.status);
const definition = job => TYPES[job.type] || [job.type,'历史任务','','查看执行记录'];
function trace(job) {
  const d=definition(job), t=job.trace || {};
  return {title:t.title || d[0], description:t.description || d[3],
    source:t.source || {label:d[1],path:d[2],recorded:false}, operator:t.operator || job.operator || '',
    accounts:t.accounts || [], retry_from_job:t.retry_from_job, filters:t.filters || {}, destination:t.destination,
    mode:t.mode, count:t.count};
}
function state(job) {
  const map={running:['进行中','blue'],pausing:['暂停中','amber'],paused:['已暂停','amber'],cancelling:['终止中','amber'],cancelled:['已终止','muted'],error:['执行失败','red']};
  if(map[job.status]) return map[job.status];
  if(job.status==='done') {
    const still=job.result?.still_no_token;
    if(still !== undefined) return still>0 ? ['仍有账号未完成','amber'] : ['已完成','green'];
    return job.fail>0 ? [job.success>0?'部分失败':'执行失败','red'] : ['已完成','green'];
  }
  return [job.status || '未知','muted'];
}
const time = (value, full=false) => value ? new Date(value*1000).toLocaleString('zh-CN',
  {year:full?'numeric':undefined,month:'2-digit',day:'2-digit',hour:'2-digit',minute:'2-digit',second:full?'2-digit':undefined,hour12:false}) : '尚未结束';
function duration(job) {
  if(!job.created_at) return '—';
  const sec=Math.max(0,(job.finished_at || Math.floor(Date.now()/1000))-job.created_at);
  return sec<60 ? `${sec} 秒` : sec<3600 ? `${Math.floor(sec/60)} 分 ${sec%60} 秒` : `${Math.floor(sec/3600)} 小时 ${Math.floor(sec%3600/60)} 分`;
}
function outcome(job) {
  if(job.type==='pool_cookie_sub2' && job.result) return `新导入 ${job.result.pushed || 0} · 已在库 ${job.result.existing || 0} · 失败 ${job.fail || 0}`;
  if(job.type==='pool_login' && job.result?.still_no_token !== undefined) return `已拿到 Token ${Math.max(0,job.target-job.result.still_no_token)} · 仍未拿到 ${job.result.still_no_token}`;
  return `成功 ${job.success || 0} · 失败 ${job.fail || 0} · 目标 ${job.target || 0}`;
}
function percentage(job) {
  if(job.status==='done') return 100;
  return job.target ? Math.min(100,Math.round(((job.success||0)+(job.fail||0))/job.target*100)) : 0;
}
function records(job) {
  const rows=job.extra?.items || job.result?.items || job.extra?.teams || [];
  const all=trace(job).accounts.map(a=>({...a}));
  for(const row of rows) {
    const id=row.id || row.admin_id;
    const found=all.find(a=>a.id===id);
    if(found) Object.assign(found,row);
    else all.push({...row,id});
  }
  return all.map(row=>{
    if(['cancelled','error'].includes(job.status)&&['pending','running'].includes(row.status))
      return {...row,status:'cancelled',message:row.status==='pending'?'任务已停止，未开始处理':'任务已中断，请查看执行记录'};
    return row;
  });
}
const itemState = row => ({pending:'等待处理',running:'处理中',done:'成功',pushed:'已导入',existing:'已在库，跳过',failed:'失败',error:'失败',partial:'部分完成',cancelled:'已终止'})[row.status] || '未记录结果';
const field = (label, control) => h('label',{class:'ws-field'},[h('span',{},label),control]);
const btn = (label, props={}) => h(Button,props,()=>label);
const pill = (label,tone='muted') => h('span',{class:`ws-pill ${tone}`},label);
const safe = fn => (...args) => Promise.resolve(fn(...args)).catch(()=>{});
const severity = text => /失败|异常|ERROR|✗|错误/.test(text)?'error':/重试|告警|WARNING|限流/.test(text)?'warning':/成功|完成|✓/.test(text)?'success':'info';
const filtersText = filters => Object.entries(filters).filter(([k,v])=>v!==''&&v!==null&&v!==undefined&&(v!==false||k==='has_token')).map(([k,v])=>{
  const names={keyword:'搜索',registered_only:'只看已注册',pool_type:'账号类型',has_token:'Token',credit_status:'额度',credit_value:'积分',status_filter:'状态',export_status:'导出状态'};
  const values={all:'全部',imported:'导入',sub:'子号',admin:'母号',yes:'有',no:'无',exported:'已导出',unexported:'未导出',known:'已知',unknown:'未知',registered:'已拿 Token',pending:'未拿 Token',failed:'失败'};
  return `${names[k] || k}：${k==='has_token'?(v?'有 Token':'无 Token'):values[v] || (v===true?'是':String(v))}`;
}).join(' · ');

export default defineComponent({name:'JobsWorkspace',setup(){
  const router=useRouter(), route=useRoute();
  const jobs=ref([]), detail=ref(null), loading=ref(false), error=ref(''), actionError=ref(''), busy=ref('');
  const selected=ref([]), keyword=ref(''), status=ref(''), type=ref(''), source=ref(''), auto=ref(true), limit=ref(100);
  const tab=ref('accounts'), accountQuery=ref(''), logQuery=ref(''), logLevel=ref(''), updated=ref('');
  let timer, disposed=false, listPending=false, sequence=0;
  const controllers=new Set();
  async function api(path,body) {
    const controller=new AbortController();controllers.add(controller);
    const timeout=setTimeout(()=>controller.abort(),30000);
    try {
      const response=await fetch('/api'+path,{method:body===undefined?'GET':'POST',signal:controller.signal,
        headers:{Authorization:'Bearer '+(localStorage.getItem('okad_token')||''),'Content-Type':'application/json'},
        ...(body===undefined?{}:{body:JSON.stringify(body)})});
      const data=await response.json();
      if(!response.ok || data.success===false) throw new Error(data.detail || data.message || '操作失败，请重试');
      return data;
    } finally {clearTimeout(timeout);controllers.delete(controller);}
  }
  const id=computed(()=>Number(route.query.id)||0);
  async function loadDetail() {
    const current=id.value, own=++sequence;
    if(!current){detail.value=null;return;}
    try {
      const data=await api('/adobe-accounts/jobs/'+current);
      if(disposed || own!==sequence || current!==id.value) return;
      detail.value=data;error.value='';
    } catch(e) {if(!disposed&&own===sequence) error.value=e.name==='AbortError'?'读取任务超时，请重试':e.message;}
  }
  async function loadList() {
    if(listPending) return;
    listPending=true;loading.value=true;
    try {
      const data=await api('/adobe-accounts/jobs?limit='+limit.value);
      if(disposed) return;
      jobs.value=Array.isArray(data)?data:[];
      selected.value=selected.value.filter(i=>jobs.value.some(j=>j.id===i&&!active(j)));
      updated.value=new Date().toLocaleTimeString('zh-CN',{hour12:false});error.value='';
    } catch(e){if(!disposed)error.value=e.name==='AbortError'?'读取任务超时，请重试':e.message;}
    finally {loading.value=false;listPending=false;}
  }
  async function refresh(){if(id.value) await loadDetail();else await loadList();}
  function open(jobId){router.push({path:'/jobs',query:{id:String(jobId)}});}
  function back(){router.push('/jobs');}
  function origin(job){const s=trace(job).source;if(s.path==='external'){document.getElementById('extm-nav')?.click();}else if(s.path){router.push(s.path);}}
  async function operation(action,jobId=id.value) {
    if(busy.value)return false;
    busy.value=action;actionError.value='';
    try {
      if(action==='delete'){
        await api('/adobe-accounts/jobs/batch-delete',{ids:jobId?[jobId]:selected.value});
        selected.value=[];if(id.value) back();await loadList();
      }else if(action==='retry'){
        const job=await api('/pool/batch-login-retry/'+jobId,{});open(job.id);
      }else{await api('/adobe-accounts/jobs/'+jobId+'/'+action,{});await loadDetail();}
      return true;
    }catch(e){actionError.value=e.message;return false;}
    finally{busy.value='';}
  }
  function confirmation(label,action,message,props={},jobId=id.value){
    return h(Popconfirm,{onPositiveClick:()=>operation(action,jobId)}, {
      trigger:()=>btn(label,{...props,loading:busy.value===action,disabled:props.disabled||!!busy.value}),default:()=>message});
  }
  const shown=computed(()=>jobs.value.filter(job=>{
    const t=trace(job), term=keyword.value.trim().toLowerCase();
    const needs=['red','amber'].includes(state(job)[1])&&!active(job);
    const statusMatch=!status.value || (status.value==='active'?active(job):status.value==='attention'?needs:status.value==='done'?state(job)[1]==='green':job.status===status.value);
    return statusMatch && (!type.value||job.type===type.value) && (!source.value||t.source.label===source.value) &&
      (!term||[job.id,t.title,t.operator,t.source.label,...t.accounts.map(a=>a.email||a.id)].join(' ').toLowerCase().includes(term));
  }));
  const pickAll=computed(()=>shown.value.filter(j=>!active(j)));
  function toggle(jobId,on){selected.value=on?[...new Set([...selected.value,jobId])]:selected.value.filter(i=>i!==jobId);}
  function reset(){keyword.value='';status.value='';type.value='';source.value='';}
  function selectFilter(value, options){return h(Select,{value:value.value,options,'onUpdate:value':v=>value.value=v});}
  function card(job) {
    const t=trace(job), [label,tone]=state(job), accounts=t.accounts;
    return h('article',{class:'task-card','data-job-id':job.id},[
      h('div',{class:'task-card-top'},[
        h('input',{type:'checkbox',checked:selected.value.includes(job.id),disabled:active(job),'aria-label':`选择任务 #${job.id}`,onChange:e=>toggle(job.id,e.target.checked)}),
        h('span',{class:'ws-muted'},`#${job.id}`),pill(label,tone),h('span',{class:'task-card-time'},time(job.created_at))]),
      h('button',{class:'task-title-button',onClick:()=>open(job.id)},t.title),
      h('p',{class:'task-description'},t.description),
      h('div',{class:'task-account-preview'},accounts.length?[
        h('span',{title:accounts.map(a=>a.email||`账号 #${a.id}`).join('、')},accounts.slice(0,2).map(a=>a.email||`账号 #${a.id}`).join('、')),
        accounts.length>2?h('small',{},`等 ${accounts.length} 个账号`):null]:h('span',{class:'ws-muted'},'历史任务未记录账号清单')),
      h('div',{class:'task-card-result'},[h('span',{},outcome(job)),h('span',{class:'ws-muted'},active(job)?'执行中':`耗时 ${duration(job)}`)]),
      h('div',{class:'task-progress','aria-label':'执行进度'},[h('i',{class:tone,style:{width:percentage(job)+'%'}})]),
      job.error?h('p',{class:'task-error-preview',title:job.error},job.error):null,
      h('div',{class:'task-card-footer'},[h('span',{class:'ws-muted'},`${t.source.label} · ${t.operator||'操作者未记录'}`),btn('查看详情 →',{text:true,type:'primary',onClick:()=>open(job.id)})])
    ]);
  }
  function board(){
    const counts=[['已加载任务',jobs.value.length,''],['进行中',jobs.value.filter(active).length,'active'],['需要关注',jobs.value.filter(j=>!active(j)&&['red','amber'].includes(state(j)[1])).length,'attention'],['已完成',jobs.value.filter(j=>state(j)[1]==='green').length,'done']];
    return [
      h('header',{class:'ws-heading'},[h('div',{},[h('h2',{},'任务中心'),h('p',{},'查看账号处理进度，追溯每一次操作的来源和结果')]),h('div',{class:'ws-actions'},[
        h('label',{class:'ws-switch'},[h(Switch,{size:'small',value:auto.value,'onUpdate:value':v=>auto.value=v}),'自动刷新']),btn('刷新',{loading:loading.value,onClick:loadList})])]),
      h('div',{class:'ws-stats task-stats'},counts.map(([label,count,key])=>h('button',{class:status.value===key?'is-active':'',onClick:()=>status.value=key},[h('b',{},String(count)),h('span',{},label)]))),
      h('section',{class:'ws-filter','aria-label':'筛选任务'},[
        field('搜索任务',h(Input,{placeholder:'任务编号、邮箱或操作者',value:keyword.value,clearable:true,'onUpdate:value':v=>keyword.value=v})),
        field('任务类型',selectFilter(type,[{label:'全部类型',value:''},...Object.entries(TYPES).map(([value,d])=>({label:d[0],value}))])),
        field('来源页面',selectFilter(source,[{label:'全部来源',value:''},...Array.from(new Set(jobs.value.map(j=>trace(j).source.label))).map(v=>({label:v,value:v}))])),
        field('执行状态',selectFilter(status,[{label:'全部状态',value:''},{label:'进行中',value:'active'},{label:'需要关注',value:'attention'},{label:'已完成',value:'done'},{label:'已终止',value:'cancelled'}])),
        btn('重置',{onClick:reset})]),
      h('div',{class:'ws-batch'},[h('label',{class:'ws-switch'},[
        h('input',{type:'checkbox','aria-label':'选择筛选结果中的已结束任务',checked:!!pickAll.value.length&&pickAll.value.every(j=>selected.value.includes(j.id)),
          disabled:!pickAll.value.length,onChange:e=>{const ids=pickAll.value.map(j=>j.id);selected.value=e.target.checked?[...new Set([...selected.value,...ids])]:selected.value.filter(i=>!ids.includes(i));}}),
        `已选 ${selected.value.length} 项`,h('span',{class:'ws-muted'},`筛选结果 ${shown.value.length} 项`)]),
        h('div',{class:'ws-actions'},[h('small',{class:'ws-muted'},updated.value?`更新于 ${updated.value}`:''),confirmation('删除选中','delete',`删除选中的 ${selected.value.length} 个任务及其记录？`,{text:true,type:'error',disabled:!selected.value.length},0)])]),
      shown.value.length?h('div',{class:'task-grid'},shown.value.map(card)):h('div',{class:'ws-empty'},[h('b',{},loading.value?'正在读取任务…':'暂无匹配任务'),h('p',{},'从账号管理页面发起操作后，可在这里查看。')]),
      h('footer',{class:'task-list-footer'},[h('span',{class:'ws-muted'},`显示最近 ${jobs.value.length} 项任务`),jobs.value.length>=limit.value?btn('加载更早任务',{loading:loading.value,onClick:()=>{limit.value+=100;loadList();}}):null])
    ];
  }
  function accountResults(job) {
    const all=records(job), query=accountQuery.value.trim().toLowerCase();
    const items=all.filter(row=>[row.email,row.id,row.message].join(' ').toLowerCase().includes(query));
    return h('section',{class:'task-account-results'},[
      h('div',{class:'ws-section-heading'},[h('h3',{},`涉及账号（${all.length}）`),h(Input,{placeholder:'查找账号或结果',value:accountQuery.value,clearable:true,'onUpdate:value':v=>accountQuery.value=v,style:{maxWidth:'280px'}})]),
      items.length?h('div',{class:'task-account-list'},items.map(row=>{
        const title=row.email || `账号 #${row.id}`;
        const tone=['failed','error'].includes(row.status)?'red':['done','pushed','existing'].includes(row.status)?'green':row.status==='running'?'blue':'muted';
        return h('article',{class:'task-account-row','data-account-id':row.id},[
          h('div',{},[h('strong',{translate:'no'},title),h('small',{class:'ws-muted'},row.email?`账号 #${row.id}`:'历史任务未保存邮箱')]),
          pill(itemState(row),tone),h('p',{},row.message || '未保存逐账号结果，可按账号查看执行记录'),
          btn('执行记录',{text:true,type:'primary',onClick:()=>{logQuery.value=row.email||String(row.id);tab.value='logs';}})
        ]);
      })):h('div',{class:'ws-empty'},all.length?'没有匹配账号':'此历史任务未保存账号清单，请查看执行记录。')
    ]);
  }
  function executionLogs(job) {
    const logs=(job.logs||[]).map((text,index)=>({text,index,level:severity(text)})).filter(row=>(!logLevel.value||row.level===logLevel.value)&&(!logQuery.value||row.text.toLowerCase().includes(logQuery.value.toLowerCase())));
    return h('section',{},[
      h('div',{class:'ws-section-heading'},[h('h3',{},`执行记录（${job.log_total||0}）`),confirmation('清空记录','clear-logs','清空本任务的执行记录？账号结果与任务摘要会保留。',{text:true,type:'error',disabled:!job.log_total})]),
      h('div',{class:'task-log-filter'},[h(Input,{placeholder:'搜索邮箱、失败原因或执行内容',value:logQuery.value,clearable:true,'onUpdate:value':v=>logQuery.value=v}),
        selectFilter(logLevel,[{label:'全部记录',value:''},{label:'失败 / 异常',value:'error'},{label:'告警 / 重试',value:'warning'},{label:'成功 / 完成',value:'success'},{label:'过程信息',value:'info'}])]),
      logs.length?h('ol',{class:'task-timeline'},logs.map(row=>{const m=row.text.match(/^(\d{2}:\d{2}:\d{2})\s+([\s\S]*)$/);return h('li',{class:row.level,key:row.index},[
        h('time',{},m?m[1]:'—'),h('div',{},[pill({error:'异常',warning:'提醒',success:'结果',info:'过程'}[row.level],{error:'red',warning:'amber',success:'green',info:'muted'}[row.level]),h('p',{},m?m[2]:row.text)])]);})):
        h('div',{class:'ws-empty'},job.log_total?'没有匹配记录，可调整搜索条件。':'暂无执行记录')
    ]);
  }
  function detailView(job) {
    const t=trace(job), [label,tone]=state(job), retry=job.type==='pool_login'&&!active(job)&&(job.fail>0||job.result?.still_no_token>0);
    return [
      h('header',{class:'ws-heading task-detail-heading'},[h('div',{},[btn('← 返回任务列表',{text:true,onClick:back}),h('h2',{},[t.title,h('small',{class:'ws-muted'},` #${job.id}`)]),h('p',{},t.description)]),h('div',{class:'ws-actions'},[
        btn('刷新',{onClick:loadDetail}),active(job)&&job.type==='external_login'&&job.status!=='cancelling'?btn(['paused','pausing'].includes(job.status)?'继续任务':'暂停任务',{loading:!!busy.value,onClick:()=>operation(['paused','pausing'].includes(job.status)?'resume':'pause')}):null,
        active(job)?confirmation(job.status==='cancelling'?'终止中…':'终止任务','cancel','终止本任务？等待当前请求退出，已完成结果会保留。',{type:'error',disabled:job.status==='cancelling'}):null,
        retry?btn('重试未完成账号',{type:'primary',loading:busy.value==='retry',onClick:()=>operation('retry')}):null,
        !active(job)?confirmation('删除任务','delete','删除此任务及其执行记录？',{text:true,type:'error'}):null])]),
      h('section',{class:'task-outcome '+tone},[h('div',{},[pill(label,tone),h('h3',{},outcome(job)),h('p',{class:'ws-muted'},`开始于 ${time(job.created_at,true)} · ${job.finished_at?'耗时':'已运行'} ${duration(job)}`)]),
        h('div',{class:'task-outcome-progress'},[h('strong',{},`${percentage(job)}%`),h('span',{class:'ws-muted'},'执行进度'),h('div',{class:'task-progress'},[h('i',{class:tone,style:{width:percentage(job)+'%'}})])])]),
      job.error?h('div',{class:'ws-alert error',role:'alert'},job.error):null,
      h('section',{class:'task-provenance'},[
        h('div',{},[h('span',{class:'ws-label'},'发起入口'),btn(t.source.label,{text:true,type:'primary',disabled:!t.source.path,onClick:()=>origin(job)}),h('small',{class:'ws-muted'},t.source.action||'具体操作未记录')]),
        h('div',{},[h('span',{class:'ws-label'},'操作者'),h('strong',{},t.operator||'历史任务未记录'),h('small',{class:'ws-muted'},t.source.recorded?'已记录本次发起信息':'来源根据任务类型识别')]),
        h('div',{},[h('span',{class:'ws-label'},'处理范围'),h('strong',{},`${t.accounts.length || job.target || 0} 个账号`),h('small',{class:'ws-muted'},filtersText(t.filters)||'查看下方账号清单')]),
        h('div',{},[h('span',{class:'ws-label'},'任务关联'),t.retry_from_job?btn(`来自任务 #${t.retry_from_job}`,{text:true,type:'primary',onClick:()=>open(t.retry_from_job)}):h('strong',{},'无前置任务记录'),
          btn('复制任务链接',{text:true,size:'small',onClick:safe(async()=>{await navigator.clipboard.writeText(location.href);window.$message?.success('任务链接已复制');})})])]),
      t.destination?.url?h('div',{class:'ws-alert'},[h('strong',{},'导入目标：'),h('span',{},t.destination.url),h('span',{},` · 分组 ${(t.destination.group_ids||[]).join('、')||'未记录'}`)]):null,
      h('div',{class:'task-milestones'},[
        h('div',{class:'complete'},[h('b',{},'1'),h('span',{},'任务发起'),h('small',{},time(job.created_at))]),
        h('div',{class:active(job)?'current':'complete'},[h('b',{},'2'),h('span',{},active(job)?label:'账号处理'),h('small',{},outcome(job))]),
        h('div',{class:job.finished_at?tone:''},[h('b',{},'3'),h('span',{},job.finished_at?label:'等待结束'),h('small',{},job.finished_at?time(job.finished_at):'结果会持续更新')])]),
      h('div',{class:'task-tabs',role:'tablist','aria-label':'任务详情'},[['accounts','账号结果'],['logs','执行记录']].map(([key,label])=>h('button',{role:'tab','aria-selected':tab.value===key,class:tab.value===key?'active':'',onClick:()=>tab.value=key},label))),
      tab.value==='accounts'?accountResults(job):executionLogs(job)
    ];
  }
  watch(id,async()=>{sequence++;detail.value=null;error.value='';actionError.value='';tab.value='accounts';accountQuery.value='';logQuery.value='';logLevel.value='';await refresh();});
  onMounted(async()=>{await refresh();timer=setInterval(()=>{if(auto.value&&!document.hidden&&!busy.value)refresh();},5000);});
  onUnmounted(()=>{disposed=true;sequence++;clearInterval(timer);controllers.forEach(c=>c.abort());});
  return ()=>h('main',{id:'jobs-workspace',class:'ws-page notranslate',translate:'no'},[
    error.value?h('div',{class:'ws-alert error',role:'alert'},[error.value,btn('重试',{text:true,onClick:refresh})]):null,
    actionError.value?h('div',{class:'ws-alert error',role:'alert'},actionError.value):null,
    id.value?(detail.value?detailView(detail.value):h('div',{class:'ws-empty'},[btn('← 返回任务列表',{text:true,onClick:back}),h('p',{},error.value?'无法显示任务详情':'正在读取任务详情…')])):board()
  ]);
}});
