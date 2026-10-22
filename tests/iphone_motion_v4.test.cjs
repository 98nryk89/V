const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs'),vm=require('node:vm');
const window={};let now=0;
for(const name of ['iphone-motion-v4.js','tracking-input-v4.js'])vm.runInNewContext(fs.readFileSync('viewer/'+name,'utf8'),{window,performance:{now:()=>now}});
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

test('left/right and both tilts with small vertical contamination never change pitch',()=>{
 const basis={right:[.6,.8,0],down:[-.8,.6,0],tilt:[0,0,-1]},m=mapper(learn(basis));
 for(const [right,down,tilt] of [[-12,-3,0],[12,3,0],[0,3,12],[0,-3,-12],[-60,-20,0],[0,20,60]]){
  const p=m.frame(raw(vector(right,down,tilt,basis)),20).params;
  near(p.AngleY,0,'cross-axis pitch must stay zero');
  near(p.AngleX,Math.max(-5,Math.min(5,right)),'horizontal preserved');
  near(p.AngleZ,Math.max(-5,Math.min(5,tilt)),'tilt preserved');
 }
});
test('deliberate down and up still work immediately with small sideways noise',()=>{
 const basis={right:[1,0,0],down:[0,1,0],tilt:[0,0,1]},m=mapper(learn(basis));
 for(const down of [-4,4]){
  const p=m.frame(raw(vector(.3,down,.2,basis)),20).params;near(p.AngleY,-down,'vertical preserved');
 }
});
test('upward look does not squint on a partial blink score, but a full blink still closes',()=>{
 const basis={right:[1,0,0],down:[0,1,0],tilt:[0,0,1]},m=mapper(learn(basis));
 const frame=raw(vector(0,-4,0,basis));frame.BlendShapes=[{k:'EyeBlinkLeft',v:.55},{k:'EyeBlinkRight',v:.6}];
 let p=m.frame(frame,20).params;near(p.AngleY,4,'up');near(p.EyeLOpen,1,'left eye stays open');near(p.EyeROpen,1,'right eye stays open');
 frame.BlendShapes=[{k:'EyeBlinkLeft',v:1},{k:'EyeBlinkRight',v:.6}];p=m.frame(frame,40).params;
 near(p.EyeLOpen,0,'deliberate left blink');near(p.EyeROpen,1,'right eye independent');
 frame.BlendShapes=[{k:'EyeBlinkLeft',v:1},{k:'EyeBlinkRight',v:1}];p=m.frame(frame,60).params;
 near(p.EyeLOpen,0,'full blink left');near(p.EyeROpen,0,'full blink right');
});
test('neutral and downward blink responses are unchanged',()=>{
 const basis={right:[1,0,0],down:[0,1,0],tilt:[0,0,1]},m=mapper(learn(basis));
 for(const down of [0,4])for(const score of [0,.2,.4,.65,1]){
  const frame=raw(vector(0,down,0,basis));frame.BlendShapes=[{k:'EyeBlinkLeft',v:score}];
  near(m.frame(frame,20).params.EyeLOpen,Math.max(0,Math.min(1,1-(score-.15)/.5)),'legacy blink');
 }
});
test('pitch suppression is continuous and can be disabled through configuration',()=>{
 const separate=window.L2DMotion.isolatePitch;
 near(separate({right:10,down:7.5,tilt:0}).down,0,'lower boundary');
 near(separate({right:10,down:10,tilt:0}).down,10,'upper boundary');
 const values=[7.5,8,8.5,9,9.5,10].map(down=>separate({right:10,down,tilt:0}).down);
 assert.ok(values.every((v,i)=>i===0||v>=values[i-1]));
 near(separate({right:10,down:3,tilt:0},0).down,3,'disabled');
});
