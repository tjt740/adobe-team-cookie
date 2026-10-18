// Run: NODE_PATH=<directory containing jsdom> node --test tests/integration_dom.test.cjs
const {test} = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const {JSDOM} = require('jsdom');
const script = fs.readFileSync(path.join(__dirname, '../integration.js'), 'utf8');
const flush = async () => { for (let i = 0; i < 8; i++) await new Promise(resolve => setImmediate(resolve)); };
const deferred = () => { let resolve; const promise = new Promise(r => resolve = r); return {promise, resolve}; };
const response = (data, status = 200) => ({ok: status === 200, status, json: async () => data});
function harness() {
  const dom = new JSDOM('<!doctype html><body></body>', {url:'http://okad.test/okad/integration', runScripts:'outside-only', pretendToBeVisual:true});
  const w = dom.window, calls = [], timers = new Map();
  let sequence = 0;
  const state = {
    config:{enabled:true, key_configured:true, site_id:'fixture', base_url:'http://sub2.test'},
    checked_at:1000, counts:{}, active_jobs:0, jobs:[],
    items:[{source_key:'external:1', email:'one@fixture.invalid', source:'外部子号', has_cookie:true, auto_recovery:true, version:1}],
    total:201, custom:null
  };
  w.localStorage.setItem('okad_token','fixture');
  w.OKAD_ROUTE = {href: p => '/okad' + p};
  w.OKAD_NAV = {rect:()=>({left:240,top:60}), navigate:()=>{}};
  w.setInterval = callback => { const id = ++sequence; timers.set(id,callback); return id; };
  w.clearInterval = id => timers.delete(id);
  w.fetch = async (url, options) => {
    calls.push({url,options});
    if (state.custom) { const handled = state.custom(url,options); if (handled) return handled; }
    if (url.includes('/status')) return response(structuredClone({...state,custom:null}));
    if (url.includes('/sources')) return response({items:structuredClone(state.items),total:state.total,page:Number(new URL(url,'http://okad.test').searchParams.get('page'))});
    if (url.endsWith('/config')) { state.config = {...state.config,...JSON.parse(options.body)}; return response(state.config); }
    return response({message:'已提交'});
  };
  w.eval(fs.readFileSync(path.join(__dirname, '../pagination.js'), 'utf8'));
  w.eval(script);
  return {w,state,calls,timers,dom, get: id=>w.document.getElementById('integration-'+id),
    poll:async()=>{for(const cb of timers.values())cb();await flush();},
    open:async()=>{w.OKAD_INTEGRATION.open();await flush();}};
}

test('polling preserves table/button identity, focus, draft and empty-state nodes', async t => {
  const h=harness();t.after(()=>h.dom.window.close());await h.open();
  const row=h.get('sources').firstChild, button=row.querySelector('button'), empty=h.get('jobs').firstChild;
  button.focus(); h.get('base').value='https://draft.invalid';h.get('base').dispatchEvent(new h.w.Event('input',{bubbles:true}));
  for(let i=0;i<5;i++){h.state.checked_at++;await h.poll();}
  assert.equal(h.get('sources').firstChild,row);assert.equal(row.querySelector('button'),button);
  assert.equal(h.w.document.activeElement,button);assert.equal(h.get('jobs').firstChild,empty);
  assert.equal(h.get('base').value,'https://draft.invalid');assert.equal(button.disabled,false);
  h.state.items[0].delivery={state:'ready',message:'验证完成',account_id:3,updated_at:1000};await h.poll();
  assert.equal(row.querySelector('button'),button);assert.equal(h.w.document.activeElement,button);
  assert.match(row.textContent,/已验证/);assert.match(row.textContent,/更新于/);
});

test('opening twice creates one poller; close aborts reads and retains in-flight write guard', async t=>{
  const h=harness();t.after(()=>h.dom.window.close());await h.open();h.w.OKAD_INTEGRATION.open();
  assert.equal(h.timers.size,1);const write=deferred();h.state.custom=(url,o)=>o.method==='POST'?write.promise:null;
  h.get('sources').querySelector('button').click();await flush();
  h.w.OKAD_INTEGRATION.close();assert.equal(h.timers.size,0);await h.open();
  assert.equal(h.get('sources').querySelector('button').disabled,true);
  h.get('sources').querySelector('button').click();assert.equal(h.calls.filter(c=>c.options.method==='POST').length,1);
  write.resolve(response({message:'ok'}));await flush();assert.equal(h.get('sources').querySelector('button').disabled,false);
  h.w.OKAD_INTEGRATION.close();const count=h.calls.length;await h.poll();assert.equal(h.calls.length,count);
});

