import {FilterPanel,activeFilters} from './workspace-controls.js?v=20261015-mobile';
/* Filter controls share the application's existing Vue and Naive UI runtime. */
import {createApp, ConfigProvider, k as h, r as ref, aq as useTheme, B as Button} from './assets/index-CrrzYg-U.js';
import {N as Input} from './assets/Input-fL4pqH-9.js';
import {ImportDateRange} from './external-import-date-range.js?v=20261016-filter-repair';
import {N as Spin} from './assets/Spin-DXy_lfOs.js';
import {b as Select} from './assets/text-C52gYURp.js';

const options = entries => entries.map(([value, label]) => ({value, label}));
const defaults = () => ({status:'', sub:'', stock:'', health:'', states:[], profile:'', company:'', creditsField:'available', creditsMin:'', creditsMax:'', from:'', to:'', keyword:''});
const choices = {
  status: options([['','全部状态'],['ok','正常'],['never','未登录'],['login_failed','登录失败'],['account_disabled','已停用'],['rate_limited','频繁登录限流'],['internal','内部错误']]),
  sub: options([['','全部订阅'],['true','订阅正常'],['false','掉订阅']]),
  stock: options([['','全部库存状态'],['false','未在库'],['true','在库']]),
  health: options([['','全部 Sub2 状态'],['error','全部异常'],['401','401 · 鉴权失败'],['408','408 · 请求超时'],['403','403'],['429','429 · 限流'],['500','500'],['502','502'],['503','503'],['504','504'],['529','529 · 过载'],['other','其他异常（非 401/408）'],['recovered','已有成功证据'],['unknown','待验证 / 无完整记录']]),
  profile: options([['','全部配置'],['personal','个人配置'],['organization','组织配置'],['unknown','未获取']]),
  company: options([['','全部类型'],['true','公司'],['false','非公司']]),
  creditsField: options([['available','可用积分'],['total','总积分']])
};

const stateChoices = [
  {type:'group',label:'Sub2 账号状态',key:'sub2',children:choices.health.filter(o=>o.value).map(o=>({...o,value:'sub2_'+o.value,label:'Sub2 '+o.label}))},
  {type:'group',label:'Cookie 与密码',key:'credentials',children:options([['has_cookie','有 Cookie'],['no_cookie','无 Cookie'],['has_password','有密码'],['no_password','无密码']])},
  {type:'group',label:'本轮任务状态',key:'tasks',children:options([['task_pending','排队中'],['task_running','登录中'],['task_otp','等待验证码'],['task_done','本轮成功'],['task_failed','本轮失败'],['task_pausing','暂停中'],['task_paused','已暂停'],['task_cancelling','终止中'],['task_cancelled','已终止'],['task_interrupted','已中断']])},
  {type:'group',label:'登录结果',key:'login',children:choices.status.filter(o=>o.value)}
];

