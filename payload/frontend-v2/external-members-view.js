/* Vue/Naive UI view. Account services and the task-detail renderer live in the controller. */
import {createApp, ConfigProvider, k as h, r as ref, aq as useTheme, B as Button, aR as Card} from './assets/index-CrrzYg-U.js';
import {N as Input} from './assets/Input-fL4pqH-9.js';
import {N as InputNumber} from './assets/InputNumber-xGWV9xwu.js';
import {b as Select} from './assets/text-C52gYURp.js';
import {N as Spin} from './assets/Spin-DXy_lfOs.js';

const options = entries => entries.map(([value, label]) => ({value, label}));
const defaults = () => ({status:'', sub:'', stock:'', sync:'', health:'', states:[], profile:'', company:'', group:'', creditsField:'available', creditsMin:null, creditsMax:null, from:'', to:'', keyword:''});
const filterOptions = {
  status: options([['','全部状态'],['ok','正常'],['never','未登录'],['login_failed','登录失败'],['account_disabled','已停用'],['rate_limited','频繁登录限流'],['internal','内部错误']]),
  sub: options([['','全部订阅'],['true','订阅正常'],['false','掉订阅']]),
  stock: options([['','全部库存状态'],['false','未在库'],['true','在库']]),
  health: options([['','全部 Sub2 状态'],['error','全部异常'],['401','401 · 鉴权失败'],['408','408 · 请求超时'],['403','403'],['429','429 · 限流'],['500','500'],['502','502'],['503','503'],['504','504'],['529','529 · 过载'],['other','其他异常（非 401/408）'],['recovered','已有成功证据'],['unknown','待验证 / 无完整记录']]),
  sync: options([['','全部同步状态'],['pending','Sub2 待同步'],['syncing','Sub2 同步中'],['synced','Sub2 已同步'],['failed','Sub2 同步失败'],['not_pushed','Sub2 未推送']]),
  profile: options([['','全部配置'],['personal','个人配置'],['organization','组织配置'],['unknown','未获取']]),
  company: options([['','全部类型'],['true','公司'],['vietnam','越南账号'],['false','非公司']]),
  creditsField: options([['available','可用积分'],['total','总积分']])
};

const stateChoices = [
  {type:'group',label:'Sub2 账号状态',key:'sub2',children:filterOptions.health.filter(o=>o.value).map(o=>({...o,value:'sub2_'+o.value,label:'Sub2 '+o.label}))},
  {type:'group',label:'Cookie 与密码',key:'credentials',children:options([['has_cookie','有 Cookie'],['no_cookie','无 Cookie'],['has_password','有密码'],['no_password','无密码']])},
  {type:'group',label:'本轮任务状态',key:'tasks',children:options([['task_pending','排队中'],['task_running','登录中'],['task_otp','等待验证码'],['task_done','本轮成功'],['task_failed','本轮失败'],['task_pausing','暂停中'],['task_paused','已暂停'],['task_cancelling','终止中'],['task_cancelled','已终止'],['task_interrupted','已中断']])},
  {type:'group',label:'登录结果',key:'login',children:filterOptions.status.filter(o=>o.value)}
];