test('older GET response cannot overwrite completed action state',async t=>{
  const h=harness();t.after(()=>h.dom.window.close());await h.open();
  const old=deferred();let delayed=true;
  h.state.custom=(url,o)=>url.includes('/sources')&&delayed?old.promise:null;
  for(const cb of h.timers.values())cb();await flush();
  h.get('sources').querySelector('button').click();delayed=false;
  h.state.items[0].delivery={state:'pending',message:'已入队'};await flush();
  old.resolve(response({items:[{...h.state.items[0],delivery:null}],total:201,page:1}));await flush();
  assert.match(h.get('sources').textContent,/已入队/);
});

test('failed page request keeps the displayed page and retry remains available',async t=>{
  const h=harness();t.after(()=>h.dom.window.close());await h.open();
  h.state.custom=url=>url.includes('page=2')?Promise.resolve(response({detail:'fixture failure'},503)):null;
  h.get('next').click();await flush();assert.match(h.get('page').textContent,/^1 \/ 2/);
  assert.match(h.get('notice').textContent,/保留上次结果/);assert.equal(h.get('next').disabled,false);
  h.state.custom=null;h.get('next').click();await flush();assert.match(h.get('page').textContent,/^2 \/ 2/);
});

test('configuration errors retain draft and disabled integration never offers writes',async t=>{
  const h=harness();t.after(()=>h.dom.window.close());await h.open();
  h.get('base').value='https://draft.invalid';h.get('base').dispatchEvent(new h.w.Event('input',{bubbles:true}));h.get('key').value='fixture-input';
  h.state.custom=(url,o)=>o.method==='PUT'?Promise.resolve(response({detail:'连接失败'},400)):null;
  h.get('config').dispatchEvent(new h.w.Event('submit',{bubbles:true,cancelable:true}));await flush();
  assert.equal(h.get('base').value,'https://draft.invalid');assert.equal(h.get('key').value,'fixture-input');
  assert.match(h.get('notice').textContent,/连接失败/);
  h.state.config.enabled=false;await h.poll();assert.equal(h.get('setup').hidden,false);
  assert.ok([...h.get('sources').querySelectorAll('button')].every(b=>b.disabled));
});

test('slow initial load does not erase user typing and jobs use their own IDs',async t=>{
  const h=harness();t.after(()=>h.dom.window.close());const initial=deferred();
  h.state.custom=url=>url.includes('/status')?initial.promise:null;
  h.w.OKAD_INTEGRATION.open();h.get('base').value='https://typed.invalid';h.get('base').dispatchEvent(new h.w.Event('input',{bubbles:true}));
  h.state.jobs=[{source_key:'external:1',job_id:'a',state:'done',email:'a@fixture.invalid',created_at:1000},{source_key:'external:1',job_id:'b',state:'failed',email:'b@fixture.invalid',created_at:1001}];
  initial.resolve(response(structuredClone({...h.state,custom:null})));await flush();
  assert.equal(h.get('base').value,'https://typed.invalid');assert.equal(h.get('jobs').children.length,2);
  const nodes=[...h.get('jobs').children];h.state.custom=null;await h.poll();assert.deepEqual([...h.get('jobs').children],nodes);
});

test('missing recovery prerequisites disable login without disabling cookie delivery',async t=>{
  const h=harness();t.after(()=>h.dom.window.close());h.state.items[0].auto_recovery=false;
  h.state.items[0].recovery_code='missing_mail';h.state.items[0].recovery_message='缺少取信资料';await h.open();
  assert.equal(h.get('sources').querySelector('[data-action=login]').disabled,true);
  assert.equal(h.get('sources').querySelector('[data-action=push]').disabled,false);
});

test('recovery notice follows job completion instead of remaining at waiting/login',async t=>{
  const h=harness();t.after(()=>h.dom.window.close());await h.open();
  h.state.custom=(url,o)=>url.endsWith('/login')?Promise.resolve(response({job_id:'job-1',state:'queued',message:'等待登录'})):null;
  h.get('sources').querySelector('[data-action=login]').click();await flush();
  h.state.jobs=[{job_id:'job-1',source_key:'external:1',state:'done',message:'登录完成，后续同步独立重试',email:'one@fixture.invalid',created_at:1000}];
  await h.poll();assert.match(h.get('notice').textContent,/登录完成/);assert.doesNotMatch(h.get('notice').textContent,/等待登录/);
});
