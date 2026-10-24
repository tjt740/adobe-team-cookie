/* Shared import drawer for mother accounts, mailboxes and the account pool. */
import {d as defineComponent,k as h,r as ref,l as watch,B as Button} from './assets/index-CrrzYg-U.js';
import {N as Input} from './assets/Input-fL4pqH-9.js';
import {b as Select} from './assets/text-C52gYURp.js';
import {WorkspaceModal} from './workspace-controls.js?v=20261015-mobile';
import {EmailImportFields,importOptionsError} from './email-import-fields.js?v=20261024-batches';
let sequence=0;
export const BatchImportDrawer=defineComponent({
  name:'BatchImportDrawer',props:{title:String,formatHint:String,placeholder:String,importFn:Function,show:Boolean,requireBatch:Boolean},emits:['update:show','success'],
  setup(props,{emit,expose}) {
    const visible=ref(props.show),content=ref(''),duplicate=ref(props.requireBatch?null:'skip'),batch=ref(''),busy=ref(false),result=ref(null),error=ref('');
    const id='ws-account-content-'+(++sequence);
    const show=value=>{visible.value=value;emit('update:show',value);};
    watch(()=>props.show,value=>visible.value=value);
    expose({open(){show(true);}});
    async function submit() {
      if(busy.value)return;
      if(!content.value.trim()){error.value='请粘贴要导入的账号内容';return;}
      if(props.requireBatch){const message=importOptionsError(batch.value,duplicate.value);if(message){error.value=message;return;}}
      busy.value=true;error.value='';result.value=null;
      try {
        const response=await props.importFn(content.value.trim(),duplicate.value,batch.value);
        result.value=response;
        if(!response.failed)content.value='';
        emit('success');
      } catch(e) {error.value=e.response?.data?.detail || e.message || '导入失败，请重试';}
      finally {busy.value=false;}
    }
    const button=(label,props)=>h(Button,props,()=>label);
    return ()=>h(WorkspaceModal,{show:visible.value,'onUpdate:show':show,preset:'card',title:props.title,'aria-label':props.title,closable:true,class:'ws-import-drawer'}, {
      default:()=>[
        h('section',{class:'ws-import-example','aria-label':'导入格式示例'},[h('h4',{},'导入格式示例'),h('code',{},props.formatHint),h('p',{},'每行一个账号，按上述顺序填写。')]),
        h('label',{class:'ws-content-label',for:id},'账号内容识别'),
        h(Input,{value:content.value,'onUpdate:value':v=>content.value=v,type:'textarea',autosize:{minRows:10,maxRows:16},disabled:busy.value,placeholder:'粘贴账号内容，每行一个账号',inputProps:{id,'aria-label':'账号内容识别'}}),
        props.requireBatch?h(EmailImportFields,{id,batch:batch.value,'onUpdate:batch':v=>batch.value=v,duplicate:duplicate.value,'onUpdate:duplicate':v=>duplicate.value=v,disabled:busy.value}):
          h('div',{class:'ws-import-options'},[h('label',{id:id+'-duplicate'},'重复邮箱'),h(Select,{value:duplicate.value,'onUpdate:value':v=>duplicate.value=v,disabled:busy.value,'aria-labelledby':id+'-duplicate',options:[{label:'跳过',value:'skip'},{label:'覆盖更新',value:'overwrite'}]})]),
        props.requireBatch?h('p',{class:'ws-muted'},'使用状态按 Sub2 在库情况初始化，默认关闭。'):null
      ],
      footer:()=>[
        error.value?h('p',{class:'ws-import-error',role:'alert'},String(error.value)):null,
        result.value?h('div',{class:'ws-import-result',role:'status'},[
          h('p',{},`新增 ${result.value.created} · 更新 ${result.value.updated} · 跳过 ${result.value.skipped} · 失败 ${result.value.failed}`),
          result.value.errors?.length?h('ul',{},result.value.errors.slice(0,8).map(e=>h('li',{},String(e)))):null
        ]):null,
        h('div',{class:'ws-drawer-actions'},[button('关闭',{onClick:()=>show(false)}),button('开始导入',{type:'primary',loading:busy.value,onClick:submit})])
      ]
    });
  }
});
