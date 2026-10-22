const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const vm=require('node:vm');

function environment(href='http://localhost:45678/owl_prince_iphone_test.html'){
 let now=0,id=0;const timers=new Map();
 const set=(fn,ms,repeat=false)=>{const key=++id;timers.set(key,{fn,at:now+ms,ms,repeat});return key};
 function advance(ms){const end=now+ms;for(let n=0;n<10000;n++){
  const next=[...timers].filter(([,t])=>t.at<=end).sort((a,b)=>a[1].at-b[1].at)[0];if(!next){now=end;return}
  const [key,t]=next;now=t.at;if(t.repeat)t.at+=t.ms;else timers.delete(key);t.fn();
 }throw Error('too many timer callbacks')}
 class Socket{
  static all=[];
  constructor(url){this.url=url;this.readyState=0;Socket.all.push(this)}
  open(){this.readyState=1;this.onopen?.()}
  message(data){this.onmessage?.({data})}
  close(){this.readyState=3;this.onclose?.()}
 }
 const window={location:{href}};
 vm.runInNewContext(fs.readFileSync('viewer/tracking-input-v21.js','utf8'),{
  window,URL,WebSocket:Socket,performance:{now:()=>now},
  setTimeout:(fn,ms)=>set(fn,ms),clearTimeout:key=>timers.delete(key),
  setInterval:(fn,ms)=>set(fn,ms,true),clearInterval:key=>timers.delete(key),
  // Deliberately no structuredClone: parsed poses contain only plain data.
 });
 const model={setParams(p){this.params={...p}}},c=new window.L2DInput.Controller(model),messages=[];
 const input=new window.L2DInput.IphoneInput(c,t=>messages.push(t));
 return {...window.L2DInput,c,input,model,messages,Socket,advance,timers};
}
const frame=()=>JSON.stringify({FaceFound:true,Rotation:{x:0,y:0,z:0},Position:{x:0,y:0,z:0},BlendShapes:[]});

test('local endpoint follows the HTTP page and uses the IPv4 bind address',()=>{
 const e=environment();const p=e.connectionPlan('http://localhost:45678/model.html','ws://localhost:8765');
 assert.equal(p.url,'ws://127.0.0.1:45678/');assert.equal(p.setupUrl,'http://localhost:45678/');
 assert.equal(e.connectionPlan('http://127.0.0.1:8765/model.html').url,'ws://127.0.0.1:8765/');
 assert.equal(e.connectionPlan('http://localhost:45678/model.html','ws://localhost:9000/').url,'ws://localhost:9000/');
});
test('file opening is stopped with an explicit link instead of a retry loop',()=>{
 const e=environment('file:///Users/example/Downloads/owl_prince_iphone_test.html');e.input.start();
 assert.equal(e.input.phase,'blocked');assert.equal(e.input.running,false);assert.equal(e.Socket.all.length,0);assert.equal(e.timers.size,0);
 assert.match(e.messages.at(-1),/直接開いて/);assert.equal(e.input.plan.setupUrl,'http://localhost:8765/');
 assert.equal(e.connectionPlan('https://unrelated.example/model.html').allowed,false);
});
test('an uncompleted handshake times out and a late callback cannot overwrite a new connection',()=>{
 const e=environment();e.input.start();const first=e.Socket.all[0],late=first.onopen;
 e.advance(5000);assert.equal(e.input.phase,'error');assert.match(e.input.lastError,/5秒/);
 e.advance(1000);assert.equal(e.Socket.all.length,2);late();assert.equal(e.input.phase,'connecting');
 e.Socket.all[1].open();assert.equal(e.input.phase,'connected');e.input.stop();assert.equal(e.timers.size,0);
});
test('an open socket without iPhone frames is distinguished from a connection failure',()=>{
 const e=environment();e.input.start();e.Socket.all[0].open();e.advance(3000);
 assert.equal(e.input.phase,'waiting-data');assert.match(e.messages.at(-1),/中継には接続済み/);
 assert.equal(e.Socket.all.length,1);e.input.stop();e.advance(10000);assert.equal(e.Socket.all.length,1);
});
test('bad receive data is visible and a subsequent good frame recovers without native structuredClone',()=>{
 const e=environment();e.input.start();const s=e.Socket.all[0];s.open();s.message('{broken');
 assert.equal(e.input.receiveErrors,1);assert.equal(e.input.phase,'error');assert.match(e.input.lastError,/受信データ処理エラー/);
 s.message(frame());e.c.tick(0);assert.equal(e.input.phase,'tracking');assert.equal(e.input.appliedFrames,1);assert.equal(e.input.lastError,'');
 assert.equal(e.model.params.EyeLOpen,1);assert.match(e.input.lastIssue,/受信データ処理エラー/);
 for(let i=0;i<20;i++){e.advance(20);s.message(frame())}
 assert.equal(e.input.calibrate(),true);e.input.stop();
});
test('a mapping exception is reported rather than silently leaving a waiting message',()=>{
 const e=environment();e.input.start();const s=e.Socket.all[0];s.open();const original=e.input.mapper.frame;
 e.input.mapper.frame=()=>{throw Error('mapping failed')};s.message(frame());
 assert.equal(e.input.getDiagnostics().receiveErrors,1);assert.match(e.messages.at(-1),/mapping failed/);
 e.input.mapper.frame=original;s.message(frame());assert.equal(e.input.phase,'tracking');e.input.stop();
});
test('stop clears all reconnect and watchdog work even if the socket opens later',()=>{
 const e=environment();e.input.start();const s=e.Socket.all[0],late=s.onopen;e.input.stop();late();e.advance(20000);
 assert.equal(e.input.phase,'stopped');assert.equal(e.Socket.all.length,1);assert.equal(e.timers.size,0);
});
