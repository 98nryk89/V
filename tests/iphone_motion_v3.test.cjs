const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs'),vm=require('node:vm');
const window={};let now=0;
for(const name of ['iphone-motion.js','tracking-input-v3.js'])vm.runInNewContext(fs.readFileSync('viewer/'+name,'utf8'),{window,performance:{now:()=>now}});
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

test('all 48 axis orders/signs: ONLY horizontal parameter moves for left/right input',()=>{
 const perms=[[0,1,2],[0,2,1],[1,0,2],[1,2,0],[2,0,1],[2,1,0]];
 for(const axes of perms)for(const a of [-1,1])for(const b of [-1,1])for(const c of [-1,1]){
  const basis={};['right','down','tilt'].forEach((key,i)=>{basis[key]=[0,0,0];basis[key][axes[i]]=[a,b,c][i]});
  const m=mapper(learn(basis));
  for(const amount of [-60,-3,3,60]){
   const p=m.frame(raw(vector(amount,0,0,basis),{x:100,y:-100,z:100}),20).params;
   near(p.AngleX,Math.max(-5,Math.min(5,amount)),'horizontal');near(p.AngleY,0,'vertical must not move');near(p.AngleZ,0,'tilt must not move');
  }
 }
});
test('all 48 axis orders/signs: ONLY vertical parameter moves for up/down input',()=>{
 const perms=[[0,1,2],[0,2,1],[1,0,2],[1,2,0],[2,0,1],[2,1,0]];
 for(const axes of perms)for(const a of [-1,1])for(const b of [-1,1])for(const c of [-1,1]){
  const basis={};['right','down','tilt'].forEach((key,i)=>{basis[key]=[0,0,0];basis[key][axes[i]]=[a,b,c][i]});
  const m=mapper(learn(basis));
  for(const amount of [-60,-2,2,60]){
   const p=m.frame(raw(vector(0,amount,0,basis)),20).params;
   near(p.AngleX,0,'horizontal must not move');near(p.AngleY,Math.max(-10,Math.min(5,-amount)),'vertical');near(p.AngleZ,0,'tilt must not move');
  }
 }
});
test('mixed raw coordinates separate physical turn, nod, and tilt BEFORE clamping',()=>{
 const basis={right:[.6,.8,0],down:[-.8,.6,0],tilt:[0,0,-1]};
 const m=mapper(learn(basis));
 for(const [right,down,tilt] of [[4,0,0],[0,4,0],[0,-4,0],[0,0,4],[30,2,-30]]){
  const p=m.frame(raw(vector(right,down,tilt,basis)),20).params;
  near(p.AngleX,Math.max(-5,Math.min(5,right)),'horizontal');near(p.AngleY,-down,'vertical');near(p.AngleZ,Math.max(-5,Math.min(5,tilt)),'tilt');
 }
});
test('nonorthogonal measurement basis removes cross-axis leakage',()=>{
 const basis={right:[1,0,0],down:[.2,Math.sqrt(.96),0],tilt:[0,0,1]};
 const m=mapper(learn(basis));const p=m.frame(raw(vector(0,4,0,basis)),20).params;
 near(p.AngleX,0,'horizontal');near(p.AngleY,-4,'vertical');near(p.AngleZ,0,'tilt');
});
test('unconfigured or unfinished setup never guesses a direction',()=>{
 const m=mapper();for(const r of [{x:30,y:-20,z:10},{x:-40,y:40,z:-30}]){
  const p=m.frame(raw(r,{x:100,y:100,z:100}),20).params;
  for(const key of ['AngleX','AngleY','AngleZ','BodyX','BodyY'])near(p[key],0,key);
 }
});
test('ambiguous/weak movements and corrupted saved profiles are rejected',()=>{
 const c=new Calibration();c.capture(zero);assert.equal(c.capture({x:1,y:0,z:0}).ok,false);
 c.capture({x:10,y:0,z:0});assert.equal(c.capture({x:-10,y:0,z:0}).ok,false);assert.equal(c.stage,'right');
 assert.equal(validate({schema:2,right:[1,0,0],down:[-1,0,0],tilt:[0,0,1]}),null);
 assert.equal(validate({schema:2,right:[NaN,0,0],down:[0,1,0],tilt:[0,0,1]}),null);
 assert.equal(validate({pitchAxis:'x',pitchSign:-1}),null);
});
test('stable face data required for capture; stale or lost frames do not advance setup',()=>{
 const c=new Controller({setParams(){}}),input=new IphoneInput(c);
 input.mapper.frame(raw(),0);c.found=true;c.lastFrame=0;now=0;
 assert.equal(input.captureMotion().ok,false);
 for(let t=20;t<=400;t+=20)input.mapper.frame(raw(),t);
 now=2000;assert.equal(input.captureMotion().ok,false);
 now=400;c.lastFrame=400;assert.equal(input.captureMotion().ok,true);assert.equal(input.mapper.motion.stage,'down');
 input.mapper.frame({FaceFound:false},420);assert.equal(input.captureMotion().ok,false);
});
test('saved basis survives serialization, new neutral and angular wrapping',()=>{
 const basis={right:[0,0,-1],down:[-1,0,0],tilt:[0,1,0]};
 const profile=JSON.parse(JSON.stringify(learn(basis))),m=new IphoneMapper({motionProfile:profile,rotationDeadzone:0});
 m.frame(raw({x:0,y:178,z:0}),0);
 const p=m.frame(raw({x:0,y:-178,z:0}),20).params;near(p.AngleY,-4,'wrapped nod');near(p.AngleX,0,'horizontal');
 m.frame(raw(),40);assert.equal(m.calibrate(),true);
 near(m.frame(raw(encode([-4,0,0])),60).params.AngleY,-4,'recenter preserves direction');
});

