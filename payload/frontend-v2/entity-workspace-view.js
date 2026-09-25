/* Shared layout for the native account and mailbox screens; existing actions/dialogs stay in place. */
import {k as h,B as Button} from './assets/index-CrrzYg-U.js';
import {N as Input} from './assets/Input-fL4pqH-9.js';
import {b as Select} from './assets/text-C52gYURp.js';
import {N as Table} from './assets/DataTable-Bp7hAEDt.js';
import {a as Dropdown} from './assets/Dropdown-yKLdvPjR.js';
import {S as Stats} from './assets/BatchImportModal-COnkF9EJ.js';
const btn=(label,props={})=>h(Button,props,()=>label);
const field=(label,control)=>h('label',{class:'ws-field'},[h('span',{},label),control]);
const menu=(label,options,select)=>h(Dropdown,{trigger:'click',options,onSelect:select},{default:()=>btn(label+' ▾')});
export function createEntityWorkspace({kind,s,a}) {
  const mail=kind==='email';
  const title=mail?'邮箱列表':'母号列表';
  function columns(){
    const source=s.columns.value;
    if(!mail)return source.filter(c=>c.key!=='id').map(c=>c.key==='actions'?{...c,width:175,render:row=>h('div',{class:'ws-row-actions'},[
      btn('登录',{text:true,type:'primary',loading:s.loginBusy.value.has(row.id),onClick:()=>a.login(row)}),
      btn('成员',{text:true,type:'primary',onClick:()=>a.members(row)}),
      h(Dropdown,{trigger:'click',options:[{label:'检测有效性',key:'check',disabled:s.checkBusy.value.has(row.id)},{label:'测试收邮件',key:'test'},{label:'编辑',key:'edit'},{label:'删除',key:'delete'}],onSelect:key=>key==='check'?a.check(row):a.more(key,row)},
        {default:()=>btn('更多 ▾',{text:true})})
    ])}:c);
    const credential={title:'取信配置',key:'credentials',width:230,render:row=>h('div',{class:'ws-credential-list'},[
      h('span',{class:(row.refresh_token&&row.client_id)||row.mail_url?'available':''},row.mail_url?'取信链接已配置':row.refresh_token&&row.client_id?'微软授权已配置':'待配置取信方式'),
      btn('查看 / 编辑',{text:true,size:'small',type:'primary',onClick:()=>a.edit(row)})])};
    return [source[0],{...source.find(c=>c.key==='email'),width:320},credential,...source.filter(c=>['is_used','remark','actions'].includes(c.key))];
  }
  return ()=>h('section',{id:kind+'-workspace',class:'ws-entity notranslate',translate:'no'},[
    s.stats.value.length?h(Stats,{items:s.stats.value,onPick:a.pickStats}):null,
    h('header',{class:'ws-heading'},[h('div',{},[h('h2',{},title),h('p',{},mail?'管理邮箱与收件配置，为账号登录做好准备':'管理组织权限、团队成员与子号创建')]),
      h('div',{class:'ws-actions'},[btn(mail?'新增邮箱':'新增账号',{type:'primary',onClick:a.create}),btn('批量导入',{onClick:a.import}),
        mail?btn('创建 MoeMail',{onClick:a.createMail}):menu('维护操作',[{label:'清理组织已删母号',key:'prune'}],()=>a.prune())])]),
    h('section',{class:'ws-filter ws-filter-compact','aria-label':'筛选'+title},[
      field('搜索',h(Input,{value:s.keyword.value,'onUpdate:value':v=>s.keyword.value=v,clearable:true,placeholder:mail?'搜索邮箱 / 备注':'搜索邮箱 / Client ID / 备注',onKeyup:e=>e.key==='Enter'&&a.search()})),
      mail?field('使用状态',h(Select,{value:s.status.value,options:s.statusOptions,'onUpdate:value':v=>{s.status.value=v;a.search();}})):null,
      h('div',{class:'ws-actions'},[btn('重置',{onClick:()=>{s.keyword.value='';if(mail)s.status.value='all';a.search();}}),btn('搜索',{type:'primary',secondary:true,onClick:a.search})])]),
    h('div',{class:'ws-batch'},[h('span',{class:'ws-muted'},['已选 ',h('b',{class:'ws-accent'},String(s.selected.value.length)),' 个']),
      h('div',{class:'ws-actions ws-entity-batch'},[mail?btn('抽检收码',{loading:s.sampleBusy.value,onClick:a.sample}):btn('批量拉号',{disabled:!s.selected.value.length,onClick:a.build}),
        // Keep the wrapper expected by the existing remote-cleanup extension.
        h('div',{class:'ws-actions'},btn('批量删除',{type:'error',text:true,disabled:!s.selected.value.length,onClick:a.delete}))])]),
    h(Table,{columns:columns(),data:s.rows.value,loading:s.loading.value,rowKey:r=>r.id,
      checkedRowKeys:s.selected.value,'onUpdate:checkedRowKeys':v=>s.selected.value=v,scrollX:mail?1040:1110,remote:true,
      pagination:{...s.pagination,showSizePicker:true,prefix:p=>`共 ${p.itemCount} 个`,onUpdatePage:a.page,onUpdatePageSize:a.size}})
  ]);
}
