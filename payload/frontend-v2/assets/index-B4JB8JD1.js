import{M as ke,m as A,au as dt,av as ut,aw as ye,ax as ct,R as Ze,p as H,s as G,x as oe,y as ae,d as le,k as u,G as xe,J as Oe,l as de,H as me,I as Le,r as k,t as ce,ai as He,ay as ft,U as Fe,ad as mt,a0 as De,ap as We,X as gt,K as ht,L as vt,az as pt,aA as Ue,aB as bt,a2 as pe,aC as yt,aD as wt,aE as $t,q as Ce,aF as kt,aG as xt,aH as Ct,aI as St,aJ as zt,aK as Rt,a4 as ue,aL as Tt,aM as jt,aN as Bt,Z as Nt,_ as Et,A as Mt,aO as Ht,S as Pt,n as qe,aP as Xe,af as It,c as be,aa as Ee,e as l,u as a,w as d,ah as we,o as Z,f as M,am as se,B as W,i as et,ag as re,al as Pe,j as $e,aQ as _t,aR as Ke,h as Ot,g as Lt}from"./index-CrrzYg-U.js";import{N as Ft,l as Dt,b as Ut,a as At,c as Wt,g as qt,d as Xt,e as Kt,f as Vt,h as Yt,u as Gt,i as Jt,j as Qt,k as Zt,t as en,m as tn}from"./adobe-DKrXd9Ds.js";import{g as nn,t as on}from"./dashboard-CE7SxDew.js";import{B as rn,S as an}from"./BatchImportModal-COnkF9EJ.js";import{a as Ve,b as ln}from"./auth-DQiNxie4.js";import{f as Ye}from"./get-Cpzh6RY9.js";import{N as q,a as J}from"./text-C52gYURp.js";import{N as tt,a as sn,b as Ge}from"./DataTable-Bp7hAEDt.js";import{a as dn,b as Q}from"./Tag-Bwosooua.js";import{N as Ie,a as un}from"./Dropdown-yKLdvPjR.js";import{N as ie}from"./Input-fL4pqH-9.js";import{N as _e}from"./InputNumber-xGWV9xwu.js";import{N as cn,a as fe}from"./FormItem-DqgsvfhG.js";import"./_plugin-vue_export-helper-DlAUqK2U.js";import"./use-compitable-NwYE7-py.js";import"./Checkbox-DxqZLUeA.js";import"./Icon-CHxV3kM7.js";function nt(e,t){const r=ke(dt,null);return A(()=>e.hljs||(r==null?void 0:r.mergedHljsRef.value))}var fn=/\s/;function mn(e){for(var t=e.length;t--&&fn.test(e.charAt(t)););return t}var gn=/^\s+/;function hn(e){return e&&e.slice(0,mn(e)+1).replace(gn,"")}var Je=NaN,vn=/^[-+]0x[0-9a-f]+$/i,pn=/^0b[01]+$/i,bn=/^0o[0-7]+$/i,yn=parseInt;function Qe(e){if(typeof e=="number")return e;if(ut(e))return Je;if(ye(e)){var t=typeof e.valueOf=="function"?e.valueOf():e;e=ye(t)?t+"":t}if(typeof e!="string")return e===0?e:+e;e=hn(e);var r=pn.test(e);return r||bn.test(e)?yn(e.slice(2),r?2:8):vn.test(e)?Je:+e}var Me=function(){return ct.Date.now()},wn="Expected a function",$n=Math.max,kn=Math.min;function xn(e,t,r){var g,v,C,S,b,j,w=0,L=!1,F=!1,z=!0;if(typeof e!="function")throw new TypeError(wn);t=Qe(t)||0,ye(r)&&(L=!!r.leading,F="maxWait"in r,C=F?$n(Qe(r.maxWait)||0,t):C,z="trailing"in r?!!r.trailing:z);function m(s){var y=g,T=v;return g=v=void 0,w=s,S=e.apply(T,y),S}function E(s){return w=s,b=setTimeout(O,t),L?m(s):S}function $(s){var y=s-j,T=s-w,f=t-y;return F?kn(f,C-T):f}function D(s){var y=s-j,T=s-w;return j===void 0||y>=t||y<0||F&&T>=C}function O(){var s=Me();if(D(s))return x(s);b=setTimeout(O,$(s))}function x(s){return b=void 0,z&&g?m(s):(g=v=void 0,S)}function R(){b!==void 0&&clearTimeout(b),w=0,g=j=v=b=void 0}function p(){return b===void 0?S:x(Me())}function P(){var s=Me(),y=D(s);if(g=arguments,v=this,j=s,y){if(b===void 0)return E(j);if(F)return clearTimeout(b),b=setTimeout(O,t),m(j)}return b===void 0&&(b=setTimeout(O,t)),S}return P.cancel=R,P.flush=p,P}var Cn="Expected a function";function Sn(e,t,r){var g=!0,v=!0;if(typeof e!="function")throw new TypeError(Cn);return ye(r)&&(g="leading"in r?!!r.leading:g,v="trailing"in r?!!r.trailing:v),xn(e,t,{leading:g,maxWait:t,trailing:v})}function zn(e){const{textColor2:t,fontSize:r,fontWeightStrong:g,textColor3:v}=e;return{textColor:t,fontSize:r,fontWeightStrong:g,"mono-3":"#a0a1a7","hue-1":"#0184bb","hue-2":"#4078f2","hue-3":"#a626a4","hue-4":"#50a14f","hue-5":"#e45649","hue-5-2":"#c91243","hue-6":"#986801","hue-6-2":"#c18401",lineNumberTextColor:v}}const ot={name:"Code",common:Ze,self:zn},Rn=H([G("code",`
 font-size: var(--n-font-size);
 font-family: var(--n-font-family);
 `,[oe("show-line-numbers",`
 display: flex;
 `),ae("line-numbers",`
 user-select: none;
 padding-right: 12px;
 text-align: right;
 transition: color .3s var(--n-bezier);
 color: var(--n-line-number-text-color);
 `),oe("word-wrap",[H("pre",`
 white-space: pre-wrap;
 word-break: break-all;
 `)]),H("pre",`
 margin: 0;
 line-height: inherit;
 font-size: inherit;
 font-family: inherit;
 `),H("[class^=hljs]",`
 color: var(--n-text-color);
 transition: 
 color .3s var(--n-bezier),
 background-color .3s var(--n-bezier);
 `)]),({props:e})=>{const t=`${e.bPrefix}code`;return[`${t} .hljs-comment,
 ${t} .hljs-quote {
 color: var(--n-mono-3);
 font-style: italic;
 }`,`${t} .hljs-doctag,
 ${t} .hljs-keyword,
 ${t} .hljs-formula {
 color: var(--n-hue-3);
 }`,`${t} .hljs-section,
 ${t} .hljs-name,
 ${t} .hljs-selector-tag,
 ${t} .hljs-deletion,
 ${t} .hljs-subst {
 color: var(--n-hue-5);
 }`,`${t} .hljs-literal {
 color: var(--n-hue-1);
 }`,`${t} .hljs-string,
 ${t} .hljs-regexp,
 ${t} .hljs-addition,
 ${t} .hljs-attribute,
 ${t} .hljs-meta-string {
 color: var(--n-hue-4);
 }`,`${t} .hljs-built_in,
 ${t} .hljs-class .hljs-title {
 color: var(--n-hue-6-2);
 }`,`${t} .hljs-attr,
 ${t} .hljs-variable,
 ${t} .hljs-template-variable,
 ${t} .hljs-type,
 ${t} .hljs-selector-class,
 ${t} .hljs-selector-attr,
 ${t} .hljs-selector-pseudo,
 ${t} .hljs-number {
 color: var(--n-hue-6);
 }`,`${t} .hljs-symbol,
 ${t} .hljs-bullet,
 ${t} .hljs-link,
 ${t} .hljs-meta,
 ${t} .hljs-selector-id,
 ${t} .hljs-title {
 color: var(--n-hue-2);
 }`,`${t} .hljs-emphasis {
 font-style: italic;
 }`,`${t} .hljs-strong {
 font-weight: var(--n-font-weight-strong);
 }`,`${t} .hljs-link {
 text-decoration: underline;
 }`]}]),Tn=Object.assign(Object.assign({},me.props),{language:String,code:{type:String,default:""},trim:{type:Boolean,default:!0},hljs:Object,uri:Boolean,inline:Boolean,wordWrap:Boolean,showLineNumbers:Boolean,internalFontSize:Number,internalNoHighlight:Boolean}),jn=le({name:"Code",props:Tn,setup(e,{slots:t}){const{internalNoHighlight:r}=e,{mergedClsPrefixRef:g,inlineThemeDisabled:v}=xe(),C=k(null),S=r?{value:void 0}:nt(e),b=(m,E,$)=>{const{value:D}=S;return!D||!(m&&D.getLanguage(m))?null:D.highlight($?E.trim():E,{language:m}).value},j=A(()=>e.inline||e.wordWrap?!1:e.showLineNumbers),w=()=>{if(t.default)return;const{value:m}=C;if(!m)return;const{language:E}=e,$=e.uri?window.decodeURIComponent(e.code):e.code;if(E){const O=b(E,$,e.trim);if(O!==null){if(e.inline)m.innerHTML=O;else{const x=m.querySelector(".__code__");x&&m.removeChild(x);const R=document.createElement("pre");R.className="__code__",R.innerHTML=O,m.appendChild(R)}return}}if(e.inline){m.textContent=$;return}const D=m.querySelector(".__code__");if(D)D.textContent=$;else{const O=document.createElement("pre");O.className="__code__",O.textContent=$,m.innerHTML="",m.appendChild(O)}};Oe(w),de(ce(e,"language"),w),de(ce(e,"code"),w),r||de(S,w);const L=me("Code","-code",Rn,ot,e,g),F=A(()=>{const{common:{cubicBezierEaseInOut:m,fontFamilyMono:E},self:{textColor:$,fontSize:D,fontWeightStrong:O,lineNumberTextColor:x,"mono-3":R,"hue-1":p,"hue-2":P,"hue-3":s,"hue-4":y,"hue-5":T,"hue-5-2":f,"hue-6":B,"hue-6-2":I}}=L.value,{internalFontSize:X}=e;return{"--n-font-size":X?`${X}px`:D,"--n-font-family":E,"--n-font-weight-strong":O,"--n-bezier":m,"--n-text-color":$,"--n-mono-3":R,"--n-hue-1":p,"--n-hue-2":P,"--n-hue-3":s,"--n-hue-4":y,"--n-hue-5":T,"--n-hue-5-2":f,"--n-hue-6":B,"--n-hue-6-2":I,"--n-line-number-text-color":x}}),z=v?Le("code",A(()=>`${e.internalFontSize||"a"}`),F,e):void 0;return{mergedClsPrefix:g,codeRef:C,mergedShowLineNumbers:j,lineNumbers:A(()=>{let m=1;const E=[];let $=!1;for(const D of e.code)D===`
`?($=!0,E.push(m++)):$=!1;return $||E.push(m++),E.join(`
`)}),cssVars:v?void 0:F,themeClass:z==null?void 0:z.themeClass,onRender:z==null?void 0:z.onRender}},render(){var e,t;const{mergedClsPrefix:r,wordWrap:g,mergedShowLineNumbers:v,onRender:C}=this;return C==null||C(),u("code",{class:[`${r}-code`,this.themeClass,g&&`${r}-code--word-wrap`,v&&`${r}-code--show-line-numbers`],style:this.cssVars,ref:"codeRef"},v?u("pre",{class:`${r}-code__line-numbers`},this.lineNumbers):null,(t=(e=this.$slots).default)===null||t===void 0?void 0:t.call(e))}}),Bn=le({name:"NDrawerContent",inheritAttrs:!1,props:{blockScroll:Boolean,show:{type:Boolean,default:void 0},displayDirective:{type:String,required:!0},placement:{type:String,required:!0},contentClass:String,contentStyle:[Object,String],nativeScrollbar:{type:Boolean,required:!0},scrollbarProps:Object,trapFocus:{type:Boolean,default:!0},autoFocus:{type:Boolean,default:!0},showMask:{type:[Boolean,String],required:!0},maxWidth:Number,maxHeight:Number,minWidth:Number,minHeight:Number,resizable:Boolean,onClickoutside:Function,onAfterLeave:Function,onAfterEnter:Function,onEsc:Function},setup(e){const t=k(!!e.show),r=k(null),g=ke(Ue);let v=0,C="",S=null;const b=k(!1),j=k(!1),w=A(()=>e.placement==="top"||e.placement==="bottom"),{mergedClsPrefixRef:L,mergedRtlRef:F}=xe(e),z=gt("Drawer",F,L),m=s,E=f=>{j.value=!0,v=w.value?f.clientY:f.clientX,C=document.body.style.cursor,document.body.style.cursor=w.value?"ns-resize":"ew-resize",document.body.addEventListener("mousemove",P),document.body.addEventListener("mouseleave",m),document.body.addEventListener("mouseup",s)},$=()=>{S!==null&&(window.clearTimeout(S),S=null),j.value?b.value=!0:S=window.setTimeout(()=>{b.value=!0},300)},D=()=>{S!==null&&(window.clearTimeout(S),S=null),b.value=!1},{doUpdateHeight:O,doUpdateWidth:x}=g,R=f=>{const{maxWidth:B}=e;if(B&&f>B)return B;const{minWidth:I}=e;return I&&f<I?I:f},p=f=>{const{maxHeight:B}=e;if(B&&f>B)return B;const{minHeight:I}=e;return I&&f<I?I:f};function P(f){var B,I;if(j.value)if(w.value){let X=((B=r.value)===null||B===void 0?void 0:B.offsetHeight)||0;const ne=v-f.clientY;X+=e.placement==="bottom"?ne:-ne,X=p(X),O(X),v=f.clientY}else{let X=((I=r.value)===null||I===void 0?void 0:I.offsetWidth)||0;const ne=v-f.clientX;X+=e.placement==="right"?ne:-ne,X=R(X),x(X),v=f.clientX}}function s(){j.value&&(v=0,j.value=!1,document.body.style.cursor=C,document.body.removeEventListener("mousemove",P),document.body.removeEventListener("mouseup",s),document.body.removeEventListener("mouseleave",m))}ht(()=>{e.show&&(t.value=!0)}),de(()=>e.show,f=>{f||s()}),vt(()=>{s()});const y=A(()=>{const{show:f}=e,B=[[We,f]];return e.showMask||B.push([bt,e.onClickoutside,void 0,{capture:!0}]),B});function T(){var f;t.value=!1,(f=e.onAfterLeave)===null||f===void 0||f.call(e)}return pt(A(()=>e.blockScroll&&t.value)),pe(yt,r),pe(wt,null),pe($t,null),{bodyRef:r,rtlEnabled:z,mergedClsPrefix:g.mergedClsPrefixRef,isMounted:g.isMountedRef,mergedTheme:g.mergedThemeRef,displayed:t,transitionName:A(()=>({right:"slide-in-from-right-transition",left:"slide-in-from-left-transition",top:"slide-in-from-top-transition",bottom:"slide-in-from-bottom-transition"})[e.placement]),handleAfterLeave:T,bodyDirectives:y,handleMousedownResizeTrigger:E,handleMouseenterResizeTrigger:$,handleMouseleaveResizeTrigger:D,isDragging:j,isHoverOnResizeTrigger:b}},render(){const{$slots:e,mergedClsPrefix:t}=this;return this.displayDirective==="show"||this.displayed||this.show?He(u("div",{role:"none"},u(ft,{disabled:!this.showMask||!this.trapFocus,active:this.show,autoFocus:this.autoFocus,onEsc:this.onEsc},{default:()=>u(Fe,{name:this.transitionName,appear:this.isMounted,onAfterEnter:this.onAfterEnter,onAfterLeave:this.handleAfterLeave},{default:()=>He(u("div",mt(this.$attrs,{role:"dialog",ref:"bodyRef","aria-modal":"true",class:[`${t}-drawer`,this.rtlEnabled&&`${t}-drawer--rtl`,`${t}-drawer--${this.placement}-placement`,this.isDragging&&`${t}-drawer--unselectable`,this.nativeScrollbar&&`${t}-drawer--native-scrollbar`]}),[this.resizable?u("div",{class:[`${t}-drawer__resize-trigger`,(this.isDragging||this.isHoverOnResizeTrigger)&&`${t}-drawer__resize-trigger--hover`],onMouseenter:this.handleMouseenterResizeTrigger,onMouseleave:this.handleMouseleaveResizeTrigger,onMousedown:this.handleMousedownResizeTrigger}):null,this.nativeScrollbar?u("div",{class:[`${t}-drawer-content-wrapper`,this.contentClass],style:this.contentStyle,role:"none"},e):u(De,Object.assign({},this.scrollbarProps,{contentStyle:this.contentStyle,contentClass:[`${t}-drawer-content-wrapper`,this.contentClass],theme:this.mergedTheme.peers.Scrollbar,themeOverrides:this.mergedTheme.peerOverrides.Scrollbar}),e)]),this.bodyDirectives)})})),[[We,this.displayDirective==="if"||this.displayed||this.show]]):null}}),{cubicBezierEaseIn:Nn,cubicBezierEaseOut:En}=Ce;function Mn({duration:e="0.3s",leaveDuration:t="0.2s",name:r="slide-in-from-bottom"}={}){return[H(`&.${r}-transition-leave-active`,{transition:`transform ${t} ${Nn}`}),H(`&.${r}-transition-enter-active`,{transition:`transform ${e} ${En}`}),H(`&.${r}-transition-enter-to`,{transform:"translateY(0)"}),H(`&.${r}-transition-enter-from`,{transform:"translateY(100%)"}),H(`&.${r}-transition-leave-from`,{transform:"translateY(0)"}),H(`&.${r}-transition-leave-to`,{transform:"translateY(100%)"})]}const{cubicBezierEaseIn:Hn,cubicBezierEaseOut:Pn}=Ce;function In({duration:e="0.3s",leaveDuration:t="0.2s",name:r="slide-in-from-left"}={}){return[H(`&.${r}-transition-leave-active`,{transition:`transform ${t} ${Hn}`}),H(`&.${r}-transition-enter-active`,{transition:`transform ${e} ${Pn}`}),H(`&.${r}-transition-enter-to`,{transform:"translateX(0)"}),H(`&.${r}-transition-enter-from`,{transform:"translateX(-100%)"}),H(`&.${r}-transition-leave-from`,{transform:"translateX(0)"}),H(`&.${r}-transition-leave-to`,{transform:"translateX(-100%)"})]}const{cubicBezierEaseIn:_n,cubicBezierEaseOut:On}=Ce;function Ln({duration:e="0.3s",leaveDuration:t="0.2s",name:r="slide-in-from-right"}={}){return[H(`&.${r}-transition-leave-active`,{transition:`transform ${t} ${_n}`}),H(`&.${r}-transition-enter-active`,{transition:`transform ${e} ${On}`}),H(`&.${r}-transition-enter-to`,{transform:"translateX(0)"}),H(`&.${r}-transition-enter-from`,{transform:"translateX(100%)"}),H(`&.${r}-transition-leave-from`,{transform:"translateX(0)"}),H(`&.${r}-transition-leave-to`,{transform:"translateX(100%)"})]}const{cubicBezierEaseIn:Fn,cubicBezierEaseOut:Dn}=Ce;function Un({duration:e="0.3s",leaveDuration:t="0.2s",name:r="slide-in-from-top"}={}){return[H(`&.${r}-transition-leave-active`,{transition:`transform ${t} ${Fn}`}),H(`&.${r}-transition-enter-active`,{transition:`transform ${e} ${Dn}`}),H(`&.${r}-transition-enter-to`,{transform:"translateY(0)"}),H(`&.${r}-transition-enter-from`,{transform:"translateY(-100%)"}),H(`&.${r}-transition-leave-from`,{transform:"translateY(0)"}),H(`&.${r}-transition-leave-to`,{transform:"translateY(-100%)"})]}const An=H([G("drawer",`
 word-break: break-word;
 line-height: var(--n-line-height);
 position: absolute;
 pointer-events: all;
 box-shadow: var(--n-box-shadow);
 transition:
 background-color .3s var(--n-bezier),
 color .3s var(--n-bezier);
 background-color: var(--n-color);
 color: var(--n-text-color);
 box-sizing: border-box;
 `,[Ln(),In(),Un(),Mn(),oe("unselectable",`
 user-select: none; 
 -webkit-user-select: none;
 `),oe("native-scrollbar",[G("drawer-content-wrapper",`
 overflow: auto;
 height: 100%;
 `)]),ae("resize-trigger",`
 position: absolute;
 background-color: #0000;
 transition: background-color .3s var(--n-bezier);
 `,[oe("hover",`
 background-color: var(--n-resize-trigger-color-hover);
 `)]),G("drawer-content-wrapper",`
 box-sizing: border-box;
 `),G("drawer-content",`
 height: 100%;
 display: flex;
 flex-direction: column;
 `,[oe("native-scrollbar",[G("drawer-body-content-wrapper",`
 height: 100%;
 overflow: auto;
 `)]),G("drawer-body",`
 flex: 1 0 0;
 overflow: hidden;
 `),G("drawer-body-content-wrapper",`
 box-sizing: border-box;
 padding: var(--n-body-padding);
 `),G("drawer-header",`
 font-weight: var(--n-title-font-weight);
 line-height: 1;
 font-size: var(--n-title-font-size);
 color: var(--n-title-text-color);
 padding: var(--n-header-padding);
 transition: border .3s var(--n-bezier);
 border-bottom: 1px solid var(--n-divider-color);
 border-bottom: var(--n-header-border-bottom);
 display: flex;
 justify-content: space-between;
 align-items: center;
 `,[ae("main",`
 flex: 1;
 `),ae("close",`
 margin-left: 6px;
 transition:
 background-color .3s var(--n-bezier),
 color .3s var(--n-bezier);
 `)]),G("drawer-footer",`
 display: flex;
 justify-content: flex-end;
 border-top: var(--n-footer-border-top);
 transition: border .3s var(--n-bezier);
 padding: var(--n-footer-padding);
 `)]),oe("right-placement",`
 top: 0;
 bottom: 0;
 right: 0;
 border-top-left-radius: var(--n-border-radius);
 border-bottom-left-radius: var(--n-border-radius);
 `,[ae("resize-trigger",`
 width: 3px;
 height: 100%;
 top: 0;
 left: 0;
 transform: translateX(-1.5px);
 cursor: ew-resize;
 `)]),oe("left-placement",`
 top: 0;
 bottom: 0;
 left: 0;
 border-top-right-radius: var(--n-border-radius);
 border-bottom-right-radius: var(--n-border-radius);
 `,[ae("resize-trigger",`
 width: 3px;
 height: 100%;
 top: 0;
 right: 0;
 transform: translateX(1.5px);
 cursor: ew-resize;
 `)]),oe("top-placement",`
 top: 0;
 left: 0;
 right: 0;
 border-bottom-left-radius: var(--n-border-radius);
 border-bottom-right-radius: var(--n-border-radius);
 `,[ae("resize-trigger",`
 width: 100%;
 height: 3px;
 bottom: 0;
 left: 0;
 transform: translateY(1.5px);
 cursor: ns-resize;
 `)]),oe("bottom-placement",`
 left: 0;
 bottom: 0;
 right: 0;
 border-top-left-radius: var(--n-border-radius);
 border-top-right-radius: var(--n-border-radius);
 `,[ae("resize-trigger",`
 width: 100%;
 height: 3px;
 top: 0;
 left: 0;
 transform: translateY(-1.5px);
 cursor: ns-resize;
 `)])]),H("body",[H(">",[G("drawer-container",`
 position: fixed;
 `)])]),G("drawer-container",`
 position: relative;
 position: absolute;
 left: 0;
 right: 0;
 top: 0;
 bottom: 0;
 pointer-events: none;
 `,[H("> *",`
 pointer-events: all;
 `)]),G("drawer-mask",`
 background-color: rgba(0, 0, 0, .3);
 position: absolute;
 left: 0;
 right: 0;
 top: 0;
 bottom: 0;
 `,[oe("invisible",`
 background-color: rgba(0, 0, 0, 0)
 `),kt({enterDuration:"0.2s",leaveDuration:"0.2s",enterCubicBezier:"var(--n-bezier-in)",leaveCubicBezier:"var(--n-bezier-out)"})])]),Wn=Object.assign(Object.assign({},me.props),{show:Boolean,width:[Number,String],height:[Number,String],placement:{type:String,default:"right"},maskClosable:{type:Boolean,default:!0},showMask:{type:[Boolean,String],default:!0},to:[String,Object],displayDirective:{type:String,default:"if"},nativeScrollbar:{type:Boolean,default:!0},zIndex:Number,onMaskClick:Function,scrollbarProps:Object,contentClass:String,contentStyle:[Object,String],trapFocus:{type:Boolean,default:!0},onEsc:Function,autoFocus:{type:Boolean,default:!0},closeOnEsc:{type:Boolean,default:!0},blockScroll:{type:Boolean,default:!0},maxWidth:Number,maxHeight:Number,minWidth:Number,minHeight:Number,resizable:Boolean,defaultWidth:{type:[Number,String],default:251},defaultHeight:{type:[Number,String],default:251},onUpdateWidth:[Function,Array],onUpdateHeight:[Function,Array],"onUpdate:width":[Function,Array],"onUpdate:height":[Function,Array],"onUpdate:show":[Function,Array],onUpdateShow:[Function,Array],onAfterEnter:Function,onAfterLeave:Function,drawerStyle:[String,Object],drawerClass:String,target:null,onShow:Function,onHide:Function}),qn=le({name:"Drawer",inheritAttrs:!1,props:Wn,setup(e){const{mergedClsPrefixRef:t,namespaceRef:r,inlineThemeDisabled:g}=xe(e),v=St(),C=me("Drawer","-drawer",An,Tt,e,t),S=k(e.defaultWidth),b=k(e.defaultHeight),j=Ve(ce(e,"width"),S),w=Ve(ce(e,"height"),b),L=A(()=>{const{placement:s}=e;return s==="top"||s==="bottom"?"":Ye(j.value)}),F=A(()=>{const{placement:s}=e;return s==="left"||s==="right"?"":Ye(w.value)}),z=s=>{const{onUpdateWidth:y,"onUpdate:width":T}=e;y&&ue(y,s),T&&ue(T,s),S.value=s},m=s=>{const{onUpdateHeight:y,"onUpdate:width":T}=e;y&&ue(y,s),T&&ue(T,s),b.value=s},E=A(()=>[{width:L.value,height:F.value},e.drawerStyle||""]);function $(s){const{onMaskClick:y,maskClosable:T}=e;T&&R(!1),y&&y(s)}function D(s){$(s)}const O=zt();function x(s){var y;(y=e.onEsc)===null||y===void 0||y.call(e),e.show&&e.closeOnEsc&&Rt(s)&&(O.value||R(!1))}function R(s){const{onHide:y,onUpdateShow:T,"onUpdate:show":f}=e;T&&ue(T,s),f&&ue(f,s),y&&!s&&ue(y,s)}pe(Ue,{isMountedRef:v,mergedThemeRef:C,mergedClsPrefixRef:t,doUpdateShow:R,doUpdateHeight:m,doUpdateWidth:z});const p=A(()=>{const{common:{cubicBezierEaseInOut:s,cubicBezierEaseIn:y,cubicBezierEaseOut:T},self:{color:f,textColor:B,boxShadow:I,lineHeight:X,headerPadding:ne,footerPadding:ge,borderRadius:he,bodyPadding:h,titleFontSize:i,titleTextColor:N,titleFontWeight:U,headerBorderBottom:V,footerBorderTop:Y,closeIconColor:ee,closeIconColorHover:_,closeIconColorPressed:Se,closeColorHover:ze,closeColorPressed:Re,closeIconSize:Te,closeSize:ve,closeBorderRadius:je,resizableTriggerColorHover:Be}}=C.value;return{"--n-line-height":X,"--n-color":f,"--n-border-radius":he,"--n-text-color":B,"--n-box-shadow":I,"--n-bezier":s,"--n-bezier-out":T,"--n-bezier-in":y,"--n-header-padding":ne,"--n-body-padding":h,"--n-footer-padding":ge,"--n-title-text-color":N,"--n-title-font-size":i,"--n-title-font-weight":U,"--n-header-border-bottom":V,"--n-footer-border-top":Y,"--n-close-icon-color":ee,"--n-close-icon-color-hover":_,"--n-close-icon-color-pressed":Se,"--n-close-size":ve,"--n-close-color-hover":ze,"--n-close-color-pressed":Re,"--n-close-icon-size":Te,"--n-close-border-radius":je,"--n-resize-trigger-color-hover":Be}}),P=g?Le("drawer",void 0,p,e):void 0;return{mergedClsPrefix:t,namespace:r,mergedBodyStyle:E,handleOutsideClick:D,handleMaskClick:$,handleEsc:x,mergedTheme:C,cssVars:g?void 0:p,themeClass:P==null?void 0:P.themeClass,onRender:P==null?void 0:P.onRender,isMounted:v}},render(){const{mergedClsPrefix:e}=this;return u(Ct,{to:this.to,show:this.show},{default:()=>{var t;return(t=this.onRender)===null||t===void 0||t.call(this),He(u("div",{class:[`${e}-drawer-container`,this.namespace,this.themeClass],style:this.cssVars,role:"none"},this.showMask?u(Fe,{name:"fade-in-transition",appear:this.isMounted},{default:()=>this.show?u("div",{"aria-hidden":!0,class:[`${e}-drawer-mask`,this.showMask==="transparent"&&`${e}-drawer-mask--invisible`],onClick:this.handleMaskClick}):null}):null,u(Bn,Object.assign({},this.$attrs,{class:[this.drawerClass,this.$attrs.class],style:[this.mergedBodyStyle,this.$attrs.style],blockScroll:this.blockScroll,contentStyle:this.contentStyle,contentClass:this.contentClass,placement:this.placement,scrollbarProps:this.scrollbarProps,show:this.show,displayDirective:this.displayDirective,nativeScrollbar:this.nativeScrollbar,onAfterEnter:this.onAfterEnter,onAfterLeave:this.onAfterLeave,trapFocus:this.trapFocus,autoFocus:this.autoFocus,resizable:this.resizable,maxHeight:this.maxHeight,minHeight:this.minHeight,maxWidth:this.maxWidth,minWidth:this.minWidth,showMask:this.showMask,onEsc:this.handleEsc,onClickoutside:this.handleOutsideClick}),this.$slots)),[[xt,{zIndex:this.zIndex,enabled:this.show}]])}})}}),Xn={title:String,headerClass:String,headerStyle:[Object,String],footerClass:String,footerStyle:[Object,String],bodyClass:String,bodyStyle:[Object,String],bodyContentClass:String,bodyContentStyle:[Object,String],nativeScrollbar:{type:Boolean,default:!0},scrollbarProps:Object,closable:Boolean},Kn=le({name:"DrawerContent",props:Xn,slots:Object,setup(){const e=ke(Ue,null);e||Bt("drawer-content","`n-drawer-content` must be placed inside `n-drawer`.");const{doUpdateShow:t}=e;function r(){t(!1)}return{handleCloseClick:r,mergedTheme:e.mergedThemeRef,mergedClsPrefix:e.mergedClsPrefixRef}},render(){const{title:e,mergedClsPrefix:t,nativeScrollbar:r,mergedTheme:g,bodyClass:v,bodyStyle:C,bodyContentClass:S,bodyContentStyle:b,headerClass:j,headerStyle:w,footerClass:L,footerStyle:F,scrollbarProps:z,closable:m,$slots:E}=this;return u("div",{role:"none",class:[`${t}-drawer-content`,r&&`${t}-drawer-content--native-scrollbar`]},E.header||e||m?u("div",{class:[`${t}-drawer-header`,j],style:w,role:"none"},u("div",{class:`${t}-drawer-header__main`,role:"heading","aria-level":"1"},E.header!==void 0?E.header():e),m&&u(jt,{onClick:this.handleCloseClick,clsPrefix:t,class:`${t}-drawer-header__close`,absolute:!0})):null,r?u("div",{class:[`${t}-drawer-body`,v],style:C,role:"none"},u("div",{class:[`${t}-drawer-body-content-wrapper`,S],style:b,role:"none"},E)):u(De,Object.assign({themeOverrides:g.peerOverrides.Scrollbar,theme:g.peers.Scrollbar},z,{class:`${t}-drawer-body`,contentClass:[`${t}-drawer-body-content-wrapper`,S],contentStyle:b}),E),E.footer?u("div",{class:[`${t}-drawer-footer`,L],style:F,role:"none"},E.footer()):null)}});function Vn(e){const{textColor2:t,modalColor:r,borderColor:g,fontSize:v,primaryColor:C}=e;return{loaderFontSize:v,loaderTextColor:t,loaderColor:r,loaderBorder:`1px solid ${g}`,loadingColor:C}}const Yn=Nt({name:"Log",common:Ze,peers:{Scrollbar:Et,Code:ot},self:Vn}),rt=Mt("n-log"),Gn=le({props:{line:{type:String,default:""}},setup(e){const{trimRef:t,highlightRef:r,languageRef:g,mergedHljsRef:v}=ke(rt),C=k(null),S=A(()=>t.value?e.line.trim():e.line);function b(){C.value&&(C.value.innerHTML=j(g.value,S.value))}function j(w,L){const{value:F}=v;return F&&w&&F.getLanguage(w)?F.highlight(L,{language:w}).value:L}return Oe(()=>{r.value&&b()}),de(ce(e,"line"),()=>{r.value&&b()}),{highlight:r,selfRef:C,maybeTrimmedLines:S}},render(){const{highlight:e,maybeTrimmedLines:t}=this;return u("pre",{ref:"selfRef"},e?null:t)}}),Jn=le({name:"LogLoader",props:{clsPrefix:{type:String,required:!0},spinProps:Object},setup(){return{locale:ln("Log").localeRef}},render(){const{clsPrefix:e}=this;return u("div",{class:`${e}-log-loader`},u(Ht,Object.assign({clsPrefix:e,strokeWidth:24,scale:.85},this.spinProps)),u("span",{class:`${e}-log-loader__content`},this.locale.loading))}}),Qn=G("log",`
 position: relative;
 box-sizing: border-box;
 transition: border-color .3s var(--n-bezier);
`,[H("pre",`
 white-space: pre-wrap;
 word-break: break-word;
 margin: 0;
 `),G("log-loader",`
 transition:
 color .3s var(--n-bezier),
 background-color .3s var(--n-bezier),
 border-color .3s var(--n-bezier);
 box-sizing: border-box;
 position: absolute;
 right: 16px;
 top: 8px;
 height: 34px;
 border-radius: 17px;
 line-height: 34px;
 white-space: nowrap;
 overflow: hidden;
 border: var(--n-loader-border);
 color: var(--n-loader-text-color);
 background-color: var(--n-loader-color);
 font-size: var(--n-loader-font-size);
 `,[Pt(),ae("content",`
 display: inline-block;
 vertical-align: bottom;
 line-height: 34px;
 padding-left: 40px;
 padding-right: 20px;
 white-space: nowrap;
 `),G("base-loading",`
 color: var(--n-loading-color);
 position: absolute;
 left: 12px;
 top: calc(50% - 10px);
 font-size: 20px;
 width: 20px;
 height: 20px;
 display: inline-block;
 `)])]),Zn=Sn,eo=Object.assign(Object.assign({},me.props),{loading:Boolean,trim:Boolean,log:String,fontSize:{type:Number,default:14},lines:{type:Array,default:()=>[]},lineHeight:{type:Number,default:1.25},language:String,rows:{type:Number,default:15},offsetTop:{type:Number,default:0},offsetBottom:{type:Number,default:0},hljs:Object,spinProps:Object,onReachTop:Function,onReachBottom:Function,onRequireMore:Function}),to=le({name:"Log",props:eo,setup(e){const{mergedClsPrefixRef:t,inlineThemeDisabled:r}=xe(e),g=k(!1),v=A(()=>e.language!==void 0),C=A(()=>`calc(${Math.round(e.rows*e.lineHeight*e.fontSize)}px)`),S=A(()=>{const{log:x}=e;return x?x.split(`
`):e.lines}),b=k(null),j=me("Log","-log",Qn,Yn,e,t);function w(x){const R=x.target,p=R.firstElementChild;if(g.value){qe(()=>{g.value=!1});return}const P=R.offsetHeight,s=R.scrollTop,y=p.offsetHeight,T=s,f=y-s-P;if(T<=e.offsetTop){const{onReachTop:B,onRequireMore:I}=e;I&&I("top"),B&&B()}if(f<=e.offsetBottom){const{onReachBottom:B,onRequireMore:I}=e;I&&I("bottom"),B&&B()}}const L=Zn(F,300);function F(x){if(g.value){qe(()=>{g.value=!1});return}if(b.value){const{containerRef:R,contentRef:p}=b.value;if(R&&p){const P=R.offsetHeight,s=R.scrollTop,y=p.offsetHeight,T=s,f=y-s-P,B=x.deltaY;if(T===0&&B<0){const{onRequireMore:I}=e;I&&I("top")}if(f<=0&&B>0){const{onRequireMore:I}=e;I&&I("bottom")}}}}function z(x){const{value:R}=b;if(!R)return;const{silent:p,top:P,position:s}=x;p&&(g.value=!0),P!==void 0?R.scrollTo({left:0,top:P}):(s==="bottom"||s==="top")&&R.scrollTo({position:s})}function m(x=!1){Xe("log","`scrollToTop` is deprecated, please use `scrollTo({ position: 'top'})` instead."),z({position:"top",silent:x})}function E(x=!1){Xe("log","`scrollToTop` is deprecated, please use `scrollTo({ position: 'bottom'})` instead."),z({position:"bottom",silent:x})}pe(rt,{languageRef:ce(e,"language"),mergedHljsRef:nt(e),trimRef:ce(e,"trim"),highlightRef:v});const $={scrollTo:z},D=A(()=>{const{self:{loaderFontSize:x,loaderTextColor:R,loaderColor:p,loaderBorder:P,loadingColor:s},common:{cubicBezierEaseInOut:y}}=j.value;return{"--n-bezier":y,"--n-loader-font-size":x,"--n-loader-border":P,"--n-loader-color":p,"--n-loader-text-color":R,"--n-loading-color":s}}),O=r?Le("log",void 0,D,e):void 0;return Object.assign(Object.assign({},$),{mergedClsPrefix:t,scrollbarRef:b,mergedTheme:j,styleHeight:C,mergedLines:S,scrollToTop:m,scrollToBottom:E,handleWheel:L,handleScroll:w,cssVars:r?void 0:D,themeClass:O==null?void 0:O.themeClass,onRender:O==null?void 0:O.onRender})},render(){const{mergedClsPrefix:e,mergedTheme:t,onRender:r}=this;return r==null||r(),u("div",{class:[`${e}-log`,this.themeClass],style:[{lineHeight:this.lineHeight,height:this.styleHeight},this.cssVars],onWheelPassive:this.handleWheel},[u(De,{ref:"scrollbarRef",theme:t.peers.Scrollbar,themeOverrides:t.peerOverrides.Scrollbar,onScroll:this.handleScroll},{default:()=>u(jn,{internalNoHighlight:!0,internalFontSize:this.fontSize,theme:t.peers.Code,themeOverrides:t.peerOverrides.Code},{default:()=>this.mergedLines.map((g,v)=>u(Gn,{key:v,line:g}))})}),u(Fe,{name:"fade-in-scale-up-transition"},{default:()=>this.loading?u(Jn,{clsPrefix:e,spinProps:this.spinProps}):null})])}}),no=le({__name:"MembersDrawer",props:{show:{type:Boolean},account:{}},emits:["update:show","refresh"],setup(e,{emit:t}){const r=e,g=t,v=A({get:()=>r.show,set:h=>g("update:show",h)}),C=k([]),S=k(!1),b=k(""),j=k([]),w=$e({page:1,pageSize:50,itemCount:0});async function L(){if(r.account){S.value=!0;try{const h=await Dt(r.account.id,{page:w.page,size:w.pageSize,keyword:b.value.trim()});C.value=h.items,w.itemCount=h.total}finally{S.value=!1}}}de(()=>r.show,h=>{h&&(w.page=1,b.value="",j.value=[],L())});function F(h){const N={registered:{type:"success",label:"已注册"},granted:{type:"warning",label:"已授权"},member:{type:"success",label:"已是成员"},failed:{type:"error",label:"失败"},removed_failed:{type:"warning",label:"移除失败"}}[h.status]||{type:"default",label:h.status||"—"},U=u(Q,{type:N.type,size:"small",round:!0},()=>N.label);return h.message?u(Ie,null,{trigger:()=>U,default:()=>u("div",{style:"max-width:360px;word-break:break-all;"},h.message)}):U}const z=A(()=>[{type:"selection"},{title:"邮箱",key:"email",minWidth:220,ellipsis:{tooltip:!0}},{title:"状态",key:"status",width:100,render:h=>F(h)},{title:"额度",key:"credits",width:80,render:h=>h.credits===null||h.credits===void 0?u(J,{depth:3},()=>"—"):String(h.credits)},{title:"newbanana",key:"nb",width:90,render:h=>h.registered?u(Q,{type:"success",size:"small",round:!0},()=>"可导出"):u(J,{depth:3},()=>"—")},{title:"时间",key:"updated_at",width:170,render:h=>new Date(h.updated_at).toLocaleString()}]),m=k(!1),E=k(!1),$=$e({mode:"pool",count:10,emails:""});function D(){$.mode="pool",$.count=10,$.emails="",m.value=!0}async function O(){var i,N,U,V;if(!r.account)return;const h={};if($.mode==="pool"){if(!$.count||$.count<1){(i=window.$message)==null||i.warning("请输入要授权的数量");return}h.count=$.count}else{const Y=$.emails.split(/[\s,;]+/).map(ee=>ee.trim()).filter(ee=>ee.includes("@"));if(!Y.length){(N=window.$message)==null||N.warning("请粘贴至少一个邮箱");return}h.emails=Y}E.value=!0;try{const Y=await Ut(r.account.id,h);if(Y.failed===0)(U=window.$message)==null||U.success(`授权完成:成功 ${Y.granted} 个`);else{const ee=Y.items.find(_=>!_.ok);(V=window.$message)==null||V.warning(`完成:成功 ${Y.granted} 个,失败 ${Y.failed} 个${ee?`(示例:${ee.email} ${ee.message}）`:""}`)}m.value=!1,w.page=1,await L(),g("refresh")}catch{}finally{E.value=!1}}const x=k(!1),R=k(9),p=k(null),P=k(!1);let s=null;const y=A(()=>{var h;return(((h=p.value)==null?void 0:h.logs)??[]).join(`
`)}),T=A(()=>{var h;return((h=p.value)==null?void 0:h.status)==="running"}),f=A(()=>{var i,N;const h=((i=p.value)==null?void 0:i.target)||0;return h?Math.min(100,Math.round((((N=p.value)==null?void 0:N.success)||0)/h*100)):0});function B(){s!==null&&(window.clearInterval(s),s=null)}function I(){B(),s=window.setInterval(async()=>{var i;const h=(i=p.value)==null?void 0:i.id;if(h)try{p.value=await qt(h),p.value.status!=="running"&&(B(),await L(),g("refresh"))}catch{B()}},2e3)}function X(){R.value=9,p.value=null,x.value=!0}async function ne(){if(r.account){P.value=!0;try{p.value=await Wt(r.account.id,R.value),p.value.status==="running"?I():(await L(),g("refresh"))}catch{}finally{P.value=!1}}}de(()=>r.show,h=>{h||(B(),x.value=!1)}),It(B);async function ge(){var i,N;if(!r.account||!j.value.length){(i=window.$message)==null||i.warning("请先勾选要移除的成员");return}const h=await At(r.account.id,j.value);(N=window.$message)==null||N.success(h.message),j.value=[],await L(),g("refresh")}function he(h){w.page=h,L()}return(h,i)=>(Z(),be(Ee,null,[l(a(qn),{show:v.value,"onUpdate:show":i[4]||(i[4]=N=>v.value=N),width:720,placement:"right"},{default:d(()=>{var N;return[l(a(Kn),{title:`子账号管理 · ${((N=e.account)==null?void 0:N.email)??""}`,closable:""},{default:d(()=>[l(a(q),{vertical:"",size:"large"},{default:d(()=>[l(a(J),{depth:"3",style:{"font-size":"13px"}},{default:d(()=>{var U,V;return[M(" 组织:"+se(((U=e.account)==null?void 0:U.org_id)||"—")+" · 授权产品:"+se(((V=e.account)==null?void 0:V.product_name)||"—"),1)]}),_:1}),l(a(q),{justify:"space-between"},{default:d(()=>[l(a(q),null,{default:d(()=>{var U,V;return[l(a(W),{type:"primary",disabled:!((U=e.account)!=null&&U.has_org),onClick:X},{default:d(()=>[...i[14]||(i[14]=[M(" 一键拉号(凑满 N 个) ",-1)])]),_:1},8,["disabled"]),l(a(W),{disabled:!((V=e.account)!=null&&V.has_org),onClick:D},{default:d(()=>[...i[15]||(i[15]=[M(" 仅授权(不注册) ",-1)])]),_:1},8,["disabled"]),l(a(W),{type:"error",disabled:!j.value.length,onClick:ge},{default:d(()=>[...i[16]||(i[16]=[M(" 批量移除 ",-1)])]),_:1},8,["disabled"])]}),_:1}),l(a(q),null,{default:d(()=>[l(a(ie),{value:b.value,"onUpdate:value":i[0]||(i[0]=U=>b.value=U),placeholder:"搜索邮箱",clearable:"",style:{width:"200px"},onKeyup:i[1]||(i[1]=et(U=>(w.page=1,L()),["enter"]))},null,8,["value"]),l(a(W),{onClick:i[2]||(i[2]=U=>(w.page=1,L()))},{default:d(()=>[...i[17]||(i[17]=[M("搜索",-1)])]),_:1})]),_:1})]),_:1}),l(a(tt),{columns:z.value,data:C.value,loading:S.value,"row-key":U=>U.id,"checked-row-keys":j.value,"onUpdate:checkedRowKeys":i[3]||(i[3]=U=>j.value=U),"scroll-x":640,remote:"",pagination:{page:w.page,pageSize:w.pageSize,itemCount:w.itemCount,prefix:U=>`共 ${U.itemCount} 个成员`,onUpdatePage:he}},{empty:d(()=>[l(a(dn),{description:"还没有子账号,点击「批量加号授权」开始"})]),_:1},8,["columns","data","loading","row-key","checked-row-keys","pagination"])]),_:1})]),_:1},8,["title"])]}),_:1},8,["show"]),l(a(we),{show:m.value,"onUpdate:show":i[9]||(i[9]=N=>m.value=N),preset:"card",title:"批量加子账号并授权",style:{width:"560px"}},{footer:d(()=>[l(a(q),{justify:"end"},{default:d(()=>[l(a(W),{onClick:i[8]||(i[8]=N=>m.value=!1)},{default:d(()=>[...i[22]||(i[22]=[M("取消",-1)])]),_:1}),l(a(W),{type:"primary",loading:E.value,onClick:O},{default:d(()=>[...i[23]||(i[23]=[M("开始授权",-1)])]),_:1},8,["loading"])]),_:1})]),default:d(()=>[l(a(q),{vertical:"",size:"large"},{default:d(()=>[l(a(sn),{value:$.mode,"onUpdate:value":i[5]||(i[5]=N=>$.mode=N)},{default:d(()=>[l(a(q),null,{default:d(()=>[l(a(Ge),{value:"pool"},{default:d(()=>[...i[18]||(i[18]=[M("从邮箱池取号",-1)])]),_:1}),l(a(Ge),{value:"paste"},{default:d(()=>[...i[19]||(i[19]=[M("手动粘贴邮箱",-1)])]),_:1})]),_:1})]),_:1},8,["value"]),$.mode==="pool"?(Z(),be(Ee,{key:0},[l(a(q),{align:"center"},{default:d(()=>[l(a(J),null,{default:d(()=>[...i[20]||(i[20]=[M("取未使用邮箱数量:",-1)])]),_:1}),l(a(_e),{value:$.count,"onUpdate:value":i[6]||(i[6]=N=>$.count=N),min:1,max:500,style:{width:"160px"}},null,8,["value"])]),_:1}),l(a(J),{depth:"3",style:{"font-size":"12px"}},{default:d(()=>[...i[21]||(i[21]=[M(" 将从「邮箱管理」池里取未使用的邮箱作为子账号,授权成功后自动标记为已使用。 ",-1)])]),_:1})],64)):(Z(),re(a(ie),{key:1,value:$.emails,"onUpdate:value":i[7]||(i[7]=N=>$.emails=N),type:"textarea",autosize:{minRows:5,maxRows:12},placeholder:"每行一个邮箱,或用空格/逗号分隔"},null,8,["value"]))]),_:1})]),_:1},8,["show"]),l(a(we),{show:x.value,"onUpdate:show":i[13]||(i[13]=N=>x.value=N),preset:"card",title:"一键拉号(邀请 + 授权 + 注册)",style:{width:"680px"},"mask-closable":!T.value,closable:!T.value},{footer:d(()=>[l(a(q),{justify:"end"},{default:d(()=>[l(a(W),{disabled:T.value,onClick:i[11]||(i[11]=N=>x.value=!1)},{default:d(()=>[...i[29]||(i[29]=[M("关闭",-1)])]),_:1},8,["disabled"]),p.value?T.value?Pe("",!0):(Z(),re(a(W),{key:1,type:"primary",onClick:i[12]||(i[12]=N=>p.value=null)},{default:d(()=>[...i[31]||(i[31]=[M(" 再拉一批 ",-1)])]),_:1})):(Z(),re(a(W),{key:0,type:"primary",loading:P.value,onClick:ne},{default:d(()=>[...i[30]||(i[30]=[M(" 开始拉号 ",-1)])]),_:1},8,["loading"]))]),_:1})]),default:d(()=>[l(a(q),{vertical:"",size:"large"},{default:d(()=>[p.value?(Z(),re(a(q),{key:1,vertical:""},{default:d(()=>[l(a(J),null,{default:d(()=>[M("进度:成功 "+se(p.value.success)+" / 目标 "+se(p.value.target)+" · 失败 "+se(p.value.fail)+" ",1),p.value.status==="done"?(Z(),re(a(Q),{key:0,type:"success",size:"small",round:"",style:{"margin-left":"8px"}},{default:d(()=>[...i[26]||(i[26]=[M("已完成",-1)])]),_:1})):p.value.status==="error"?(Z(),re(a(Q),{key:1,type:"error",size:"small",round:"",style:{"margin-left":"8px"}},{default:d(()=>[...i[27]||(i[27]=[M("出错",-1)])]),_:1})):(Z(),re(a(Q),{key:2,type:"info",size:"small",round:"",style:{"margin-left":"8px"}},{default:d(()=>[...i[28]||(i[28]=[M("进行中",-1)])]),_:1}))]),_:1}),l(a(Ft),{type:"line",percentage:f.value,status:p.value.status==="error"?"error":p.value.status==="done"?"success":"default"},null,8,["percentage","status"]),p.value.error?(Z(),re(a(J),{key:0,type:"error",style:{"font-size":"12px"}},{default:d(()=>[M(se(p.value.error),1)]),_:1})):Pe("",!0),l(a(to),{log:y.value,rows:14,trim:"",style:{border:"1px solid #eee","border-radius":"6px"}},null,8,["log"])]),_:1})):(Z(),be(Ee,{key:0},[l(a(q),{align:"center"},{default:d(()=>[l(a(J),null,{default:d(()=>[...i[24]||(i[24]=[M("目标已注册子号数量:",-1)])]),_:1}),l(a(_e),{value:R.value,"onUpdate:value":i[10]||(i[10]=N=>R.value=N),min:1,max:50,style:{width:"160px"}},null,8,["value"])]),_:1}),l(a(J),{depth:"3",style:{"font-size":"12px"}},{default:d(()=>[...i[25]||(i[25]=[M(" 从邮箱池逐个取号:邀请 → 分配产品 → 子号自助登录注册(收验证码)。失败的会自动从组织移除并换号重拉, 直到注册成功数达到目标或邮箱池耗尽。注册成功的子号即可在「号池管理」按 newbanana 格式导出。 ",-1)])]),_:1})],64))]),_:1})]),_:1},8,["show","mask-closable","closable"])],64))}}),$o=le({__name:"index",setup(e){const t=_t(),r=Lt();function g(){t.warning({title:"清理组织已删母号",content:"将登录核验所有无效母号,自动删除「组织已删(Deleted-Org)」的(带备份,不误删 type2e / 瞬时失败)。后台运行,完成后刷新查看。",positiveText:"开始清理",negativeText:"取消",onPositiveClick:async()=>{var n,o;try{const c=await on("pruneorg");(n=window.$message)==null||n[c.ok?"success":"warning"](c.ok?"已触发清死母号(后台跑,稍后刷新)":c.message)}catch{(o=window.$message)==null||o.error("触发失败")}}})}const v=k(!1),C=k(9),S=k(!1);function b(){var n;if(!z.value.length){(n=window.$message)==null||n.warning("请先勾选要拉号的主号");return}C.value=9,v.value=!0}async function j(){var n;S.value=!0;try{const o=await Vt(z.value,C.value);v.value=!1,(n=window.$message)==null||n.success(`已开始批量拉号(${z.value.length} 个主号),前往拉号任务查看进度`),r.push({name:"jobs",query:{id:String(o.id)}})}finally{S.value=!1}}const w=k([]),L=k(!1),F=k(""),z=k([]),m=$e({page:1,pageSize:20,itemCount:0,pageSizes:[20,50,100],showSizePicker:!0}),E=k(null);async function $(){try{E.value=await nn()}catch{}}const D=A(()=>{var o;const n=(o=E.value)==null?void 0:o.admins;return n?[{label:"总母号",value:n.total,tone:"accent"},{label:"有效",value:n.valid,tone:"good"},{label:"type2e",value:n.type2e,tone:n.type2e?"warn":"default"},{label:"组织已删",value:n.dead_org,tone:n.dead_org?"bad":"default"},{label:"未检测",value:n.unchecked,tone:n.unchecked?"warn":"default"}]:[]}),O=k(null),x=k(new Set),R=k(new Set),p=k(new Set),P=k(!1),s=k(null);function y(n){s.value=n,P.value=!0}function T(n,o,c){const K=new Set(n.value);c?K.add(o):K.delete(o),n.value=K}async function f(){L.value=!0;try{const n=await Kt({page:m.page,size:m.pageSize,keyword:F.value.trim()});w.value=n.items,m.itemCount=n.total}finally{L.value=!1}}function B(n){const o=(n.check_message||"").toLowerCase();let c;return n.is_valid===!0?c=u(Q,{type:"success",size:"small",round:!0},()=>"有效"):n.is_valid===!1?o.includes("type2e")||o.includes("eoachoose")?c=u(Q,{type:"warning",size:"small",round:!0},()=>"type2e"):o.includes("组织已删")||o.includes("deleted")||o.includes("无可用组织")||o.includes("无组织")||o.includes("无可用产品")?c=u(Q,{type:"error",size:"small",round:!0},()=>"组织已删"):c=u(Q,{type:"error",size:"small",round:!0},()=>"无效"):c=u(Q,{type:"default",size:"small",round:!0},()=>"未检测"),n.check_message?u(Ie,null,{trigger:()=>c,default:()=>u("div",{style:"max-width: 320px; word-break: break-all;"},[u("div",n.check_message),n.last_checked_at?u("div",{style:"margin-top:4px; opacity:0.7; font-size:12px;"},"检测时间:"+new Date(n.last_checked_at).toLocaleString()):null])}):c}function I(n){return n.has_org===!0?u(Q,{type:"success",size:"small"},()=>"有组织"):n.has_org===!1?u(Q,{type:"warning",size:"small"},()=>"无组织"):u(J,{depth:3},()=>"—")}function X(n){const o=n.mail_ok===!0?u(Q,{type:"success",size:"tiny",round:!0},()=>"收件正常"):n.mail_ok===!1?u(Q,{type:"error",size:"tiny",round:!0},()=>"收件异常"):u(J,{depth:3},()=>"—");return n.mail_message?u(Ie,null,{trigger:()=>o,default:()=>u("div",{style:"max-width:320px;word-break:break-all;"},n.mail_message)}):o}const ne=[{label:"测试收邮件",key:"test"},{label:"编辑",key:"edit"},{label:"删除",key:"delete"}];function ge(n,o){n==="test"?U(o):n==="edit"?Te(o):n==="delete"&&N(o)}const he=A(()=>[{type:"selection"},{title:"ID",key:"id",width:56},{title:"邮箱",key:"email",minWidth:220,ellipsis:{tooltip:!0}},{title:"是否有效",key:"is_valid",width:96,render:n=>B(n)},{title:"组织",key:"has_org",width:84,render:n=>I(n)},{title:"授权产品",key:"product_name",minWidth:150,ellipsis:{tooltip:!0},render:n=>n.product_name||u(J,{depth:3},()=>"—")},{title:"成员数",key:"member_count",width:92,render:n=>{const o=n.member_count??0,c=Math.max(2,Math.min(100,o/9*100)),K=o>=9?"#18a058":o===0?"#d03050":"#2f6bd6";return u("div",{style:"display:flex;flex-direction:column;gap:3px;min-width:56px"},[u("span",{style:"font-size:12px;font-variant-numeric:tabular-nums"},`${o}/9`),u("div",{style:"height:4px;border-radius:2px;background:var(--track,#eef1f5);overflow:hidden"},[u("div",{style:`height:100%;width:${c}%;background:${K}`})])])}},{title:"收件",key:"mail_ok",width:96,render:n=>X(n)},{title:"备注",key:"remark",minWidth:100,ellipsis:{tooltip:!0}},{title:"操作",key:"actions",width:270,fixed:"right",render:n=>u(q,{size:6,wrap:!1},()=>[u(W,{size:"small",type:"primary",secondary:!0,loading:R.value.has(n.id),onClick:()=>h(n)},()=>"登录"),u(W,{size:"small",type:"info",secondary:!0,loading:p.value.has(n.id),onClick:()=>i(n)},()=>"检测"),u(W,{size:"small",type:"success",secondary:!0,onClick:()=>y(n)},()=>"成员"),u(un,{trigger:"click",options:ne,onSelect:o=>ge(o,n)},{default:()=>u(W,{size:"small",text:!0},()=>"更多")})])}]);async function h(n){var o,c,K;if(!n.refresh_token||!n.client_id){(o=window.$message)==null||o.warning("该账号缺少 Refresh Token / Client ID,无法自动收验证码登录");return}T(R,n.id,!0);try{const te=await Qt(n.id);te.success?(c=window.$message)==null||c.success(`${n.email} 登录成功:${te.message}`):(K=window.$message)==null||K.error(`${n.email} 登录失败:${te.message}`)}finally{T(R,n.id,!1),f()}}async function i(n){var o,c;T(p,n.id,!0);try{const K=await Zt(n.id);K.success?(o=window.$message)==null||o.success(`${n.email} ${K.message}`):(c=window.$message)==null||c.warning(`${n.email} ${K.message}`)}finally{T(p,n.id,!1),f()}}function N(n){t.warning({title:"删除账号",content:`确认删除 ${n.email}?`,positiveText:"删除",negativeText:"取消",onPositiveClick:()=>Be(n.id)})}async function U(n){var o,c,K;if(!n.refresh_token||!n.client_id){(o=window.$message)==null||o.warning("该账号缺少 Refresh Token 或 Client ID,无法测试");return}x.value=new Set(x.value).add(n.id);try{const te=await en(n.id);if(te.success){const st=te.latest_subject?`,最新邮件:${te.latest_subject}`:"";(c=window.$message)==null||c.success(`${n.email} ${te.message}${st}`)}else(K=window.$message)==null||K.error(`${n.email} 测试失败:${te.message}`)}finally{const te=new Set(x.value);te.delete(n.id),x.value=te,f()}}const V=k(!1),Y=k(null),ee=k(null),_=$e({email:"",hotmail_password:"",adobe_password:"",refresh_token:"",client_id:"",remark:""}),Se={email:{required:!0,message:"请输入邮箱",trigger:"blur"}};function ze(){_.email="",_.hotmail_password="",_.adobe_password="",_.refresh_token="",_.client_id="",_.remark=""}function Re(){Y.value=null,ze(),V.value=!0}function Te(n){Y.value=n.id,_.email=n.email,_.hotmail_password=n.hotmail_password,_.adobe_password=n.adobe_password,_.refresh_token=n.refresh_token,_.client_id=n.client_id,_.remark=n.remark,V.value=!0}const ve=k(!1);async function je(){var n,o,c;try{await((n=ee.value)==null?void 0:n.validate())}catch{return}ve.value=!0;try{Y.value===null?(await Yt({..._}),(o=window.$message)==null||o.success("新增成功")):(await Gt(Y.value,{..._}),(c=window.$message)==null||c.success("保存成功")),V.value=!1,f()}finally{ve.value=!1}}async function Be(n){var o;await tn(n),(o=window.$message)==null||o.success("删除成功"),f()}function at(){var n;if(!z.value.length){(n=window.$message)==null||n.warning("请先勾选要删除的账号");return}t.warning({title:"批量删除",content:`确认删除选中的 ${z.value.length} 个账号?`,positiveText:"删除",negativeText:"取消",onPositiveClick:async()=>{var o;await Jt(z.value),(o=window.$message)==null||o.success("批量删除成功"),z.value=[],f()}})}function it(n){m.page=n,f()}function lt(n){m.pageSize=n,m.page=1,f()}function Ne(){m.page=1,f()}const Ae=Ot();return de(()=>Ae.query.kw,n=>{typeof n=="string"&&n&&(F.value=n,Ne())}),Oe(()=>{const n=Ae.query.kw;typeof n=="string"&&n&&(F.value=n),f(),$()}),(n,o)=>(Z(),be("div",null,[l(a(Ke),{bordered:!1},{default:d(()=>[D.value.length?(Z(),re(an,{key:0,items:D.value},null,8,["items"])):Pe("",!0),l(a(q),{justify:"space-between",align:"center",style:{"margin-bottom":"16px"}},{default:d(()=>[l(a(q),null,{default:d(()=>[l(a(W),{type:"primary",onClick:Re},{default:d(()=>[...o[15]||(o[15]=[M("+ 新增账号",-1)])]),_:1}),l(a(W),{type:"info",onClick:o[0]||(o[0]=c=>{var K;return(K=O.value)==null?void 0:K.open()})},{default:d(()=>[...o[16]||(o[16]=[M("批量导入",-1)])]),_:1}),l(a(W),{type:"warning",disabled:!z.value.length,onClick:b},{default:d(()=>[M(" 批量拉号 ("+se(z.value.length)+") ",1)]),_:1},8,["disabled"]),l(a(W),{type:"error",disabled:!z.value.length,onClick:at},{default:d(()=>[...o[17]||(o[17]=[M(" 批量删除 ",-1)])]),_:1},8,["disabled"]),l(a(W),{type:"warning",secondary:"",onClick:g},{default:d(()=>[...o[18]||(o[18]=[M("清死母号",-1)])]),_:1})]),_:1}),l(a(q),null,{default:d(()=>[l(a(ie),{value:F.value,"onUpdate:value":o[1]||(o[1]=c=>F.value=c),placeholder:"搜索邮箱 / Client ID / 备注",clearable:"",style:{width:"260px"},onKeyup:et(Ne,["enter"])},null,8,["value"]),l(a(W),{onClick:Ne},{default:d(()=>[...o[19]||(o[19]=[M("搜索",-1)])]),_:1})]),_:1})]),_:1}),l(a(tt),{columns:he.value,data:w.value,loading:L.value,"row-key":c=>c.id,"checked-row-keys":z.value,"onUpdate:checkedRowKeys":o[2]||(o[2]=c=>z.value=c),"scroll-x":1240,remote:"",pagination:{page:m.page,pageSize:m.pageSize,itemCount:m.itemCount,pageSizes:m.pageSizes,showSizePicker:!0,prefix:c=>`共 ${c.itemCount} 条`,onUpdatePage:it,onUpdatePageSize:lt}},null,8,["columns","data","loading","row-key","checked-row-keys","pagination"])]),_:1}),l(a(we),{show:V.value,"onUpdate:show":o[10]||(o[10]=c=>V.value=c)},{default:d(()=>[l(a(Ke),{title:Y.value===null?"新增账号":"编辑账号",style:{width:"560px"},bordered:!1,role:"dialog"},{footer:d(()=>[l(a(q),{justify:"end"},{default:d(()=>[l(a(W),{onClick:o[9]||(o[9]=c=>V.value=!1)},{default:d(()=>[...o[20]||(o[20]=[M("取消",-1)])]),_:1}),l(a(W),{type:"primary",loading:ve.value,onClick:je},{default:d(()=>[...o[21]||(o[21]=[M("保存",-1)])]),_:1},8,["loading"])]),_:1})]),default:d(()=>[l(a(cn),{ref_key:"formRef",ref:ee,model:_,rules:Se,"label-placement":"top"},{default:d(()=>[l(a(fe),{label:"邮箱",path:"email"},{default:d(()=>[l(a(ie),{value:_.email,"onUpdate:value":o[3]||(o[3]=c=>_.email=c),placeholder:"example@hotmail.com"},null,8,["value"])]),_:1}),l(a(fe),{label:"Hotmail 密码"},{default:d(()=>[l(a(ie),{value:_.hotmail_password,"onUpdate:value":o[4]||(o[4]=c=>_.hotmail_password=c)},null,8,["value"])]),_:1}),l(a(fe),{label:"母号密码"},{default:d(()=>[l(a(ie),{value:_.adobe_password,"onUpdate:value":o[5]||(o[5]=c=>_.adobe_password=c)},null,8,["value"])]),_:1}),l(a(fe),{label:"Refresh Token"},{default:d(()=>[l(a(ie),{value:_.refresh_token,"onUpdate:value":o[6]||(o[6]=c=>_.refresh_token=c),type:"textarea",autosize:{minRows:2,maxRows:4}},null,8,["value"])]),_:1}),l(a(fe),{label:"Client ID"},{default:d(()=>[l(a(ie),{value:_.client_id,"onUpdate:value":o[7]||(o[7]=c=>_.client_id=c)},null,8,["value"])]),_:1}),l(a(fe),{label:"备注"},{default:d(()=>[l(a(ie),{value:_.remark,"onUpdate:value":o[8]||(o[8]=c=>_.remark=c)},null,8,["value"])]),_:1})]),_:1},8,["model"])]),_:1},8,["title"])]),_:1},8,["show"]),l(rn,{ref_key:"importModalRef",ref:O,title:"批量导入母号","format-hint":"邮箱 | Hotmail密码 | 母号密码 | Refresh Token | Client ID",placeholder:"BoychukBialy58@hotmail.com|Boychukayho2109#|vwpPvHVW$R0X|M.C537_SN1...|9e5f94bc-e8a4-4e73-b8be-63364c29d753","import-fn":a(Xt),onSuccess:f},null,8,["import-fn"]),l(a(we),{show:v.value,"onUpdate:show":o[13]||(o[13]=c=>v.value=c),preset:"card",title:"批量拉号",style:{width:"520px"}},{footer:d(()=>[l(a(q),{justify:"end"},{default:d(()=>[l(a(W),{onClick:o[12]||(o[12]=c=>v.value=!1)},{default:d(()=>[...o[24]||(o[24]=[M("取消",-1)])]),_:1}),l(a(W),{type:"primary",loading:S.value,onClick:j},{default:d(()=>[...o[25]||(o[25]=[M(" 开始批量拉号 ",-1)])]),_:1},8,["loading"])]),_:1})]),default:d(()=>[l(a(q),{vertical:"",size:"large"},{default:d(()=>[l(a(J),null,{default:d(()=>[M("已选 "+se(z.value.length)+' 个主号。每个主号将凑满下方数量的"已注册可用"子号: 邀请 → 分配产品 → 子号登录拿 cookie/token。未登录的主号会自动登录。',1)]),_:1}),l(a(q),{align:"center"},{default:d(()=>[l(a(J),null,{default:d(()=>[...o[22]||(o[22]=[M("每个主号目标数量:",-1)])]),_:1}),l(a(_e),{value:C.value,"onUpdate:value":o[11]||(o[11]=c=>C.value=c),min:1,max:50,style:{width:"160px"}},null,8,["value"])]),_:1}),l(a(J),{depth:"3",style:{"font-size":"12px"}},{default:d(()=>[...o[23]||(o[23]=[M(" 按主号顺序处理,每个主号内子号并发(并发数见「设置」)。进度可在「拉号任务」页查看。 ",-1)])]),_:1})]),_:1})]),_:1},8,["show"]),l(no,{show:P.value,"onUpdate:show":o[14]||(o[14]=c=>P.value=c),account:s.value,onRefresh:f},null,8,["show","account"])]))}});export{$o as default};