export function mountExternalMembers(host, actions, tableHTML) {
  const form = ref({content:'', duplicate:'skip', otpMode:'', mailToken:'', group:'', groupName:''});
  const filters = ref(defaults());
  const ui = ref({group:'__mixed__', groupSaving:false, groupCreating:false, groupError:'', groupsError:'', total:0, loading:false, selected:0, buttons:{}, message:'', messageTone:'mut', importMessage:'', importTone:'mut', mailState:'读取中…', mailResult:'', mailPlaceholder:'粘贴 supply.ink Token', profile:'__mixed__', profilePlaceholder:'请先勾选账号', profileDisabled:true, pagination:{page:1,pages:1,size:200,total:0,start:0,end:0,busy:false}});
  const groups = ref([]);
  const errors = ref({credits:'', dates:''});
  const openSelect = ref(null);
  const mailOpen = ref(false);
  const importOpen = ref(false);
  const jump = ref(1);
  const customSize = ref('200');
  let keywordTimer;
  const importDrawer = () => host.querySelector('#extm-import-drawer');
  function openImport() {
    openSelect.value = null;
    importDrawer().showModal();
    importOpen.value = true;
  }
  function closeImport() {
    openSelect.value = null;
    importOpen.value = false;
    importDrawer()?.close();
  }
  function positionActions(event) {
    const details=event.currentTarget;
    if(!details.open)return;
    details.dataset.scrollLeft=String(details.closest('.extm-batch-row').scrollLeft);
    const menu=details.querySelector('div'), anchor=details.querySelector('summary').getBoundingClientRect();
    const width=Math.min(menu.offsetWidth,window.innerWidth-24);
    const below=window.innerHeight-anchor.bottom-12, above=anchor.top-12;
    const height=Math.min(menu.scrollHeight,Math.max(below,above));
    Object.assign(menu.style,{left:Math.max(12,Math.min(anchor.right-width,window.innerWidth-width-12))+'px',right:'auto',
      top:(below>=height?anchor.bottom+6:Math.max(12,anchor.top-height-6))+'px',maxHeight:Math.max(44,height)+'px'});
  }
  function closeActions() {
    const more=host.querySelector('#extm-more-actions');
    if(more && more.dataset.scrollLeft!==String(more.closest('.extm-batch-row').scrollLeft))more.open=false;
  }
  function apply() {
    const f = filters.value;
    errors.value.credits = f.creditsMin != null && f.creditsMax != null && f.creditsMin > f.creditsMax ? '积分最大值不能小于最小值' : '';
    errors.value.dates = f.from && f.to && f.from > f.to ? '结束日期不能早于开始日期' : '';
    if (errors.value.credits || errors.value.dates) return;
    clearTimeout(keywordTimer);
    actions.filter({...f, keyword:f.keyword.trim()});
  }
  function reset() { clearTimeout(keywordTimer); filters.value = defaults(); errors.value = {credits:'',dates:''}; apply(); }
  const button = (id, label, onClick, props={}) => {
    const state = ui.value.buttons[id] || {};
    return h(Button, {id, ...props, disabled:!!state.disabled, loading:!!state.loading, 'aria-busy':String(!!state.loading), onClick}, () => state.text || label);
  };
  const field = (label, id, child, cls='') => h('div', {class:'extv-field '+cls}, [h('label', {id:id+'-label', for:id}, label), child]);
  const input = (id, value, update, props={}) => h(Input, {value, 'onUpdate:value':update, ...props, inputProps:{id, 'aria-labelledby':id+'-label', ...props.inputProps}});
  const select = (id, value, list, update, props={}) => h(Select, {id, value, options:list, 'onUpdate:value':value=>{if(!props.multiple)openSelect.value=null;update(value);}, virtualScroll:!["extm-f-health","extm-f-states"].includes(id),show:openSelect.value===id, 'onUpdate:show':show=>openSelect.value=show?id:null, 'aria-labelledby':id+'-label', to:host, ...props});
  const filterSelect = (key, label, suffix=key) => field(label, 'extm-f-'+suffix, select('extm-f-'+suffix, filters.value[key], filterOptions[key], value => {filters.value[key]=value; apply();}));
  const groupOptions = () => groups.value.map(g=>({value:String(g.id),label:g.name}));
  async function createGroup() {
    const name=form.value.groupName.trim();
    if(!name){ui.value.groupError='请输入分组名称';return;}
    if(ui.value.groupCreating)return;
    ui.value.groupCreating=true;ui.value.groupError='';
    try { const group=await actions.createGroup(name);form.value.group=String(group.id);form.value.groupName=''; }
    catch(error){ui.value.groupError=error.message;}
    finally{ui.value.groupCreating=false;}
  }
  const TableRegion = {name:'ExternalMemberTaskTable', render:() => h('div', {class:'extv-table-region', innerHTML:tableHTML})};
  const app = createApp({name:'ExternalMembersWorkspace', setup() {
    const {naiveTheme} = useTheme();
    return () => h(ConfigProvider, {theme:naiveTheme.value, themeOverrides:{common:{primaryColor:'#1890ff',primaryColorHover:'#46a6ff',primaryColorPressed:'#0e80e6',borderRadius:'6px'}}}, {default:() => {
      const f=filters.value, p=ui.value.pagination;
      const credit = (key, suffix, label) => h(InputNumber, {value:f[key], min:0, showButton:false, clearable:true, placeholder:label, status:errors.value.credits?'error':undefined, inputProps:{id:'extm-f-credits-'+suffix,'aria-label':'积分'+label,'aria-describedby':'extv-credit-error'}, 'onUpdate:value':v=>{f[key]=v;}, onBlur:apply, onClear:()=>{f[key]=null;apply();}, onKeyup:e=>{if(e.key==='Enter')apply();}});
      return [
        h('header', {class:'extm-hd'}, [h('h2', {}, '外部子号管理'), h('span', {class:'cnt'}, ['共 ',h('b',{id:'extm-total'},String(ui.value.total)),' 个']), h('span',{class:'cnt'},'Sub2 库存自动更新'),button('extm-stop-all','终止所有任务',actions.stopAll,{type:'error',secondary:true}),button('extm-open-import','导入外部子号',openImport,{type:'primary','aria-haspopup':'dialog','aria-controls':'extm-import-drawer','aria-expanded':String(importOpen.value)})]),
        h('dialog',{id:'extm-import-drawer',class:'extv-import-drawer','aria-labelledby':'extm-import-title','aria-describedby':'extm-import-description',onClose:()=>{if(!importDrawer()?.open){openSelect.value=null;importOpen.value=false;}},onCancel:event=>{event.preventDefault();closeImport();},onKeydownCapture:event=>{
          if(event.key==='Escape' && openSelect.value){event.preventDefault();event.stopPropagation();openSelect.value=null;}
        },onClick:event=>{
          if(event.target!==event.currentTarget)return;
          const r=event.currentTarget.getBoundingClientRect();
          if(event.clientX<r.left || event.clientX>r.right || event.clientY<r.top || event.clientY>r.bottom)closeImport();
        }},[
          h('header',{class:'extv-drawer-header'},[
            h('div',{},[h('h3',{id:'extm-import-title'},'导入外部子号'),h('p',{id:'extm-import-description'},'批量添加账号，登录成功后自动推送 Sub2。')]),
            button('extm-import-close','×',closeImport,{quaternary:true,'aria-label':'关闭导入抽屉',autofocus:true})
          ]),
          h('div',{class:'extv-drawer-body'},[
            h('section',{class:'extv-import-examples','aria-labelledby':'extm-import-examples-title'},[
              h('h4',{id:'extm-import-examples-title'},'导入格式示例'),
              ...[
                ['仅邮箱','user@example.com'],
                ['邮箱 + Adobe 密码','user@example.com----Adobe密码'],
                ['完整邮箱凭据','邮箱----邮箱密码----ClientID----RefreshToken[----Adobe密码]']
              ].map(([label,example])=>h('div',{class:'extv-import-example'},[h('span',{},label),h('code',{},example)])),
              h('p',{},'每行一个账号；兼容 | 或制表符分隔，可直接粘贴表格的邮箱、密码两列。方括号内为可选项。')
            ]),
            field('账号内容识别','extm-import',input('extm-import',form.value.content,v=>form.value.content=v,{type:'textarea',autosize:{minRows:10,maxRows:16},placeholder:'粘贴邮箱或账号凭据，每行一个账号',inputProps:{'aria-describedby':'extm-import-help'}}),'extv-import-content'),
            h('p',{id:'extm-import-help',class:'extv-import-help'},'可一次粘贴超过 50 个账号，任务自动分批。仅邮箱导入固定走验证码；自动取码时按粘贴顺序逐个获取验证码登录。带密码的账号优先使用密码登录。'),
            h('div',{class:'extv-import-controls'},[
              field('重复邮箱','extm-dup',select('extm-dup',form.value.duplicate,options([['skip','跳过'],['overwrite','覆盖']]),v=>form.value.duplicate=v,{to:'#extm-import-drawer'})),
              field('取码方式','extm-otp-mode',select('extm-otp-mode',form.value.otpMode,options([['','保留设置（新账号自动取码）'],['auto','自动取码（supply.ink）'],['manual','手动输入验证码（普通账号）'],['vietnam','越南登录（密码 + 自动接码）']]),v=>{form.value.otpMode=v;if(v!=='auto')mailOpen.value=false;},{to:'#extm-import-drawer'}))
            ]),
            field('自定义分组','extm-import-group',select('extm-import-group',form.value.group,[{value:'',label:'保留分组（新账号未分组）'},{value:'0',label:'未分组'},...groupOptions()],v=>form.value.group=v,{filterable:true,to:'#extm-import-drawer'})),
            h('div',{class:'extv-group-create'},[
              field('新分组名称','extm-group-name',input('extm-group-name',form.value.groupName,v=>form.value.groupName=v,{maxlength:64,placeholder:'例如：客户 A、10 月新号',onKeyup:e=>{if(e.key==='Enter')createGroup();}})),
              h(Button,{id:'extm-create-group',loading:ui.value.groupCreating,disabled:ui.value.groupCreating,onClick:createGroup},()=> '添加分组')
            ]),
            ui.value.groupError?h('p',{class:'extv-filter-error',role:'alert'},ui.value.groupError):null,
            h('p',{class:'extv-import-help'},'分组可与公司、越南、非公司账号类型组合筛选。覆盖导入时，未指定分组会保留原分组。'),
            h('p',{class:'extv-import-help'},'越南登录需填写邮箱和 Adobe 密码，出现邮箱验证时自动接码，无需 supply.ink Token；仅适用于越南取码站支持的账号。普通账号可手动填码，覆盖导入可更新已有账号的选择。'),
            h('details',{id:'extm-mail-config',class:'extm-card extm-import-card',hidden:form.value.otpMode!=='auto',open:mailOpen.value,onToggle:event=>mailOpen.value=event.target.open},[
              h('summary',{},['邮件配置 · supply.ink ',h('span',{id:'extm-mail-state',class:'extm-msg mut'},ui.value.mailState)]),
              h('div',{class:'bd'},[h('p',{class:'tip'},'Token 保存在本项目，所有管理员共享；留空保留已保存配置。'),h('div',{class:'extv-mail-controls'},[
                field('邮件 Token','extm-mail-token',input('extm-mail-token',form.value.mailToken,v=>form.value.mailToken=v,{type:'password',showPasswordOn:'click',placeholder:ui.value.mailPlaceholder,autocomplete:'off'})),
                button('extm-mail-save','保存 Token',()=>actions.mail('save'),{type:'primary'}),button('extm-mail-test','测试连接',()=>actions.mail('test')),button('extm-mail-clear','清除 Token',()=>actions.mail('clear'))
              ]),h('p',{id:'extm-mail-result',class:'extm-msg',role:'status'},ui.value.mailResult)])
            ])
          ]),
          h('footer',{class:'extv-drawer-footer'},[
            h('p',{id:'extm-import-result',class:'extm-msg '+ui.value.importTone,role:'status'},ui.value.importMessage),
            h('div',{},[button('extm-import-done','关闭',closeImport),button('extm-do-import','批量导入',actions.import,{type:'primary'})])
          ])
        ]),
        h('p',{id:'extm-op',class:'extm-msg extv-operation-message '+ui.value.messageTone,role:'status'},ui.value.message),
        h(Card,{class:'extm-card extv-list',contentStyle:{padding:'0'}},{default:()=>[
          h('section',{class:'extv-filters','aria-label':'筛选外部子号'},[
            h('div',{class:'extv-filter-grid'},[
              field('邮箱','extm-f-kw',input('extm-f-kw',f.keyword,v=>{f.keyword=v;clearTimeout(keywordTimer);keywordTimer=setTimeout(apply,300);},{clearable:true,placeholder:'搜索邮箱…',onKeyup:e=>{if(e.key==='Enter')apply();}}),'extv-span-2'),
              filterSelect('status','登录状态'),filterSelect('sub','订阅状态'),
              field('账号状态','extm-f-states',select('extm-f-states',f.states,stateChoices,v=>{f.states=v;apply();},{multiple:true,clearable:true,placeholder:'选择一个或多个状态'}),'extv-span-2'),
              field('积分范围','extm-f-credits-field',h('div',{class:'extv-credit-range'},[
                select('extm-f-credits-field',f.creditsField,filterOptions.creditsField,v=>{f.creditsField=v;apply();}),
                h('div',{class:'extv-range'},[credit('creditsMin','min','最小值'),h('span',{},'至'),credit('creditsMax','max','最大值')])
              ]),'extv-span-2'),filterSelect('profile','当前配置'),filterSelect('company','账号类型'),
              field('导入时间','extm-f-import-from',h('div',{class:'extv-range'},[
                input('extm-f-import-from',f.from,v=>{f.from=v;apply();},{type:'date',placeholder:'',inputProps:{'aria-label':'导入开始日期'},status:errors.value.dates?'error':undefined}),h('span',{},'至'),
                input('extm-f-import-to',f.to,v=>{f.to=v;apply();},{type:'date',placeholder:'',inputProps:{'aria-label':'导入结束日期'},status:errors.value.dates?'error':undefined})
              ]),'extv-span-2'),filterSelect('stock','Sub2 库存'),filterSelect('sync','Sub2 同步状态'),filterSelect('health','Sub2 状态'),
              field('自定义分组','extm-f-group',select('extm-f-group',f.group,[{value:'',label:'全部分组'},{value:'0',label:'未分组'},...groupOptions()],v=>{f.group=v;apply();},{filterable:true}))
            ]),
            ui.value.groupsError?h('p',{class:'extv-filter-error',role:'alert'},[ui.value.groupsError,h(Button,{text:true,onClick:actions.loadGroups},()=> '重新加载分组')]):null,
            errors.value.credits?h('p',{id:'extv-credit-error',class:'extv-filter-error',role:'alert'},errors.value.credits):null,
            errors.value.dates?h('p',{class:'extv-filter-error',role:'alert'},errors.value.dates):null,
            h('div',{class:'extv-filter-actions'},[
              ui.value.loading?h('span',{class:'extv-filter-status',role:'status','aria-live':'polite'},[h(Spin,{size:14}),'正在更新列表…']):null,
              button('extm-reset-filters','重置筛选',reset),button('extm-refresh','刷新',actions.refresh,{type:'primary',secondary:true})
            ])
          ]),
          h('div',{class:'extm-batch-row',role:'group',tabindex:0,'aria-label':'批量操作，宽度不足时可左右滚动',onScroll:closeActions},[
            h('div',{class:'extm-batch-controls'},[
              h('span',{class:'selc'},ui.value.selected?['已选 ',h('b',{id:'extm-selc'},String(ui.value.selected)),' 个']:['勾选账号后可批量操作',h('b',{id:'extm-selc',hidden:true},'0')]),
              field('批量登录配置','extm-batch-profile',select('extm-batch-profile',ui.value.profile,options([['__mixed__',ui.value.profilePlaceholder],['','不指定（原逻辑）'],['personal','个人配置'],['organization','组织配置优先']]).map(o=>({...o,disabled:o.value==='__mixed__'})),actions.profile,{disabled:ui.value.profileDisabled}),'extv-batch-profile'),
              field('批量设置分组','extm-batch-group',select('extm-batch-group',ui.value.group,[{value:'__mixed__',label:ui.value.groupSaving?'保存分组中…':ui.value.selected?'选择分组':'请先勾选账号',disabled:true},{value:'0',label:'未分组'},...groupOptions()],actions.assignGroup,{filterable:true,disabled:!ui.value.selected||ui.value.groupSaving}),'extv-batch-profile'),
              button('extm-batch-login','选中批量重登',actions.batchLogin,{type:'primary',secondary:true}),
              button('extm-batch-del','删除选中',actions.delete,{type:'error',quaternary:true})
            ]),
            h('div',{class:'extv-batch-exports'},[
              button('extm-export','导出全部 Cookie',actions.export),button('extm-export-emails','导出选中邮箱',actions.exportEmails),button('extm-sub2-push','推送 Sub2',()=>actions.push(false),{type:'primary',secondary:true}),
              h('details',{id:'extm-more-actions',class:'ws-maintenance-menu',onToggle:positionActions},[h('summary',{},'更多操作 ▾'),h('div',{},[
                button('extm-login-all','一键重登全部',()=>{host.querySelector('#extm-more-actions').open=false;actions.loginAll();}),
                button('extm-sub2-relink','重新关联 / 推送',()=>{host.querySelector('#extm-more-actions').open=false;actions.push(true);})
              ])])
            ])
          ]),
          h('section',{class:'extv-results','aria-label':'外部子号列表','aria-busy':String(ui.value.loading)},[
            h(Spin,{show:ui.value.loading,description:'正在加载账号…',class:'extv-list-loading'},{default:()=>h(TableRegion)})
          ]),
          h('nav',{class:'extm-pagination','aria-label':'外部子号分页'},[
            h('span',{id:'extm-page-summary',class:'extm-page-summary',role:'status'},`共 ${p.total} 条 · 当前 ${p.start}–${p.end} 条`),
            h('form',{id:'extm-page-size-form',class:'extv-page-size',onSubmit:event=>{event.preventDefault();if(!p.busy && event.currentTarget.reportValidity() && window.OKAD_PAGINATION.valid(customSize.value))actions.size(Number(customSize.value));}},[
              h('label',{id:'extm-page-size-label'},'每页'),
              select('extm-page-size',p.size,options([...new Set([...window.OKAD_PAGINATION.sizes,p.size])].map(size=>[size,size+' 条'])),actions.size,{disabled:p.busy,'aria-label':'每页显示条数'}),
              h('label',{for:'extm-custom-size'},'自定义'),input('extm-custom-size',customSize.value,v=>customSize.value=v,{type:'number',disabled:p.busy,inputProps:{name:'pageSize',min:1,max:window.OKAD_PAGINATION.max,step:1,required:true,'aria-label':'自定义每页条数'}}),
              h(Button,{attrType:'submit',disabled:p.busy},()=> '应用')
            ]),
            button('extm-first','首页',()=>actions.page(1)),button('extm-prev','上一页',()=>actions.page(p.page-1)),
            h('span',{id:'extm-page-info'},`第 ${p.page} / ${p.pages} 页`),
            button('extm-next','下一页',()=>actions.page(p.page+1)),button('extm-last','末页',()=>actions.page(p.pages)),
            h('form',{id:'extm-page-jump',class:'extm-page-jump',onSubmit:e=>{e.preventDefault();actions.page(jump.value);}},[
              h('label',{for:'extm-page-number'},'跳至'),h(InputNumber,{value:jump.value,'onUpdate:value':v=>jump.value=v,min:1,max:p.pages,precision:0,showButton:false,disabled:p.busy,inputProps:{id:'extm-page-number','aria-label':'跳转页码'}}),h('span',{},'页'),button('extm-page-go','跳转',undefined,{attrType:'submit'})
            ])
          ])
        ]})
      ];
    }});
  }});
  app.mount(host);
  function closeMenus(event) {
    const more=host.querySelector('#extm-more-actions');
    if(more && (!more.contains(event.target) || event.key==='Escape')) more.open=false;
  }
  document.addEventListener('click',closeMenus);
  host.addEventListener('keydown',closeMenus);
  return {
    form:form.value,
    groups(value) {groups.value=value;ui.value.groupsError='';},
    update(value) {if(value.profileDisabled && openSelect.value==='extm-batch-profile')openSelect.value=null;Object.assign(ui.value,value);},
    importResult(message, tone) {Object.assign(ui.value,{importMessage:message,importTone:tone,message,messageTone:tone});},
    button(id, value) {ui.value.buttons[id]={...ui.value.buttons[id],...value};},
    ownsButton(id) {return !!id && !!host.querySelector('#'+id+'.n-button');},
    pagination(value) {if(ui.value.pagination.size!==value.size)customSize.value=String(value.size);ui.value.pagination=value; if(document.activeElement?.id!=='extm-page-number')jump.value=value.page;},
    close() {closeImport();},
    destroy() {closeImport();clearTimeout(keywordTimer);document.removeEventListener('click',closeMenus);host.removeEventListener('keydown',closeMenus);app.unmount();}
  };
}
