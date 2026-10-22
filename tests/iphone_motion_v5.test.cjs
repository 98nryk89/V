const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs'),vm=require('node:vm');
const window={};let now=0;
for(const name of ['iphone-motion-v4.js','tracking-input-v5.js'])vm.runInNewContext(fs.readFileSync('viewer/'+name,'utf8'),{window,performance:{now:()=>now}});
const {Calibration,validate}=window.L2DMotion;
const {IphoneMapper,Controller,IphoneInput}=window.L2DInput;
const zero={x:0,y:0,z:0};
const raw=(rotation=zero,position=zero)=>({FaceFound:true,Rotation:rotation,Position:position,BlendShapes:[]});
function encode(v){
 const angle=Math.hypot(...v),half=angle*Math.PI/360,scale=angle?Math.sin(half)/angle:0;
 return encodeQuaternion([v[0]*scale,v[1]*scale,v[2]*scale,Math.cos(half)]);
}
function encodeQuaternion(q){
 const [x,y,z,w]=q,degrees=180/Math.PI;
 return {x:-Math.atan2(2*(x*z+w*y),1-2*(x*x+y*y))*degrees,
         y:-Math.asin(Math.max(-1,Math.min(1,2*(w*x-y*z))))*degrees,
         z:Math.atan2(2*(x*y+w*z),1-2*(x*x+z*z))*degrees};
}

const vector=(right,down,tilt,basis)=>encode([0,1,2].map(i=>right*basis.right[i]+down*basis.down[i]+tilt*basis.tilt[i]));
function learn(basis){
 const c=new Calibration();assert.ok(c.capture(zero).ok);
 for(const kind of ['down','right','tilt']){
  const v=encode(basis[kind].map(x=>x*10));
  assert.ok(c.capture(v).ok,kind);
 }assert.equal(c.stage,'ready');return c.profile;
}
function mapper(profile){const m=new IphoneMapper({motionProfile:profile,rotationDeadzone:0});m.frame(raw(),0);return m}
function near(value,expected,label){assert.ok(Math.abs(value-expected)<1e-8,`${label}: ${value} != ${expected}`)}

const blend=(jaw=0,stretch=0)=>({...raw(),BlendShapes:[{k:'JawOpen',v:jaw},{k:'MouthStretchLeft',v:stretch},{k:'MouthStretchRight',v:stretch}]});
function mouth(){const m=mapper(learn({right:[1,0,0],down:[0,1,0],tilt:[0,0,1]}));let time=0;return {m,feed(jaw,stretch=0){let f;for(let i=0;i<8;i++)f=m.frame(blend(jaw,stretch),time+=20);return f.params}}}

test('small jaw movements open the mouth continuously, while tiny idle noise stays closed',()=>{
 const {feed}=mouth();near(feed(.008,.01).MouthOpen,0,'idle noise');
 const levels=[.03,.04,.06,.10,.20,.30].map(jaw=>feed(jaw).MouthOpen);
 assert.ok(levels[0]>0);assert.ok(levels.every((v,i)=>i===0||v>levels[i-1]));assert.ok(levels[levels.length-1]<1);
 near(feed(0,0).MouthOpen,0,'closed');
});
test('small A, I and E movements select one integer shape and old larger gestures still work',()=>{
 const {feed}=mouth();
 for(const [form,jaw,stretch] of [[0,.04,0],[1,.02,.08],[2,.10,.05],[0,.8,0],[1,.3,.8],[2,.45,.3]]){
  const p=feed(jaw,stretch);assert.equal(p.MouthForm,form);assert.ok(p.MouthOpen>0);assert.ok(Number.isInteger(p.MouthForm));
 }
});
test('both jaw and lip stretch subtract the neutral face before sensitive detection',()=>{
 const m=new IphoneMapper();m.frame(blend(.15,.20),0);
 for(let t=20;t<=400;t+=20)m.frame(blend(.15+(t===400?.005:0),.20),t);
 assert.ok(m.calibrate(true));
 let p=m.frame(blend(.15,.20),420).params;near(p.MouthOpen,0,'neutral');
 for(let t=440;t<=640;t+=20)p=m.frame(blend(.19,.20),t).params;
 assert.ok(p.MouthOpen>0&&p.MouthOpen<.2,'small opening relative to baseline');assert.equal(p.MouthForm,0);
});
test('shape changes remain discrete during smoothing and face loss closes the mouth',()=>{
 const m=mapper(),model={setParams(p){this.params={...p}}},c=new Controller(model);let time=0;
 for(const [jaw,stretch] of [[.04,0],[.02,.08],[.10,.05],[.8,0],[0,0]]){
  for(let i=0;i<16;i++){
   const f=m.frame(blend(jaw,stretch),time+=20);c.accept(f,time);c.tick(time);
   assert.ok([0,1,2].includes(c.values.MouthForm));assert.ok(c.values.MouthOpen>=0&&c.values.MouthOpen<=1);
  }
 }
 c.accept({found:false},time+=20);c.tick(time);c.tick(time+10000);near(c.values.MouthOpen,0,'face lost closes');
});
test('head angles and normalized translation inputs are identical to v4',()=>{
 const oldWindow={};for(const name of ['iphone-motion-v4.js','tracking-input-v4.js'])vm.runInNewContext(fs.readFileSync('viewer/'+name,'utf8'),{window:oldWindow,performance:{now:()=>now}});
 const basis={right:[.6,.8,0],down:[-.8,.6,0],tilt:[0,0,-1]},profile=learn(basis),a=new IphoneMapper({motionProfile:profile}),b=new oldWindow.L2DInput.IphoneMapper({motionProfile:profile});
 a.frame(raw(),0);b.frame(raw(),0);
 for(const values of [[4,0,0],[0,4,0],[0,-4,0],[0,0,-4],[-12,-3,-2]]){
  const f=raw(vector(...values,basis),{x:6,y:1,z:0}),pa=a.frame(f,20).params,pb=b.frame(f,20).params;
  for(const key of ['AngleX','AngleY','AngleZ','BodyX','BodyY','EyeLOpen','EyeROpen'])near(pa[key],pb[key],key);
 }
});
