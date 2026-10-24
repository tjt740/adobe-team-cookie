import {d as defineComponent,k as h,r as ref,B as Button} from './assets/index-CrrzYg-U.js';
import {r as request} from './assets/auth-DQiNxie4.js';
import {b as Select} from './assets/text-C52gYURp.js';
import {WorkspaceModal} from './workspace-controls.js?v=20261015-mobile';

const button=(label,props={})=>h(Button,props,()=>label);
const formats=[
  {label:'四横线分隔（ClientID 在前）',value:'standard'},
  {label:'竖线分隔（RefreshToken 在前）',value:'pipe'}
];

export const EmailFormatsDrawer=defineComponent({
  name:'EmailFormatsDrawer',props:{getContext:Function},
  setup(props,{expose}) {
    const visible=ref(false),scope=ref('filtered'),format=ref('standard'),busy=ref(false),
      content=ref(''),total=ref(0),error=ref(''),textarea=ref(null),copying=ref(false);
    let context={ids:[],filters:{}},single=null,revision=0;
    function close(){revision++;visible.value=false;busy.value=false;content.value='';total.value=0;error.value='';single=null;context={ids:[],filters:{}};}
    async function load() {
      const current=++revision;
      busy.value=true;error.value='';content.value='';total.value=0;
      const filters=scope.value==='single'?{ids:[single.id]}:scope.value==='selected'?{ids:context.ids}:context.filters;
      try {
        const result=await request.post('/emails/formats',{...filters,format:format.value});
        if(current!==revision || !visible.value)return;
        content.value=result.content;total.value=result.total;
      } catch(e) {
        if(current!==revision || !visible.value)return;
        error.value=typeof e.response?.data?.detail==='string'?e.response.data.detail:'读取邮箱格式失败，请重试';
      } finally {if(current===revision)busy.value=false;}
    }
    expose({open(row=null){
      context=props.getContext();single=row;
      scope.value=row?'single':context.ids.length?'selected':'filtered';
      visible.value=true;load();
    }});
    function selectAll(){textarea.value?.focus();textarea.value?.select();}
    async function copy() {
      if(busy.value || copying.value || !content.value)return;
      copying.value=true;
      let copied=false;
      try {
        if(navigator.clipboard?.writeText){try{await navigator.clipboard.writeText(content.value);copied=true;}catch{}}
        if(!copied){selectAll();try{copied=document.execCommand('copy');}catch{}}
        if(copied)window.$message?.success('邮箱格式已复制');
        else window.$message?.error('复制失败，请点击「选择全部」后手动复制');
      } finally {copying.value=false;}
    }
    function scopeOptions(){return [
      ...(single?[{label:'当前邮箱：'+single.email,value:'single'}]:[]),
      {label:`已勾选（${context.ids.length} 条）`,value:'selected',disabled:!context.ids.length},
      {label:'当前筛选的全部邮箱',value:'filtered'}
    ];}
    return ()=>h(WorkspaceModal,{show:visible.value,'onUpdate:show':value=>{if(!value)close();},
      preset:'card',title:'历史邮箱格式',closable:true,'aria-label':'历史邮箱格式',class:'ws-email-formats'}, {
      default:()=>[
        h('p',{class:'ws-muted'},'完整展示当前保存的邮箱资料，空字段保留空位，有取信链接时追加在末尾。'),
        h('div',{class:'ws-email-format-controls'},[
          h('div',{class:'ws-field'},[h('label',{id:'email-format-scope-label'},'展示范围'),h(Select,{
            value:scope.value,options:scopeOptions(),'aria-labelledby':'email-format-scope-label',
            'onUpdate:value':value=>{scope.value=value;load();}})]),
          h('div',{class:'ws-field'},[h('label',{id:'email-format-kind-label'},'数据格式'),h(Select,{
            value:format.value,options:formats,'aria-labelledby':'email-format-kind-label',
            'onUpdate:value':value=>{format.value=value;load();}})])
        ]),
        h('code',{class:'ws-email-format-hint'},format.value==='pipe'?'邮箱|密码|RefreshToken|ClientID[|取信链接]':'邮箱----密码----ClientID----RefreshToken[----取信链接]'),
        h('label',{class:'ws-content-label',for:'email-format-content'},'完整邮箱格式'),
        h('textarea',{id:'email-format-content',ref:textarea,value:content.value,readonly:true,wrap:'off',spellcheck:false,
          class:'ws-email-format-content','aria-label':'完整邮箱格式','aria-busy':String(busy.value),
          placeholder:busy.value?'正在读取邮箱资料…':error.value?'读取失败，请重试':'当前范围没有邮箱记录'}),
        error.value?h('p',{class:'ws-import-error',role:'alert'},error.value):null
      ],
      footer:()=>[
        h('p',{class:'ws-muted',role:'status'},busy.value?'正在读取…':`共 ${total.value} 条，每行一个邮箱，可完整选择和复制。`),
        h('div',{class:'ws-drawer-actions ws-email-format-actions'},[
          button('关闭',{onClick:close}),
          error.value?button('重试',{onClick:load}):button('选择全部',{disabled:busy.value||!content.value,onClick:selectAll}),
          button('复制全部',{type:'primary',disabled:busy.value||!content.value,loading:copying.value,onClick:copy})
        ])
      ]
    });
  }
});
