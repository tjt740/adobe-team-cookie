import{d as R,k as r,a3 as W,m as $,b3 as j,b4 as q,b5 as O,b6 as G,b7 as M,p as B,s as c,x as w,G as L,H as T,I as _,b8 as X,P as A}from"./index-CrrzYg-U.js";import{f as P}from"./get-Cpzh6RY9.js";import{r as g}from"./auth-DQiNxie4.js";const Y={success:r(G,null),error:r(O,null),warning:r(q,null),info:r(j,null)},H=R({name:"ProgressCircle",props:{clsPrefix:{type:String,required:!0},status:{type:String,required:!0},strokeWidth:{type:Number,required:!0},fillColor:[String,Object],railColor:String,railStyle:[String,Object],percentage:{type:Number,default:0},offsetDegree:{type:Number,default:0},showIndicator:{type:Boolean,required:!0},indicatorTextColor:String,unit:String,viewBoxWidth:{type:Number,required:!0},gapDegree:{type:Number,required:!0},gapOffsetDegree:{type:Number,default:0}},setup(e,{slots:i}){const p=$(()=>{const n="gradient",{fillColor:t}=e;return typeof t=="object"?`${n}-${M(JSON.stringify(t))}`:n});function m(n,t,s,u){const{gapDegree:f,viewBoxWidth:h,strokeWidth:b}=e,a=50,y=0,l=a,o=0,x=2*a,C=50+b/2,v=`M ${C},${C} m ${y},${l}
      a ${a},${a} 0 1 1 ${o},${-x}
      a ${a},${a} 0 1 1 ${-o},${x}`,S=Math.PI*2*a,k={stroke:u==="rail"?s:typeof e.fillColor=="object"?`url(#${p.value})`:s,strokeDasharray:`${Math.min(n,100)/100*(S-f)}px ${h*8}px`,strokeDashoffset:`-${f/2}px`,transformOrigin:t?"center":void 0,transform:t?`rotate(${t}deg)`:void 0};return{pathString:v,pathStyle:k}}const d=()=>{const n=typeof e.fillColor=="object",t=n?e.fillColor.stops[0]:"",s=n?e.fillColor.stops[1]:"";return n&&r("defs",null,r("linearGradient",{id:p.value,x1:"0%",y1:"100%",x2:"100%",y2:"0%"},r("stop",{offset:"0%","stop-color":t}),r("stop",{offset:"100%","stop-color":s})))};return()=>{const{fillColor:n,railColor:t,strokeWidth:s,offsetDegree:u,status:f,percentage:h,showIndicator:b,indicatorTextColor:a,unit:y,gapOffsetDegree:l,clsPrefix:o}=e,{pathString:x,pathStyle:C}=m(100,0,t,"rail"),{pathString:v,pathStyle:S}=m(h,u,n,"fill"),k=100+s;return r("div",{class:`${o}-progress-content`,role:"none"},r("div",{class:`${o}-progress-graph`,"aria-hidden":!0},r("div",{class:`${o}-progress-graph-circle`,style:{transform:l?`rotate(${l}deg)`:void 0}},r("svg",{viewBox:`0 0 ${k} ${k}`},d(),r("g",null,r("path",{class:`${o}-progress-graph-circle-rail`,d:x,"stroke-width":s,"stroke-linecap":"round",fill:"none",style:C})),r("g",null,r("path",{class:[`${o}-progress-graph-circle-fill`,h===0&&`${o}-progress-graph-circle-fill--empty`],d:v,"stroke-width":s,"stroke-linecap":"round",fill:"none",style:S}))))),b?r("div",null,i.default?r("div",{class:`${o}-progress-custom-content`,role:"none"},i.default()):f!=="default"?r("div",{class:`${o}-progress-icon`,"aria-hidden":!0},r(W,{clsPrefix:o},{default:()=>Y[f]})):r("div",{class:`${o}-progress-text`,style:{color:a},role:"none"},r("span",{class:`${o}-progress-text__percentage`},h),r("span",{class:`${o}-progress-text__unit`},y))):null)}}}),J={success:r(G,null),error:r(O,null),warning:r(q,null),info:r(j,null)},E=R({name:"ProgressLine",props:{clsPrefix:{type:String,required:!0},percentage:{type:Number,default:0},railColor:String,railStyle:[String,Object],fillColor:[String,Object],status:{type:String,required:!0},indicatorPlacement:{type:String,required:!0},indicatorTextColor:String,unit:{type:String,default:"%"},processing:{type:Boolean,required:!0},showIndicator:{type:Boolean,required:!0},height:[String,Number],railBorderRadius:[String,Number],fillBorderRadius:[String,Number]},setup(e,{slots:i}){const p=$(()=>P(e.height)),m=$(()=>{var t,s;return typeof e.fillColor=="object"?`linear-gradient(to right, ${(t=e.fillColor)===null||t===void 0?void 0:t.stops[0]} , ${(s=e.fillColor)===null||s===void 0?void 0:s.stops[1]})`:e.fillColor}),d=$(()=>e.railBorderRadius!==void 0?P(e.railBorderRadius):e.height!==void 0?P(e.height,{c:.5}):""),n=$(()=>e.fillBorderRadius!==void 0?P(e.fillBorderRadius):e.railBorderRadius!==void 0?P(e.railBorderRadius):e.height!==void 0?P(e.height,{c:.5}):"");return()=>{const{indicatorPlacement:t,railColor:s,railStyle:u,percentage:f,unit:h,indicatorTextColor:b,status:a,showIndicator:y,processing:l,clsPrefix:o}=e;return r("div",{class:`${o}-progress-content`,role:"none"},r("div",{class:`${o}-progress-graph`,"aria-hidden":!0},r("div",{class:[`${o}-progress-graph-line`,{[`${o}-progress-graph-line--indicator-${t}`]:!0}]},r("div",{class:`${o}-progress-graph-line-rail`,style:[{backgroundColor:s,height:p.value,borderRadius:d.value},u]},r("div",{class:[`${o}-progress-graph-line-fill`,l&&`${o}-progress-graph-line-fill--processing`],style:{maxWidth:`${e.percentage}%`,background:m.value,height:p.value,lineHeight:p.value,borderRadius:n.value}},t==="inside"?r("div",{class:`${o}-progress-graph-line-indicator`,style:{color:b}},i.default?i.default():`${f}${h}`):null)))),y&&t==="outside"?r("div",null,i.default?r("div",{class:`${o}-progress-custom-content`,style:{color:b},role:"none"},i.default()):a==="default"?r("div",{role:"none",class:`${o}-progress-icon ${o}-progress-icon--as-text`,style:{color:b}},f,h):r("div",{class:`${o}-progress-icon`,"aria-hidden":!0},r(W,{clsPrefix:o},{default:()=>J[a]}))):null)}}});function I(e,i,p=100){return`m ${p/2} ${p/2-e} a ${e} ${e} 0 1 1 0 ${2*e} a ${e} ${e} 0 1 1 0 -${2*e}`}const V=R({name:"ProgressMultipleCircle",props:{clsPrefix:{type:String,required:!0},viewBoxWidth:{type:Number,required:!0},percentage:{type:Array,default:[0]},strokeWidth:{type:Number,required:!0},circleGap:{type:Number,required:!0},showIndicator:{type:Boolean,required:!0},fillColor:{type:Array,default:()=>[]},railColor:{type:Array,default:()=>[]},railStyle:{type:Array,default:()=>[]}},setup(e,{slots:i}){const p=$(()=>e.percentage.map((n,t)=>`${Math.PI*n/100*(e.viewBoxWidth/2-e.strokeWidth/2*(1+2*t)-e.circleGap*t)*2}, ${e.viewBoxWidth*8}`)),m=(d,n)=>{const t=e.fillColor[n],s=typeof t=="object"?t.stops[0]:"",u=typeof t=="object"?t.stops[1]:"";return typeof e.fillColor[n]=="object"&&r("linearGradient",{id:`gradient-${n}`,x1:"100%",y1:"0%",x2:"0%",y2:"100%"},r("stop",{offset:"0%","stop-color":s}),r("stop",{offset:"100%","stop-color":u}))};return()=>{const{viewBoxWidth:d,strokeWidth:n,circleGap:t,showIndicator:s,fillColor:u,railColor:f,railStyle:h,percentage:b,clsPrefix:a}=e;return r("div",{class:`${a}-progress-content`,role:"none"},r("div",{class:`${a}-progress-graph`,"aria-hidden":!0},r("div",{class:`${a}-progress-graph-circle`},r("svg",{viewBox:`0 0 ${d} ${d}`},r("defs",null,b.map((y,l)=>m(y,l))),b.map((y,l)=>r("g",{key:l},r("path",{class:`${a}-progress-graph-circle-rail`,d:I(d/2-n/2*(1+2*l)-t*l,n,d),"stroke-width":n,"stroke-linecap":"round",fill:"none",style:[{strokeDashoffset:0,stroke:f[l]},h[l]]}),r("path",{class:[`${a}-progress-graph-circle-fill`,y===0&&`${a}-progress-graph-circle-fill--empty`],d:I(d/2-n/2*(1+2*l)-t*l,n,d),"stroke-width":n,"stroke-linecap":"round",fill:"none",style:{strokeDasharray:p.value[l],strokeDashoffset:0,stroke:typeof u[l]=="object"?`url(#gradient-${l})`:u[l]}})))))),s&&i.default?r("div",null,r("div",{class:`${a}-progress-text`},i.default())):null)}}}),F=B([c("progress",{display:"inline-block"},[c("progress-icon",`
 color: var(--n-icon-color);
 transition: color .3s var(--n-bezier);
 `),w("line",`
 width: 100%;
 display: block;
 `,[c("progress-content",`
 display: flex;
 align-items: center;
 `,[c("progress-graph",{flex:1})]),c("progress-custom-content",{marginLeft:"14px"}),c("progress-icon",`
 width: 30px;
 padding-left: 14px;
 height: var(--n-icon-size-line);
 line-height: var(--n-icon-size-line);
 font-size: var(--n-icon-size-line);
 `,[w("as-text",`
 color: var(--n-text-color-line-outer);
 text-align: center;
 width: 40px;
 font-size: var(--n-font-size);
 padding-left: 4px;
 transition: color .3s var(--n-bezier);
 `)])]),w("circle, dashboard",{width:"120px"},[c("progress-custom-content",`
 position: absolute;
 left: 50%;
 top: 50%;
 transform: translateX(-50%) translateY(-50%);
 display: flex;
 align-items: center;
 justify-content: center;
 `),c("progress-text",`
 position: absolute;
 left: 50%;
 top: 50%;
 transform: translateX(-50%) translateY(-50%);
 display: flex;
 align-items: center;
 color: inherit;
 font-size: var(--n-font-size-circle);
 color: var(--n-text-color-circle);
 font-weight: var(--n-font-weight-circle);
 transition: color .3s var(--n-bezier);
 white-space: nowrap;
 `),c("progress-icon",`
 position: absolute;
 left: 50%;
 top: 50%;
 transform: translateX(-50%) translateY(-50%);
 display: flex;
 align-items: center;
 color: var(--n-icon-color);
 font-size: var(--n-icon-size-circle);
 `)]),w("multiple-circle",`
 width: 200px;
 color: inherit;
 `,[c("progress-text",`
 font-weight: var(--n-font-weight-circle);
 color: var(--n-text-color-circle);
 position: absolute;
 left: 50%;
 top: 50%;
 transform: translateX(-50%) translateY(-50%);
 display: flex;
 align-items: center;
 justify-content: center;
 transition: color .3s var(--n-bezier);
 `)]),c("progress-content",{position:"relative"}),c("progress-graph",{position:"relative"},[c("progress-graph-circle",[B("svg",{verticalAlign:"bottom"}),c("progress-graph-circle-fill",`
 stroke: var(--n-fill-color);
 transition:
 opacity .3s var(--n-bezier),
 stroke .3s var(--n-bezier),
 stroke-dasharray .3s var(--n-bezier);
 `,[w("empty",{opacity:0})]),c("progress-graph-circle-rail",`
 transition: stroke .3s var(--n-bezier);
 overflow: hidden;
 stroke: var(--n-rail-color);
 `)]),c("progress-graph-line",[w("indicator-inside",[c("progress-graph-line-rail",`
 height: 16px;
 line-height: 16px;
 border-radius: 10px;
 `,[c("progress-graph-line-fill",`
 height: inherit;
 border-radius: 10px;
 `),c("progress-graph-line-indicator",`
 background: #0000;
 white-space: nowrap;
 text-align: right;
 margin-left: 14px;
 margin-right: 14px;
 height: inherit;
 font-size: 12px;
 color: var(--n-text-color-line-inner);
 transition: color .3s var(--n-bezier);
 `)])]),w("indicator-inside-label",`
 height: 16px;
 display: flex;
 align-items: center;
 `,[c("progress-graph-line-rail",`
 flex: 1;
 transition: background-color .3s var(--n-bezier);
 `),c("progress-graph-line-indicator",`
 background: var(--n-fill-color);
 font-size: 12px;
 transform: translateZ(0);
 display: flex;
 vertical-align: middle;
 height: 16px;
 line-height: 16px;
 padding: 0 10px;
 border-radius: 10px;
 position: absolute;
 white-space: nowrap;
 color: var(--n-text-color-line-inner);
 transition:
 right .2s var(--n-bezier),
 color .3s var(--n-bezier),
 background-color .3s var(--n-bezier);
 `)]),c("progress-graph-line-rail",`
 position: relative;
 overflow: hidden;
 height: var(--n-rail-height);
 border-radius: 5px;
 background-color: var(--n-rail-color);
 transition: background-color .3s var(--n-bezier);
 `,[c("progress-graph-line-fill",`
 background: var(--n-fill-color);
 position: relative;
 border-radius: 5px;
 height: inherit;
 width: 100%;
 max-width: 0%;
 transition:
 background-color .3s var(--n-bezier),
 max-width .2s var(--n-bezier);
 `,[w("processing",[B("&::after",`
 content: "";
 background-image: var(--n-line-bg-processing);
 animation: progress-processing-animation 2s var(--n-bezier) infinite;
 `)])])])])])]),B("@keyframes progress-processing-animation",`
 0% {
 position: absolute;
 left: 0;
 top: 0;
 bottom: 0;
 right: 100%;
 opacity: 1;
 }
 66% {
 position: absolute;
 left: 0;
 top: 0;
 bottom: 0;
 right: 0;
 opacity: 0;
 }
 100% {
 position: absolute;
 left: 0;
 top: 0;
 bottom: 0;
 right: 0;
 opacity: 0;
 }
 `)]),K=Object.assign(Object.assign({},T.props),{processing:Boolean,type:{type:String,default:"line"},gapDegree:Number,gapOffsetDegree:Number,status:{type:String,default:"default"},railColor:[String,Array],railStyle:[String,Array],color:[String,Array,Object],viewBoxWidth:{type:Number,default:100},strokeWidth:{type:Number,default:7},percentage:[Number,Array],unit:{type:String,default:"%"},showIndicator:{type:Boolean,default:!0},indicatorPosition:{type:String,default:"outside"},indicatorPlacement:{type:String,default:"outside"},indicatorTextColor:String,circleGap:{type:Number,default:1},height:Number,borderRadius:[String,Number],fillBorderRadius:[String,Number],offsetDegree:Number}),ee=R({name:"Progress",props:K,setup(e){const i=$(()=>e.indicatorPlacement||e.indicatorPosition),p=$(()=>{if(e.gapDegree||e.gapDegree===0)return e.gapDegree;if(e.type==="dashboard")return 75}),{mergedClsPrefixRef:m,inlineThemeDisabled:d}=L(e),n=T("Progress","-progress",F,X,e,m),t=$(()=>{const{status:u}=e,{common:{cubicBezierEaseInOut:f},self:{fontSize:h,fontSizeCircle:b,railColor:a,railHeight:y,iconSizeCircle:l,iconSizeLine:o,textColorCircle:x,textColorLineInner:C,textColorLineOuter:v,lineBgProcessing:S,fontWeightCircle:k,[A("iconColor",u)]:D,[A("fillColor",u)]:z}}=n.value;return{"--n-bezier":f,"--n-fill-color":z,"--n-font-size":h,"--n-font-size-circle":b,"--n-font-weight-circle":k,"--n-icon-color":D,"--n-icon-size-circle":l,"--n-icon-size-line":o,"--n-line-bg-processing":S,"--n-rail-color":a,"--n-rail-height":y,"--n-text-color-circle":x,"--n-text-color-line-inner":C,"--n-text-color-line-outer":v}}),s=d?_("progress",$(()=>e.status[0]),t,e):void 0;return{mergedClsPrefix:m,mergedIndicatorPlacement:i,gapDeg:p,cssVars:d?void 0:t,themeClass:s==null?void 0:s.themeClass,onRender:s==null?void 0:s.onRender}},render(){const{type:e,cssVars:i,indicatorTextColor:p,showIndicator:m,status:d,railColor:n,railStyle:t,color:s,percentage:u,viewBoxWidth:f,strokeWidth:h,mergedIndicatorPlacement:b,unit:a,borderRadius:y,fillBorderRadius:l,height:o,processing:x,circleGap:C,mergedClsPrefix:v,gapDeg:S,gapOffsetDegree:k,themeClass:D,$slots:z,onRender:N}=this;return N==null||N(),r("div",{class:[D,`${v}-progress`,`${v}-progress--${e}`,`${v}-progress--${d}`],style:i,"aria-valuemax":100,"aria-valuemin":0,"aria-valuenow":u,role:e==="circle"||e==="line"||e==="dashboard"?"progressbar":"none"},e==="circle"||e==="dashboard"?r(H,{clsPrefix:v,status:d,showIndicator:m,indicatorTextColor:p,railColor:n,fillColor:s,railStyle:t,offsetDegree:this.offsetDegree,percentage:u,viewBoxWidth:f,strokeWidth:h,gapDegree:S===void 0?e==="dashboard"?75:0:S,gapOffsetDegree:k,unit:a},z):e==="line"?r(E,{clsPrefix:v,status:d,showIndicator:m,indicatorTextColor:p,railColor:n,fillColor:s,railStyle:t,percentage:u,processing:x,indicatorPlacement:b,unit:a,fillBorderRadius:l,railBorderRadius:y,height:o},z):e==="multiple-circle"?r(V,{clsPrefix:v,strokeWidth:h,railColor:n,fillColor:s,railStyle:t,viewBoxWidth:f,percentage:u,showIndicator:m,circleGap:C},z):null)}});function re(e){return g.get("/adobe-accounts",{params:e})}function te(e){return g.post("/adobe-accounts",e)}function oe(e,i){return g.put(`/adobe-accounts/${e}`,i)}function ie(e){return g.delete(`/adobe-accounts/${e}`)}function ne(e){return g.post("/adobe-accounts/batch-delete",{ids:e})}function se(e,i){return g.post("/adobe-accounts/batch-import",{content:e,on_duplicate:i})}function ae(e){return g.post(`/adobe-accounts/${e}/test-email`)}function le(e){return g.post(`/adobe-accounts/${e}/login`)}function ce(e){return g.post(`/adobe-accounts/${e}/check`)}function de(e,i){return g.get(`/adobe-accounts/${e}/members`,{params:i})}function ue(e,i){return g.post(`/adobe-accounts/${e}/members/batch-grant`,i)}function ge(e,i){return g.post(`/adobe-accounts/${e}/members/batch-delete`,{ids:i})}function pe(e,i=9){return g.post(`/adobe-accounts/${e}/members/build-team`,{count:i})}function fe(e,i=0){return g.get(`/adobe-accounts/jobs/${e}`,{params:{log_offset:i}})}function he(e,i=9){return g.post("/adobe-accounts/build-team-batch",{admin_ids:e,count:i})}function be(e=30){return g.get("/adobe-accounts/jobs",{params:{limit:e}})}function me(e){return g.post("/adobe-accounts/jobs/batch-delete",{ids:e})}function ye(e){return g.post(`/adobe-accounts/jobs/${e}/clear-logs`)}export{ee as N,ge as a,ue as b,pe as c,se as d,re as e,he as f,fe as g,te as h,ne as i,le as j,ce as k,de as l,ie as m,be as n,me as o,ye as p,ae as t,oe as u};
