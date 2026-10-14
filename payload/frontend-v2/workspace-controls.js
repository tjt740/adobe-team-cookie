/* Shared controls keep each page's existing state, API actions and Naive UI focus handling. */
import {d as defineComponent, k as h, r as ref, ah as Modal} from './assets/index-CrrzYg-U.js';
let sequence = 0;
export const FilterPanel = defineComponent({
  name:'WorkspaceFilters', inheritAttrs:false, props:{active:{type:Number,default:0},onCollapse:Function},
  setup(props,{attrs,slots}) {
    const expanded=ref(false), id='ws-filter-body-'+(++sequence);
    return ()=>h('section',{class:'ws-filter-shell','aria-label':attrs['aria-label'] || '筛选条件','data-expanded':String(expanded.value)},[
      h('button',{type:'button',class:'ws-filter-toggle','aria-expanded':String(expanded.value),'aria-controls':id,onClick:()=>{expanded.value=!expanded.value;if(!expanded.value)props.onCollapse?.();}},[
        h('span',{},'筛选条件'),h('span',{class:'ws-filter-count'},props.active?'已设置 '+props.active+' 项':'全部'),h('span',{},expanded.value?'收起 −':'展开 +')
      ]),
      h('div',{...attrs,id,class:[attrs.class,'ws-filter-body']},slots.default?.())
    ]);
  }
});
export const activeFilters = values => values.filter(value=>value!=='' && value!=null && value!==false && value!=='all').length;
export const WorkspaceModal = defineComponent({
  name:'WorkspaceDrawer', inheritAttrs:false,
  setup(_,{attrs,slots}) {return ()=>h(Modal,{...attrs,class:[attrs.class,'ws-drawer'],transformOrigin:'center'},slots);}
});
