/* Local calendar range picker; no browser-native date-popup dependency. */
import {d as defineComponent,k as h,r as ref,n as nextTick} from './assets/index-CrrzYg-U.js';
const pad=n=>String(n).padStart(2,'0');
const dateKey=d=>`${d.getFullYear()}-${pad(d.getMonth()+1)}-${pad(d.getDate())}`;
function validDate(value) {
  if (!value) return true;
  if (!/^\d{4}-\d{2}-\d{2}$/.test(value)) return false;
  const d=new Date(value+'T12:00:00');
  return !isNaN(d) && dateKey(d)===value;
}
export const ImportDateRange=defineComponent({
  name:'ExternalImportDateRange',props:{from:{type:String,default:''},to:{type:String,default:''},onChange:Function},
  setup(props,{expose}) {
    const draft=ref({from:'',to:''}),error=ref(''),opened=ref(false),month=ref(new Date().getFullYear()*12+new Date().getMonth()),selectingEnd=ref(false);
    let dialog,trigger;
    function close() { if(dialog?.open)dialog.close();opened.value=false; }
    function open() {
      draft.value={from:props.from,to:props.to};error.value='';selectingEnd.value=false;
      const start=props.from || props.to, d=start && validDate(start)?new Date(start+'T12:00:00'):new Date();
      month.value=d.getFullYear()*12+d.getMonth();opened.value=true;
      dialog.showModal();
    }
    function apply() {
      const {from,to}=draft.value;
      error.value=!validDate(from)||!validDate(to)?'请输入有效日期，格式为 YYYY-MM-DD':from&&to&&from>to?'结束日期不能早于开始日期':'';
      if(error.value)return;
      props.onChange?.(from,to);close();
    }
    function choose(value) {
      error.value='';
      if(!selectingEnd.value){draft.value={from:value,to:''};selectingEnd.value=true;}
      else {const start=draft.value.from;draft.value=value<start?{from:value,to:start}:{from:start,to:value};selectingEnd.value=false;}
    }
    function preset(days) {
      const end=new Date(),start=new Date(end);
      if(days===0)start.setDate(1);else start.setDate(start.getDate()-days+1);
      draft.value={from:dateKey(start),to:dateKey(end)};error.value='';selectingEnd.value=false;
      month.value=start.getFullYear()*12+start.getMonth();
    }
    function moveFocus(event,value) {
      const steps={ArrowLeft:-1,ArrowRight:1,ArrowUp:-7,ArrowDown:7};
      if(!(event.key in steps))return;
      event.preventDefault();const d=new Date(value+'T12:00:00');d.setDate(d.getDate()+steps[event.key]);
      const targetMonth=d.getFullYear()*12+d.getMonth();if(targetMonth<month.value||targetMonth>month.value+1)month.value=targetMonth;
      nextTick(()=>dialog.querySelector(`[data-date="${dateKey(d)}"]`)?.focus());
    }
    function calendar(offset) {
      const index=month.value+offset,year=Math.floor(index/12),m=index%12,first=new Date(year,m,1),count=new Date(year,m+1,0).getDate(),leading=(first.getDay()+6)%7;
      const days=Array.from({length:42},(_,i)=>{
        const day=i-leading+1;if(day<1||day>count)return h('span',{class:'extf-calendar-blank','aria-hidden':'true'});
        const value=`${year}-${pad(m+1)}-${pad(day)}`,selected=value===draft.value.from||value===draft.value.to,inRange=draft.value.from&&draft.value.to&&value>draft.value.from&&value<draft.value.to;
        return h('button',{type:'button',class:['extf-calendar-day',selected&&'is-selected',inRange&&'in-range',value===dateKey(new Date())&&'is-today'],'data-date':value,'aria-label':value,'aria-pressed':String(selected),onClick:()=>choose(value),onKeydown:e=>moveFocus(e,value)},String(day));
      });
      return h('section',{class:'extf-calendar-month','aria-label':`${year}年${m+1}月`},[
        h('h4',{},`${year} 年 ${m+1} 月`),h('div',{class:'extf-calendar-grid'},['一','二','三','四','五','六','日'].map(day=>h('span',{class:'extf-calendar-weekday'},day)).concat(days))
      ]);
    }
    expose({close});
    return ()=>h('div',{class:'extf-date-range'},[
      h('button',{id:'extm-f-import-range',type:'button',ref:el=>trigger=el,class:'extf-date-trigger','aria-haspopup':'dialog','aria-controls':'extm-import-date-dialog','aria-expanded':String(opened.value),'aria-labelledby':'extm-f-import-range-label',onClick:open},[
        h('span',{class:!props.from?'is-placeholder':''},props.from||'开始日期'),h('span',{},'至'),h('span',{class:!props.to?'is-placeholder':''},props.to||'结束日期'),h('span',{'aria-hidden':'true',innerHTML:window.OKAD_ICONS.svg('calendar',16)})
      ]),
      h('dialog',{id:'extm-import-date-dialog',ref:el=>dialog=el,class:'extf-date-dialog','aria-labelledby':'extm-import-date-title',onClose:()=>{opened.value=false;trigger?.focus({preventScroll:true});},onCancel:()=>{opened.value=false;},onClick:e=>{
        if(e.target!==e.currentTarget)return;const r=dialog.getBoundingClientRect();if(e.clientX<r.left||e.clientX>r.right||e.clientY<r.top||e.clientY>r.bottom)close();
      }},[
        h('header',{},[h('h3',{id:'extm-import-date-title'},'选择导入日期范围'),h('button',{type:'button','aria-label':'关闭日期选择器',onClick:close},'×')]),
        h('p',{class:'extf-date-help'},'先选开始日期，再选结束日期；结束日期当天也包含在筛选中。'),
        h('div',{class:'extf-date-inputs'},[['from','开始日期'],['to','结束日期']].map(([key,label])=>h('label',{},[label,h('input',{id:'extm-f-import-'+key,value:opened.value?draft.value[key]:props[key],type:'text',placeholder:'YYYY-MM-DD',maxLength:10,inputmode:'text','aria-label':'导入'+label,'aria-invalid':String(!!error.value),onInput:e=>{draft.value[key]=e.target.value;error.value='';selectingEnd.value=false;},onKeydown:e=>{if(e.key==='Enter'){e.preventDefault();apply();}}})]))),
        h('div',{class:'extf-calendar-nav'},[h('button',{type:'button','aria-label':'上个月',onClick:()=>month.value--},'‹'),h('div',{class:'extf-date-presets'},[['今天',1],['最近 7 天',7],['本月',0]].map(([label,days])=>h('button',{type:'button',onClick:()=>preset(days)},label))),h('button',{type:'button','aria-label':'下个月',onClick:()=>month.value++},'›')]),
        h('div',{class:'extf-calendars'},[calendar(0),calendar(1)]),
        h('p',{class:'extf-date-selection',role:'status'},selectingEnd.value?'请选择结束日期':draft.value.from||draft.value.to?`${draft.value.from||'不限开始'} 至 ${draft.value.to||'不限结束'}`:'可选择完整区间，也可只填写一侧日期'),
        error.value?h('p',{class:'extf-error',role:'alert'},error.value):null,
        h('footer',{},[h('button',{type:'button',class:'extf-date-clear',onClick:()=>{props.onChange?.('','');close();}},'清除日期'),h('button',{type:'button',onClick:close},'取消'),h('button',{id:'extm-date-apply',type:'button',class:'extf-date-apply',onClick:apply},'确定')])
      ])
    ]);
  }
});
