import{d as K,k as a,r as O,l as fe,m as C,n as xe,t as re,p as w,q as zo,s as p,v as wo,x as _,y as x,z as So,T as Io,N as Ke,A as ae,C as Ro,D as ko,E as De,F as Po,V as Ue,G as se,H as G,I as ce,J as ke,K as ye,L as No,M as J,O as To,P as Ye,Q as We,R as Ge,S as Ee,U as $o,W as _o,X as Ao,Y as Oo,Z as Bo,_ as Eo,$ as He,a0 as qe,a1 as Xe,a2 as ie,a3 as Ze,a4 as q,a5 as de,a6 as Ho,a7 as le,a8 as Pe,a9 as Ce,aa as Ne,ab as pe,ac as Mo,ad as Lo,ae as Fo,af as Je,o as W,ag as ze,u as F,ah as jo,w as U,b as N,ai as Qe,aj as Vo,c as Z,ak as eo,al as we,am as Y,g as oo,an as Ko,ao as ue,e as D,ap as Do,f as Me,h as Uo,aq as Yo,ar as Wo,as as oe}from"./index-CrrzYg-U.js";import{s as Go,g as qo}from"./dashboard-CE7SxDew.js";import{_ as to}from"./_plugin-vue_export-helper-DlAUqK2U.js";import{a as Se,u as Xo}from"./auth-DQiNxie4.js";import{C as Zo,N as Jo,a as ro}from"./Dropdown-yKLdvPjR.js";import{t as Qo,g as et,V as ot,c as ge,N as tt,a as rt}from"./Tag-Bwosooua.js";import{u as nt}from"./use-compitable-NwYE7-py.js";import{f as be}from"./get-Cpzh6RY9.js";import{i as lt,o as it}from"./utils-Cof7dQhH.js";import{N as me}from"./Icon-CHxV3kM7.js";const at=K({name:"ChevronDownFilled",render(){return a("svg",{viewBox:"0 0 16 16",fill:"none",xmlns:"http://www.w3.org/2000/svg"},a("path",{d:"M3.20041 5.73966C3.48226 5.43613 3.95681 5.41856 4.26034 5.70041L8 9.22652L11.7397 5.70041C12.0432 5.41856 12.5177 5.43613 12.7996 5.73966C13.0815 6.0432 13.0639 6.51775 12.7603 6.7996L8.51034 10.7996C8.22258 11.0668 7.77743 11.0668 7.48967 10.7996L3.23966 6.7996C2.93613 6.51775 2.91856 6.0432 3.20041 5.73966Z",fill:"currentColor"}))}}),Le=K({name:"SlotMachineNumber",props:{clsPrefix:{type:String,required:!0},value:{type:[Number,String],required:!0},oldOriginalNumber:{type:Number,default:void 0},newOriginalNumber:{type:Number,default:void 0}},setup(e){const o=O(null),t=O(e.value),i=O(e.value),l=O("up"),r=O(!1),c=C(()=>r.value?`${e.clsPrefix}-base-slot-machine-current-number--${l.value}-scroll`:null),u=C(()=>r.value?`${e.clsPrefix}-base-slot-machine-old-number--${l.value}-scroll`:null);fe(re(e,"value"),(h,S)=>{t.value=S,i.value=h,xe(v)});function v(){const h=e.newOriginalNumber,S=e.oldOriginalNumber;S===void 0||h===void 0||(h>S?m("up"):S>h&&m("down"))}function m(h){l.value=h,r.value=!1,xe(()=>{var S;(S=o.value)===null||S===void 0||S.offsetWidth,r.value=!0})}return()=>{const{clsPrefix:h}=e;return a("span",{ref:o,class:`${h}-base-slot-machine-number`},t.value!==null?a("span",{class:[`${h}-base-slot-machine-old-number ${h}-base-slot-machine-old-number--top`,u.value]},t.value):null,a("span",{class:[`${h}-base-slot-machine-current-number`,c.value]},a("span",{ref:"numberWrapper",class:[`${h}-base-slot-machine-current-number__inner`,typeof e.value!="number"&&`${h}-base-slot-machine-current-number__inner--not-number`]},i.value)),t.value!==null?a("span",{class:[`${h}-base-slot-machine-old-number ${h}-base-slot-machine-old-number--bottom`,u.value]},t.value):null)}}}),{cubicBezierEaseOut:ne}=zo;function st({duration:e=".2s"}={}){return[w("&.fade-up-width-expand-transition-leave-active",{transition:`
 opacity ${e} ${ne},
 max-width ${e} ${ne},
 transform ${e} ${ne}
 `}),w("&.fade-up-width-expand-transition-enter-active",{transition:`
 opacity ${e} ${ne},
 max-width ${e} ${ne},
 transform ${e} ${ne}
 `}),w("&.fade-up-width-expand-transition-enter-to",{opacity:1,transform:"translateX(0) translateY(0)"}),w("&.fade-up-width-expand-transition-enter-from",{maxWidth:"0 !important",opacity:0,transform:"translateY(60%)"}),w("&.fade-up-width-expand-transition-leave-from",{opacity:1,transform:"translateY(0)"}),w("&.fade-up-width-expand-transition-leave-to",{maxWidth:"0 !important",opacity:0,transform:"translateY(60%)"})]}const ct=w([w("@keyframes n-base-slot-machine-fade-up-in",`
 from {
 transform: translateY(60%);
 opacity: 0;
 }
 to {
 transform: translateY(0);
 opacity: 1;
 }
 `),w("@keyframes n-base-slot-machine-fade-down-in",`
 from {
 transform: translateY(-60%);
 opacity: 0;
 }
 to {
 transform: translateY(0);
 opacity: 1;
 }
 `),w("@keyframes n-base-slot-machine-fade-up-out",`
 from {
 transform: translateY(0%);
 opacity: 1;
 }
 to {
 transform: translateY(-60%);
 opacity: 0;
 }
 `),w("@keyframes n-base-slot-machine-fade-down-out",`
 from {
 transform: translateY(0%);
 opacity: 1;
 }
 to {
 transform: translateY(60%);
 opacity: 0;
 }
 `),p("base-slot-machine",`
 overflow: hidden;
 white-space: nowrap;
 display: inline-block;
 height: 18px;
 line-height: 18px;
 `,[p("base-slot-machine-number",`
 display: inline-block;
 position: relative;
 height: 18px;
 width: .6em;
 max-width: .6em;
 `,[st({duration:".2s"}),wo({duration:".2s",delay:"0s"}),p("base-slot-machine-old-number",`
 display: inline-block;
 opacity: 0;
 position: absolute;
 left: 0;
 right: 0;
 `,[_("top",{transform:"translateY(-100%)"}),_("bottom",{transform:"translateY(100%)"}),_("down-scroll",{animation:"n-base-slot-machine-fade-down-out .2s cubic-bezier(0, 0, .2, 1)",animationIterationCount:1}),_("up-scroll",{animation:"n-base-slot-machine-fade-up-out .2s cubic-bezier(0, 0, .2, 1)",animationIterationCount:1})]),p("base-slot-machine-current-number",`
 display: inline-block;
 position: absolute;
 left: 0;
 top: 0;
 bottom: 0;
 right: 0;
 opacity: 1;
 transform: translateY(0);
 width: .6em;
 `,[_("down-scroll",{animation:"n-base-slot-machine-fade-down-in .2s cubic-bezier(0, 0, .2, 1)",animationIterationCount:1}),_("up-scroll",{animation:"n-base-slot-machine-fade-up-in .2s cubic-bezier(0, 0, .2, 1)",animationIterationCount:1}),x("inner",`
 display: inline-block;
 position: absolute;
 right: 0;
 top: 0;
 width: .6em;
 `,[_("not-number",`
 right: unset;
 left: 0;
 `)])])])])]),dt=K({name:"BaseSlotMachine",props:{clsPrefix:{type:String,required:!0},value:{type:[Number,String],default:0},max:{type:Number,default:void 0},appeared:{type:Boolean,required:!0}},setup(e){So("-base-slot-machine",ct,re(e,"clsPrefix"));const o=O(),t=O(),i=C(()=>{if(typeof e.value=="string")return[];if(e.value<1)return[0];const l=[];let r=e.value;for(e.max!==void 0&&(r=Math.min(e.max,r));r>=1;)l.push(r%10),r/=10,r=Math.floor(r);return l.reverse(),l});return fe(re(e,"value"),(l,r)=>{typeof l=="string"?(t.value=void 0,o.value=void 0):typeof r=="string"?(t.value=l,o.value=void 0):(t.value=l,o.value=r)}),()=>{const{value:l,clsPrefix:r}=e;return typeof l=="number"?a("span",{class:`${r}-base-slot-machine`},a(Io,{name:"fade-up-width-expand-transition",tag:"span"},{default:()=>i.value.map((c,u)=>a(Le,{clsPrefix:r,key:i.value.length-u-1,oldOriginalNumber:o.value,newOriginalNumber:t.value,value:c}))}),a(Ke,{key:"+",width:!0},{default:()=>e.max!==void 0&&e.max<l?a(Le,{clsPrefix:r,value:"+"}):null})):a("span",{class:`${r}-base-slot-machine`},l)}}}),ut=ae("n-avatar-group"),vt=p("avatar",`
 width: var(--n-merged-size);
 height: var(--n-merged-size);
 color: #FFF;
 font-size: var(--n-font-size);
 display: inline-flex;
 position: relative;
 overflow: hidden;
 text-align: center;
 border: var(--n-border);
 border-radius: var(--n-border-radius);
 --n-merged-color: var(--n-color);
 background-color: var(--n-merged-color);
 transition:
 border-color .3s var(--n-bezier),
 background-color .3s var(--n-bezier),
 color .3s var(--n-bezier);
`,[Ro(w("&","--n-merged-color: var(--n-color-modal);")),ko(w("&","--n-merged-color: var(--n-color-popover);")),w("img",`
 width: 100%;
 height: 100%;
 `),x("text",`
 white-space: nowrap;
 display: inline-block;
 position: absolute;
 left: 50%;
 top: 50%;
 `),p("icon",`
 vertical-align: bottom;
 font-size: calc(var(--n-merged-size) - 6px);
 `),x("text","line-height: 1.25")]),mt=Object.assign(Object.assign({},G.props),{size:[String,Number],src:String,circle:{type:Boolean,default:void 0},objectFit:String,round:{type:Boolean,default:void 0},bordered:{type:Boolean,default:void 0},onError:Function,fallbackSrc:String,intersectionObserverOptions:Object,lazy:Boolean,onLoad:Function,renderPlaceholder:Function,renderFallback:Function,imgProps:Object,color:String}),ht=K({name:"Avatar",props:mt,slots:Object,setup(e){const{mergedClsPrefixRef:o,inlineThemeDisabled:t}=se(e),i=O(!1);let l=null;const r=O(null),c=O(null),u=()=>{const{value:d}=r;if(d&&(l===null||l!==d.innerHTML)){l=d.innerHTML;const{value:b}=c;if(b){const{offsetWidth:E,offsetHeight:A}=b,{offsetWidth:k,offsetHeight:y}=d,I=.9,V=Math.min(E/k*I,A/y*I,1);d.style.transform=`translateX(-50%) translateY(-50%) scale(${V})`}}},v=J(ut,null),m=C(()=>{const{size:d}=e;if(d)return d;const{size:b}=v||{};return b||"medium"}),h=G("Avatar","-avatar",vt,To,e,o),S=J(Qo,null),f=C(()=>{if(v)return!0;const{round:d,circle:b}=e;return d!==void 0||b!==void 0?d||b:S?S.roundRef.value:!1}),B=C(()=>v?!0:e.bordered||!1),$=C(()=>{const d=m.value,b=f.value,E=B.value,{color:A}=e,{self:{borderRadius:k,fontSize:y,color:I,border:V,colorModal:M,colorPopover:j},common:{cubicBezierEaseInOut:X}}=h.value;let Q;return typeof d=="number"?Q=`${d}px`:Q=h.value.self[Ye("height",d)],{"--n-font-size":y,"--n-border":E?V:"none","--n-border-radius":b?"50%":k,"--n-color":A||I,"--n-color-modal":A||M,"--n-color-popover":A||j,"--n-bezier":X,"--n-merged-size":`var(--n-avatar-size-override, ${Q})`}}),z=t?ce("avatar",C(()=>{const d=m.value,b=f.value,E=B.value,{color:A}=e;let k="";return d&&(typeof d=="number"?k+=`a${d}`:k+=d[0]),b&&(k+="b"),E&&(k+="c"),A&&(k+=We(A)),k}),$,e):void 0,P=O(!e.lazy);ke(()=>{if(e.lazy&&e.intersectionObserverOptions){let d;const b=ye(()=>{d==null||d(),d=void 0,e.lazy&&(d=it(c.value,e.intersectionObserverOptions,P))});No(()=>{b(),d==null||d()})}}),fe(()=>{var d;return e.src||((d=e.imgProps)===null||d===void 0?void 0:d.src)},()=>{i.value=!1});const g=O(!e.lazy);return{textRef:r,selfRef:c,mergedRoundRef:f,mergedClsPrefix:o,fitTextTransform:u,cssVars:t?void 0:$,themeClass:z==null?void 0:z.themeClass,onRender:z==null?void 0:z.onRender,hasLoadError:i,shouldStartLoading:P,loaded:g,mergedOnError:d=>{if(!P.value)return;i.value=!0;const{onError:b,imgProps:{onError:E}={}}=e;b==null||b(d),E==null||E(d)},mergedOnLoad:d=>{const{onLoad:b,imgProps:{onLoad:E}={}}=e;b==null||b(d),E==null||E(d),g.value=!0}}},render(){var e,o;const{$slots:t,src:i,mergedClsPrefix:l,lazy:r,onRender:c,loaded:u,hasLoadError:v,imgProps:m={}}=this;c==null||c();let h;const S=!u&&!v&&(this.renderPlaceholder?this.renderPlaceholder():(o=(e=this.$slots).placeholder)===null||o===void 0?void 0:o.call(e));return this.hasLoadError?h=this.renderFallback?this.renderFallback():De(t.fallback,()=>[a("img",{src:this.fallbackSrc,style:{objectFit:this.objectFit}})]):h=Po(t.default,f=>{if(f)return a(Ue,{onResize:this.fitTextTransform},{default:()=>a("span",{ref:"textRef",class:`${l}-avatar__text`},f)});if(i||m.src){const B=this.src||m.src;return a("img",Object.assign(Object.assign({},m),{loading:lt&&!this.intersectionObserverOptions&&r?"lazy":"eager",src:r&&this.intersectionObserverOptions?this.shouldStartLoading?B:void 0:B,"data-image-src":B,onLoad:this.mergedOnLoad,onError:this.mergedOnError,style:[m.style||"",{objectFit:this.objectFit},S?{height:"0",width:"0",visibility:"hidden",position:"absolute"}:""]}))}}),a("span",{ref:"selfRef",class:[`${l}-avatar`,this.themeClass],style:this.cssVars},h,r&&S)}});function ft(e){const{errorColor:o,infoColor:t,successColor:i,warningColor:l,fontFamily:r}=e;return{color:o,colorInfo:t,colorSuccess:i,colorError:o,colorWarning:l,fontSize:"12px",fontFamily:r}}const pt={common:Ge,self:ft},gt=w([w("@keyframes badge-wave-spread",{from:{boxShadow:"0 0 0.5px 0px var(--n-ripple-color)",opacity:.6},to:{boxShadow:"0 0 0.5px 4.5px var(--n-ripple-color)",opacity:0}}),p("badge",`
 display: inline-flex;
 position: relative;
 vertical-align: middle;
 font-family: var(--n-font-family);
 `,[_("as-is",[p("badge-sup",{position:"static",transform:"translateX(0)"},[Ee({transformOrigin:"left bottom",originalTransform:"translateX(0)"})])]),_("dot",[p("badge-sup",`
 height: 8px;
 width: 8px;
 padding: 0;
 min-width: 8px;
 left: 100%;
 bottom: calc(100% - 4px);
 `,[w("::before","border-radius: 4px;")])]),p("badge-sup",`
 background: var(--n-color);
 transition:
 background-color .3s var(--n-bezier),
 color .3s var(--n-bezier);
 color: #FFF;
 position: absolute;
 height: 18px;
 line-height: 18px;
 border-radius: 9px;
 padding: 0 6px;
 text-align: center;
 font-size: var(--n-font-size);
 transform: translateX(-50%);
 left: 100%;
 bottom: calc(100% - 9px);
 font-variant-numeric: tabular-nums;
 z-index: 2;
 display: flex;
 align-items: center;
 `,[Ee({transformOrigin:"left bottom",originalTransform:"translateX(-50%)"}),p("base-wave",{zIndex:1,animationDuration:"2s",animationIterationCount:"infinite",animationDelay:"1s",animationTimingFunction:"var(--n-ripple-bezier)",animationName:"badge-wave-spread"}),w("&::before",`
 opacity: 0;
 transform: scale(1);
 border-radius: 9px;
 content: "";
 position: absolute;
 left: 0;
 right: 0;
 top: 0;
 bottom: 0;
 `)])])]),bt=Object.assign(Object.assign({},G.props),{value:[String,Number],max:Number,dot:Boolean,type:{type:String,default:"default"},show:{type:Boolean,default:!0},showZero:Boolean,processing:Boolean,color:String,offset:Array}),xt=K({name:"Badge",props:bt,setup(e,{slots:o}){const{mergedClsPrefixRef:t,inlineThemeDisabled:i,mergedRtlRef:l}=se(e),r=G("Badge","-badge",gt,pt,e,t),c=O(!1),u=()=>{c.value=!0},v=()=>{c.value=!1},m=C(()=>e.show&&(e.dot||e.value!==void 0&&!(!e.showZero&&Number(e.value)<=0)||!Oo(o.value)));ke(()=>{m.value&&(c.value=!0)});const h=Ao("Badge",l,t),S=C(()=>{const{type:$,color:z}=e,{common:{cubicBezierEaseInOut:P,cubicBezierEaseOut:g},self:{[Ye("color",$)]:d,fontFamily:b,fontSize:E}}=r.value;return{"--n-font-size":E,"--n-font-family":b,"--n-color":z||d,"--n-ripple-color":z||d,"--n-bezier":P,"--n-ripple-bezier":g}}),f=i?ce("badge",C(()=>{let $="";const{type:z,color:P}=e;return z&&($+=z[0]),P&&($+=We(P)),$}),S,e):void 0,B=C(()=>{const{offset:$}=e;if(!$)return;const[z,P]=$,g=typeof z=="number"?`${z}px`:z,d=typeof P=="number"?`${P}px`:P;return{transform:`translate(calc(${h!=null&&h.value?"50%":"-50%"} + ${g}), ${d})`}});return{rtlEnabled:h,mergedClsPrefix:t,appeared:c,showBadge:m,handleAfterEnter:u,handleAfterLeave:v,cssVars:i?void 0:S,themeClass:f==null?void 0:f.themeClass,onRender:f==null?void 0:f.onRender,offsetStyle:B}},render(){var e;const{mergedClsPrefix:o,onRender:t,themeClass:i,$slots:l}=this;t==null||t();const r=(e=l.default)===null||e===void 0?void 0:e.call(l);return a("div",{class:[`${o}-badge`,this.rtlEnabled&&`${o}-badge--rtl`,i,{[`${o}-badge--dot`]:this.dot,[`${o}-badge--as-is`]:!r}],style:this.cssVars},r,a($o,{name:"fade-in-scale-up-transition",onAfterEnter:this.handleAfterEnter,onAfterLeave:this.handleAfterLeave},{default:()=>this.showBadge?a("sup",{class:`${o}-badge-sup`,title:et(this.value),style:this.offsetStyle},De(l.value,()=>[this.dot?null:a(dt,{clsPrefix:o,appeared:this.appeared,max:this.max,value:this.value})]),this.processing?a(_o,{clsPrefix:o}):null):null}))}});function yt(e){const{baseColor:o,textColor2:t,bodyColor:i,cardColor:l,dividerColor:r,actionColor:c,scrollbarColor:u,scrollbarColorHover:v,invertedColor:m}=e;return{textColor:t,textColorInverted:"#FFF",color:i,colorEmbedded:c,headerColor:l,headerColorInverted:m,footerColor:c,footerColorInverted:m,headerBorderColor:r,headerBorderColorInverted:m,footerBorderColor:r,footerBorderColorInverted:m,siderBorderColor:r,siderBorderColorInverted:m,siderColor:l,siderColorInverted:m,siderToggleButtonBorder:`1px solid ${r}`,siderToggleButtonColor:o,siderToggleButtonIconColor:t,siderToggleButtonIconColorInverted:t,siderToggleBarColor:He(i,u),siderToggleBarColorHover:He(i,v),__invertScrollbar:"true"}}const Te=Bo({name:"Layout",common:Ge,peers:{Scrollbar:Eo},self:yt}),no=ae("n-layout-sider"),$e={type:String,default:"static"},Ct=p("layout",`
 color: var(--n-text-color);
 background-color: var(--n-color);
 box-sizing: border-box;
 position: relative;
 z-index: auto;
 flex: auto;
 overflow: hidden;
 transition:
 box-shadow .3s var(--n-bezier),
 background-color .3s var(--n-bezier),
 color .3s var(--n-bezier);
`,[p("layout-scroll-container",`
 overflow-x: hidden;
 box-sizing: border-box;
 height: 100%;
 `),_("absolute-positioned",`
 position: absolute;
 left: 0;
 right: 0;
 top: 0;
 bottom: 0;
 `)]),zt={embedded:Boolean,position:$e,nativeScrollbar:{type:Boolean,default:!0},scrollbarProps:Object,onScroll:Function,contentClass:String,contentStyle:{type:[String,Object],default:""},hasSider:Boolean,siderPlacement:{type:String,default:"left"}},lo=ae("n-layout");function io(e){return K({name:e?"LayoutContent":"Layout",props:Object.assign(Object.assign({},G.props),zt),setup(o){const t=O(null),i=O(null),{mergedClsPrefixRef:l,inlineThemeDisabled:r}=se(o),c=G("Layout","-layout",Ct,Te,o,l);function u(z,P){if(o.nativeScrollbar){const{value:g}=t;g&&(P===void 0?g.scrollTo(z):g.scrollTo(z,P))}else{const{value:g}=i;g&&g.scrollTo(z,P)}}ie(lo,o);let v=0,m=0;const h=z=>{var P;const g=z.target;v=g.scrollLeft,m=g.scrollTop,(P=o.onScroll)===null||P===void 0||P.call(o,z)};Xe(()=>{if(o.nativeScrollbar){const z=t.value;z&&(z.scrollTop=m,z.scrollLeft=v)}});const S={display:"flex",flexWrap:"nowrap",width:"100%",flexDirection:"row"},f={scrollTo:u},B=C(()=>{const{common:{cubicBezierEaseInOut:z},self:P}=c.value;return{"--n-bezier":z,"--n-color":o.embedded?P.colorEmbedded:P.color,"--n-text-color":P.textColor}}),$=r?ce("layout",C(()=>o.embedded?"e":""),B,o):void 0;return Object.assign({mergedClsPrefix:l,scrollableElRef:t,scrollbarInstRef:i,hasSiderStyle:S,mergedTheme:c,handleNativeElScroll:h,cssVars:r?void 0:B,themeClass:$==null?void 0:$.themeClass,onRender:$==null?void 0:$.onRender},f)},render(){var o;const{mergedClsPrefix:t,hasSider:i}=this;(o=this.onRender)===null||o===void 0||o.call(this);const l=i?this.hasSiderStyle:void 0,r=[this.themeClass,e&&`${t}-layout-content`,`${t}-layout`,`${t}-layout--${this.position}-positioned`];return a("div",{class:r,style:this.cssVars},this.nativeScrollbar?a("div",{ref:"scrollableElRef",class:[`${t}-layout-scroll-container`,this.contentClass],style:[this.contentStyle,l],onScroll:this.handleNativeElScroll},this.$slots):a(qe,Object.assign({},this.scrollbarProps,{onScroll:this.onScroll,ref:"scrollbarInstRef",theme:this.mergedTheme.peers.Scrollbar,themeOverrides:this.mergedTheme.peerOverrides.Scrollbar,contentClass:this.contentClass,contentStyle:[this.contentStyle,l]}),this.$slots))}})}const Fe=io(!1),wt=io(!0),St=p("layout-header",`
 transition:
 color .3s var(--n-bezier),
 background-color .3s var(--n-bezier),
 box-shadow .3s var(--n-bezier),
 border-color .3s var(--n-bezier);
 box-sizing: border-box;
 width: 100%;
 background-color: var(--n-color);
 color: var(--n-text-color);
`,[_("absolute-positioned",`
 position: absolute;
 left: 0;
 right: 0;
 top: 0;
 `),_("bordered",`
 border-bottom: solid 1px var(--n-border-color);
 `)]),It={position:$e,inverted:Boolean,bordered:{type:Boolean,default:!1}},Rt=K({name:"LayoutHeader",props:Object.assign(Object.assign({},G.props),It),setup(e){const{mergedClsPrefixRef:o,inlineThemeDisabled:t}=se(e),i=G("Layout","-layout-header",St,Te,e,o),l=C(()=>{const{common:{cubicBezierEaseInOut:c},self:u}=i.value,v={"--n-bezier":c};return e.inverted?(v["--n-color"]=u.headerColorInverted,v["--n-text-color"]=u.textColorInverted,v["--n-border-color"]=u.headerBorderColorInverted):(v["--n-color"]=u.headerColor,v["--n-text-color"]=u.textColor,v["--n-border-color"]=u.headerBorderColor),v}),r=t?ce("layout-header",C(()=>e.inverted?"a":"b"),l,e):void 0;return{mergedClsPrefix:o,cssVars:t?void 0:l,themeClass:r==null?void 0:r.themeClass,onRender:r==null?void 0:r.onRender}},render(){var e;const{mergedClsPrefix:o}=this;return(e=this.onRender)===null||e===void 0||e.call(this),a("div",{class:[`${o}-layout-header`,this.themeClass,this.position&&`${o}-layout-header--${this.position}-positioned`,this.bordered&&`${o}-layout-header--bordered`],style:this.cssVars},this.$slots)}}),kt=p("layout-sider",`
 flex-shrink: 0;
 box-sizing: border-box;
 position: relative;
 z-index: 1;
 color: var(--n-text-color);
 transition:
 color .3s var(--n-bezier),
 border-color .3s var(--n-bezier),
 min-width .3s var(--n-bezier),
 max-width .3s var(--n-bezier),
 transform .3s var(--n-bezier),
 background-color .3s var(--n-bezier);
 background-color: var(--n-color);
 display: flex;
 justify-content: flex-end;
`,[_("bordered",[x("border",`
 content: "";
 position: absolute;
 top: 0;
 bottom: 0;
 width: 1px;
 background-color: var(--n-border-color);
 transition: background-color .3s var(--n-bezier);
 `)]),x("left-placement",[_("bordered",[x("border",`
 right: 0;
 `)])]),_("right-placement",`
 justify-content: flex-start;
 `,[_("bordered",[x("border",`
 left: 0;
 `)]),_("collapsed",[p("layout-toggle-button",[p("base-icon",`
 transform: rotate(180deg);
 `)]),p("layout-toggle-bar",[w("&:hover",[x("top",{transform:"rotate(-12deg) scale(1.15) translateY(-2px)"}),x("bottom",{transform:"rotate(12deg) scale(1.15) translateY(2px)"})])])]),p("layout-toggle-button",`
 left: 0;
 transform: translateX(-50%) translateY(-50%);
 `,[p("base-icon",`
 transform: rotate(0);
 `)]),p("layout-toggle-bar",`
 left: -28px;
 transform: rotate(180deg);
 `,[w("&:hover",[x("top",{transform:"rotate(12deg) scale(1.15) translateY(-2px)"}),x("bottom",{transform:"rotate(-12deg) scale(1.15) translateY(2px)"})])])]),_("collapsed",[p("layout-toggle-bar",[w("&:hover",[x("top",{transform:"rotate(-12deg) scale(1.15) translateY(-2px)"}),x("bottom",{transform:"rotate(12deg) scale(1.15) translateY(2px)"})])]),p("layout-toggle-button",[p("base-icon",`
 transform: rotate(0);
 `)])]),p("layout-toggle-button",`
 transition:
 color .3s var(--n-bezier),
 right .3s var(--n-bezier),
 left .3s var(--n-bezier),
 border-color .3s var(--n-bezier),
 background-color .3s var(--n-bezier);
 cursor: pointer;
 width: 24px;
 height: 24px;
 position: absolute;
 top: 50%;
 right: 0;
 border-radius: 50%;
 display: flex;
 align-items: center;
 justify-content: center;
 font-size: 18px;
 color: var(--n-toggle-button-icon-color);
 border: var(--n-toggle-button-border);
 background-color: var(--n-toggle-button-color);
 box-shadow: 0 2px 4px 0px rgba(0, 0, 0, .06);
 transform: translateX(50%) translateY(-50%);
 z-index: 1;
 `,[p("base-icon",`
 transition: transform .3s var(--n-bezier);
 transform: rotate(180deg);
 `)]),p("layout-toggle-bar",`
 cursor: pointer;
 height: 72px;
 width: 32px;
 position: absolute;
 top: calc(50% - 36px);
 right: -28px;
 `,[x("top, bottom",`
 position: absolute;
 width: 4px;
 border-radius: 2px;
 height: 38px;
 left: 14px;
 transition: 
 background-color .3s var(--n-bezier),
 transform .3s var(--n-bezier);
 `),x("bottom",`
 position: absolute;
 top: 34px;
 `),w("&:hover",[x("top",{transform:"rotate(12deg) scale(1.15) translateY(-2px)"}),x("bottom",{transform:"rotate(-12deg) scale(1.15) translateY(2px)"})]),x("top, bottom",{backgroundColor:"var(--n-toggle-bar-color)"}),w("&:hover",[x("top, bottom",{backgroundColor:"var(--n-toggle-bar-color-hover)"})])]),x("border",`
 position: absolute;
 top: 0;
 right: 0;
 bottom: 0;
 width: 1px;
 transition: background-color .3s var(--n-bezier);
 `),p("layout-sider-scroll-container",`
 flex-grow: 1;
 flex-shrink: 0;
 box-sizing: border-box;
 height: 100%;
 opacity: 0;
 transition: opacity .3s var(--n-bezier);
 max-width: 100%;
 `),_("show-content",[p("layout-sider-scroll-container",{opacity:1})]),_("absolute-positioned",`
 position: absolute;
 left: 0;
 top: 0;
 bottom: 0;
 `)]),Pt=K({props:{clsPrefix:{type:String,required:!0},onClick:Function},render(){const{clsPrefix:e}=this;return a("div",{onClick:this.onClick,class:`${e}-layout-toggle-bar`},a("div",{class:`${e}-layout-toggle-bar__top`}),a("div",{class:`${e}-layout-toggle-bar__bottom`}))}}),Nt=K({name:"LayoutToggleButton",props:{clsPrefix:{type:String,required:!0},onClick:Function},render(){const{clsPrefix:e}=this;return a("div",{class:`${e}-layout-toggle-button`,onClick:this.onClick},a(Ze,{clsPrefix:e},{default:()=>a(Zo,null)}))}}),Tt={position:$e,bordered:Boolean,collapsedWidth:{type:Number,default:48},width:{type:[Number,String],default:272},contentClass:String,contentStyle:{type:[String,Object],default:""},collapseMode:{type:String,default:"transform"},collapsed:{type:Boolean,default:void 0},defaultCollapsed:Boolean,showCollapsedContent:{type:Boolean,default:!0},showTrigger:{type:[Boolean,String],default:!1},nativeScrollbar:{type:Boolean,default:!0},inverted:Boolean,scrollbarProps:Object,triggerClass:String,triggerStyle:[String,Object],collapsedTriggerClass:String,collapsedTriggerStyle:[String,Object],"onUpdate:collapsed":[Function,Array],onUpdateCollapsed:[Function,Array],onAfterEnter:Function,onAfterLeave:Function,onExpand:[Function,Array],onCollapse:[Function,Array],onScroll:Function},$t=K({name:"LayoutSider",props:Object.assign(Object.assign({},G.props),Tt),setup(e){const o=J(lo),t=O(null),i=O(null),l=O(e.defaultCollapsed),r=Se(re(e,"collapsed"),l),c=C(()=>be(r.value?e.collapsedWidth:e.width)),u=C(()=>e.collapseMode!=="transform"?{}:{minWidth:be(e.width)}),v=C(()=>o?o.siderPlacement:"left");function m(A,k){if(e.nativeScrollbar){const{value:y}=t;y&&(k===void 0?y.scrollTo(A):y.scrollTo(A,k))}else{const{value:y}=i;y&&y.scrollTo(A,k)}}function h(){const{"onUpdate:collapsed":A,onUpdateCollapsed:k,onExpand:y,onCollapse:I}=e,{value:V}=r;k&&q(k,!V),A&&q(A,!V),l.value=!V,V?y&&q(y):I&&q(I)}let S=0,f=0;const B=A=>{var k;const y=A.target;S=y.scrollLeft,f=y.scrollTop,(k=e.onScroll)===null||k===void 0||k.call(e,A)};Xe(()=>{if(e.nativeScrollbar){const A=t.value;A&&(A.scrollTop=f,A.scrollLeft=S)}}),ie(no,{collapsedRef:r,collapseModeRef:re(e,"collapseMode")});const{mergedClsPrefixRef:$,inlineThemeDisabled:z}=se(e),P=G("Layout","-layout-sider",kt,Te,e,$);function g(A){var k,y;A.propertyName==="max-width"&&(r.value?(k=e.onAfterLeave)===null||k===void 0||k.call(e):(y=e.onAfterEnter)===null||y===void 0||y.call(e))}const d={scrollTo:m},b=C(()=>{const{common:{cubicBezierEaseInOut:A},self:k}=P.value,{siderToggleButtonColor:y,siderToggleButtonBorder:I,siderToggleBarColor:V,siderToggleBarColorHover:M}=k,j={"--n-bezier":A,"--n-toggle-button-color":y,"--n-toggle-button-border":I,"--n-toggle-bar-color":V,"--n-toggle-bar-color-hover":M};return e.inverted?(j["--n-color"]=k.siderColorInverted,j["--n-text-color"]=k.textColorInverted,j["--n-border-color"]=k.siderBorderColorInverted,j["--n-toggle-button-icon-color"]=k.siderToggleButtonIconColorInverted,j.__invertScrollbar=k.__invertScrollbar):(j["--n-color"]=k.siderColor,j["--n-text-color"]=k.textColor,j["--n-border-color"]=k.siderBorderColor,j["--n-toggle-button-icon-color"]=k.siderToggleButtonIconColor),j}),E=z?ce("layout-sider",C(()=>e.inverted?"a":"b"),b,e):void 0;return Object.assign({scrollableElRef:t,scrollbarInstRef:i,mergedClsPrefix:$,mergedTheme:P,styleMaxWidth:c,mergedCollapsed:r,scrollContainerStyle:u,siderPlacement:v,handleNativeElScroll:B,handleTransitionend:g,handleTriggerClick:h,inlineThemeDisabled:z,cssVars:b,themeClass:E==null?void 0:E.themeClass,onRender:E==null?void 0:E.onRender},d)},render(){var e;const{mergedClsPrefix:o,mergedCollapsed:t,showTrigger:i}=this;return(e=this.onRender)===null||e===void 0||e.call(this),a("aside",{class:[`${o}-layout-sider`,this.themeClass,`${o}-layout-sider--${this.position}-positioned`,`${o}-layout-sider--${this.siderPlacement}-placement`,this.bordered&&`${o}-layout-sider--bordered`,t&&`${o}-layout-sider--collapsed`,(!t||this.showCollapsedContent)&&`${o}-layout-sider--show-content`],onTransitionend:this.handleTransitionend,style:[this.inlineThemeDisabled?void 0:this.cssVars,{maxWidth:this.styleMaxWidth,width:be(this.width)}]},this.nativeScrollbar?a("div",{class:[`${o}-layout-sider-scroll-container`,this.contentClass],onScroll:this.handleNativeElScroll,style:[this.scrollContainerStyle,{overflow:"auto"},this.contentStyle],ref:"scrollableElRef"},this.$slots):a(qe,Object.assign({},this.scrollbarProps,{onScroll:this.onScroll,ref:"scrollbarInstRef",style:this.scrollContainerStyle,contentStyle:this.contentStyle,contentClass:this.contentClass,theme:this.mergedTheme.peers.Scrollbar,themeOverrides:this.mergedTheme.peerOverrides.Scrollbar,builtinThemeOverrides:this.inverted&&this.cssVars.__invertScrollbar==="true"?{colorHover:"rgba(255, 255, 255, .4)",color:"rgba(255, 255, 255, .3)"}:void 0}),this.$slots),i?i==="bar"?a(Pt,{clsPrefix:o,class:t?this.collapsedTriggerClass:this.triggerClass,style:t?this.collapsedTriggerStyle:this.triggerStyle,onClick:this.handleTriggerClick}):a(Nt,{clsPrefix:o,class:t?this.collapsedTriggerClass:this.triggerClass,style:t?this.collapsedTriggerStyle:this.triggerStyle,onClick:this.handleTriggerClick}):null,this.bordered?a("div",{class:`${o}-layout-sider__border`}):null)}}),ve=ae("n-menu"),ao=ae("n-submenu"),_e=ae("n-menu-item-group"),je=[w("&::before","background-color: var(--n-item-color-hover);"),x("arrow",`
 color: var(--n-arrow-color-hover);
 `),x("icon",`
 color: var(--n-item-icon-color-hover);
 `),p("menu-item-content-header",`
 color: var(--n-item-text-color-hover);
 `,[w("a",`
 color: var(--n-item-text-color-hover);
 `),x("extra",`
 color: var(--n-item-text-color-hover);
 `)])],Ve=[x("icon",`
 color: var(--n-item-icon-color-hover-horizontal);
 `),p("menu-item-content-header",`
 color: var(--n-item-text-color-hover-horizontal);
 `,[w("a",`
 color: var(--n-item-text-color-hover-horizontal);
 `),x("extra",`
 color: var(--n-item-text-color-hover-horizontal);
 `)])],_t=w([p("menu",`
 background-color: var(--n-color);
 color: var(--n-item-text-color);
 overflow: hidden;
 transition: background-color .3s var(--n-bezier);
 box-sizing: border-box;
 font-size: var(--n-font-size);
 padding-bottom: 6px;
 `,[_("horizontal",`
 max-width: 100%;
 width: 100%;
 display: flex;
 overflow: hidden;
 padding-bottom: 0;
 `,[p("submenu","margin: 0;"),p("menu-item","margin: 0;"),p("menu-item-content",`
 padding: 0 20px;
 border-bottom: 2px solid #0000;
 `,[w("&::before","display: none;"),_("selected","border-bottom: 2px solid var(--n-border-color-horizontal)")]),p("menu-item-content",[_("selected",[x("icon","color: var(--n-item-icon-color-active-horizontal);"),p("menu-item-content-header",`
 color: var(--n-item-text-color-active-horizontal);
 `,[w("a","color: var(--n-item-text-color-active-horizontal);"),x("extra","color: var(--n-item-text-color-active-horizontal);")])]),_("child-active",`
 border-bottom: 2px solid var(--n-border-color-horizontal);
 `,[p("menu-item-content-header",`
 color: var(--n-item-text-color-child-active-horizontal);
 `,[w("a",`
 color: var(--n-item-text-color-child-active-horizontal);
 `),x("extra",`
 color: var(--n-item-text-color-child-active-horizontal);
 `)]),x("icon",`
 color: var(--n-item-icon-color-child-active-horizontal);
 `)]),de("disabled",[de("selected, child-active",[w("&:focus-within",Ve)]),_("selected",[te(null,[x("icon","color: var(--n-item-icon-color-active-hover-horizontal);"),p("menu-item-content-header",`
 color: var(--n-item-text-color-active-hover-horizontal);
 `,[w("a","color: var(--n-item-text-color-active-hover-horizontal);"),x("extra","color: var(--n-item-text-color-active-hover-horizontal);")])])]),_("child-active",[te(null,[x("icon","color: var(--n-item-icon-color-child-active-hover-horizontal);"),p("menu-item-content-header",`
 color: var(--n-item-text-color-child-active-hover-horizontal);
 `,[w("a","color: var(--n-item-text-color-child-active-hover-horizontal);"),x("extra","color: var(--n-item-text-color-child-active-hover-horizontal);")])])]),te("border-bottom: 2px solid var(--n-border-color-horizontal);",Ve)]),p("menu-item-content-header",[w("a","color: var(--n-item-text-color-horizontal);")])])]),de("responsive",[p("menu-item-content-header",`
 overflow: hidden;
 text-overflow: ellipsis;
 `)]),_("collapsed",[p("menu-item-content",[_("selected",[w("&::before",`
 background-color: var(--n-item-color-active-collapsed) !important;
 `)]),p("menu-item-content-header","opacity: 0;"),x("arrow","opacity: 0;"),x("icon","color: var(--n-item-icon-color-collapsed);")])]),p("menu-item",`
 height: var(--n-item-height);
 margin-top: 6px;
 position: relative;
 `),p("menu-item-content",`
 box-sizing: border-box;
 line-height: 1.75;
 height: 100%;
 display: grid;
 grid-template-areas: "icon content arrow";
 grid-template-columns: auto 1fr auto;
 align-items: center;
 cursor: pointer;
 position: relative;
 padding-right: 18px;
 transition:
 background-color .3s var(--n-bezier),
 padding-left .3s var(--n-bezier),
 border-color .3s var(--n-bezier);
 `,[w("> *","z-index: 1;"),w("&::before",`
 z-index: auto;
 content: "";
 background-color: #0000;
 position: absolute;
 left: 8px;
 right: 8px;
 top: 0;
 bottom: 0;
 pointer-events: none;
 border-radius: var(--n-border-radius);
 transition: background-color .3s var(--n-bezier);
 `),_("disabled",`
 opacity: .45;
 cursor: not-allowed;
 `),_("collapsed",[x("arrow","transform: rotate(0);")]),_("selected",[w("&::before","background-color: var(--n-item-color-active);"),x("arrow","color: var(--n-arrow-color-active);"),x("icon","color: var(--n-item-icon-color-active);"),p("menu-item-content-header",`
 color: var(--n-item-text-color-active);
 `,[w("a","color: var(--n-item-text-color-active);"),x("extra","color: var(--n-item-text-color-active);")])]),_("child-active",[p("menu-item-content-header",`
 color: var(--n-item-text-color-child-active);
 `,[w("a",`
 color: var(--n-item-text-color-child-active);
 `),x("extra",`
 color: var(--n-item-text-color-child-active);
 `)]),x("arrow",`
 color: var(--n-arrow-color-child-active);
 `),x("icon",`
 color: var(--n-item-icon-color-child-active);
 `)]),de("disabled",[de("selected, child-active",[w("&:focus-within",je)]),_("selected",[te(null,[x("arrow","color: var(--n-arrow-color-active-hover);"),x("icon","color: var(--n-item-icon-color-active-hover);"),p("menu-item-content-header",`
 color: var(--n-item-text-color-active-hover);
 `,[w("a","color: var(--n-item-text-color-active-hover);"),x("extra","color: var(--n-item-text-color-active-hover);")])])]),_("child-active",[te(null,[x("arrow","color: var(--n-arrow-color-child-active-hover);"),x("icon","color: var(--n-item-icon-color-child-active-hover);"),p("menu-item-content-header",`
 color: var(--n-item-text-color-child-active-hover);
 `,[w("a","color: var(--n-item-text-color-child-active-hover);"),x("extra","color: var(--n-item-text-color-child-active-hover);")])])]),_("selected",[te(null,[w("&::before","background-color: var(--n-item-color-active-hover);")])]),te(null,je)]),x("icon",`
 grid-area: icon;
 color: var(--n-item-icon-color);
 transition:
 color .3s var(--n-bezier),
 font-size .3s var(--n-bezier),
 margin-right .3s var(--n-bezier);
 box-sizing: content-box;
 display: inline-flex;
 align-items: center;
 justify-content: center;
 `),x("arrow",`
 grid-area: arrow;
 font-size: 16px;
 color: var(--n-arrow-color);
 transform: rotate(180deg);
 opacity: 1;
 transition:
 color .3s var(--n-bezier),
 transform 0.2s var(--n-bezier),
 opacity 0.2s var(--n-bezier);
 `),p("menu-item-content-header",`
 grid-area: content;
 transition:
 color .3s var(--n-bezier),
 opacity .3s var(--n-bezier);
 opacity: 1;
 white-space: nowrap;
 color: var(--n-item-text-color);
 `,[w("a",`
 outline: none;
 text-decoration: none;
 transition: color .3s var(--n-bezier);
 color: var(--n-item-text-color);
 `,[w("&::before",`
 content: "";
 position: absolute;
 left: 0;
 right: 0;
 top: 0;
 bottom: 0;
 `)]),x("extra",`
 font-size: .93em;
 color: var(--n-group-text-color);
 transition: color .3s var(--n-bezier);
 `)])]),p("submenu",`
 cursor: pointer;
 position: relative;
 margin-top: 6px;
 `,[p("menu-item-content",`
 height: var(--n-item-height);
 `),p("submenu-children",`
 overflow: hidden;
 padding: 0;
 `,[Ho({duration:".2s"})])]),p("menu-item-group",[p("menu-item-group-title",`
 margin-top: 6px;
 color: var(--n-group-text-color);
 cursor: default;
 font-size: .93em;
 height: 36px;
 display: flex;
 align-items: center;
 transition:
 padding-left .3s var(--n-bezier),
 color .3s var(--n-bezier);
 `)])]),p("menu-tooltip",[w("a",`
 color: inherit;
 text-decoration: none;
 `)]),p("menu-divider",`
 transition: background-color .3s var(--n-bezier);
 background-color: var(--n-divider-color);
 height: 1px;
 margin: 6px 18px;
 `)]);function te(e,o){return[_("hover",e,o),w("&:hover",e,o)]}const so=K({name:"MenuOptionContent",props:{collapsed:Boolean,disabled:Boolean,title:[String,Function],icon:Function,extra:[String,Function],showArrow:Boolean,childActive:Boolean,hover:Boolean,paddingLeft:Number,selected:Boolean,maxIconSize:{type:Number,required:!0},activeIconSize:{type:Number,required:!0},iconMarginRight:{type:Number,required:!0},clsPrefix:{type:String,required:!0},onClick:Function,tmNode:{type:Object,required:!0},isEllipsisPlaceholder:Boolean},setup(e){const{props:o}=J(ve);return{menuProps:o,style:C(()=>{const{paddingLeft:t}=e;return{paddingLeft:t&&`${t}px`}}),iconStyle:C(()=>{const{maxIconSize:t,activeIconSize:i,iconMarginRight:l}=e;return{width:`${t}px`,height:`${t}px`,fontSize:`${i}px`,marginRight:`${l}px`}})}},render(){const{clsPrefix:e,tmNode:o,menuProps:{renderIcon:t,renderLabel:i,renderExtra:l,expandIcon:r}}=this,c=t?t(o.rawNode):le(this.icon);return a("div",{onClick:u=>{var v;(v=this.onClick)===null||v===void 0||v.call(this,u)},role:"none",class:[`${e}-menu-item-content`,{[`${e}-menu-item-content--selected`]:this.selected,[`${e}-menu-item-content--collapsed`]:this.collapsed,[`${e}-menu-item-content--child-active`]:this.childActive,[`${e}-menu-item-content--disabled`]:this.disabled,[`${e}-menu-item-content--hover`]:this.hover}],style:this.style},c&&a("div",{class:`${e}-menu-item-content__icon`,style:this.iconStyle,role:"none"},[c]),a("div",{class:`${e}-menu-item-content-header`,role:"none"},this.isEllipsisPlaceholder?this.title:i?i(o.rawNode):le(this.title),this.extra||l?a("span",{class:`${e}-menu-item-content-header__extra`}," ",l?l(o.rawNode):le(this.extra)):null),this.showArrow?a(Ze,{ariaHidden:!0,class:`${e}-menu-item-content__arrow`,clsPrefix:e},{default:()=>r?r(o.rawNode):a(at,null)}):null)}}),he=8;function Ae(e){const o=J(ve),{props:t,mergedCollapsedRef:i}=o,l=J(ao,null),r=J(_e,null),c=C(()=>t.mode==="horizontal"),u=C(()=>c.value?t.dropdownPlacement:"tmNodes"in e?"right-start":"right"),v=C(()=>{var f;return Math.max((f=t.collapsedIconSize)!==null&&f!==void 0?f:t.iconSize,t.iconSize)}),m=C(()=>{var f;return!c.value&&e.root&&i.value&&(f=t.collapsedIconSize)!==null&&f!==void 0?f:t.iconSize}),h=C(()=>{if(c.value)return;const{collapsedWidth:f,indent:B,rootIndent:$}=t,{root:z,isGroup:P}=e,g=$===void 0?B:$;return z?i.value?f/2-v.value/2:g:r&&typeof r.paddingLeftRef.value=="number"?B/2+r.paddingLeftRef.value:l&&typeof l.paddingLeftRef.value=="number"?(P?B/2:B)+l.paddingLeftRef.value:0}),S=C(()=>{const{collapsedWidth:f,indent:B,rootIndent:$}=t,{value:z}=v,{root:P}=e;return c.value||!P||!i.value?he:($===void 0?B:$)+z+he-(f+z)/2});return{dropdownPlacement:u,activeIconSize:m,maxIconSize:v,paddingLeft:h,iconMarginRight:S,NMenu:o,NSubmenu:l,NMenuOptionGroup:r}}const Oe={internalKey:{type:[String,Number],required:!0},root:Boolean,isGroup:Boolean,level:{type:Number,required:!0},title:[String,Function],extra:[String,Function]},At=K({name:"MenuDivider",setup(){const e=J(ve),{mergedClsPrefixRef:o,isHorizontalRef:t}=e;return()=>t.value?null:a("div",{class:`${o.value}-menu-divider`})}}),co=Object.assign(Object.assign({},Oe),{tmNode:{type:Object,required:!0},disabled:Boolean,icon:Function,onClick:Function}),Ot=Pe(co),Bt=K({name:"MenuOption",props:co,setup(e){const o=Ae(e),{NSubmenu:t,NMenu:i,NMenuOptionGroup:l}=o,{props:r,mergedClsPrefixRef:c,mergedCollapsedRef:u}=i,v=t?t.mergedDisabledRef:l?l.mergedDisabledRef:{value:!1},m=C(()=>v.value||e.disabled);function h(f){const{onClick:B}=e;B&&B(f)}function S(f){m.value||(i.doSelect(e.internalKey,e.tmNode.rawNode),h(f))}return{mergedClsPrefix:c,dropdownPlacement:o.dropdownPlacement,paddingLeft:o.paddingLeft,iconMarginRight:o.iconMarginRight,maxIconSize:o.maxIconSize,activeIconSize:o.activeIconSize,mergedTheme:i.mergedThemeRef,menuProps:r,dropdownEnabled:Ce(()=>e.root&&u.value&&r.mode!=="horizontal"&&!m.value),selected:Ce(()=>i.mergedValueRef.value===e.internalKey),mergedDisabled:m,handleClick:S}},render(){const{mergedClsPrefix:e,mergedTheme:o,tmNode:t,menuProps:{renderLabel:i,nodeProps:l}}=this,r=l==null?void 0:l(t.rawNode);return a("div",Object.assign({},r,{role:"menuitem",class:[`${e}-menu-item`,r==null?void 0:r.class]}),a(Jo,{theme:o.peers.Tooltip,themeOverrides:o.peerOverrides.Tooltip,trigger:"hover",placement:this.dropdownPlacement,disabled:!this.dropdownEnabled||this.title===void 0,internalExtraClass:["menu-tooltip"]},{default:()=>i?i(t.rawNode):le(this.title),trigger:()=>a(so,{tmNode:t,clsPrefix:e,paddingLeft:this.paddingLeft,iconMarginRight:this.iconMarginRight,maxIconSize:this.maxIconSize,activeIconSize:this.activeIconSize,selected:this.selected,title:this.title,extra:this.extra,disabled:this.mergedDisabled,icon:this.icon,onClick:this.handleClick})}))}}),uo=Object.assign(Object.assign({},Oe),{tmNode:{type:Object,required:!0},tmNodes:{type:Array,required:!0}}),Et=Pe(uo),Ht=K({name:"MenuOptionGroup",props:uo,setup(e){const o=Ae(e),{NSubmenu:t}=o,i=C(()=>t!=null&&t.mergedDisabledRef.value?!0:e.tmNode.disabled);ie(_e,{paddingLeftRef:o.paddingLeft,mergedDisabledRef:i});const{mergedClsPrefixRef:l,props:r}=J(ve);return function(){const{value:c}=l,u=o.paddingLeft.value,{nodeProps:v}=r,m=v==null?void 0:v(e.tmNode.rawNode);return a("div",{class:`${c}-menu-item-group`,role:"group"},a("div",Object.assign({},m,{class:[`${c}-menu-item-group-title`,m==null?void 0:m.class],style:[(m==null?void 0:m.style)||"",u!==void 0?`padding-left: ${u}px;`:""]}),le(e.title),e.extra?a(Ne,null," ",le(e.extra)):null),a("div",null,e.tmNodes.map(h=>Be(h,r))))}}});function Ie(e){return e.type==="divider"||e.type==="render"}function Mt(e){return e.type==="divider"}function Be(e,o){const{rawNode:t}=e,{show:i}=t;if(i===!1)return null;if(Ie(t))return Mt(t)?a(At,Object.assign({key:e.key},t.props)):null;const{labelField:l}=o,{key:r,level:c,isGroup:u}=e,v=Object.assign(Object.assign({},t),{title:t.title||t[l],extra:t.titleExtra||t.extra,key:r,internalKey:r,level:c,root:c===0,isGroup:u});return e.children?e.isGroup?a(Ht,pe(v,Et,{tmNode:e,tmNodes:e.children,key:r})):a(Re,pe(v,Lt,{key:r,rawNodes:t[o.childrenField],tmNodes:e.children,tmNode:e})):a(Bt,pe(v,Ot,{key:r,tmNode:e}))}const vo=Object.assign(Object.assign({},Oe),{rawNodes:{type:Array,default:()=>[]},tmNodes:{type:Array,default:()=>[]},tmNode:{type:Object,required:!0},disabled:Boolean,icon:Function,onClick:Function,domId:String,virtualChildActive:{type:Boolean,default:void 0},isEllipsisPlaceholder:Boolean}),Lt=Pe(vo),Re=K({name:"Submenu",props:vo,setup(e){const o=Ae(e),{NMenu:t,NSubmenu:i}=o,{props:l,mergedCollapsedRef:r,mergedThemeRef:c}=t,u=C(()=>{const{disabled:f}=e;return i!=null&&i.mergedDisabledRef.value||l.disabled?!0:f}),v=O(!1);ie(ao,{paddingLeftRef:o.paddingLeft,mergedDisabledRef:u}),ie(_e,null);function m(){const{onClick:f}=e;f&&f()}function h(){u.value||(r.value||t.toggleExpand(e.internalKey),m())}function S(f){v.value=f}return{menuProps:l,mergedTheme:c,doSelect:t.doSelect,inverted:t.invertedRef,isHorizontal:t.isHorizontalRef,mergedClsPrefix:t.mergedClsPrefixRef,maxIconSize:o.maxIconSize,activeIconSize:o.activeIconSize,iconMarginRight:o.iconMarginRight,dropdownPlacement:o.dropdownPlacement,dropdownShow:v,paddingLeft:o.paddingLeft,mergedDisabled:u,mergedValue:t.mergedValueRef,childActive:Ce(()=>{var f;return(f=e.virtualChildActive)!==null&&f!==void 0?f:t.activePathRef.value.includes(e.internalKey)}),collapsed:C(()=>l.mode==="horizontal"?!1:r.value?!0:!t.mergedExpandedKeysRef.value.includes(e.internalKey)),dropdownEnabled:C(()=>!u.value&&(l.mode==="horizontal"||r.value)),handlePopoverShowChange:S,handleClick:h}},render(){var e;const{mergedClsPrefix:o,menuProps:{renderIcon:t,renderLabel:i}}=this,l=()=>{const{isHorizontal:c,paddingLeft:u,collapsed:v,mergedDisabled:m,maxIconSize:h,activeIconSize:S,title:f,childActive:B,icon:$,handleClick:z,menuProps:{nodeProps:P},dropdownShow:g,iconMarginRight:d,tmNode:b,mergedClsPrefix:E,isEllipsisPlaceholder:A,extra:k}=this,y=P==null?void 0:P(b.rawNode);return a("div",Object.assign({},y,{class:[`${E}-menu-item`,y==null?void 0:y.class],role:"menuitem"}),a(so,{tmNode:b,paddingLeft:u,collapsed:v,disabled:m,iconMarginRight:d,maxIconSize:h,activeIconSize:S,title:f,extra:k,showArrow:!c,childActive:B,clsPrefix:E,icon:$,hover:g,onClick:z,isEllipsisPlaceholder:A}))},r=()=>a(Ke,null,{default:()=>{const{tmNodes:c,collapsed:u}=this;return u?null:a("div",{class:`${o}-submenu-children`,role:"menu"},c.map(v=>Be(v,this.menuProps)))}});return this.root?a(ro,Object.assign({size:"large",trigger:"hover"},(e=this.menuProps)===null||e===void 0?void 0:e.dropdownProps,{themeOverrides:this.mergedTheme.peerOverrides.Dropdown,theme:this.mergedTheme.peers.Dropdown,builtinThemeOverrides:{fontSizeLarge:"14px",optionIconSizeLarge:"18px"},value:this.mergedValue,disabled:!this.dropdownEnabled,placement:this.dropdownPlacement,keyField:this.menuProps.keyField,labelField:this.menuProps.labelField,childrenField:this.menuProps.childrenField,onUpdateShow:this.handlePopoverShowChange,options:this.rawNodes,onSelect:this.doSelect,inverted:this.inverted,renderIcon:t,renderLabel:i}),{default:()=>a("div",{class:`${o}-submenu`,role:"menu","aria-expanded":!this.collapsed,id:this.domId},l(),this.isHorizontal?null:r())}):a("div",{class:`${o}-submenu`,role:"menu","aria-expanded":!this.collapsed,id:this.domId},l(),r())}}),Ft=Object.assign(Object.assign({},G.props),{options:{type:Array,default:()=>[]},collapsed:{type:Boolean,default:void 0},collapsedWidth:{type:Number,default:48},iconSize:{type:Number,default:20},collapsedIconSize:{type:Number,default:24},rootIndent:Number,indent:{type:Number,default:32},labelField:{type:String,default:"label"},keyField:{type:String,default:"key"},childrenField:{type:String,default:"children"},disabledField:{type:String,default:"disabled"},defaultExpandAll:Boolean,defaultExpandedKeys:Array,expandedKeys:Array,value:[String,Number],defaultValue:{type:[String,Number],default:null},mode:{type:String,default:"vertical"},watchProps:{type:Array,default:void 0},disabled:Boolean,show:{type:Boolean,default:!0},inverted:Boolean,"onUpdate:expandedKeys":[Function,Array],onUpdateExpandedKeys:[Function,Array],onUpdateValue:[Function,Array],"onUpdate:value":[Function,Array],expandIcon:Function,renderIcon:Function,renderLabel:Function,renderExtra:Function,dropdownProps:Object,accordion:Boolean,nodeProps:Function,dropdownPlacement:{type:String,default:"bottom"},responsive:Boolean,items:Array,onOpenNamesChange:[Function,Array],onSelect:[Function,Array],onExpandedNamesChange:[Function,Array],expandedNames:Array,defaultExpandedNames:Array}),jt=K({name:"Menu",inheritAttrs:!1,props:Ft,setup(e){const{mergedClsPrefixRef:o,inlineThemeDisabled:t}=se(e),i=G("Menu","-menu",_t,Fo,e,o),l=J(no,null),r=C(()=>{var R;const{collapsed:H}=e;if(H!==void 0)return H;if(l){const{collapseModeRef:n,collapsedRef:T}=l;if(n.value==="width")return(R=T.value)!==null&&R!==void 0?R:!1}return!1}),c=C(()=>{const{keyField:R,childrenField:H,disabledField:n}=e;return ge(e.items||e.options,{getIgnored(T){return Ie(T)},getChildren(T){return T[H]},getDisabled(T){return T[n]},getKey(T){var L;return(L=T[R])!==null&&L!==void 0?L:T.name}})}),u=C(()=>new Set(c.value.treeNodes.map(R=>R.key))),{watchProps:v}=e,m=O(null);v!=null&&v.includes("defaultValue")?ye(()=>{m.value=e.defaultValue}):m.value=e.defaultValue;const h=re(e,"value"),S=Se(h,m),f=O([]),B=()=>{f.value=e.defaultExpandAll?c.value.getNonLeafKeys():e.defaultExpandedNames||e.defaultExpandedKeys||c.value.getPath(S.value,{includeSelf:!1}).keyPath};v!=null&&v.includes("defaultExpandedKeys")?ye(B):B();const $=nt(e,["expandedNames","expandedKeys"]),z=Se($,f),P=C(()=>c.value.treeNodes),g=C(()=>c.value.getPath(S.value).keyPath);ie(ve,{props:e,mergedCollapsedRef:r,mergedThemeRef:i,mergedValueRef:S,mergedExpandedKeysRef:z,activePathRef:g,mergedClsPrefixRef:o,isHorizontalRef:C(()=>e.mode==="horizontal"),invertedRef:re(e,"inverted"),doSelect:d,toggleExpand:E});function d(R,H){const{"onUpdate:value":n,onUpdateValue:T,onSelect:L}=e;T&&q(T,R,H),n&&q(n,R,H),L&&q(L,R,H),m.value=R}function b(R){const{"onUpdate:expandedKeys":H,onUpdateExpandedKeys:n,onExpandedNamesChange:T,onOpenNamesChange:L}=e;H&&q(H,R),n&&q(n,R),T&&q(T,R),L&&q(L,R),f.value=R}function E(R){const H=Array.from(z.value),n=H.findIndex(T=>T===R);if(~n)H.splice(n,1);else{if(e.accordion&&u.value.has(R)){const T=H.findIndex(L=>u.value.has(L));T>-1&&H.splice(T,1)}H.push(R)}b(H)}const A=R=>{const H=c.value.getPath(R??S.value,{includeSelf:!1}).keyPath;if(!H.length)return;const n=Array.from(z.value),T=new Set([...n,...H]);e.accordion&&u.value.forEach(L=>{T.has(L)&&!H.includes(L)&&T.delete(L)}),b(Array.from(T))},k=C(()=>{const{inverted:R}=e,{common:{cubicBezierEaseInOut:H},self:n}=i.value,{borderRadius:T,borderColorHorizontal:L,fontSize:xo,itemHeight:yo,dividerColor:Co}=n,s={"--n-divider-color":Co,"--n-bezier":H,"--n-font-size":xo,"--n-border-color-horizontal":L,"--n-border-radius":T,"--n-item-height":yo};return R?(s["--n-group-text-color"]=n.groupTextColorInverted,s["--n-color"]=n.colorInverted,s["--n-item-text-color"]=n.itemTextColorInverted,s["--n-item-text-color-hover"]=n.itemTextColorHoverInverted,s["--n-item-text-color-active"]=n.itemTextColorActiveInverted,s["--n-item-text-color-child-active"]=n.itemTextColorChildActiveInverted,s["--n-item-text-color-child-active-hover"]=n.itemTextColorChildActiveInverted,s["--n-item-text-color-active-hover"]=n.itemTextColorActiveHoverInverted,s["--n-item-icon-color"]=n.itemIconColorInverted,s["--n-item-icon-color-hover"]=n.itemIconColorHoverInverted,s["--n-item-icon-color-active"]=n.itemIconColorActiveInverted,s["--n-item-icon-color-active-hover"]=n.itemIconColorActiveHoverInverted,s["--n-item-icon-color-child-active"]=n.itemIconColorChildActiveInverted,s["--n-item-icon-color-child-active-hover"]=n.itemIconColorChildActiveHoverInverted,s["--n-item-icon-color-collapsed"]=n.itemIconColorCollapsedInverted,s["--n-item-text-color-horizontal"]=n.itemTextColorHorizontalInverted,s["--n-item-text-color-hover-horizontal"]=n.itemTextColorHoverHorizontalInverted,s["--n-item-text-color-active-horizontal"]=n.itemTextColorActiveHorizontalInverted,s["--n-item-text-color-child-active-horizontal"]=n.itemTextColorChildActiveHorizontalInverted,s["--n-item-text-color-child-active-hover-horizontal"]=n.itemTextColorChildActiveHoverHorizontalInverted,s["--n-item-text-color-active-hover-horizontal"]=n.itemTextColorActiveHoverHorizontalInverted,s["--n-item-icon-color-horizontal"]=n.itemIconColorHorizontalInverted,s["--n-item-icon-color-hover-horizontal"]=n.itemIconColorHoverHorizontalInverted,s["--n-item-icon-color-active-horizontal"]=n.itemIconColorActiveHorizontalInverted,s["--n-item-icon-color-active-hover-horizontal"]=n.itemIconColorActiveHoverHorizontalInverted,s["--n-item-icon-color-child-active-horizontal"]=n.itemIconColorChildActiveHorizontalInverted,s["--n-item-icon-color-child-active-hover-horizontal"]=n.itemIconColorChildActiveHoverHorizontalInverted,s["--n-arrow-color"]=n.arrowColorInverted,s["--n-arrow-color-hover"]=n.arrowColorHoverInverted,s["--n-arrow-color-active"]=n.arrowColorActiveInverted,s["--n-arrow-color-active-hover"]=n.arrowColorActiveHoverInverted,s["--n-arrow-color-child-active"]=n.arrowColorChildActiveInverted,s["--n-arrow-color-child-active-hover"]=n.arrowColorChildActiveHoverInverted,s["--n-item-color-hover"]=n.itemColorHoverInverted,s["--n-item-color-active"]=n.itemColorActiveInverted,s["--n-item-color-active-hover"]=n.itemColorActiveHoverInverted,s["--n-item-color-active-collapsed"]=n.itemColorActiveCollapsedInverted):(s["--n-group-text-color"]=n.groupTextColor,s["--n-color"]=n.color,s["--n-item-text-color"]=n.itemTextColor,s["--n-item-text-color-hover"]=n.itemTextColorHover,s["--n-item-text-color-active"]=n.itemTextColorActive,s["--n-item-text-color-child-active"]=n.itemTextColorChildActive,s["--n-item-text-color-child-active-hover"]=n.itemTextColorChildActiveHover,s["--n-item-text-color-active-hover"]=n.itemTextColorActiveHover,s["--n-item-icon-color"]=n.itemIconColor,s["--n-item-icon-color-hover"]=n.itemIconColorHover,s["--n-item-icon-color-active"]=n.itemIconColorActive,s["--n-item-icon-color-active-hover"]=n.itemIconColorActiveHover,s["--n-item-icon-color-child-active"]=n.itemIconColorChildActive,s["--n-item-icon-color-child-active-hover"]=n.itemIconColorChildActiveHover,s["--n-item-icon-color-collapsed"]=n.itemIconColorCollapsed,s["--n-item-text-color-horizontal"]=n.itemTextColorHorizontal,s["--n-item-text-color-hover-horizontal"]=n.itemTextColorHoverHorizontal,s["--n-item-text-color-active-horizontal"]=n.itemTextColorActiveHorizontal,s["--n-item-text-color-child-active-horizontal"]=n.itemTextColorChildActiveHorizontal,s["--n-item-text-color-child-active-hover-horizontal"]=n.itemTextColorChildActiveHoverHorizontal,s["--n-item-text-color-active-hover-horizontal"]=n.itemTextColorActiveHoverHorizontal,s["--n-item-icon-color-horizontal"]=n.itemIconColorHorizontal,s["--n-item-icon-color-hover-horizontal"]=n.itemIconColorHoverHorizontal,s["--n-item-icon-color-active-horizontal"]=n.itemIconColorActiveHorizontal,s["--n-item-icon-color-active-hover-horizontal"]=n.itemIconColorActiveHoverHorizontal,s["--n-item-icon-color-child-active-horizontal"]=n.itemIconColorChildActiveHorizontal,s["--n-item-icon-color-child-active-hover-horizontal"]=n.itemIconColorChildActiveHoverHorizontal,s["--n-arrow-color"]=n.arrowColor,s["--n-arrow-color-hover"]=n.arrowColorHover,s["--n-arrow-color-active"]=n.arrowColorActive,s["--n-arrow-color-active-hover"]=n.arrowColorActiveHover,s["--n-arrow-color-child-active"]=n.arrowColorChildActive,s["--n-arrow-color-child-active-hover"]=n.arrowColorChildActiveHover,s["--n-item-color-hover"]=n.itemColorHover,s["--n-item-color-active"]=n.itemColorActive,s["--n-item-color-active-hover"]=n.itemColorActiveHover,s["--n-item-color-active-collapsed"]=n.itemColorActiveCollapsed),s}),y=t?ce("menu",C(()=>e.inverted?"a":"b"),k,e):void 0,I=Mo(),V=O(null),M=O(null);let j=!0;const X=()=>{var R;j?j=!1:(R=V.value)===null||R===void 0||R.sync({showAllItemsBeforeCalculate:!0})};function Q(){return document.getElementById(I)}const ee=O(-1);function mo(R){ee.value=e.options.length-R}function ho(R){R||(ee.value=-1)}const fo=C(()=>{const R=ee.value;return{children:R===-1?[]:e.options.slice(R)}}),po=C(()=>{const{childrenField:R,disabledField:H,keyField:n}=e;return ge([fo.value],{getIgnored(T){return Ie(T)},getChildren(T){return T[R]},getDisabled(T){return T[H]},getKey(T){var L;return(L=T[n])!==null&&L!==void 0?L:T.name}})}),go=C(()=>ge([{}]).treeNodes[0]);function bo(){var R;if(ee.value===-1)return a(Re,{root:!0,level:0,key:"__ellpisisGroupPlaceholder__",internalKey:"__ellpisisGroupPlaceholder__",title:"···",tmNode:go.value,domId:I,isEllipsisPlaceholder:!0});const H=po.value.treeNodes[0],n=g.value,T=!!(!((R=H.children)===null||R===void 0)&&R.some(L=>n.includes(L.key)));return a(Re,{level:0,root:!0,key:"__ellpisisGroup__",internalKey:"__ellpisisGroup__",title:"···",virtualChildActive:T,tmNode:H,domId:I,rawNodes:H.rawNode.children||[],tmNodes:H.children||[],isEllipsisPlaceholder:!0})}return{mergedClsPrefix:o,controlledExpandedKeys:$,uncontrolledExpanededKeys:f,mergedExpandedKeys:z,uncontrolledValue:m,mergedValue:S,activePath:g,tmNodes:P,mergedTheme:i,mergedCollapsed:r,cssVars:t?void 0:k,themeClass:y==null?void 0:y.themeClass,overflowRef:V,counterRef:M,updateCounter:()=>{},onResize:X,onUpdateOverflow:ho,onUpdateCount:mo,renderCounter:bo,getCounter:Q,onRender:y==null?void 0:y.onRender,showOption:A,deriveResponsiveState:X}},render(){const{mergedClsPrefix:e,mode:o,themeClass:t,onRender:i}=this;i==null||i();const l=()=>this.tmNodes.map(v=>Be(v,this.$props)),c=o==="horizontal"&&this.responsive,u=()=>a("div",Lo(this.$attrs,{role:o==="horizontal"?"menubar":"menu",class:[`${e}-menu`,t,`${e}-menu--${o}`,c&&`${e}-menu--responsive`,this.mergedCollapsed&&`${e}-menu--collapsed`],style:this.cssVars}),c?a(ot,{ref:"overflowRef",onUpdateOverflow:this.onUpdateOverflow,getCounter:this.getCounter,onUpdateCount:this.onUpdateCount,updateCounter:this.updateCounter,style:{width:"100%",display:"flex",overflow:"hidden"}},{default:l,counter:this.renderCounter}):l());return c?a(Ue,{onResize:this.onResize},{default:u}):u()}}),Vt={class:"cp-input"},Kt={key:0,class:"cp-list"},Dt=["onMouseenter","onClick"],Ut={class:"cp-email"},Yt={key:0,class:"cp-extra"},Wt={class:"cp-status"},Gt={class:"cp-hint"},qt=K({__name:"CommandPalette",props:{show:{type:Boolean}},emits:["update:show"],setup(e,{emit:o}){const t=e,i=o,l=oo(),r=O(""),c=O([]),u=O(0),v=O(!1),m=O(null);let h,S=0;const f={admin:{label:"母号",color:"#2f6bd6",route:"/adobe"},member:{label:"子号",color:"#18a058",route:"/pool"},email:{label:"邮箱",color:"#0ea5b7",route:"/email"}};fe(()=>t.show,g=>{g?(S++,r.value="",c.value=[],u.value=0,xe(()=>{var d;return(d=m.value)==null?void 0:d.focus()})):h&&(clearTimeout(h),h=void 0)});function B(){u.value=0,h&&clearTimeout(h);const g=r.value.trim();if(g.length<2){S++,c.value=[];return}const d=++S;h=setTimeout(async()=>{v.value=!0;try{const b=await Go(g);d===S&&t.show&&r.value.trim()===g&&(c.value=b.results||[])}catch{d===S&&(c.value=[])}finally{d===S&&(v.value=!1)}},250)}function $(g){const d=f[g.type];i("update:show",!1),l.push({path:d.route,query:{kw:g.email||String(g.id)}})}function z(g){if(!(g.isComposing||g.keyCode===229))if(g.key==="ArrowDown")g.preventDefault(),u.value=Math.min(u.value+1,c.value.length-1);else if(g.key==="ArrowUp")g.preventDefault(),u.value=Math.max(u.value-1,0);else if(g.key==="Enter"){g.preventDefault();const d=c.value[u.value];d&&$(d)}else g.key==="Escape"&&i("update:show",!1)}const P=C(()=>r.value.trim().length<2?"输入邮箱、账号 ID 或组织号搜索(至少 2 个字符)":v.value?"搜索中…":c.value.length?c.value.length+" 条结果 · ↑↓ 选择 · Enter 跳转":"没有匹配结果");return Je(()=>{h&&clearTimeout(h)}),(g,d)=>(W(),ze(F(jo),{show:e.show,"mask-closable":!0,"auto-focus":!1,"transform-origin":"center","onUpdate:show":d[1]||(d[1]=b=>i("update:show",b))},{default:U(()=>[N("div",{class:"cp",onKeydown:z},[N("div",Vt,[d[2]||(d[2]=N("svg",{viewBox:"0 0 24 24",width:"18",height:"18",class:"cp-ic"},[N("path",{fill:"currentColor",d:"M15.5 14h-.8l-.3-.3a6.5 6.5 0 1 0-.7.7l.3.3v.8l5 5 1.5-1.5-5-5zm-6 0A4.5 4.5 0 1 1 14 9.5 4.5 4.5 0 0 1 9.5 14z"})],-1)),Qe(N("input",{ref_key:"inputRef",ref:m,"onUpdate:modelValue":d[0]||(d[0]=b=>r.value=b),class:"cp-field",placeholder:"搜索母号 / 子号 / 邮箱…",spellcheck:"false",onInput:B},null,544),[[Vo,r.value]]),d[3]||(d[3]=N("kbd",{class:"cp-esc"},"Esc",-1))]),c.value.length?(W(),Z("div",Kt,[(W(!0),Z(Ne,null,eo(c.value,(b,E)=>(W(),Z("div",{key:b.type+"-"+b.id,class:Ko(["cp-item",{on:E===u.value}]),onMouseenter:A=>u.value=E,onClick:A=>$(b)},[N("span",{class:"cp-tag",style:ue({background:f[b.type].color})},Y(f[b.type].label),5),N("span",Ut,Y(b.email||"#"+b.id),1),b.extra?(W(),Z("span",Yt,Y(b.extra),1)):we("",!0),N("span",Wt,Y(b.status),1)],42,Dt))),128))])):we("",!0),N("div",Gt,Y(P.value),1)],32)]),_:1},8,["show"]))}}),Xt=to(qt,[["__scopeId","data-v-a1db1eb4"]]),Zt={class:"logo"},Jt={class:"logo-text"},Qt={class:"header-title"},er={class:"header-right"},or=["title"],tr={class:"health-grade"},rr=["title"],nr={class:"alert-pop"},lr={class:"alert-pop-head"},ir={class:"alert-pop-count"},ar={key:0,class:"alert-list"},sr={class:"alert-body"},cr={class:"alert-title"},dr={class:"alert-detail"},ur=["title"],vr={key:0,viewBox:"0 0 24 24"},mr={key:1,viewBox:"0 0 24 24"},hr={class:"user-info"},fr={class:"username"},pr=K({__name:"AdminLayout",setup(e){const o=oo(),t=Uo(),i=Xo(),l=O(!1),{isDark:r,toggle:c}=Yo(),u=O(!1);function v(y){(y.ctrlKey||y.metaKey)&&(y.key==="k"||y.key==="K")&&(y.preventDefault(),u.value=!u.value)}const m=O([]),h=O(null),S=O("");let f;async function B(){var y,I,V;try{const M=await qo();m.value=((y=M.health)==null?void 0:y.alerts)||[],h.value=((I=M.health)==null?void 0:I.score)??null,S.value=((V=M.health)==null?void 0:V.grade)||""}catch{}}const $=C(()=>m.value.filter(y=>y.level==="critical").length),z=C(()=>h.value==null?"#97a0ad":h.value>=90?"#18a058":h.value>=75?"#2f9e44":h.value>=60?"#f0a020":"#d03050"),P={critical:{color:"#d03050",label:"严重"},warning:{color:"#f0a020",label:"警告"},info:{color:"#2f6bd6",label:"提示"}};function g(y){return()=>a(me,null,{default:()=>a("svg",{viewBox:"0 0 24 24",width:18,height:18},[a("path",{fill:"currentColor",d:y})])})}const d=C(()=>[{label:()=>a(oe,{to:"/dashboard"},{default:()=>"运营驾驶舱"}),key:"dashboard",icon:g("M13 3v6h8V3zM13 21h8V11h-8zM3 21h8v-6H3zM3 13h8V3H3z")},{label:()=>a(oe,{to:"/adobe"},{default:()=>"母号管理"}),key:"adobe",icon:g("M9 22V10h3.2c3.6 0 5.8 2.3 5.8 6s-2.2 6-5.8 6H9zm3-2.6h.2c1.9 0 3-1.2 3-3.4s-1.1-3.4-3-3.4H12v6.8z")},{label:()=>a(oe,{to:"/pool"},{default:()=>"号池管理"}),key:"pool",icon:g("M12 2 2 7l10 5 10-5-10-5zm0 7.2L4.5 7 12 4.3 19.5 7 12 9.2zM2 12l10 5 10-5-2.2-1.1L12 14.5 4.2 10.9 2 12zm0 5 10 5 10-5-2.2-1.1L12 19.5 4.2 15.9 2 17z")},{label:()=>a(oe,{to:"/jobs"},{default:()=>"拉号任务"}),key:"jobs",icon:g("M13 2.05v2.02c3.95.49 7 3.85 7 7.93 0 4.42-3.58 8-8 8s-8-3.58-8-8c0-2.05.77-3.92 2.04-5.34L7.5 8.07A5.96 5.96 0 0 0 6 12c0 3.31 2.69 6 6 6s6-2.69 6-6a6 6 0 0 0-5-5.91V8l4-4-4-4v2.05zM11 7h2v6h-2V7z")},{label:()=>a(oe,{to:"/email"},{default:()=>"邮箱管理"}),key:"email",icon:g("M20 4H4a2 2 0 0 0-2 2v12a2 2 0 0 0 2 2h16a2 2 0 0 0 2-2V6a2 2 0 0 0-2-2zm0 4l-8 5-8-5V6l8 5 8-5v2z")},{label:()=>a(oe,{to:"/logs"},{default:()=>"日志管理"}),key:"logs",icon:g("M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8l-6-6zm-1 7V3.5L18.5 9H13zM8 13h8v2H8v-2zm0 4h8v2H8v-2z")},{label:()=>a(oe,{to:"/settings"},{default:()=>"设置"}),key:"settings",icon:g("M19.4 13a7.8 7.8 0 0 0 0-2l2-1.6-2-3.4-2.4 1a7.6 7.6 0 0 0-1.7-1l-.4-2.6H10.1l-.4 2.6a7.6 7.6 0 0 0-1.7 1l-2.4-1-2 3.4L3.6 11a7.8 7.8 0 0 0 0 2l-2 1.6 2 3.4 2.4-1c.5.4 1.1.7 1.7 1l.4 2.6h3.8l.4-2.6c.6-.3 1.2-.6 1.7-1l2.4 1 2-3.4-2-1.6zM12 15.5A3.5 3.5 0 1 1 12 8.5a3.5 3.5 0 0 1 0 7z")}]),b=C(()=>t.name),E=[{label:"退出登录",key:"logout"}];function A(y){var I;y==="logout"&&(i.clear(),(I=window.$message)==null||I.success("已退出登录"),o.push({name:"login"}))}ke(()=>{B(),f=setInterval(B,6e4),window.addEventListener("keydown",v),i.userInfo||i.fetchUserInfo().catch(()=>{})}),Je(()=>{f&&clearInterval(f),window.removeEventListener("keydown",v)});function k(){o.push("/dashboard")}return(y,I)=>{const V=Wo("RouterView");return W(),ze(F(Fe),{"has-sider":"",style:{height:"100vh"}},{default:U(()=>[D(F($t),{bordered:"","collapse-mode":"width","collapsed-width":64,width:220,collapsed:l.value,"show-trigger":"",onCollapse:I[0]||(I[0]=M=>l.value=!0),onExpand:I[1]||(I[1]=M=>l.value=!1)},{default:U(()=>[N("div",Zt,[I[5]||(I[5]=N("svg",{viewBox:"0 0 32 32",width:"28",height:"28"},[N("rect",{width:"32",height:"32",rx:"7",fill:"#1890ff"}),N("path",{d:"M9 22V10h3.2c3.6 0 5.8 2.3 5.8 6s-2.2 6-5.8 6H9zm3-2.6h.2c1.9 0 3-1.2 3-3.4s-1.1-3.4-3-3.4H12v6.8zM20 22V10h2.8v12H20z",fill:"#fff"})],-1)),Qe(N("span",Jt,"okad 管理平台",512),[[Do,!l.value]])]),D(F(jt),{value:b.value,collapsed:l.value,"collapsed-width":64,options:d.value},null,8,["value","collapsed","options"])]),_:1},8,["collapsed"]),D(F(Fe),null,{default:U(()=>[D(F(Rt),{bordered:"",class:"header"},{default:U(()=>[N("div",Qt,Y(F(t).meta.title),1),N("div",er,[N("button",{class:"search-trigger",title:"搜索母号/子号/邮箱 (Ctrl+K)",onClick:I[2]||(I[2]=M=>u.value=!0)},[D(F(me),{size:"16"},{default:U(()=>[...I[6]||(I[6]=[N("svg",{viewBox:"0 0 24 24"},[N("path",{fill:"currentColor",d:"M15.5 14h-.8l-.3-.3a6.5 6.5 0 1 0-.7.7l.3.3v.8l5 5 1.5-1.5-5-5zm-6 0A4.5 4.5 0 1 1 14 9.5 4.5 4.5 0 0 1 9.5 14z"})],-1)])]),_:1}),I[7]||(I[7]=N("span",{class:"search-ph"},"搜索…",-1)),I[8]||(I[8]=N("kbd",{class:"search-kbd"},"Ctrl K",-1))]),h.value!==null?(W(),Z("div",{key:0,class:"health-chip",title:"系统健康分 "+h.value,onClick:k},[N("span",{class:"health-dot",style:ue({background:z.value})},null,4),N("span",{class:"health-score",style:ue({color:z.value})},Y(h.value),5),N("span",tr,Y(S.value),1)],8,or)):we("",!0),D(F(tt),{trigger:"click",placement:"bottom-end",width:320},{trigger:U(()=>[N("button",{class:"icon-btn",title:m.value.length?m.value.length+" 条告警":"暂无告警"},[D(F(xt),{value:m.value.length,max:99,type:$.value?"error":"warning",show:m.value.length>0},{default:U(()=>[D(F(me),{size:"20"},{default:U(()=>[...I[9]||(I[9]=[N("svg",{viewBox:"0 0 24 24"},[N("path",{fill:"currentColor",d:"M12 22a2.5 2.5 0 0 0 2.45-2h-4.9A2.5 2.5 0 0 0 12 22zm6.5-6v-5.5a6.5 6.5 0 0 0-5-6.32V3.5a1.5 1.5 0 0 0-3 0v.68a6.5 6.5 0 0 0-5 6.32V16l-2 2v1h17v-1l-2-2z"})],-1)])]),_:1})]),_:1},8,["value","type","show"])],8,rr)]),default:U(()=>[N("div",nr,[N("div",lr,[I[10]||(I[10]=N("span",null,"系统告警",-1)),N("span",ir,Y(m.value.length)+" 条",1)]),m.value.length?(W(),Z("div",ar,[(W(!0),Z(Ne,null,eo(m.value,(M,j)=>{var X,Q,ee;return W(),Z("div",{key:j,class:"alert-item",onClick:k},[N("span",{class:"alert-bar",style:ue({background:(X=P[M.level])==null?void 0:X.color})},null,4),N("div",sr,[N("div",cr,[N("span",{class:"alert-tag",style:ue({color:(Q=P[M.level])==null?void 0:Q.color})},Y((ee=P[M.level])==null?void 0:ee.label),5),Me(" "+Y(M.title),1)]),N("div",dr,Y(M.detail),1)])])}),128))])):(W(),ze(F(rt),{key:1,description:"一切正常,无告警",size:"small",style:{padding:"16px 0"}}))])]),_:1}),N("button",{class:"icon-btn",title:F(r)?"切换浅色":"切换深色",onClick:I[3]||(I[3]=(...M)=>F(c)&&F(c)(...M))},[D(F(me),{size:"20"},{default:U(()=>[F(r)?(W(),Z("svg",vr,[...I[11]||(I[11]=[N("path",{d:"M12 7a5 5 0 1 0 0 10 5 5 0 0 0 0-10zm0-5v2m0 16v2M4.2 4.2l1.4 1.4m12.8 12.8 1.4 1.4M2 12h2m16 0h2M4.2 19.8l1.4-1.4M18.4 5.6l1.4-1.4",stroke:"currentColor","stroke-width":"1.6","stroke-linecap":"round",fill:"none"},null,-1)])])):(W(),Z("svg",mr,[...I[12]||(I[12]=[N("path",{fill:"currentColor",d:"M12.3 3a9 9 0 1 0 8.7 11.3A7 7 0 0 1 12.3 3z"},null,-1)])]))]),_:1})],8,ur),D(F(ro),{options:E,onSelect:A},{default:U(()=>{var M;return[N("div",hr,[D(F(ht),{round:"",size:"small",style:{background:"#1890ff"}},{default:U(()=>{var j,X;return[Me(Y(((X=(j=F(i).userInfo)==null?void 0:j.nickname)==null?void 0:X.charAt(0))||"U"),1)]}),_:1}),N("span",fr,Y(((M=F(i).userInfo)==null?void 0:M.nickname)||"管理员"),1)])]}),_:1})])]),_:1}),D(F(wt),{class:"content"},{default:U(()=>[D(V)]),_:1})]),_:1}),D(Xt,{show:u.value,"onUpdate:show":I[4]||(I[4]=M=>u.value=M)},null,8,["show"])]),_:1})}}}),kr=to(pr,[["__scopeId","data-v-686786f2"]]);export{kr as default};