export function mountFilters(host, actions, initial) {
  const filters = ref({...defaults(), ...initial}), errors = ref({credits:''});
  const openSelect = ref(null), loading = ref(false), refreshing = ref(false);
  let keywordTimer, datePicker;
  function apply() {
    clearTimeout(keywordTimer);
    const f = filters.value;
    const number=value=>value==null||String(value).trim()===''?null:Number(String(value).trim());
    const valid=value=>value==null||String(value).trim()===''||(/^\d+(?:\.\d*)?$|^\.\d+$/.test(String(value).trim())&&Number.isFinite(number(value)));
    const min=number(f.creditsMin),max=number(f.creditsMax);
    errors.value.credits = !valid(f.creditsMin)||!valid(f.creditsMax)?'积分请输入大于或等于 0 的有效数字':min!=null&&max!=null&&min>max?'积分最大值不能小于最小值':'';
    if (!errors.value.credits) return actions.filter({...f,creditsMin:min,creditsMax:max,states:[...f.states],keyword:f.keyword.trim()});
  }

  function reset() { datePicker?.close();filters.value = defaults(); openSelect.value = null; apply(); }
  async function refresh() {
    refreshing.value = true;
    try { await apply(); } finally { refreshing.value = false; }
  }
  const field = (label, id, child, wide=false) => h('div', {class:['extf-field', wide && 'extf-wide']}, [h('label', {id:id+'-label', for:id}, label), child]);
  const input = (id, value, update, props={}) => h(Input, {value, 'onUpdate:value':update, ...props, inputProps:{id, 'aria-labelledby':id+'-label', ...props.inputProps}});
  const select = (id, value, list, update, props={}) => h(Select, {id, value, options:list, 'onUpdate:value':update, show:openSelect.value===id, 'onUpdate:show':show=>openSelect.value=show?id:null, 'aria-labelledby':id+'-label', to:host, ...props});
  const filterSelect = (key, label) => field(label, 'extm-f-'+key, select('extm-f-'+key, filters.value[key], choices[key], value=>{filters.value[key]=value;apply();}));
  const app = createApp({name:'ExternalMemberFilters', setup() {
    const {naiveTheme} = useTheme();
    return () => h(ConfigProvider, {theme:naiveTheme.value, themeOverrides:{common:{primaryColor:'#1890ff',primaryColorHover:'#46a6ff',primaryColorPressed:'#0e80e6',borderRadius:'6px'}}}, {default:()=>{
      const f = filters.value;
      const credit = (key, suffix, label) => input('extm-f-credits-'+suffix,f[key]==null?'':String(f[key]),v=>{f[key]=v;}, {clearable:true,placeholder:label,status:errors.value.credits?'error':undefined,inputProps:{'aria-label':'积分'+label,'aria-describedby':errors.value.credits?'extf-credit-error':undefined,inputmode:'decimal'},onBlur:apply,onClear:()=>{f[key]='';apply();},onKeyup:e=>{if(e.key==='Enter')apply();}});
      return h(FilterPanel, {class:'extf-panel',active:activeFilters(Object.entries(f).filter(([key])=>key!=='creditsField' && key!=='states').map(([,v])=>v))+(f.states.length?1:0),onCollapse:()=>{openSelect.value=null;datePicker?.close();}}, [
        h('div',{class:'extf-grid'},[
          field('邮箱','extm-f-kw',input('extm-f-kw',f.keyword,v=>{f.keyword=v;clearTimeout(keywordTimer);keywordTimer=setTimeout(apply,300);},{clearable:true,placeholder:'搜索邮箱…',onKeyup:e=>{if(e.key==='Enter')apply();}}),true),
          field('账号状态','extm-f-states',select('extm-f-states',f.states,stateChoices,value=>{f.states=value;apply();},{multiple:true,clearable:true,filterable:true,maxTagCount:1,placeholder:'选择状态（可多选）','aria-describedby':'extf-state-help',consistentMenuWidth:false,menuProps:{class:'extf-state-menu'}}),true),
          filterSelect('status','登录状态'),filterSelect('sub','订阅状态'),filterSelect('stock','Sub2 库存'),filterSelect('profile','当前配置'),
          field('积分范围','extm-f-credits-field',h('div',{class:'extf-credit'},[
            select('extm-f-credits-field',f.creditsField,choices.creditsField,v=>{f.creditsField=v;apply();}),
            h('div',{class:'extf-range'},[credit('creditsMin','min','最小值'),h('span',{},'至'),credit('creditsMax','max','最大值')])
          ]),true),
          field('导入时间','extm-f-import-range',h(ImportDateRange,{ref:el=>datePicker=el,from:f.from,to:f.to,onChange:(from,to)=>{f.from=from;f.to=to;apply();}}),true),
          field('账号类型','extm-f-company',select('extm-f-company',f.company,choices.company,value=>{f.company=value;apply();}),true)

        ]),
        errors.value.credits?h('p',{id:'extf-credit-error',class:'extf-error',role:'alert'},errors.value.credits):null,
        h('div',{class:'extf-actions'},[
          h('div',{class:'extf-action-buttons'},[
            h(Button,{id:'extm-refresh',type:'primary',loading:refreshing.value || loading.value,disabled:refreshing.value || loading.value,'aria-busy':String(refreshing.value || loading.value),onClick:refresh},{default:()=> '搜索',icon:()=>h('span',{innerHTML:window.OKAD_ICONS.svg('search',16)})}),
            h(Button,{id:'extm-reset-filters',onClick:reset},()=> '重置')
          ]),
          h('span',{id:'extf-state-help',class:'extf-state-help'},f.states.length?'已选 '+f.states.length+' 个状态，满足任一即可':'账号状态支持多选'),
          loading.value?h('span',{class:'extf-status',role:'status','aria-live':'polite'},[h(Spin,{size:14}),'正在搜索账号…']):null
        ])
      ]);
    }});
  }});
  app.mount(host);
  return {loading(value){loading.value=value;},close(){openSelect.value=null;datePicker?.close();},destroy(){clearTimeout(keywordTimer);datePicker?.close();app.unmount();}};
}
