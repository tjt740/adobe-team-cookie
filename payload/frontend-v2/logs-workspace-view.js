import {k as h,B as Button} from './assets/index-CrrzYg-U.js';
import {N as Input} from './assets/Input-fL4pqH-9.js';
import {b as Select} from './assets/text-C52gYURp.js';
import {N as Switch} from './assets/Switch-DPOdd19W.js';
import {N as Popconfirm} from './assets/Popconfirm-ATXmzMdR.js';
import {N as Table} from './assets/DataTable-Bp7hAEDt.js';
const btn=(label,props={})=>h(Button,props,()=>label);
export function createLogsWorkspace({s,a}){return ()=>h('section',{id:'logs-workspace',class:'ws-entity'},[
  h('header',{class:'ws-heading',style:{marginTop:0}},[h('div',{},[h('h2',{},'系统日志'),h('p',{},'查看服务运行与请求异常；账号处理进度可前往任务中心')]),h('div',{class:'ws-actions'},[
    btn('任务中心 →',{onClick:()=>location.assign('/jobs')}),h(Popconfirm,{onPositiveClick:a.clear},{trigger:()=>btn('清空日志',{text:true,type:'error'}),default:()=> '确认清空所有系统日志？'})])]),
  h('section',{class:'ws-filter ws-filter-compact','aria-label':'筛选系统日志'},[
    h('label',{class:'ws-field'},[h('span',{},'搜索'),h(Input,{value:s.keyword.value,'onUpdate:value':v=>s.keyword.value=v,placeholder:'搜索内容 / 来源',clearable:true,onKeyup:e=>e.key==='Enter'&&a.refresh()})]),
    h('label',{class:'ws-field'},[h('span',{},'级别'),h(Select,{value:s.level.value,options:s.levels,'onUpdate:value':v=>{s.level.value=v;a.refresh();}})]),btn('搜索',{onClick:a.refresh,type:'primary',secondary:true})]),
  h('div',{class:'ws-batch'},[h('span',{class:'ws-muted'},`最近 ${s.rows.value.length} 条记录`),h('div',{class:'ws-actions'},[
    h('label',{class:'ws-switch'},[h(Switch,{size:'small',value:s.auto.value,'onUpdate:value':v=>{s.auto.value=v;a.auto(v);}}),'自动刷新']),btn('刷新',{loading:s.loading.value,onClick:a.refresh})])]),
  h(Table,{columns:s.columns.value,data:s.rows.value,loading:s.loading.value,rowKey:r=>r.id,scrollX:900,maxHeight:600,pagination:{pageSize:50}},
    {empty:()=>h('div',{class:'ws-empty'},'暂无系统日志')})
]);}