test('a tilted nonzero neutral does not mix yaw into pitch even at a large turn',()=>{
 const multiply=(a,b)=>[
  a[3]*b[0]+a[0]*b[3]+a[1]*b[2]-a[2]*b[1],a[3]*b[1]-a[0]*b[2]+a[1]*b[3]+a[2]*b[0],
  a[3]*b[2]+a[0]*b[1]-a[1]*b[0]+a[2]*b[3],a[3]*b[3]-a[0]*b[0]-a[1]*b[1]-a[2]*b[2]];
 const toQ=v=>{const size=Math.hypot(...v),s=Math.sin(size*Math.PI/360)/(size||1);return [...v.map(x=>x*s),Math.cos(size*Math.PI/360)]};
 const base=toQ([10,-15,20]),basis={right:[.6,.8,0],down:[-.8,.6,0],tilt:[0,0,-1]};
 const pose=(right=0,down=0,tilt=0)=>encodeQuaternion(multiply(toQ([0,1,2].map(i=>basis.right[i]*right+basis.down[i]*down+basis.tilt[i]*tilt)),base));
 const calibration=new Calibration();calibration.capture(pose());
 for(const values of [[0,10,0],[10,0,0],[0,0,10]])assert.ok(calibration.capture(pose(...values)).ok);
 const m=new IphoneMapper({motionProfile:calibration.profile,rotationDeadzone:0});m.frame(raw(pose()),0);
 for(const amount of [-60,-4,4,60]){
  let p=m.frame(raw(pose(amount)),20).params;near(p.AngleY,0,'yaw must not nod');near(p.AngleZ,0,'yaw must not tilt');
  p=m.frame(raw(pose(0,amount)),40).params;near(p.AngleX,0,'pitch must not turn');near(p.AngleZ,0,'pitch must not tilt');
 }
});

test('stable capture remains possible when rendering limits reception to 10 fps',()=>{
 const m=mapper();for(let time=100;time<=600;time+=100)m.frame(raw(),time);
 assert.equal(m.captureMotion().ok,true);assert.equal(m.motion.stage,'down');
 for(let time=700;time<=1200;time+=100)m.frame(raw({x:0,y:8,z:0}),time);
 assert.equal(m.captureMotion().ok,true);assert.equal(m.motion.stage,'right');
});
