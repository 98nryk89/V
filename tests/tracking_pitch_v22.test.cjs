const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const vm=require('node:vm');
const window={};
let now=0;
vm.runInNewContext(fs.readFileSync('viewer/tracking-input-v22.js','utf8'),{window,performance:{now:()=>now}});
const {IphoneMapper,Controller,IphoneInput,options}=window.L2DInput;
const data=(rotation={},position={})=>({FaceFound:true,Rotation:{x:0,y:0,z:0,...rotation},Position:{x:0,y:0,z:0,...position},BlendShapes:[]});
function setup(opts={}){const m=new IphoneMapper({rotationDeadzone:0,...opts});m.frame(data(),0);return m}
function hold(m,rotation,time=20){for(let i=0;i<18;i++)m.frame(data(rotation),time+i*20)}

test('a small downward rotation nods immediately; up and down retain their separate limits',()=>{
 const m=setup();
 assert.equal(m.frame(data({x:2}),20).params.AngleY,-2);
 assert.equal(m.frame(data({x:20}),40).params.AngleY,-10);
 assert.equal(m.frame(data({x:-20}),60).params.AngleY,5);
});
test('turning, tilting, and maximum translations cannot generate a nod',()=>{
 const m=setup();
 for(const y of [-90,-5,0,5,90])for(const z of [-30,0,30])for(const x of [-100,100]){
  const p=m.frame(data({y,z},{x,y:-100}),20).params;
  assert.equal(Math.abs(p.AngleY),0,JSON.stringify({y,z,x}));
  assert.equal(p.AngleX,Math.max(-5,Math.min(5,-y)));
 }
 const p=m.frame(data({x:4,y:80,z:30},{x:100,y:100}),40).params;
 assert.equal(p.AngleY,-4);assert.equal(p.AngleX,-5);assert.equal(p.AngleZ,5);
});
test('labelled downward pose discovers either axis and sign without changing the neutral',()=>{
 for(const axis of ['x','y'])for(const sign of [-1,1]){
  const m=setup(),saved=JSON.stringify(m.neutral);hold(m,{[axis]:sign*8});
  const mapping=m.calibrateDown();assert.equal(mapping.pitchAxis,axis);assert.equal(mapping.pitchSign,-sign);
  assert.equal(JSON.stringify(m.neutral),saved);
  assert.equal(m.frame(data({[axis]:sign*4}),400).params.AngleY,-4);
  const other=axis==='x'?'y':'x';assert.equal(Math.abs(m.frame(data({[other]:90,z:30},{x:100}),420).params.AngleY),0);
 }
});
test('ambiguous, weak, moving and lost-face poses cannot overwrite axis settings',()=>{
 for(const r of [{x:1},{x:8,y:6},{x:1,z:12}]){
  const m=setup();hold(m,r);assert.equal(m.calibrateDown(),null);assert.equal(m.opts.pitchAxis,'x');
 }
 const m=setup();for(let i=1;i<20;i++)m.frame(data({x:i}),i*20);
 assert.equal(m.calibrateDown(),null);
 m.frame({FaceFound:false},400);assert.equal(m.calibrateDown(),null);
});
test('down-pose calibration handles wrapped angles and later C calibration preserves axes',()=>{
 const m=new IphoneMapper({rotationDeadzone:0});m.frame(data({y:178}),0);
 hold(m,{y:-174});assert.equal(m.calibrateDown().pitchSign,-1);
 assert.equal(m.frame(data({y:-178}),400).params.AngleY,-4);
 hold(m,{y:178},420);assert.equal(m.calibrate(true),true);assert.equal(m.opts.pitchAxis,'y');
 assert.equal(m.frame(data({y:-178}),800).params.AngleY,-4);
});
test('down calibration does not use stale packets and updates both controller and mapper',()=>{
 const c=new Controller({setParams(){}}),i=new IphoneInput(c);i.mapper.frame(data(),0);
 hold(i.mapper,{y:-8});c.found=true;c.lastFrame=340;now=2000;
 assert.equal(i.calibrateDown(),null);
 now=350;const mapping=i.calibrateDown();assert.equal(mapping.pitchAxis,'y');assert.equal(c.opts.pitchSign,1);
 assert.equal(i.mapper.opts,c.opts);assert.equal(c.opts.invY,false);
});
test('axis settings are validated rather than permitting duplicate yaw and pitch channels',()=>{
 assert.equal(options({pitchAxis:'z',pitchSign:NaN}).pitchAxis,'x');
 assert.equal(options({pitchAxis:'y',pitchSign:1}).pitchAxis,'y');
 assert.equal(options({pitchSign:0}).pitchSign,-1);
});
