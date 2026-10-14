/* Import drawer shares the existing Vue/Naive UI runtime and preserves draft state. */
import {createApp, ConfigProvider, k as h, r as ref, aq as useTheme, B as Button} from './assets/index-CrrzYg-U.js';
import {N as Input} from './assets/Input-fL4pqH-9.js';
import {b as Select} from './assets/text-C52gYURp.js';

const options = entries => entries.map(([value, label]) => ({value, label}));

export function mountImport(host, actions, trigger) {
  const form = ref({content:'', duplicate:'skip', otpMode:'', mailToken:''});
  const ui = ref({buttons:{}, importMessage:'', importTone:'mut', mailState:'读取中…', mailResult:'', mailPlaceholder:'粘贴 supply.ink Token'});
  const openSelect = ref(null), mailOpen = ref(false);
  const importDrawer = () => host.querySelector('#extm-import-drawer');
  function openImport() {
    openSelect.value = null;
    importDrawer().showModal();
    trigger.setAttribute('aria-expanded','true');
  }
  function closeImport() {
    openSelect.value = null;
    trigger.setAttribute('aria-expanded','false');
    const drawer = importDrawer();
    if (drawer?.open) {
      drawer.close();
      trigger.focus({preventScroll:true});
    }
  }
  const button = (id, label, onClick, props={}) => {
    const state = ui.value.buttons[id] || {};
    return h(Button, {id, ...props, disabled:!!state.disabled, loading:!!state.loading, 'aria-busy':String(!!state.loading), onClick}, () => state.text || label);
  };
  const field = (label, id, child, cls='') => h('div', {class:'extv-field '+cls}, [h('label', {id:id+'-label', for:id}, label), child]);
  const input = (id, value, update, props={}) => h(Input, {value, 'onUpdate:value':update, ...props, inputProps:{id, 'aria-labelledby':id+'-label', ...props.inputProps}});
  const select = (id, value, list, update, props={}) => h(Select, {id, value, options:list, 'onUpdate:value':update, show:openSelect.value===id, 'onUpdate:show':show=>openSelect.value=show?id:null, 'aria-labelledby':id+'-label', ...props});
  const app = createApp({name:'ExternalMemberImport', setup() {
    const {naiveTheme} = useTheme();
    return () => h(ConfigProvider, {theme:naiveTheme.value, themeOverrides:{common:{primaryColor:'#1890ff',primaryColorHover:'#46a6ff',primaryColorPressed:'#0e80e6',borderRadius:'6px'}}}, {default:() =>
        h('dialog',{id:'extm-import-drawer',class:'extv-import-drawer','aria-labelledby':'extm-import-title','aria-describedby':'extm-import-description',onClose:()=>{if(!importDrawer()?.open){openSelect.value=null;trigger.setAttribute('aria-expanded','false');}},onCancel:event=>{event.preventDefault();closeImport();},onKeydownCapture:event=>{
          if(event.key==='Escape' && openSelect.value){event.preventDefault();event.stopPropagation();openSelect.value=null;}
        },onClick:event=>{
          if(event.target!==event.currentTarget)return;
          const r=event.currentTarget.getBoundingClientRect();
          if(event.clientX<r.left || event.clientX>r.right || event.clientY<r.top || event.clientY>r.bottom)closeImport();
        }},[
          h('header',{class:'extv-drawer-header'},[
            h('div',{},[h('h3',{id:'extm-import-title'},'导入外部子号'),h('p',{id:'extm-import-description'},'批量添加账号，登录成功后自动推送 Sub2。')]),
            button('extm-import-close','×',closeImport,{quaternary:true,'aria-label':'关闭导入抽屉',autofocus:true})
          ]),
          h('div',{class:'extv-drawer-body'},[
            h('section',{class:'extv-import-examples','aria-labelledby':'extm-import-examples-title'},[
              h('h4',{id:'extm-import-examples-title'},'导入格式示例'),
              ...[
                ['仅邮箱','user@example.com'],
                ['邮箱 + Adobe 密码','user@example.com----Adobe密码'],
                ['完整邮箱凭据','邮箱----邮箱密码----ClientID----RefreshToken[----Adobe密码]']
              ].map(([label,example])=>h('div',{class:'extv-import-example'},[h('span',{},label),h('code',{},example)])),
              h('p',{},'每行一个账号；兼容 | 分隔。方括号内为可选项，填写时无需保留方括号。')
            ]),
            field('账号内容识别','extm-import',input('extm-import',form.value.content,v=>form.value.content=v,{type:'textarea',autosize:{minRows:10,maxRows:16},placeholder:'粘贴邮箱或账号凭据，每行一个账号',inputProps:{'aria-describedby':'extm-import-help'}}),'extv-import-content'),
            h('p',{id:'extm-import-help',class:'extv-import-help'},'每批最多 50 个。仅邮箱导入固定走验证码；自动取码时按粘贴顺序逐个获取验证码登录。带密码的账号优先使用密码登录。'),
            h('div',{class:'extv-import-controls'},[
              field('重复邮箱','extm-dup',select('extm-dup',form.value.duplicate,options([['skip','跳过'],['overwrite','覆盖']]),v=>form.value.duplicate=v,{to:'#extm-import-drawer'})),
              field('取码方式','extm-otp-mode',select('extm-otp-mode',form.value.otpMode,options([['','保留设置（新账号自动取码）'],['auto','自动取码（supply.ink）'],['manual','手动输入验证码（普通账号）']]),v=>{form.value.otpMode=v;if(v!=='auto')mailOpen.value=false;},{to:'#extm-import-drawer'}))
            ]),
            h('p',{class:'extv-import-help'},'普通账号可选择手动输入，收到邮件后在账号行填验证码。自动取码使用已有邮箱配置或 supply.ink Token；覆盖导入可更新已有账号设置。'),
            h('details',{id:'extm-mail-config',class:'extm-card extm-import-card',hidden:form.value.otpMode!=='auto',open:mailOpen.value,onToggle:event=>mailOpen.value=event.target.open},[
              h('summary',{},['邮件配置 · supply.ink ',h('span',{id:'extm-mail-state',class:'extm-msg mut'},ui.value.mailState)]),
              h('div',{class:'bd'},[h('p',{class:'tip'},'Token 保存在本项目，所有管理员共享；留空保留已保存配置。'),h('div',{class:'extv-mail-controls'},[
                field('邮件 Token','extm-mail-token',input('extm-mail-token',form.value.mailToken,v=>form.value.mailToken=v,{type:'password',showPasswordOn:'click',placeholder:ui.value.mailPlaceholder,autocomplete:'off'})),
                button('extm-mail-save','保存 Token',()=>actions.mail('save'),{type:'primary'}),button('extm-mail-test','测试连接',()=>actions.mail('test')),button('extm-mail-clear','清除 Token',()=>actions.mail('clear'))
              ]),h('p',{id:'extm-mail-result',class:'extm-msg',role:'status'},ui.value.mailResult)])
            ])
          ]),
          h('footer',{class:'extv-drawer-footer'},[
            h('p',{id:'extm-import-result',class:'extm-msg '+ui.value.importTone,role:'status'},ui.value.importMessage),
            h('div',{},[button('extm-import-done','关闭',closeImport),button('extm-do-import','批量导入',actions.import,{type:'primary'})])
          ])
        ])
    });
  }});
  app.mount(host);
  return {
    form:form.value, open:openImport, close:closeImport,
    update(value) {Object.assign(ui.value,value);},
    button(id,value) {ui.value.buttons[id]={...ui.value.buttons[id],...value};},
    ownsButton(id) {return !!id && !!host.querySelector('#'+id+'.n-button');},
    destroy() {closeImport();app.unmount();}
  };
}
