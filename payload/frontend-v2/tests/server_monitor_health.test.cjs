const {test} = require('node:test');
const assert = require('node:assert/strict');
const {health, tone, resourceScore} = require('../server-monitor.js');
const sample = () => ({container:true, stale:false, current:{host:{cpu_percent:30,memory_percent:40,io_wait_percent:1},application:{cpu_percent:20,memory_percent:50,memory_limit:1024},disk:{percent:40}}});
test('resource-only score and risk caps agree at exact boundaries', () => {
  const data = sample();
  assert.equal(health(data).score,100);
  for (const [value, state, max] of [[79.9,'good',100],[80,'warn',79],[89.9,'warn',79],[90,'bad',59],[100,'bad',59]]) {
    data.current.host.cpu_percent=value;
    const result=health(data);
    assert.equal(result.tone,state); assert.ok(result.score<=max);
    assert.equal(tone(value),state);
  }
});
test('every scored dimension can cap the total, including IO and app memory', () => {
  for (const [group,key,value] of [['host','cpu_percent',90],['host','memory_percent',90],['host','io_wait_percent',20],['application','cpu_percent',90],['application','memory_percent',90],['disk','percent',90]]) {
    const data=sample(); data.current[group][key]=value;
    assert.equal(health(data).tone,'bad'); assert.ok(health(data).score<=59);
  }
  const data=sample(); data.current.host.io_wait_percent=10;
  assert.equal(health(data).tone,'warn'); assert.equal(tone(10,10,20),'warn');
});
test('missing, invalid, paused and stale data cannot produce a healthy score', () => {
  for (const value of [null,undefined,NaN,Infinity,-1,101,'50']) {
    const data=sample(); data.current.host.cpu_percent=value;
    assert.equal(health(data).score,null); assert.equal(health(data).tone,'unknown');
  }
  assert.equal(health({}).score,null);
  assert.equal(health({...sample(),stale:true}).score,null);
  assert.equal(health(sample(),true).score,null);
  const data=sample(); delete data.current.application.cpu_percent;
  assert.equal(health(data).score,null);
});
test('no visible memory limit is explicit and not fabricated as zero percent', () => {
  const data=sample(); data.current.application.memory_limit=null;
  data.current.application.memory_percent=null;
  const result=health(data);
  assert.equal(result.score,100); assert.equal(result.items.length,5);
  assert.match(result.excluded,/未提供有效内存上限/);
  data.container=false;
  assert.equal(health(data).items.length,4);
  assert.match(health(data).excluded,/非容器环境/);
});
test('traffic silence, historic OOM and 5xx do not misrepresent the resource score', () => {
  const data=sample(); data.current.http={count:0,p95_ms:null}; data.current.application.oom_kills=5;
  assert.equal(health(data).score,100);
  data.current.http={count:100,server_errors:20,error_percent:20};
  assert.equal(health(data).score,100);
});
test('score is bounded and monotonic over valid resource ranges', () => {
  for (const [warn,bad] of [[80,90],[10,20]]) {
    let previous=100;
    for(let i=0;i<=1000;i++) {
      const value=resourceScore(i/10,warn,bad);
      assert.ok(value>=0&&value<=100); assert.ok(value<=previous+1e-8); previous=value;
    }
  }
});
