import{a9 as xe,m as P,r as z,a2 as at,d as ae,M as ut,k as u,V as ht,ad as ln,J as Ge,bJ as rn,bp as an,bk as Ne,bK as sn,t as J,a_ as _e,bL as et,l as Ce,L as Rt,a7 as Fe,a3 as dn,U as Tt,s as _,y as W,x as Q,p as ce,a5 as st,S as Ot,F as vt,aO as un,a0 as cn,E as fn,G as Ae,X as ct,H as fe,I as qe,bM as hn,n as Ft,P as ge,bd as $e,bN as vn,aa as gn,K as bn,bO as pn,ai as mn,ap as wn,aB as gt,bl as yn,aI as xn,bP as Cn,bQ as Sn,bR as Rn,a4 as ue,bS as Tn,aY as On,b0 as Fn,bT as zn,bU as Mn,bV as Pn}from"./index-CrrzYg-U.js";import{i as In,d as kn,j as tt,k as ft,a as Bn,h as Ee,l as _n,m as $n,b as nt,V as bt,N as En,g as pt,B as Nn,e as An,f as Ln,u as dt,c as Dn}from"./Tag-Bwosooua.js";import{a as Vn}from"./Input-fL4pqH-9.js";import{a as mt,b as jn}from"./auth-DQiNxie4.js";import{u as zt}from"./use-compitable-NwYE7-py.js";function wt(e){return e&-e}class Mt{constructor(n,o){this.l=n,this.min=o;const l=new Array(n+1);for(let i=0;i<n+1;++i)l[i]=0;this.ft=l}add(n,o){if(o===0)return;const{l,ft:i}=this;for(n+=1;n<=l;)i[n]+=o,n+=wt(n)}get(n){return this.sum(n+1)-this.sum(n)}sum(n){if(n===void 0&&(n=this.l),n<=0)return 0;const{ft:o,min:l,l:i}=this;if(n>i)throw new Error("[FinweckTree.sum]: `i` is larger than length.");let d=n*l;for(;n>0;)d+=o[n],n-=wt(n);return d}getBound(n){let o=0,l=this.l;for(;l>o;){const i=Math.floor((o+l)/2),d=this.sum(i);if(d>n){l=i;continue}else if(d<n){if(o===i)return this.sum(o+1)<=n?o+1:i;o=i}else return i}return o}}let Ke;function Wn(){return typeof document>"u"?!1:(Ke===void 0&&("matchMedia"in window?Ke=window.matchMedia("(pointer:coarse)").matches:Ke=!1),Ke)}let ot;function yt(){return typeof document>"u"?1:(ot===void 0&&(ot="chrome"in window?window.devicePixelRatio:1),ot)}const Pt="VVirtualListXScroll";function Hn({columnsRef:e,renderColRef:n,renderItemWithColsRef:o}){const l=z(0),i=z(0),d=P(()=>{const p=e.value;if(p.length===0)return null;const C=new Mt(p.length,0);return p.forEach((x,k)=>{C.add(k,x.width)}),C}),h=xe(()=>{const p=d.value;return p!==null?Math.max(p.getBound(i.value)-1,0):0}),r=p=>{const C=d.value;return C!==null?C.sum(p):0},m=xe(()=>{const p=d.value;return p!==null?Math.min(p.getBound(i.value+l.value)+1,e.value.length-1):0});return at(Pt,{startIndexRef:h,endIndexRef:m,columnsRef:e,renderColRef:n,renderItemWithColsRef:o,getLeft:r}),{listWidthRef:l,scrollLeftRef:i}}const xt=ae({name:"VirtualListRow",props:{index:{type:Number,required:!0},item:{type:Object,required:!0}},setup(){const{startIndexRef:e,endIndexRef:n,columnsRef:o,getLeft:l,renderColRef:i,renderItemWithColsRef:d}=ut(Pt);return{startIndex:e,endIndex:n,columns:o,renderCol:i,renderItemWithCols:d,getLeft:l}},render(){const{startIndex:e,endIndex:n,columns:o,renderCol:l,renderItemWithCols:i,getLeft:d,item:h}=this;if(i!=null)return i({itemIndex:this.index,startColIndex:e,endColIndex:n,allColumns:o,item:h,getLeft:d});if(l!=null){const r=[];for(let m=e;m<=n;++m){const p=o[m];r.push(l({column:p,left:d(m),item:h}))}return r}return null}}),Kn=tt(".v-vl",{maxHeight:"inherit",height:"100%",overflow:"auto",minWidth:"1px"},[tt("&:not(.v-vl--show-scrollbar)",{scrollbarWidth:"none"},[tt("&::-webkit-scrollbar, &::-webkit-scrollbar-track-piece, &::-webkit-scrollbar-thumb",{width:0,height:0,display:"none"})])]),Un=ae({name:"VirtualList",inheritAttrs:!1,props:{showScrollbar:{type:Boolean,default:!0},columns:{type:Array,default:()=>[]},renderCol:Function,renderItemWithCols:Function,items:{type:Array,default:()=>[]},itemSize:{type:Number,required:!0},itemResizable:Boolean,itemsStyle:[String,Object],visibleItemsTag:{type:[String,Object],default:"div"},visibleItemsProps:Object,ignoreItemResize:Boolean,onScroll:Function,onWheel:Function,onResize:Function,defaultScrollKey:[Number,String],defaultScrollIndex:Number,keyField:{type:String,default:"key"},paddingTop:{type:[Number,String],default:0},paddingBottom:{type:[Number,String],default:0}},setup(e){const n=sn();Kn.mount({id:"vueuc/virtual-list",head:!0,anchorMetaName:In,ssr:n}),Ge(()=>{const{defaultScrollIndex:c,defaultScrollKey:w}=e;c!=null?D({index:c}):w!=null&&D({key:w})});let o=!1,l=!1;rn(()=>{if(o=!1,!l){l=!0;return}D({top:T.value,left:h.value})}),an(()=>{o=!0,l||(l=!0)});const i=xe(()=>{if(e.renderCol==null&&e.renderItemWithCols==null||e.columns.length===0)return;let c=0;return e.columns.forEach(w=>{c+=w.width}),c}),d=P(()=>{const c=new Map,{keyField:w}=e;return e.items.forEach(($,A)=>{c.set($[w],A)}),c}),{scrollLeftRef:h,listWidthRef:r}=Hn({columnsRef:J(e,"columns"),renderColRef:J(e,"renderCol"),renderItemWithColsRef:J(e,"renderItemWithCols")}),m=z(null),p=z(void 0),C=new Map,x=P(()=>{const{items:c,itemSize:w,keyField:$}=e,A=new Mt(c.length,w);return c.forEach((j,G)=>{const L=j[$],K=C.get(L);K!==void 0&&A.add(G,K)}),A}),k=z(0),T=z(0),b=xe(()=>Math.max(x.value.getBound(T.value-Ne(e.paddingTop))-1,0)),E=P(()=>{const{value:c}=p;if(c===void 0)return[];const{items:w,itemSize:$}=e,A=b.value,j=Math.min(A+Math.ceil(c/$+1),w.length-1),G=[];for(let L=A;L<=j;++L)G.push(w[L]);return G}),D=(c,w)=>{if(typeof c=="number"){H(c,w,"auto");return}const{left:$,top:A,index:j,key:G,position:L,behavior:K,debounce:U=!0}=c;if($!==void 0||A!==void 0)H($,A,K);else if(j!==void 0)N(j,K,U);else if(G!==void 0){const ee=d.value.get(G);ee!==void 0&&N(ee,K,U)}else L==="bottom"?H(0,Number.MAX_SAFE_INTEGER,K):L==="top"&&H(0,0,K)};let M,R=null;function N(c,w,$){const{value:A}=x,j=A.sum(c)+Ne(e.paddingTop);if(!$)m.value.scrollTo({left:0,top:j,behavior:w});else{M=c,R!==null&&window.clearTimeout(R),R=window.setTimeout(()=>{M=void 0,R=null},16);const{scrollTop:G,offsetHeight:L}=m.value;if(j>G){const K=A.get(c);j+K<=G+L||m.value.scrollTo({left:0,top:j+K-L,behavior:w})}else m.value.scrollTo({left:0,top:j,behavior:w})}}function H(c,w,$){m.value.scrollTo({left:c,top:w,behavior:$})}function V(c,w){var $,A,j;if(o||e.ignoreItemResize||te(w.target))return;const{value:G}=x,L=d.value.get(c),K=G.get(L),U=(j=(A=($=w.borderBoxSize)===null||$===void 0?void 0:$[0])===null||A===void 0?void 0:A.blockSize)!==null&&j!==void 0?j:w.contentRect.height;if(U===K)return;U-e.itemSize===0?C.delete(c):C.set(c,U-e.itemSize);const le=U-K;if(le===0)return;G.add(L,le);const a=m.value;if(a!=null){if(M===void 0){const v=G.sum(L);a.scrollTop>v&&a.scrollBy(0,le)}else if(L<M)a.scrollBy(0,le);else if(L===M){const v=G.sum(L);U+v>a.scrollTop+a.offsetHeight&&a.scrollBy(0,le)}Z()}k.value++}const B=!Wn();let ne=!1;function oe(c){var w;(w=e.onScroll)===null||w===void 0||w.call(e,c),(!B||!ne)&&Z()}function he(c){var w;if((w=e.onWheel)===null||w===void 0||w.call(e,c),B){const $=m.value;if($!=null){if(c.deltaX===0&&($.scrollTop===0&&c.deltaY<=0||$.scrollTop+$.offsetHeight>=$.scrollHeight&&c.deltaY>=0))return;c.preventDefault(),$.scrollTop+=c.deltaY/yt(),$.scrollLeft+=c.deltaX/yt(),Z(),ne=!0,kn(()=>{ne=!1})}}}function be(c){if(o||te(c.target))return;if(e.renderCol==null&&e.renderItemWithCols==null){if(c.contentRect.height===p.value)return}else if(c.contentRect.height===p.value&&c.contentRect.width===r.value)return;p.value=c.contentRect.height,r.value=c.contentRect.width;const{onResize:w}=e;w!==void 0&&w(c)}function Z(){const{value:c}=m;c!=null&&(T.value=c.scrollTop,h.value=c.scrollLeft)}function te(c){let w=c;for(;w!==null;){if(w.style.display==="none")return!0;w=w.parentElement}return!1}return{listHeight:p,listStyle:{overflow:"auto"},keyToIndex:d,itemsStyle:P(()=>{const{itemResizable:c}=e,w=_e(x.value.sum());return k.value,[e.itemsStyle,{boxSizing:"content-box",width:_e(i.value),height:c?"":w,minHeight:c?w:"",paddingTop:_e(e.paddingTop),paddingBottom:_e(e.paddingBottom)}]}),visibleItemsStyle:P(()=>(k.value,{transform:`translateY(${_e(x.value.sum(b.value))})`})),viewportItems:E,listElRef:m,itemsElRef:z(null),scrollTo:D,handleListResize:be,handleListScroll:oe,handleListWheel:he,handleItemResize:V}},render(){const{itemResizable:e,keyField:n,keyToIndex:o,visibleItemsTag:l}=this;return u(ht,{onResize:this.handleListResize},{default:()=>{var i,d;return u("div",ln(this.$attrs,{class:["v-vl",this.showScrollbar&&"v-vl--show-scrollbar"],onScroll:this.handleListScroll,onWheel:this.handleListWheel,ref:"listElRef"}),[this.items.length!==0?u("div",{ref:"itemsElRef",class:"v-vl-items",style:this.itemsStyle},[u(l,Object.assign({class:"v-vl-visible-items",style:this.visibleItemsStyle},this.visibleItemsProps),{default:()=>{const{renderCol:h,renderItemWithCols:r}=this;return this.viewportItems.map(m=>{const p=m[n],C=o.get(p),x=h!=null?u(xt,{index:C,item:m}):void 0,k=r!=null?u(xt,{index:C,item:m}):void 0,T=this.$slots.default({item:m,renderedCols:x,renderedItemWithCols:k,index:C})[0];return e?u(ht,{key:p,onResize:b=>this.handleItemResize(p,b)},{default:()=>T}):(T.key=p,T)})}})]):(d=(i=this.$slots).empty)===null||d===void 0?void 0:d.call(i)])}})}});function It(e,n){n&&(Ge(()=>{const{value:o}=e;o&&et.registerHandler(o,n)}),Ce(e,(o,l)=>{l&&et.unregisterHandler(l)},{deep:!1}),Rt(()=>{const{value:o}=e;o&&et.unregisterHandler(o)}))}function Gn(e,n="default",o=[]){const i=e.$slots[n];return i===void 0?o:i()}function lt(e){const n=e.filter(o=>o!==void 0);if(n.length!==0)return n.length===1?n[0]:o=>{e.forEach(l=>{l&&l(o)})}}const qn=ae({name:"Checkmark",render(){return u("svg",{xmlns:"http://www.w3.org/2000/svg",viewBox:"0 0 16 16"},u("g",{fill:"none"},u("path",{d:"M14.046 3.486a.75.75 0 0 1-.032 1.06l-7.93 7.474a.85.85 0 0 1-1.188-.022l-2.68-2.72a.75.75 0 1 1 1.068-1.053l2.234 2.267l7.468-7.038a.75.75 0 0 1 1.06.032z",fill:"currentColor"})))}}),Xn=ae({props:{onFocus:Function,onBlur:Function},setup(e){return()=>u("div",{style:"width: 0; height: 0",tabindex:0,onFocus:e.onFocus,onBlur:e.onBlur})}}),Ct=ae({name:"NBaseSelectGroupHeader",props:{clsPrefix:{type:String,required:!0},tmNode:{type:Object,required:!0}},setup(){const{renderLabelRef:e,renderOptionRef:n,labelFieldRef:o,nodePropsRef:l}=ut(ft);return{labelField:o,nodeProps:l,renderLabel:e,renderOption:n}},render(){const{clsPrefix:e,renderLabel:n,renderOption:o,nodeProps:l,tmNode:{rawNode:i}}=this,d=l==null?void 0:l(i),h=n?n(i,!1):Fe(i[this.labelField],i,!1),r=u("div",Object.assign({},d,{class:[`${e}-base-select-group-header`,d==null?void 0:d.class]}),h);return i.render?i.render({node:r,option:i}):o?o({node:r,option:i,selected:!1}):r}});function Yn(e,n){return u(Tt,{name:"fade-in-scale-up-transition"},{default:()=>e?u(dn,{clsPrefix:n,class:`${n}-base-select-option__check`},{default:()=>u(qn)}):null})}const St=ae({name:"NBaseSelectOption",props:{clsPrefix:{type:String,required:!0},tmNode:{type:Object,required:!0}},setup(e){const{valueRef:n,pendingTmNodeRef:o,multipleRef:l,valueSetRef:i,renderLabelRef:d,renderOptionRef:h,labelFieldRef:r,valueFieldRef:m,showCheckmarkRef:p,nodePropsRef:C,handleOptionClick:x,handleOptionMouseEnter:k}=ut(ft),T=xe(()=>{const{value:M}=o;return M?e.tmNode.key===M.key:!1});function b(M){const{tmNode:R}=e;R.disabled||x(M,R)}function E(M){const{tmNode:R}=e;R.disabled||k(M,R)}function D(M){const{tmNode:R}=e,{value:N}=T;R.disabled||N||k(M,R)}return{multiple:l,isGrouped:xe(()=>{const{tmNode:M}=e,{parent:R}=M;return R&&R.rawNode.type==="group"}),showCheckmark:p,nodeProps:C,isPending:T,isSelected:xe(()=>{const{value:M}=n,{value:R}=l;if(M===null)return!1;const N=e.tmNode.rawNode[m.value];if(R){const{value:H}=i;return H.has(N)}else return M===N}),labelField:r,renderLabel:d,renderOption:h,handleMouseMove:D,handleMouseEnter:E,handleClick:b}},render(){const{clsPrefix:e,tmNode:{rawNode:n},isSelected:o,isPending:l,isGrouped:i,showCheckmark:d,nodeProps:h,renderOption:r,renderLabel:m,handleClick:p,handleMouseEnter:C,handleMouseMove:x}=this,k=Yn(o,e),T=m?[m(n,o),d&&k]:[Fe(n[this.labelField],n,o),d&&k],b=h==null?void 0:h(n),E=u("div",Object.assign({},b,{class:[`${e}-base-select-option`,n.class,b==null?void 0:b.class,{[`${e}-base-select-option--disabled`]:n.disabled,[`${e}-base-select-option--selected`]:o,[`${e}-base-select-option--grouped`]:i,[`${e}-base-select-option--pending`]:l,[`${e}-base-select-option--show-checkmark`]:d}],style:[(b==null?void 0:b.style)||"",n.style||""],onClick:lt([p,b==null?void 0:b.onClick]),onMouseenter:lt([C,b==null?void 0:b.onMouseenter]),onMousemove:lt([x,b==null?void 0:b.onMousemove])}),u("div",{class:`${e}-base-select-option__content`},T));return n.render?n.render({node:E,option:n,selected:o}):r?r({node:E,option:n,selected:o}):E}}),Jn=_("base-select-menu",`
 line-height: 1.5;
 outline: none;
 z-index: 0;
 position: relative;
 border-radius: var(--n-border-radius);
 transition:
 background-color .3s var(--n-bezier),
 box-shadow .3s var(--n-bezier);
 background-color: var(--n-color);
`,[_("scrollbar",`
 max-height: var(--n-height);
 `),_("virtual-list",`
 max-height: var(--n-height);
 `),_("base-select-option",`
 min-height: var(--n-option-height);
 font-size: var(--n-option-font-size);
 display: flex;
 align-items: center;
 `,[W("content",`
 z-index: 1;
 white-space: nowrap;
 text-overflow: ellipsis;
 overflow: hidden;
 `)]),_("base-select-group-header",`
 min-height: var(--n-option-height);
 font-size: .93em;
 display: flex;
 align-items: center;
 `),_("base-select-menu-option-wrapper",`
 position: relative;
 width: 100%;
 `),W("loading, empty",`
 display: flex;
 padding: 12px 32px;
 flex: 1;
 justify-content: center;
 `),W("loading",`
 color: var(--n-loading-color);
 font-size: var(--n-loading-size);
 `),W("header",`
 padding: 8px var(--n-option-padding-left);
 font-size: var(--n-option-font-size);
 transition: 
 color .3s var(--n-bezier),
 border-color .3s var(--n-bezier);
 border-bottom: 1px solid var(--n-action-divider-color);
 color: var(--n-action-text-color);
 `),W("action",`
 padding: 8px var(--n-option-padding-left);
 font-size: var(--n-option-font-size);
 transition: 
 color .3s var(--n-bezier),
 border-color .3s var(--n-bezier);
 border-top: 1px solid var(--n-action-divider-color);
 color: var(--n-action-text-color);
 `),_("base-select-group-header",`
 position: relative;
 cursor: default;
 padding: var(--n-option-padding);
 color: var(--n-group-header-text-color);
 `),_("base-select-option",`
 cursor: pointer;
 position: relative;
 padding: var(--n-option-padding);
 transition:
 color .3s var(--n-bezier),
 opacity .3s var(--n-bezier);
 box-sizing: border-box;
 color: var(--n-option-text-color);
 opacity: 1;
 `,[Q("show-checkmark",`
 padding-right: calc(var(--n-option-padding-right) + 20px);
 `),ce("&::before",`
 content: "";
 position: absolute;
 left: 4px;
 right: 4px;
 top: 0;
 bottom: 0;
 border-radius: var(--n-border-radius);
 transition: background-color .3s var(--n-bezier);
 `),ce("&:active",`
 color: var(--n-option-text-color-pressed);
 `),Q("grouped",`
 padding-left: calc(var(--n-option-padding-left) * 1.5);
 `),Q("pending",[ce("&::before",`
 background-color: var(--n-option-color-pending);
 `)]),Q("selected",`
 color: var(--n-option-text-color-active);
 `,[ce("&::before",`
 background-color: var(--n-option-color-active);
 `),Q("pending",[ce("&::before",`
 background-color: var(--n-option-color-active-pending);
 `)])]),Q("disabled",`
 cursor: not-allowed;
 `,[st("selected",`
 color: var(--n-option-text-color-disabled);
 `),Q("selected",`
 opacity: var(--n-option-opacity-disabled);
 `)]),W("check",`
 font-size: 16px;
 position: absolute;
 right: calc(var(--n-option-padding-right) - 4px);
 top: calc(50% - 7px);
 color: var(--n-option-check-color);
 transition: color .3s var(--n-bezier);
 `,[Ot({enterScale:"0.5"})])])]),Qn=ae({name:"InternalSelectMenu",props:Object.assign(Object.assign({},fe.props),{clsPrefix:{type:String,required:!0},scrollable:{type:Boolean,default:!0},treeMate:{type:Object,required:!0},multiple:Boolean,size:{type:String,default:"medium"},value:{type:[String,Number,Array],default:null},autoPending:Boolean,virtualScroll:{type:Boolean,default:!0},show:{type:Boolean,default:!0},labelField:{type:String,default:"label"},valueField:{type:String,default:"value"},loading:Boolean,focusable:Boolean,renderLabel:Function,renderOption:Function,nodeProps:Function,showCheckmark:{type:Boolean,default:!0},onMousedown:Function,onScroll:Function,onFocus:Function,onBlur:Function,onKeyup:Function,onKeydown:Function,onTabOut:Function,onMouseenter:Function,onMouseleave:Function,onResize:Function,resetMenuOnOptionsChange:{type:Boolean,default:!0},inlineThemeDisabled:Boolean,scrollbarProps:Object,onToggle:Function}),setup(e){const{mergedClsPrefixRef:n,mergedRtlRef:o,mergedComponentPropsRef:l}=Ae(e),i=ct("InternalSelectMenu",o,n),d=fe("InternalSelectMenu","-internal-select-menu",Jn,hn,e,J(e,"clsPrefix")),h=z(null),r=z(null),m=z(null),p=P(()=>e.treeMate.getFlattenedNodes()),C=P(()=>_n(p.value)),x=z(null);function k(){const{treeMate:a}=e;let v=null;const{value:q}=e;q===null?v=a.getFirstAvailableNode():(e.multiple?v=a.getNode((q||[])[(q||[]).length-1]):v=a.getNode(q),(!v||v.disabled)&&(v=a.getFirstAvailableNode())),A(v||null)}function T(){const{value:a}=x;a&&!e.treeMate.getNode(a.key)&&(x.value=null)}let b;Ce(()=>e.show,a=>{a?b=Ce(()=>e.treeMate,()=>{e.resetMenuOnOptionsChange?(e.autoPending?k():T(),Ft(j)):T()},{immediate:!0}):b==null||b()},{immediate:!0}),Rt(()=>{b==null||b()});const E=P(()=>Ne(d.value.self[ge("optionHeight",e.size)])),D=P(()=>$e(d.value.self[ge("padding",e.size)])),M=P(()=>e.multiple&&Array.isArray(e.value)?new Set(e.value):new Set),R=P(()=>{const a=p.value;return a&&a.length===0}),N=P(()=>{var a,v;return(v=(a=l==null?void 0:l.value)===null||a===void 0?void 0:a.Select)===null||v===void 0?void 0:v.renderEmpty});function H(a){const{onToggle:v}=e;v&&v(a)}function V(a){const{onScroll:v}=e;v&&v(a)}function B(a){var v;(v=m.value)===null||v===void 0||v.sync(),V(a)}function ne(){var a;(a=m.value)===null||a===void 0||a.sync()}function oe(){const{value:a}=x;return a||null}function he(a,v){v.disabled||A(v,!1)}function be(a,v){v.disabled||H(v)}function Z(a){var v;Ee(a,"action")||(v=e.onKeyup)===null||v===void 0||v.call(e,a)}function te(a){var v;Ee(a,"action")||(v=e.onKeydown)===null||v===void 0||v.call(e,a)}function c(a){var v;(v=e.onMousedown)===null||v===void 0||v.call(e,a),!e.focusable&&a.preventDefault()}function w(){const{value:a}=x;a&&A(a.getNext({loop:!0}),!0)}function $(){const{value:a}=x;a&&A(a.getPrev({loop:!0}),!0)}function A(a,v=!1){x.value=a,v&&j()}function j(){var a,v;const q=x.value;if(!q)return;const se=C.value(q.key);se!==null&&(e.virtualScroll?(a=r.value)===null||a===void 0||a.scrollTo({index:se}):(v=m.value)===null||v===void 0||v.scrollTo({index:se,elSize:E.value}))}function G(a){var v,q;!((v=h.value)===null||v===void 0)&&v.contains(a.target)&&((q=e.onFocus)===null||q===void 0||q.call(e,a))}function L(a){var v,q;!((v=h.value)===null||v===void 0)&&v.contains(a.relatedTarget)||(q=e.onBlur)===null||q===void 0||q.call(e,a)}at(ft,{handleOptionMouseEnter:he,handleOptionClick:be,valueSetRef:M,pendingTmNodeRef:x,nodePropsRef:J(e,"nodeProps"),showCheckmarkRef:J(e,"showCheckmark"),multipleRef:J(e,"multiple"),valueRef:J(e,"value"),renderLabelRef:J(e,"renderLabel"),renderOptionRef:J(e,"renderOption"),labelFieldRef:J(e,"labelField"),valueFieldRef:J(e,"valueField")}),at($n,h),Ge(()=>{const{value:a}=m;a&&a.sync()});const K=P(()=>{const{size:a}=e,{common:{cubicBezierEaseInOut:v},self:{height:q,borderRadius:se,color:Se,groupHeaderTextColor:ve,actionDividerColor:ie,optionTextColorPressed:Re,optionTextColor:pe,optionTextColorDisabled:ze,optionTextColorActive:Me,optionOpacityDisabled:Pe,optionCheckColor:we,actionTextColor:ye,optionColorPending:Ie,optionColorActive:ke,loadingColor:Be,loadingSize:Te,optionColorActivePending:Oe,[ge("optionFontSize",a)]:re,[ge("optionHeight",a)]:s,[ge("optionPadding",a)]:g}}=d.value;return{"--n-height":q,"--n-action-divider-color":ie,"--n-action-text-color":ye,"--n-bezier":v,"--n-border-radius":se,"--n-color":Se,"--n-option-font-size":re,"--n-group-header-text-color":ve,"--n-option-check-color":we,"--n-option-color-pending":Ie,"--n-option-color-active":ke,"--n-option-color-active-pending":Oe,"--n-option-height":s,"--n-option-opacity-disabled":Pe,"--n-option-text-color":pe,"--n-option-text-color-active":Me,"--n-option-text-color-disabled":ze,"--n-option-text-color-pressed":Re,"--n-option-padding":g,"--n-option-padding-left":$e(g,"left"),"--n-option-padding-right":$e(g,"right"),"--n-loading-color":Be,"--n-loading-size":Te}}),{inlineThemeDisabled:U}=e,ee=U?qe("internal-select-menu",P(()=>e.size[0]),K,e):void 0,le={selfRef:h,next:w,prev:$,getPendingTmNode:oe};return It(h,e.onResize),Object.assign({mergedTheme:d,mergedClsPrefix:n,rtlEnabled:i,virtualListRef:r,scrollbarRef:m,itemSize:E,padding:D,flattenedNodes:p,empty:R,mergedRenderEmpty:N,virtualListContainer(){const{value:a}=r;return a==null?void 0:a.listElRef},virtualListContent(){const{value:a}=r;return a==null?void 0:a.itemsElRef},doScroll:V,handleFocusin:G,handleFocusout:L,handleKeyUp:Z,handleKeyDown:te,handleMouseDown:c,handleVirtualListResize:ne,handleVirtualListScroll:B,cssVars:U?void 0:K,themeClass:ee==null?void 0:ee.themeClass,onRender:ee==null?void 0:ee.onRender},le)},render(){const{$slots:e,virtualScroll:n,clsPrefix:o,mergedTheme:l,themeClass:i,onRender:d}=this;return d==null||d(),u("div",{ref:"selfRef",tabindex:this.focusable?0:-1,class:[`${o}-base-select-menu`,`${o}-base-select-menu--${this.size}-size`,this.rtlEnabled&&`${o}-base-select-menu--rtl`,i,this.multiple&&`${o}-base-select-menu--multiple`],style:this.cssVars,onFocusin:this.handleFocusin,onFocusout:this.handleFocusout,onKeyup:this.handleKeyUp,onKeydown:this.handleKeyDown,onMousedown:this.handleMouseDown,onMouseenter:this.onMouseenter,onMouseleave:this.onMouseleave},vt(e.header,h=>h&&u("div",{class:`${o}-base-select-menu__header`,"data-header":!0,key:"header"},h)),this.loading?u("div",{class:`${o}-base-select-menu__loading`},u(un,{clsPrefix:o,strokeWidth:20})):this.empty?u("div",{class:`${o}-base-select-menu__empty`,"data-empty":!0},fn(e.empty,()=>{var h;return[((h=this.mergedRenderEmpty)===null||h===void 0?void 0:h.call(this))||u(Bn,{theme:l.peers.Empty,themeOverrides:l.peerOverrides.Empty,size:this.size})]})):u(cn,Object.assign({ref:"scrollbarRef",theme:l.peers.Scrollbar,themeOverrides:l.peerOverrides.Scrollbar,scrollable:this.scrollable,container:n?this.virtualListContainer:void 0,content:n?this.virtualListContent:void 0,onScroll:n?void 0:this.doScroll},this.scrollbarProps),{default:()=>n?u(Un,{ref:"virtualListRef",class:`${o}-virtual-list`,items:this.flattenedNodes,itemSize:this.itemSize,showScrollbar:!1,paddingTop:this.padding.top,paddingBottom:this.padding.bottom,onResize:this.handleVirtualListResize,onScroll:this.handleVirtualListScroll,itemResizable:!0},{default:({item:h})=>h.isGroup?u(Ct,{key:h.key,clsPrefix:o,tmNode:h}):h.ignored?null:u(St,{clsPrefix:o,key:h.key,tmNode:h})}):u("div",{class:`${o}-base-select-menu-option-wrapper`,style:{paddingTop:this.padding.top,paddingBottom:this.padding.bottom}},this.flattenedNodes.map(h=>h.isGroup?u(Ct,{key:h.key,clsPrefix:o,tmNode:h}):u(St,{clsPrefix:o,key:h.key,tmNode:h})))}),vt(e.action,h=>h&&[u("div",{class:`${o}-base-select-menu__action`,"data-action":!0,key:"action"},h),u(Xn,{onFocus:this.onTabOut,key:"focus-detector"})]))}}),Zn=ce([_("base-selection",`
 --n-padding-single: var(--n-padding-single-top) var(--n-padding-single-right) var(--n-padding-single-bottom) var(--n-padding-single-left);
 --n-padding-multiple: var(--n-padding-multiple-top) var(--n-padding-multiple-right) var(--n-padding-multiple-bottom) var(--n-padding-multiple-left);
 position: relative;
 z-index: auto;
 box-shadow: none;
 width: 100%;
 max-width: 100%;
 display: inline-block;
 vertical-align: bottom;
 border-radius: var(--n-border-radius);
 min-height: var(--n-height);
 line-height: 1.5;
 font-size: var(--n-font-size);
 `,[_("base-loading",`
 color: var(--n-loading-color);
 `),_("base-selection-tags","min-height: var(--n-height);"),W("border, state-border",`
 position: absolute;
 left: 0;
 right: 0;
 top: 0;
 bottom: 0;
 pointer-events: none;
 border: var(--n-border);
 border-radius: inherit;
 transition:
 box-shadow .3s var(--n-bezier),
 border-color .3s var(--n-bezier);
 `),W("state-border",`
 z-index: 1;
 border-color: #0000;
 `),_("base-suffix",`
 cursor: pointer;
 position: absolute;
 top: 50%;
 transform: translateY(-50%);
 right: 10px;
 `,[W("arrow",`
 font-size: var(--n-arrow-size);
 color: var(--n-arrow-color);
 transition: color .3s var(--n-bezier);
 `)]),_("base-selection-overlay",`
 display: flex;
 align-items: center;
 white-space: nowrap;
 pointer-events: none;
 position: absolute;
 top: 0;
 right: 0;
 bottom: 0;
 left: 0;
 padding: var(--n-padding-single);
 transition: color .3s var(--n-bezier);
 `,[W("wrapper",`
 flex-basis: 0;
 flex-grow: 1;
 overflow: hidden;
 text-overflow: ellipsis;
 `)]),_("base-selection-placeholder",`
 color: var(--n-placeholder-color);
 `,[W("inner",`
 max-width: 100%;
 overflow: hidden;
 `)]),_("base-selection-tags",`
 cursor: pointer;
 outline: none;
 box-sizing: border-box;
 position: relative;
 z-index: auto;
 display: flex;
 padding: var(--n-padding-multiple);
 flex-wrap: wrap;
 align-items: center;
 width: 100%;
 vertical-align: bottom;
 background-color: var(--n-color);
 border-radius: inherit;
 transition:
 color .3s var(--n-bezier),
 box-shadow .3s var(--n-bezier),
 background-color .3s var(--n-bezier);
 `),_("base-selection-label",`
 height: var(--n-height);
 display: inline-flex;
 width: 100%;
 vertical-align: bottom;
 cursor: pointer;
 outline: none;
 z-index: auto;
 box-sizing: border-box;
 position: relative;
 transition:
 color .3s var(--n-bezier),
 box-shadow .3s var(--n-bezier),
 background-color .3s var(--n-bezier);
 border-radius: inherit;
 background-color: var(--n-color);
 align-items: center;
 `,[_("base-selection-input",`
 font-size: inherit;
 line-height: inherit;
 outline: none;
 cursor: pointer;
 box-sizing: border-box;
 border:none;
 width: 100%;
 padding: var(--n-padding-single);
 background-color: #0000;
 color: var(--n-text-color);
 transition: color .3s var(--n-bezier);
 caret-color: var(--n-caret-color);
 `,[W("content",`
 text-overflow: ellipsis;
 overflow: hidden;
 white-space: nowrap; 
 `)]),W("render-label",`
 color: var(--n-text-color);
 `)]),st("disabled",[ce("&:hover",[W("state-border",`
 box-shadow: var(--n-box-shadow-hover);
 border: var(--n-border-hover);
 `)]),Q("focus",[W("state-border",`
 box-shadow: var(--n-box-shadow-focus);
 border: var(--n-border-focus);
 `)]),Q("active",[W("state-border",`
 box-shadow: var(--n-box-shadow-active);
 border: var(--n-border-active);
 `),_("base-selection-label","background-color: var(--n-color-active);"),_("base-selection-tags","background-color: var(--n-color-active);")])]),Q("disabled","cursor: not-allowed;",[W("arrow",`
 color: var(--n-arrow-color-disabled);
 `),_("base-selection-label",`
 cursor: not-allowed;
 background-color: var(--n-color-disabled);
 `,[_("base-selection-input",`
 cursor: not-allowed;
 color: var(--n-text-color-disabled);
 `),W("render-label",`
 color: var(--n-text-color-disabled);
 `)]),_("base-selection-tags",`
 cursor: not-allowed;
 background-color: var(--n-color-disabled);
 `),_("base-selection-placeholder",`
 cursor: not-allowed;
 color: var(--n-placeholder-color-disabled);
 `)]),_("base-selection-input-tag",`
 height: calc(var(--n-height) - 6px);
 line-height: calc(var(--n-height) - 6px);
 outline: none;
 display: none;
 position: relative;
 margin-bottom: 3px;
 max-width: 100%;
 vertical-align: bottom;
 `,[W("input",`
 font-size: inherit;
 font-family: inherit;
 min-width: 1px;
 padding: 0;
 background-color: #0000;
 outline: none;
 border: none;
 max-width: 100%;
 overflow: hidden;
 width: 1em;
 line-height: inherit;
 cursor: pointer;
 color: var(--n-text-color);
 caret-color: var(--n-caret-color);
 `),W("mirror",`
 position: absolute;
 left: 0;
 top: 0;
 white-space: pre;
 visibility: hidden;
 user-select: none;
 -webkit-user-select: none;
 opacity: 0;
 `)]),["warning","error"].map(e=>Q(`${e}-status`,[W("state-border",`border: var(--n-border-${e});`),st("disabled",[ce("&:hover",[W("state-border",`
 box-shadow: var(--n-box-shadow-hover-${e});
 border: var(--n-border-hover-${e});
 `)]),Q("active",[W("state-border",`
 box-shadow: var(--n-box-shadow-active-${e});
 border: var(--n-border-active-${e});
 `),_("base-selection-label",`background-color: var(--n-color-active-${e});`),_("base-selection-tags",`background-color: var(--n-color-active-${e});`)]),Q("focus",[W("state-border",`
 box-shadow: var(--n-box-shadow-focus-${e});
 border: var(--n-border-focus-${e});
 `)])])]))]),_("base-selection-popover",`
 margin-bottom: -3px;
 display: flex;
 flex-wrap: wrap;
 margin-right: -8px;
 `),_("base-selection-tag-wrapper",`
 max-width: 100%;
 display: inline-flex;
 padding: 0 7px 3px 0;
 `,[ce("&:last-child","padding-right: 0;"),_("tag",`
 font-size: 14px;
 max-width: 100%;
 `,[W("content",`
 line-height: 1.25;
 text-overflow: ellipsis;
 overflow: hidden;
 `)])])]),eo=ae({name:"InternalSelection",props:Object.assign(Object.assign({},fe.props),{clsPrefix:{type:String,required:!0},bordered:{type:Boolean,default:void 0},active:Boolean,pattern:{type:String,default:""},placeholder:String,selectedOption:{type:Object,default:null},selectedOptions:{type:Array,default:null},labelField:{type:String,default:"label"},valueField:{type:String,default:"value"},multiple:Boolean,filterable:Boolean,clearable:Boolean,disabled:Boolean,size:{type:String,default:"medium"},loading:Boolean,autofocus:Boolean,showArrow:{type:Boolean,default:!0},inputProps:Object,focused:Boolean,renderTag:Function,onKeydown:Function,onClick:Function,onBlur:Function,onFocus:Function,onDeleteOption:Function,maxTagCount:[String,Number],ellipsisTagPopoverProps:Object,onClear:Function,onPatternInput:Function,onPatternFocus:Function,onPatternBlur:Function,renderLabel:Function,status:String,inlineThemeDisabled:Boolean,ignoreComposition:{type:Boolean,default:!0},onResize:Function}),setup(e){const{mergedClsPrefixRef:n,mergedRtlRef:o}=Ae(e),l=ct("InternalSelection",o,n),i=z(null),d=z(null),h=z(null),r=z(null),m=z(null),p=z(null),C=z(null),x=z(null),k=z(null),T=z(null),b=z(!1),E=z(!1),D=z(!1),M=fe("InternalSelection","-internal-selection",Zn,pn,e,J(e,"clsPrefix")),R=P(()=>e.clearable&&!e.disabled&&(D.value||e.active)),N=P(()=>e.selectedOption?e.renderTag?e.renderTag({option:e.selectedOption,handleClose:()=>{}}):e.renderLabel?e.renderLabel(e.selectedOption,!0):Fe(e.selectedOption[e.labelField],e.selectedOption,!0):e.placeholder),H=P(()=>{const s=e.selectedOption;if(s)return s[e.labelField]}),V=P(()=>e.multiple?!!(Array.isArray(e.selectedOptions)&&e.selectedOptions.length):e.selectedOption!==null);function B(){var s;const{value:g}=i;if(g){const{value:X}=d;X&&(X.style.width=`${g.offsetWidth}px`,e.maxTagCount!=="responsive"&&((s=k.value)===null||s===void 0||s.sync({showAllItemsBeforeCalculate:!1})))}}function ne(){const{value:s}=T;s&&(s.style.display="none")}function oe(){const{value:s}=T;s&&(s.style.display="inline-block")}Ce(J(e,"active"),s=>{s||ne()}),Ce(J(e,"pattern"),()=>{e.multiple&&Ft(B)});function he(s){const{onFocus:g}=e;g&&g(s)}function be(s){const{onBlur:g}=e;g&&g(s)}function Z(s){const{onDeleteOption:g}=e;g&&g(s)}function te(s){const{onClear:g}=e;g&&g(s)}function c(s){const{onPatternInput:g}=e;g&&g(s)}function w(s){var g;(!s.relatedTarget||!(!((g=h.value)===null||g===void 0)&&g.contains(s.relatedTarget)))&&he(s)}function $(s){var g;!((g=h.value)===null||g===void 0)&&g.contains(s.relatedTarget)||be(s)}function A(s){te(s)}function j(){D.value=!0}function G(){D.value=!1}function L(s){!e.active||!e.filterable||s.target!==d.value&&s.preventDefault()}function K(s){Z(s)}const U=z(!1);function ee(s){if(s.key==="Backspace"&&!U.value&&!e.pattern.length){const{selectedOptions:g}=e;g!=null&&g.length&&K(g[g.length-1])}}let le=null;function a(s){const{value:g}=i;if(g){const X=s.target.value;g.textContent=X,B()}e.ignoreComposition&&U.value?le=s:c(s)}function v(){U.value=!0}function q(){U.value=!1,e.ignoreComposition&&c(le),le=null}function se(s){var g;E.value=!0,(g=e.onPatternFocus)===null||g===void 0||g.call(e,s)}function Se(s){var g;E.value=!1,(g=e.onPatternBlur)===null||g===void 0||g.call(e,s)}function ve(){var s,g;if(e.filterable)E.value=!1,(s=p.value)===null||s===void 0||s.blur(),(g=d.value)===null||g===void 0||g.blur();else if(e.multiple){const{value:X}=r;X==null||X.blur()}else{const{value:X}=m;X==null||X.blur()}}function ie(){var s,g,X;e.filterable?(E.value=!1,(s=p.value)===null||s===void 0||s.focus()):e.multiple?(g=r.value)===null||g===void 0||g.focus():(X=m.value)===null||X===void 0||X.focus()}function Re(){const{value:s}=d;s&&(oe(),s.focus())}function pe(){const{value:s}=d;s&&s.blur()}function ze(s){const{value:g}=C;g&&g.setTextContent(`+${s}`)}function Me(){const{value:s}=x;return s}function Pe(){return d.value}let we=null;function ye(){we!==null&&window.clearTimeout(we)}function Ie(){e.active||(ye(),we=window.setTimeout(()=>{V.value&&(b.value=!0)},100))}function ke(){ye()}function Be(s){s||(ye(),b.value=!1)}Ce(V,s=>{s||(b.value=!1)}),Ge(()=>{bn(()=>{const s=p.value;s&&(e.disabled?s.removeAttribute("tabindex"):s.tabIndex=E.value?-1:0)})}),It(h,e.onResize);const{inlineThemeDisabled:Te}=e,Oe=P(()=>{const{size:s}=e,{common:{cubicBezierEaseInOut:g},self:{fontWeight:X,borderRadius:Xe,color:Ye,placeholderColor:Je,textColor:Le,paddingSingle:De,paddingMultiple:Ve,caretColor:Qe,colorDisabled:Ze,textColorDisabled:je,placeholderColorDisabled:me,colorActive:t,boxShadowFocus:f,boxShadowActive:y,boxShadowHover:F,border:S,borderFocus:O,borderHover:I,borderActive:Y,arrowColor:de,arrowColorDisabled:Bt,loadingColor:_t,colorActiveWarning:$t,boxShadowFocusWarning:Et,boxShadowActiveWarning:Nt,boxShadowHoverWarning:At,borderWarning:Lt,borderFocusWarning:Dt,borderHoverWarning:Vt,borderActiveWarning:jt,colorActiveError:Wt,boxShadowFocusError:Ht,boxShadowActiveError:Kt,boxShadowHoverError:Ut,borderError:Gt,borderFocusError:qt,borderHoverError:Xt,borderActiveError:Yt,clearColor:Jt,clearColorHover:Qt,clearColorPressed:Zt,clearSize:en,arrowSize:tn,[ge("height",s)]:nn,[ge("fontSize",s)]:on}}=M.value,We=$e(De),He=$e(Ve);return{"--n-bezier":g,"--n-border":S,"--n-border-active":Y,"--n-border-focus":O,"--n-border-hover":I,"--n-border-radius":Xe,"--n-box-shadow-active":y,"--n-box-shadow-focus":f,"--n-box-shadow-hover":F,"--n-caret-color":Qe,"--n-color":Ye,"--n-color-active":t,"--n-color-disabled":Ze,"--n-font-size":on,"--n-height":nn,"--n-padding-single-top":We.top,"--n-padding-multiple-top":He.top,"--n-padding-single-right":We.right,"--n-padding-multiple-right":He.right,"--n-padding-single-left":We.left,"--n-padding-multiple-left":He.left,"--n-padding-single-bottom":We.bottom,"--n-padding-multiple-bottom":He.bottom,"--n-placeholder-color":Je,"--n-placeholder-color-disabled":me,"--n-text-color":Le,"--n-text-color-disabled":je,"--n-arrow-color":de,"--n-arrow-color-disabled":Bt,"--n-loading-color":_t,"--n-color-active-warning":$t,"--n-box-shadow-focus-warning":Et,"--n-box-shadow-active-warning":Nt,"--n-box-shadow-hover-warning":At,"--n-border-warning":Lt,"--n-border-focus-warning":Dt,"--n-border-hover-warning":Vt,"--n-border-active-warning":jt,"--n-color-active-error":Wt,"--n-box-shadow-focus-error":Ht,"--n-box-shadow-active-error":Kt,"--n-box-shadow-hover-error":Ut,"--n-border-error":Gt,"--n-border-focus-error":qt,"--n-border-hover-error":Xt,"--n-border-active-error":Yt,"--n-clear-size":en,"--n-clear-color":Jt,"--n-clear-color-hover":Qt,"--n-clear-color-pressed":Zt,"--n-arrow-size":tn,"--n-font-weight":X}}),re=Te?qe("internal-selection",P(()=>e.size[0]),Oe,e):void 0;return{mergedTheme:M,mergedClearable:R,mergedClsPrefix:n,rtlEnabled:l,patternInputFocused:E,filterablePlaceholder:N,label:H,selected:V,showTagsPanel:b,isComposing:U,counterRef:C,counterWrapperRef:x,patternInputMirrorRef:i,patternInputRef:d,selfRef:h,multipleElRef:r,singleElRef:m,patternInputWrapperRef:p,overflowRef:k,inputTagElRef:T,handleMouseDown:L,handleFocusin:w,handleClear:A,handleMouseEnter:j,handleMouseLeave:G,handleDeleteOption:K,handlePatternKeyDown:ee,handlePatternInputInput:a,handlePatternInputBlur:Se,handlePatternInputFocus:se,handleMouseEnterCounter:Ie,handleMouseLeaveCounter:ke,handleFocusout:$,handleCompositionEnd:q,handleCompositionStart:v,onPopoverUpdateShow:Be,focus:ie,focusInput:Re,blur:ve,blurInput:pe,updateCounter:ze,getCounter:Me,getTail:Pe,renderLabel:e.renderLabel,cssVars:Te?void 0:Oe,themeClass:re==null?void 0:re.themeClass,onRender:re==null?void 0:re.onRender}},render(){const{status:e,multiple:n,size:o,disabled:l,filterable:i,maxTagCount:d,bordered:h,clsPrefix:r,ellipsisTagPopoverProps:m,onRender:p,renderTag:C,renderLabel:x}=this;p==null||p();const k=d==="responsive",T=typeof d=="number",b=k||T,E=u(vn,null,{default:()=>u(Vn,{clsPrefix:r,loading:this.loading,showArrow:this.showArrow,showClear:this.mergedClearable&&this.selected,onClear:this.handleClear},{default:()=>{var M,R;return(R=(M=this.$slots).arrow)===null||R===void 0?void 0:R.call(M)}})});let D;if(n){const{labelField:M}=this,R=c=>u("div",{class:`${r}-base-selection-tag-wrapper`,key:c.value},C?C({option:c,handleClose:()=>{this.handleDeleteOption(c)}}):u(nt,{size:o,closable:!c.disabled,disabled:l,onClose:()=>{this.handleDeleteOption(c)},internalCloseIsButtonTag:!1,internalCloseFocusable:!1},{default:()=>x?x(c,!0):Fe(c[M],c,!0)})),N=()=>(T?this.selectedOptions.slice(0,d):this.selectedOptions).map(R),H=i?u("div",{class:`${r}-base-selection-input-tag`,ref:"inputTagElRef",key:"__input-tag__"},u("input",Object.assign({},this.inputProps,{ref:"patternInputRef",tabindex:-1,disabled:l,value:this.pattern,autofocus:this.autofocus,class:`${r}-base-selection-input-tag__input`,onBlur:this.handlePatternInputBlur,onFocus:this.handlePatternInputFocus,onKeydown:this.handlePatternKeyDown,onInput:this.handlePatternInputInput,onCompositionstart:this.handleCompositionStart,onCompositionend:this.handleCompositionEnd})),u("span",{ref:"patternInputMirrorRef",class:`${r}-base-selection-input-tag__mirror`},this.pattern)):null,V=k?()=>u("div",{class:`${r}-base-selection-tag-wrapper`,ref:"counterWrapperRef"},u(nt,{size:o,ref:"counterRef",onMouseenter:this.handleMouseEnterCounter,onMouseleave:this.handleMouseLeaveCounter,disabled:l})):void 0;let B;if(T){const c=this.selectedOptions.length-d;c>0&&(B=u("div",{class:`${r}-base-selection-tag-wrapper`,key:"__counter__"},u(nt,{size:o,ref:"counterRef",onMouseenter:this.handleMouseEnterCounter,disabled:l},{default:()=>`+${c}`})))}const ne=k?i?u(bt,{ref:"overflowRef",updateCounter:this.updateCounter,getCounter:this.getCounter,getTail:this.getTail,style:{width:"100%",display:"flex",overflow:"hidden"}},{default:N,counter:V,tail:()=>H}):u(bt,{ref:"overflowRef",updateCounter:this.updateCounter,getCounter:this.getCounter,style:{width:"100%",display:"flex",overflow:"hidden"}},{default:N,counter:V}):T&&B?N().concat(B):N(),oe=b?()=>u("div",{class:`${r}-base-selection-popover`},k?N():this.selectedOptions.map(R)):void 0,he=b?Object.assign({show:this.showTagsPanel,trigger:"hover",overlap:!0,placement:"top",width:"trigger",onUpdateShow:this.onPopoverUpdateShow,theme:this.mergedTheme.peers.Popover,themeOverrides:this.mergedTheme.peerOverrides.Popover},m):null,Z=(this.selected?!1:this.active?!this.pattern&&!this.isComposing:!0)?u("div",{class:`${r}-base-selection-placeholder ${r}-base-selection-overlay`},u("div",{class:`${r}-base-selection-placeholder__inner`},this.placeholder)):null,te=i?u("div",{ref:"patternInputWrapperRef",class:`${r}-base-selection-tags`},ne,k?null:H,E):u("div",{ref:"multipleElRef",class:`${r}-base-selection-tags`,tabindex:l?void 0:0},ne,E);D=u(gn,null,b?u(En,Object.assign({},he,{scrollable:!0,style:"max-height: calc(var(--v-target-height) * 6.6);"}),{trigger:()=>te,default:oe}):te,Z)}else if(i){const M=this.pattern||this.isComposing,R=this.active?!M:!this.selected,N=this.active?!1:this.selected;D=u("div",{ref:"patternInputWrapperRef",class:`${r}-base-selection-label`,title:this.patternInputFocused?void 0:pt(this.label)},u("input",Object.assign({},this.inputProps,{ref:"patternInputRef",class:`${r}-base-selection-input`,value:this.active?this.pattern:"",placeholder:"",readonly:l,disabled:l,tabindex:-1,autofocus:this.autofocus,onFocus:this.handlePatternInputFocus,onBlur:this.handlePatternInputBlur,onInput:this.handlePatternInputInput,onCompositionstart:this.handleCompositionStart,onCompositionend:this.handleCompositionEnd})),N?u("div",{class:`${r}-base-selection-label__render-label ${r}-base-selection-overlay`,key:"input"},u("div",{class:`${r}-base-selection-overlay__wrapper`},C?C({option:this.selectedOption,handleClose:()=>{}}):x?x(this.selectedOption,!0):Fe(this.label,this.selectedOption,!0))):null,R?u("div",{class:`${r}-base-selection-placeholder ${r}-base-selection-overlay`,key:"placeholder"},u("div",{class:`${r}-base-selection-overlay__wrapper`},this.filterablePlaceholder)):null,E)}else D=u("div",{ref:"singleElRef",class:`${r}-base-selection-label`,tabindex:this.disabled?void 0:0},this.label!==void 0?u("div",{class:`${r}-base-selection-input`,title:pt(this.label),key:"input"},u("div",{class:`${r}-base-selection-input__content`},C?C({option:this.selectedOption,handleClose:()=>{}}):x?x(this.selectedOption,!0):Fe(this.label,this.selectedOption,!0))):u("div",{class:`${r}-base-selection-placeholder ${r}-base-selection-overlay`,key:"placeholder"},u("div",{class:`${r}-base-selection-placeholder__inner`},this.placeholder)),E);return u("div",{ref:"selfRef",class:[`${r}-base-selection`,this.rtlEnabled&&`${r}-base-selection--rtl`,this.themeClass,e&&`${r}-base-selection--${e}-status`,{[`${r}-base-selection--active`]:this.active,[`${r}-base-selection--selected`]:this.selected||this.active&&this.pattern,[`${r}-base-selection--disabled`]:this.disabled,[`${r}-base-selection--multiple`]:this.multiple,[`${r}-base-selection--focus`]:this.focused}],style:this.cssVars,onClick:this.onClick,onMouseenter:this.handleMouseEnter,onMouseleave:this.handleMouseLeave,onKeydown:this.onKeydown,onFocusin:this.handleFocusin,onFocusout:this.handleFocusout,onMousedown:this.handleMouseDown},D,h?u("div",{class:`${r}-base-selection__border`}):null,h?u("div",{class:`${r}-base-selection__state-border`}):null)}});function Ue(e){return e.type==="group"}function kt(e){return e.type==="ignored"}function it(e,n){try{return!!(1+n.toString().toLowerCase().indexOf(e.trim().toLowerCase()))}catch{return!1}}function to(e,n){return{getIsGroup:Ue,getIgnored:kt,getKey(l){return Ue(l)?l.name||l.key||"key-required":l[e]},getChildren(l){return l[n]}}}function no(e,n,o,l){if(!n)return e;function i(d){if(!Array.isArray(d))return[];const h=[];for(const r of d)if(Ue(r)){const m=i(r[l]);m.length&&h.push(Object.assign({},r,{[l]:m}))}else{if(kt(r))continue;n(o,r)&&h.push(r)}return h}return i(e)}function oo(e,n,o){const l=new Map;return e.forEach(i=>{Ue(i)?i[o].forEach(d=>{l.set(d[n],d)}):l.set(i[n],i)}),l}const lo=ce([_("select",`
 z-index: auto;
 outline: none;
 width: 100%;
 position: relative;
 font-weight: var(--n-font-weight);
 `),_("select-menu",`
 margin: 4px 0;
 box-shadow: var(--n-menu-box-shadow);
 `,[Ot({originalTransition:"background-color .3s var(--n-bezier), box-shadow .3s var(--n-bezier)"})])]),io=Object.assign(Object.assign({},fe.props),{to:dt.propTo,bordered:{type:Boolean,default:void 0},clearable:Boolean,clearCreatedOptionsOnClear:{type:Boolean,default:!0},clearFilterAfterSelect:{type:Boolean,default:!0},options:{type:Array,default:()=>[]},defaultValue:{type:[String,Number,Array],default:null},keyboard:{type:Boolean,default:!0},value:[String,Number,Array],placeholder:String,menuProps:Object,multiple:Boolean,size:String,menuSize:{type:String},filterable:Boolean,disabled:{type:Boolean,default:void 0},remote:Boolean,loading:Boolean,filter:Function,placement:{type:String,default:"bottom-start"},widthMode:{type:String,default:"trigger"},tag:Boolean,onCreate:Function,fallbackOption:{type:[Function,Boolean],default:void 0},show:{type:Boolean,default:void 0},showArrow:{type:Boolean,default:!0},maxTagCount:[Number,String],ellipsisTagPopoverProps:Object,consistentMenuWidth:{type:Boolean,default:!0},virtualScroll:{type:Boolean,default:!0},labelField:{type:String,default:"label"},valueField:{type:String,default:"value"},childrenField:{type:String,default:"children"},renderLabel:Function,renderOption:Function,renderTag:Function,"onUpdate:value":[Function,Array],inputProps:Object,nodeProps:Function,ignoreComposition:{type:Boolean,default:!0},showOnFocus:Boolean,onUpdateValue:[Function,Array],onBlur:[Function,Array],onClear:[Function,Array],onFocus:[Function,Array],onScroll:[Function,Array],onSearch:[Function,Array],onUpdateShow:[Function,Array],"onUpdate:show":[Function,Array],displayDirective:{type:String,default:"show"},resetMenuOnOptionsChange:{type:Boolean,default:!0},status:String,showCheckmark:{type:Boolean,default:!0},scrollbarProps:Object,onChange:[Function,Array],items:Array}),mo=ae({name:"Select",props:io,slots:Object,setup(e){const{mergedClsPrefixRef:n,mergedBorderedRef:o,namespaceRef:l,inlineThemeDisabled:i,mergedComponentPropsRef:d}=Ae(e),h=fe("Select","-select",lo,Cn,e,n),r=z(e.defaultValue),m=J(e,"value"),p=mt(m,r),C=z(!1),x=z(""),k=zt(e,["items","options"]),T=z([]),b=z([]),E=P(()=>b.value.concat(T.value).concat(k.value)),D=P(()=>{const{filter:t}=e;if(t)return t;const{labelField:f,valueField:y}=e;return(F,S)=>{if(!S)return!1;const O=S[f];if(typeof O=="string")return it(F,O);const I=S[y];return typeof I=="string"?it(F,I):typeof I=="number"?it(F,String(I)):!1}}),M=P(()=>{if(e.remote)return k.value;{const{value:t}=E,{value:f}=x;return!f.length||!e.filterable?t:no(t,D.value,f,e.childrenField)}}),R=P(()=>{const{valueField:t,childrenField:f}=e,y=to(t,f);return Dn(M.value,y)}),N=P(()=>oo(E.value,e.valueField,e.childrenField)),H=z(!1),V=mt(J(e,"show"),H),B=z(null),ne=z(null),oe=z(null),{localeRef:he}=jn("Select"),be=P(()=>{var t;return(t=e.placeholder)!==null&&t!==void 0?t:he.value.placeholder}),Z=[],te=z(new Map),c=P(()=>{const{fallbackOption:t}=e;if(t===void 0){const{labelField:f,valueField:y}=e;return F=>({[f]:String(F),[y]:F})}return t===!1?!1:f=>Object.assign(t(f),{value:f})});function w(t){const f=e.remote,{value:y}=te,{value:F}=N,{value:S}=c,O=[];return t.forEach(I=>{if(F.has(I))O.push(F.get(I));else if(f&&y.has(I))O.push(y.get(I));else if(S){const Y=S(I);Y&&O.push(Y)}}),O}const $=P(()=>{if(e.multiple){const{value:t}=p;return Array.isArray(t)?w(t):[]}return null}),A=P(()=>{const{value:t}=p;return!e.multiple&&!Array.isArray(t)?t===null?null:w([t])[0]||null:null}),j=yn(e,{mergedSize:t=>{var f,y;const{size:F}=e;if(F)return F;const{mergedSize:S}=t||{};if(S!=null&&S.value)return S.value;const O=(y=(f=d==null?void 0:d.value)===null||f===void 0?void 0:f.Select)===null||y===void 0?void 0:y.size;return O||"medium"}}),{mergedSizeRef:G,mergedDisabledRef:L,mergedStatusRef:K}=j;function U(t,f){const{onChange:y,"onUpdate:value":F,onUpdateValue:S}=e,{nTriggerFormChange:O,nTriggerFormInput:I}=j;y&&ue(y,t,f),S&&ue(S,t,f),F&&ue(F,t,f),r.value=t,O(),I()}function ee(t){const{onBlur:f}=e,{nTriggerFormBlur:y}=j;f&&ue(f,t),y()}function le(){const{onClear:t}=e;t&&ue(t)}function a(t){const{onFocus:f,showOnFocus:y}=e,{nTriggerFormFocus:F}=j;f&&ue(f,t),F(),y&&ve()}function v(t){const{onSearch:f}=e;f&&ue(f,t)}function q(t){const{onScroll:f}=e;f&&ue(f,t)}function se(){var t;const{remote:f,multiple:y}=e;if(f){const{value:F}=te;if(y){const{valueField:S}=e;(t=$.value)===null||t===void 0||t.forEach(O=>{F.set(O[S],O)})}else{const S=A.value;S&&F.set(S[e.valueField],S)}}}function Se(t){const{onUpdateShow:f,"onUpdate:show":y}=e;f&&ue(f,t),y&&ue(y,t),H.value=t}function ve(){L.value||(Se(!0),H.value=!0,e.filterable&&Ve())}function ie(){Se(!1)}function Re(){x.value="",b.value=Z}const pe=z(!1);function ze(){e.filterable&&(pe.value=!0)}function Me(){e.filterable&&(pe.value=!1,V.value||Re())}function Pe(){L.value||(V.value?e.filterable?Ve():ie():ve())}function we(t){var f,y;!((y=(f=oe.value)===null||f===void 0?void 0:f.selfRef)===null||y===void 0)&&y.contains(t.relatedTarget)||(C.value=!1,ee(t),ie())}function ye(t){a(t),C.value=!0}function Ie(){C.value=!0}function ke(t){var f;!((f=B.value)===null||f===void 0)&&f.$el.contains(t.relatedTarget)||(C.value=!1,ee(t),ie())}function Be(){var t;(t=B.value)===null||t===void 0||t.focus(),ie()}function Te(t){var f;V.value&&(!((f=B.value)===null||f===void 0)&&f.$el.contains(Sn(t))||ie())}function Oe(t){if(!Array.isArray(t))return[];if(c.value)return Array.from(t);{const{remote:f}=e,{value:y}=N;if(f){const{value:F}=te;return t.filter(S=>y.has(S)||F.has(S))}else return t.filter(F=>y.has(F))}}function re(t){s(t.rawNode)}function s(t){if(L.value)return;const{tag:f,remote:y,clearFilterAfterSelect:F,valueField:S}=e;if(f&&!y){const{value:O}=b,I=O[0]||null;if(I){const Y=T.value;Y.length?Y.push(I):T.value=[I],b.value=Z}}if(y&&te.value.set(t[S],t),e.multiple){const O=Oe(p.value),I=O.findIndex(Y=>Y===t[S]);if(~I){if(O.splice(I,1),f&&!y){const Y=g(t[S]);~Y&&(T.value.splice(Y,1),F&&(x.value=""))}}else O.push(t[S]),F&&(x.value="");U(O,w(O))}else{if(f&&!y){const O=g(t[S]);~O?T.value=[T.value[O]]:T.value=Z}De(),ie(),U(t[S],t)}}function g(t){return T.value.findIndex(y=>y[e.valueField]===t)}function X(t){V.value||ve();const{value:f}=t.target;x.value=f;const{tag:y,remote:F}=e;if(v(f),y&&!F){if(!f){b.value=Z;return}const{onCreate:S}=e,O=S?S(f):{[e.labelField]:f,[e.valueField]:f},{valueField:I,labelField:Y}=e;k.value.some(de=>de[I]===O[I]||de[Y]===O[Y])||T.value.some(de=>de[I]===O[I]||de[Y]===O[Y])?b.value=Z:b.value=[O]}}function Xe(t){t.stopPropagation();const{multiple:f,tag:y,remote:F,clearCreatedOptionsOnClear:S}=e;!f&&e.filterable&&ie(),y&&!F&&S&&(T.value=Z),le(),f?U([],[]):U(null,null)}function Ye(t){!Ee(t,"action")&&!Ee(t,"empty")&&!Ee(t,"header")&&t.preventDefault()}function Je(t){q(t)}function Le(t){var f,y,F,S,O;if(!e.keyboard){t.preventDefault();return}switch(t.key){case" ":if(e.filterable)break;t.preventDefault();case"Enter":if(!(!((f=B.value)===null||f===void 0)&&f.isComposing)){if(V.value){const I=(y=oe.value)===null||y===void 0?void 0:y.getPendingTmNode();I?re(I):e.filterable||(ie(),De())}else if(ve(),e.tag&&pe.value){const I=b.value[0];if(I){const Y=I[e.valueField],{value:de}=p;e.multiple&&Array.isArray(de)&&de.includes(Y)||s(I)}}}t.preventDefault();break;case"ArrowUp":if(t.preventDefault(),e.loading)return;V.value&&((F=oe.value)===null||F===void 0||F.prev());break;case"ArrowDown":if(t.preventDefault(),e.loading)return;V.value?(S=oe.value)===null||S===void 0||S.next():ve();break;case"Escape":V.value&&(Rn(t),ie()),(O=B.value)===null||O===void 0||O.focus();break}}function De(){var t;(t=B.value)===null||t===void 0||t.focus()}function Ve(){var t;(t=B.value)===null||t===void 0||t.focusInput()}function Qe(){var t;V.value&&((t=ne.value)===null||t===void 0||t.syncPosition())}se(),Ce(J(e,"options"),se);const Ze={focus:()=>{var t;(t=B.value)===null||t===void 0||t.focus()},focusInput:()=>{var t;(t=B.value)===null||t===void 0||t.focusInput()},blur:()=>{var t;(t=B.value)===null||t===void 0||t.blur()},blurInput:()=>{var t;(t=B.value)===null||t===void 0||t.blurInput()}},je=P(()=>{const{self:{menuBoxShadow:t}}=h.value;return{"--n-menu-box-shadow":t}}),me=i?qe("select",void 0,je,e):void 0;return Object.assign(Object.assign({},Ze),{mergedStatus:K,mergedClsPrefix:n,mergedBordered:o,namespace:l,treeMate:R,isMounted:xn(),triggerRef:B,menuRef:oe,pattern:x,uncontrolledShow:H,mergedShow:V,adjustedTo:dt(e),uncontrolledValue:r,mergedValue:p,followerRef:ne,localizedPlaceholder:be,selectedOption:A,selectedOptions:$,mergedSize:G,mergedDisabled:L,focused:C,activeWithoutMenuOpen:pe,inlineThemeDisabled:i,onTriggerInputFocus:ze,onTriggerInputBlur:Me,handleTriggerOrMenuResize:Qe,handleMenuFocus:Ie,handleMenuBlur:ke,handleMenuTabOut:Be,handleTriggerClick:Pe,handleToggle:re,handleDeleteOption:s,handlePatternInput:X,handleClear:Xe,handleTriggerBlur:we,handleTriggerFocus:ye,handleKeydown:Le,handleMenuAfterLeave:Re,handleMenuClickOutside:Te,handleMenuScroll:Je,handleMenuKeydown:Le,handleMenuMousedown:Ye,mergedTheme:h,cssVars:i?void 0:je,themeClass:me==null?void 0:me.themeClass,onRender:me==null?void 0:me.onRender})},render(){return u("div",{class:`${this.mergedClsPrefix}-select`},u(Nn,null,{default:()=>[u(An,null,{default:()=>u(eo,{ref:"triggerRef",inlineThemeDisabled:this.inlineThemeDisabled,status:this.mergedStatus,inputProps:this.inputProps,clsPrefix:this.mergedClsPrefix,showArrow:this.showArrow,maxTagCount:this.maxTagCount,ellipsisTagPopoverProps:this.ellipsisTagPopoverProps,bordered:this.mergedBordered,active:this.activeWithoutMenuOpen||this.mergedShow,pattern:this.pattern,placeholder:this.localizedPlaceholder,selectedOption:this.selectedOption,selectedOptions:this.selectedOptions,multiple:this.multiple,renderTag:this.renderTag,renderLabel:this.renderLabel,filterable:this.filterable,clearable:this.clearable,disabled:this.mergedDisabled,size:this.mergedSize,theme:this.mergedTheme.peers.InternalSelection,labelField:this.labelField,valueField:this.valueField,themeOverrides:this.mergedTheme.peerOverrides.InternalSelection,loading:this.loading,focused:this.focused,onClick:this.handleTriggerClick,onDeleteOption:this.handleDeleteOption,onPatternInput:this.handlePatternInput,onClear:this.handleClear,onBlur:this.handleTriggerBlur,onFocus:this.handleTriggerFocus,onKeydown:this.handleKeydown,onPatternBlur:this.onTriggerInputBlur,onPatternFocus:this.onTriggerInputFocus,onResize:this.handleTriggerOrMenuResize,ignoreComposition:this.ignoreComposition},{arrow:()=>{var e,n;return[(n=(e=this.$slots).arrow)===null||n===void 0?void 0:n.call(e)]}})}),u(Ln,{ref:"followerRef",show:this.mergedShow,to:this.adjustedTo,teleportDisabled:this.adjustedTo===dt.tdkey,containerClass:this.namespace,width:this.consistentMenuWidth?"target":void 0,minWidth:"target",placement:this.placement},{default:()=>u(Tt,{name:"fade-in-scale-up-transition",appear:this.isMounted,onAfterLeave:this.handleMenuAfterLeave},{default:()=>{var e,n,o;return this.mergedShow||this.displayDirective==="show"?((e=this.onRender)===null||e===void 0||e.call(this),mn(u(Qn,Object.assign({},this.menuProps,{ref:"menuRef",onResize:this.handleTriggerOrMenuResize,inlineThemeDisabled:this.inlineThemeDisabled,virtualScroll:this.consistentMenuWidth&&this.virtualScroll,class:[`${this.mergedClsPrefix}-select-menu`,this.themeClass,(n=this.menuProps)===null||n===void 0?void 0:n.class],clsPrefix:this.mergedClsPrefix,focusable:!0,labelField:this.labelField,valueField:this.valueField,autoPending:!0,nodeProps:this.nodeProps,theme:this.mergedTheme.peers.InternalSelectMenu,themeOverrides:this.mergedTheme.peerOverrides.InternalSelectMenu,treeMate:this.treeMate,multiple:this.multiple,size:this.menuSize,renderOption:this.renderOption,renderLabel:this.renderLabel,value:this.mergedValue,style:[(o=this.menuProps)===null||o===void 0?void 0:o.style,this.cssVars],onToggle:this.handleToggle,onScroll:this.handleMenuScroll,onFocus:this.handleMenuFocus,onBlur:this.handleMenuBlur,onKeydown:this.handleMenuKeydown,onTabOut:this.handleMenuTabOut,onMousedown:this.handleMenuMousedown,show:this.mergedShow,showCheckmark:this.showCheckmark,resetMenuOnOptionsChange:this.resetMenuOnOptionsChange,scrollbarProps:this.scrollbarProps}),{empty:()=>{var l,i;return[(i=(l=this.$slots).empty)===null||i===void 0?void 0:i.call(l)]},header:()=>{var l,i;return[(i=(l=this.$slots).header)===null||i===void 0?void 0:i.call(l)]},action:()=>{var l,i;return[(i=(l=this.$slots).action)===null||i===void 0?void 0:i.call(l)]}}),this.displayDirective==="show"?[[wn,this.mergedShow],[gt,this.handleMenuClickOutside,void 0,{capture:!0}]]:[[gt,this.handleMenuClickOutside,void 0,{capture:!0}]])):null}})})]}))}});function ro(){return Tn}const ao={self:ro};let rt;function so(){if(!On)return!0;if(rt===void 0){const e=document.createElement("div");e.style.display="flex",e.style.flexDirection="column",e.style.rowGap="1px",e.appendChild(document.createElement("div")),e.appendChild(document.createElement("div")),document.body.appendChild(e);const n=e.scrollHeight===1;return document.body.removeChild(e),rt=n}return rt}const uo=Object.assign(Object.assign({},fe.props),{align:String,justify:{type:String,default:"start"},inline:Boolean,vertical:Boolean,reverse:Boolean,size:[String,Number,Array],wrapItem:{type:Boolean,default:!0},itemClass:String,itemStyle:[String,Object],wrap:{type:Boolean,default:!0},internalUseGap:{type:Boolean,default:void 0}}),wo=ae({name:"Space",props:uo,setup(e){const{mergedClsPrefixRef:n,mergedRtlRef:o,mergedComponentPropsRef:l}=Ae(e),i=P(()=>{var r,m;return e.size||((m=(r=l==null?void 0:l.value)===null||r===void 0?void 0:r.Space)===null||m===void 0?void 0:m.size)||"medium"}),d=fe("Space","-space",void 0,ao,e,n),h=ct("Space",o,n);return{useGap:so(),rtlEnabled:h,mergedClsPrefix:n,margin:P(()=>{const r=i.value;if(Array.isArray(r))return{horizontal:r[0],vertical:r[1]};if(typeof r=="number")return{horizontal:r,vertical:r};const{self:{[ge("gap",r)]:m}}=d.value,{row:p,col:C}=Mn(m);return{horizontal:Ne(C),vertical:Ne(p)}})}},render(){const{vertical:e,reverse:n,align:o,inline:l,justify:i,itemClass:d,itemStyle:h,margin:r,wrap:m,mergedClsPrefix:p,rtlEnabled:C,useGap:x,wrapItem:k,internalUseGap:T}=this,b=Fn(Gn(this),!1);if(!b.length)return null;const E=`${r.horizontal}px`,D=`${r.horizontal/2}px`,M=`${r.vertical}px`,R=`${r.vertical/2}px`,N=b.length-1,H=i.startsWith("space-");return u("div",{role:"none",class:[`${p}-space`,C&&`${p}-space--rtl`],style:{display:l?"inline-flex":"flex",flexDirection:e&&!n?"column":e&&n?"column-reverse":!e&&n?"row-reverse":"row",justifyContent:["start","end"].includes(i)?`flex-${i}`:i,flexWrap:!m||e?"nowrap":"wrap",marginTop:x||e?"":`-${R}`,marginBottom:x||e?"":`-${R}`,alignItems:o,gap:x?`${r.vertical}px ${r.horizontal}px`:""}},!k&&(x||T)?b:b.map((V,B)=>V.type===zn?V:u("div",{role:"none",class:d,style:[h,{maxWidth:"100%"},x?"":e?{marginBottom:B!==N?M:""}:C?{marginLeft:H?i==="space-between"&&B===N?"":D:B!==N?E:"",marginRight:H?i==="space-between"&&B===0?"":D:"",paddingTop:R,paddingBottom:R}:{marginRight:H?i==="space-between"&&B===N?"":D:B!==N?E:"",marginLeft:H?i==="space-between"&&B===0?"":D:"",paddingTop:R,paddingBottom:R}]},V)))}}),co=_("text",`
 transition: color .3s var(--n-bezier);
 color: var(--n-text-color);
`,[Q("strong",`
 font-weight: var(--n-font-weight-strong);
 `),Q("italic",{fontStyle:"italic"}),Q("underline",{textDecoration:"underline"}),Q("code",`
 line-height: 1.4;
 display: inline-block;
 font-family: var(--n-font-famliy-mono);
 transition: 
 color .3s var(--n-bezier),
 border-color .3s var(--n-bezier),
 background-color .3s var(--n-bezier);
 box-sizing: border-box;
 padding: .05em .35em 0 .35em;
 border-radius: var(--n-code-border-radius);
 font-size: .9em;
 color: var(--n-code-text-color);
 background-color: var(--n-code-color);
 border: var(--n-code-border);
 `)]),fo=Object.assign(Object.assign({},fe.props),{code:Boolean,type:{type:String,default:"default"},delete:Boolean,strong:Boolean,italic:Boolean,underline:Boolean,depth:[String,Number],tag:String,as:{type:String,validator:()=>!0,default:void 0}}),yo=ae({name:"Text",props:fo,setup(e){const{mergedClsPrefixRef:n,inlineThemeDisabled:o}=Ae(e),l=fe("Typography","-text",co,Pn,e,n),i=P(()=>{const{depth:h,type:r}=e,m=r==="default"?h===void 0?"textColor":`textColor${h}Depth`:ge("textColor",r),{common:{fontWeightStrong:p,fontFamilyMono:C,cubicBezierEaseInOut:x},self:{codeTextColor:k,codeBorderRadius:T,codeColor:b,codeBorder:E,[m]:D}}=l.value;return{"--n-bezier":x,"--n-text-color":D,"--n-font-weight-strong":p,"--n-font-famliy-mono":C,"--n-code-border-radius":T,"--n-code-text-color":k,"--n-code-color":b,"--n-code-border":E}}),d=o?qe("text",P(()=>`${e.type[0]}${e.depth||""}`),i,e):void 0;return{mergedClsPrefix:n,compitableTag:zt(e,["as","tag"]),cssVars:o?void 0:i,themeClass:d==null?void 0:d.themeClass,onRender:d==null?void 0:d.onRender}},render(){var e,n,o;const{mergedClsPrefix:l}=this;(e=this.onRender)===null||e===void 0||e.call(this);const i=[`${l}-text`,this.themeClass,{[`${l}-text--code`]:this.code,[`${l}-text--delete`]:this.delete,[`${l}-text--strong`]:this.strong,[`${l}-text--italic`]:this.italic,[`${l}-text--underline`]:this.underline}],d=(o=(n=this.$slots).default)===null||o===void 0?void 0:o.call(n);return this.code?u("code",{class:i,style:this.cssVars},this.delete?u("del",null,d):d):this.delete?u("del",{class:i,style:this.cssVars},d):u(this.compitableTag||"span",{class:i,style:this.cssVars},d)}});export{wo as N,Un as V,yo as a,mo as b,Qn as c,to as d,Gn as g,lt as m};
