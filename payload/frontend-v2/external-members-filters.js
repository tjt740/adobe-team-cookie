import {FilterPanel,activeFilters} from './workspace-controls.js?v=20261015-mobile';
/* Filter controls share the application's existing Vue and Naive UI runtime. */
import {createApp, ConfigProvider, k as h, r as ref, aq as useTheme, B as Button} from './assets/index-CrrzYg-U.js';
import {N as Input} from './assets/Input-fL4pqH-9.js';
import {N as InputNumber} from './assets/InputNumber-xGWV9xwu.js';
import {b as Select} from './assets/text-C52gYURp.js';

const options = entries => entries.map(([value, label]) => ({value, label}));
const defaults = () => ({status:'', sub:'', stock:'', health:'', profile:'', company:'', creditsField:'available', creditsMin:null, creditsMax:null, from:'', to:'', keyword:''});
const choices = {
  status: options([['','全部状态'],['ok','正常'],['never','未登录'],['login_failed','登录失败'],['account_disabled','已停用'],['rate_limited','频繁登录限流'],['internal','内部错误']]),
  sub: options([['','全部订阅'],['true','订阅正常'],['false','掉订阅']]),
  stock: options([['','全部库存状态'],['false','未在库'],['true','在库']]),
  health: options([['','全部 Sub2 状态'],['error','全部异常'],['401','401 · 鉴权失败'],['408','408 · 请求超时'],['403','403'],['429','429 · 限流'],['500','500'],['502','502'],['503','503'],['504','504'],['529','529 · 过载'],['other','其他异常（非 401/408）'],['recovered','已有成功证据'],['unknown','待验证 / 无完整记录']]),
  profile: options([['','全部配置'],['personal','个人配置'],['organization','组织配置'],['unknown','未获取']]),
  company: options([['','全部类型'],['true','公司'],['false','非公司']]),
  creditsField: options([['available','可用积分'],['total','总积分']])
};

export function mountFilters(host, actions, initial) {
  const filters = ref({...defaults(), ...initial}), errors = ref({credits:'', dates:''});
  const openSelect = ref(null), loading = ref(false), refreshing = ref(false);
  let keywordTimer;
  function apply() {
    clearTimeout(keywordTimer);
    const f = filters.value;
    errors.value.credits = f.creditsMin != null && f.creditsMax != null && f.creditsMin > f.creditsMax ? '积分最大值不能小于最小值' : '';
    errors.value.dates = f.from && f.to && f.from > f.to ? '结束日期不能早于开始日期' : '';
    if (!errors.value.credits && !errors.value.dates) actions.filter({...f, keyword:f.keyword.trim()});
  }
  function reset() { filters.value = defaults(); openSelect.value = null; apply(); }
  async function refresh() {
    refreshing.value = true;
    try { await actions.refresh(); } finally { refreshing.value = false; }
  }
  const field = (label, id, child, wide=false) => h('div', {class:['extf-field', wide && 'extf-wide']}, [h('label', {id:id+'-label', for:id}, label), child]);
  const input = (id, value, update, props={}) => h(Input, {value, 'onUpdate:value':update, ...props, inputProps:{id, 'aria-labelledby':id+'-label', ...props.inputProps}});
  const select = (id, value, list, update) => h(Select, {id, value, options:list, 'onUpdate:value':update, show:openSelect.value===id, 'onUpdate:show':show=>openSelect.value=show?id:null, 'aria-labelledby':id+'-label', to:host});
  const filterSelect = (key, label) => field(label, 'extm-f-'+key, select('extm-f-'+key, filters.value[key], choices[key], value=>{filters.value[key]=value;apply();}));
  const app = createApp({name:'ExternalMemberFilters', setup() {
    const {naiveTheme} = useTheme();
    return () => h(ConfigProvider, {theme:naiveTheme.value, themeOverrides:{common:{primaryColor:'#1890ff',primaryColorHover:'#46a6ff',primaryColorPressed:'#0e80e6',borderRadius:'6px'}}}, {default:()=>{
      const f = filters.value;
      const credit = (key, suffix, label) => h(InputNumber, {value:f[key], min:0, showButton:false, clearable:true, placeholder:label, status:errors.value.credits?'error':undefined, inputProps:{id:'extm-f-credits-'+suffix,'aria-label':'积分'+label,'aria-describedby':errors.value.credits?'extf-credit-error':undefined}, 'onUpdate:value':v=>{f[key]=v;}, onBlur:apply, onClear:()=>{f[key]=null;apply();}, onKeyup:e=>{if(e.key==='Enter')apply();}});
      const date = (key, suffix, label) => input('extm-f-import-'+suffix,f[key],v=>{f[key]=v;apply();},{type:'date',placeholder:'',inputProps:{'aria-label':label,'aria-labelledby':undefined,'aria-describedby':errors.value.dates?'extf-date-error':undefined},status:errors.value.dates?'error':undefined});
      return h(FilterPanel, {class:'extf-panel',active:activeFilters(Object.entries(f).filter(([key])=>key!=='creditsField').map(([,v])=>v)),onCollapse:()=>openSelect.value=null}, [
        h('div',{class:'extf-grid'},[
          field('邮箱','extm-f-kw',input('extm-f-kw',f.keyword,v=>{f.keyword=v;clearTimeout(keywordTimer);keywordTimer=setTimeout(apply,300);},{clearable:true,placeholder:'搜索邮箱…',onKeyup:e=>{if(e.key==='Enter')apply();}}),true),
          filterSelect('status','登录状态'),filterSelect('sub','订阅状态'),filterSelect('stock','Sub2 库存'),filterSelect('health','Sub2 状态'),
          field('积分范围','extm-f-credits-field',h('div',{class:'extf-credit'},[
            select('extm-f-credits-field',f.creditsField,choices.creditsField,v=>{f.creditsField=v;apply();}),
            h('div',{class:'extf-range'},[credit('creditsMin','min','最小值'),h('span',{},'至'),credit('creditsMax','max','最大值')])
          ]),true),
          field('导入时间','extm-f-import-from',h('div',{class:'extf-range'},[date('from','from','导入开始日期'),h('span',{},'至'),date('to','to','导入结束日期')]),true),
          filterSelect('profile','当前配置'),filterSelect('company','账号类型')
        ]),
        errors.value.credits?h('p',{id:'extf-credit-error',class:'extf-error',role:'alert'},errors.value.credits):null,
        errors.value.dates?h('p',{id:'extf-date-error',class:'extf-error',role:'alert'},errors.value.dates):null,
        h('div',{class:'extf-actions'},[
          h('span',{class:'extf-status',role:'status'},loading.value?'正在更新列表…':''),
          h(Button,{id:'extm-reset-filters',onClick:reset},()=> '重置筛选'),
          h(Button,{id:'extm-refresh',type:'primary',secondary:true,loading:refreshing.value,onClick:refresh},()=> '刷新')
        ])
      ]);
    }});
  }});
  app.mount(host);
  return {loading(value){loading.value=value;},close(){openSelect.value=null;},destroy(){clearTimeout(keywordTimer);app.unmount();}};
}
