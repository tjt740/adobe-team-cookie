import {d as defineComponent,k as h} from './assets/index-CrrzYg-U.js';
import {b as Select} from './assets/text-C52gYURp.js';

export function importOptionsError(batch, duplicate) {
  if (!batch || !/^[0-9]{8}$/.test(batch)) return '请选择导入批次';
  if (!['skip','overwrite'].includes(duplicate)) return '请选择重复邮箱操作';
  return '';
}

export const EmailImportFields=defineComponent({
  name:'EmailImportFields',
  props:{batch:String,duplicate:String,disabled:Boolean,id:String},
  emits:['update:batch','update:duplicate'],
  setup(props,{emit}) {
    return ()=>h('div',{class:'ws-email-import-fields'},[
      h('label',{class:'ws-email-import-field',for:props.id+'-batch'},[
        h('span',{},['导入批次 ',h('span',{class:'ws-required','aria-hidden':'true'},'*')]),
        h('input',{id:props.id+'-batch',type:'date',required:true,'aria-required':'true','aria-label':'导入批次',
          min:'0001-01-01',max:'9999-12-31',disabled:props.disabled,
          value:props.batch?props.batch.slice(0,4)+'-'+props.batch.slice(4,6)+'-'+props.batch.slice(6,8):'',
          onInput:event=>emit('update:batch',event.target.value.replaceAll('-',''))}),
        h('small',{},props.batch?'批次：'+props.batch:'请选择日期，批次格式如 20261024')
      ]),
      h('div',{class:'ws-email-import-field'},[
        h('label',{id:props.id+'-duplicate'},['重复邮箱操作 ',h('span',{class:'ws-required','aria-hidden':'true'},'*')]),
        h(Select,{value:props.duplicate,'onUpdate:value':value=>emit('update:duplicate',value),
          disabled:props.disabled,placeholder:'请选择重复邮箱操作','aria-required':'true','aria-labelledby':props.id+'-duplicate',
          options:[{label:'跳过',value:'skip'},{label:'覆盖更新',value:'overwrite'}]})
      ])
    ]);
  }
});
