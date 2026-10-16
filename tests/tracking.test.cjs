const {test} = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const window = {};
vm.runInNewContext(fs.readFileSync('viewer/tracking.js','utf8'), {window});
const Tracker = window.L2DTracker;
function frame(dx=0,dy=0,noseOffset=0,bs={}) {
  const l = Array.from({length:478},()=>({x:0.5+dx,y:0.5+dy}));
  for (const [i,x,y] of [[33,.4,.4],[263,.6,.4],[1,.5+noseOffset,.45],[152,.5,.65],[61,.46,.57],[291,.54,.57]]) l[i]={x:x+dx,y:y+dy};
  return {faceLandmarks:[l],faceBlendshapes:[{categories:Object.entries(bs).map(([categoryName,score])=>({categoryName,score}))}]};
}
function fixture() {
  const model={params:{},setParam(k,v){this.params[k]=v},setParams(o){Object.assign(this.params,o)}};
  const tr=new Tracker(model,{smooth:0});let result=frame();
  tr.landmarker={detectForVideo:()=>result};
  const feed=f=>{result=f;assert.equal(tr.feed({},0),true)};
  feed(frame());tr.calibrate();feed(frame());return {tr,model,feed};
}
test('face position translates the body without changing head rotation',()=>{
  const {model,feed}=fixture();feed(frame(.05,.04));
  assert.ok(Math.abs(model.params.BodyX+.375)<1e-8);
  assert.ok(Math.abs(model.params.BodyY-.3)<1e-8);
  assert.ok(Math.abs(model.params.AngleX)<1e-8);
  assert.ok(Math.abs(model.params.AngleY)<1e-8);
  assert.equal(model.params.AngleZ,0);
});
test('head turn stays capped at 5 degrees and does not move the body',()=>{
  const {model,feed}=fixture();feed(frame(0,0,.25));
  assert.equal(model.params.AngleX,-5);assert.equal(model.params.BodyX,0);assert.equal(model.params.BodyY,0);
});
test('large translations clamp, calibration recentres, and inversion is consistent',()=>{
  const {tr,model,feed}=fixture();feed(frame(.5,.5));
  assert.equal(model.params.BodyX,-1);assert.equal(model.params.BodyY,1);
  tr.calibrate();feed(frame(.5,.5));assert.equal(model.params.BodyX,0);assert.equal(model.params.BodyY,0);
  tr.opts.invX=true;tr.opts.invY=true;feed(frame(.55,.54));
  assert.ok(model.params.BodyX>0);assert.ok(model.params.BodyY<0);
});
test('mouth opening ignores expression classifications',()=>{
  const {model,feed}=fixture();
  feed(frame(0,0,0,{jawOpen:0,mouthSmileLeft:1,mouthSmileRight:1,mouthPucker:1}));
  assert.equal(model.params.MouthOpen,0);
  feed(frame(0,0,0,{jawOpen:.4,mouthFunnel:1,mouthStretchRight:1}));
  assert.ok(model.params.MouthOpen>0 && model.params.MouthOpen<1);
  for(const key of ['VowelA','VowelI','VowelU','VowelO','Smile'])assert.equal(model.params[key],undefined);
});
test('mouth has monotonic intermediate motion and settles fully open/closed',()=>{
  const {model,feed}=fixture();let prev=0;
  for(let i=0;i<12;i++){feed(frame(0,0,0,{jawOpen:.4}));assert.ok(model.params.MouthOpen>=prev);prev=model.params.MouthOpen;}
  assert.equal(model.params.MouthOpen,1);
  feed(frame(0,0,0,{jawOpen:0}));assert.ok(model.params.MouthOpen>0 && model.params.MouthOpen<1);
  prev=model.params.MouthOpen;
  for(let i=0;i<12;i++){feed(frame(0,0,0,{jawOpen:0}));assert.ok(model.params.MouthOpen<=prev);prev=model.params.MouthOpen;}
  assert.equal(model.params.MouthOpen,0);
  for(let i=0;i<20;i++)feed(frame(0,0,0,{jawOpen:.22}));
  assert.ok(Math.abs(model.params.MouthOpen-.5)<.001);
});
test('tracking preserves manual smile while independently opening the mouth',()=>{
  const {model,feed}=fixture();model.params.Smile=1;
  for(let i=0;i<12;i++)feed(frame(0,0,0,{jawOpen:.6}));
  assert.equal(model.params.Smile,1);assert.equal(model.params.MouthOpen,1);
  model.params.Smile=0;
  for(let i=0;i<12;i++)feed(frame(0,0,0,{jawOpen:0,mouthSmileLeft:1,mouthSmileRight:1}));
  assert.equal(model.params.Smile,0);assert.equal(model.params.MouthOpen,0);
});
test('vertical head rotation retains the original up/down limits',()=>{
  const {model,feed}=fixture();
  const down=frame();down.faceLandmarks[0][1].y=.8;feed(down);assert.equal(model.params.AngleY,-10);
  const up=frame();up.faceLandmarks[0][1].y=.2;feed(up);assert.equal(model.params.AngleY,5);
  const r=JSON.parse(fs.readFileSync('projects/owl_prince/rig_spec.json','utf8'));
  for(const [id,min,max] of [['AngleX',-5,5],['AngleY',-10,5],['AngleZ',-5,5]]){
    const p=r.params.find(p=>p.id===id);assert.equal(p.min,min);assert.equal(p.max,max);
  }
});

// Column-major Rz * Ry * Rx: independent of the 2D nose ratios above.
function poseFrame(yaw=0,pitch=0,roll=0,dx=0,dy=0) {
  const r=frame(dx,dy),d=Math.PI/180;
  const cy=Math.cos(yaw*d),sy=Math.sin(yaw*d),cx=Math.cos(pitch*d),sx=Math.sin(pitch*d),cz=Math.cos(roll*d),sz=Math.sin(roll*d);
  r.facialTransformationMatrixes=[{data:[
    cz*cy,sz*cy,-sy,0,
    cz*sy*sx-sz*cx,sz*sy*sx+cz*cx,cy*sx,0,
    cz*sy*cx+sz*sx,sz*sy*cx-cz*sx,cy*cx,0,
    0,0,-50,1,
  ]}];return r;
}
test('real 3D camera rotation drives the head even when nose ratios do not move',()=>{
  const {model,feed}=fixture();feed(poseFrame());
  feed(poseFrame(3,2,1));
  assert.ok(Math.abs(model.params.AngleX+3)<1e-8);
  assert.ok(Math.abs(model.params.AngleY+2)<1e-8);
  assert.ok(Math.abs(model.params.AngleZ-1)<1e-8);
  assert.equal(model.params.BodyX,0);assert.equal(model.params.BodyY,0);
  feed(poseFrame(25,20,15));
  assert.equal(model.params.AngleX,-5);assert.equal(model.params.AngleY,-10);assert.equal(model.params.AngleZ,5);
  feed(poseFrame(-25,-20,-15));
  assert.equal(model.params.AngleX,5);assert.equal(model.params.AngleY,5);assert.equal(model.params.AngleZ,-5);
});
test('3D rotation calibration and position calibration remain independent',()=>{
  const {model,tr,feed}=fixture();feed(poseFrame());feed(poseFrame(8,9,-3,.02,.03));tr.calibrate();
  for(const k of ['AngleX','AngleY','AngleZ','BodyX','BodyY'])assert.equal(model.params[k],0);
  feed(poseFrame(8,9,-3,.07,.07));
  for(const k of ['AngleX','AngleY','AngleZ'])assert.ok(Math.abs(model.params[k])<1e-8);
  assert.ok(Math.abs(model.params.BodyX+.375)<1e-8);assert.ok(Math.abs(model.params.BodyY-.3)<1e-8);
  tr.opts.invX=true;tr.opts.invY=true;tr.opts.invZ=true;feed(poseFrame(11,11,-2,.02,.03));
  assert.ok(Math.abs(model.params.AngleX-3)<1e-8);assert.ok(Math.abs(model.params.AngleY-2)<1e-8);assert.ok(Math.abs(model.params.AngleZ+1)<1e-8);
});
test('invalid camera matrices fall back to landmarks without freezing or NaN',()=>{
  const {model,feed}=fixture();const f=frame(0,0,.25);f.facialTransformationMatrixes=[{data:Array(16).fill(NaN)}];feed(f);
  assert.equal(model.params.AngleX,-5);assert.ok(Number.isFinite(model.params.AngleY));
});

test('automatic A/I selection is discrete, debounced and preserves manual expressions',()=>{
  const {model,feed}=fixture();model.params.Smile=1;model.params.Surprise=0;
  const wide=()=>frame(0,0,0,{jawOpen:.12,mouthStretchLeft:.8,mouthStretchRight:.8});
  feed(wide());feed(wide());assert.equal(model.params.MouthForm,0);
  feed(wide());assert.equal(model.params.MouthForm,1);assert.ok(model.params.MouthOpen>0);
  for(let i=0;i<6;i++)feed(frame(0,0,0,{jawOpen:.15,mouthStretchLeft:.22,mouthStretchRight:.22}));
  assert.equal(model.params.MouthForm,1); // hysteresis at the boundary
  for(let i=0;i<3;i++)feed(frame(0,0,0,{jawOpen:.7,mouthStretchLeft:.8,mouthStretchRight:.8}));
  assert.equal(model.params.MouthForm,0); // a tall jaw takes priority
  assert.equal(model.params.Smile,1);assert.equal(model.params.Surprise,0);
  for(let i=0;i<12;i++)feed(frame());
  assert.equal(model.params.MouthOpen,0);
  assert.equal(model.params.VowelE,undefined);
});

test('wide narrow lip geometry also selects I, independently of face translation and tilt',()=>{
  const {model,feed}=fixture();
  const wide=frame(0,0,0,{jawOpen:.1});
  for(const [i,x,y] of [[61,.45,.57],[291,.55,.57],[13,.5,.5625],[14,.5,.5775]])wide.faceLandmarks[0][i]={x,y};
  for(let i=0;i<6;i++)feed(wide);
  assert.equal(model.params.MouthForm,1);assert.ok(model.params.MouthOpen>.3);
  const translated=JSON.parse(JSON.stringify(wide));
  for(const p of translated.faceLandmarks[0]){p.x+=.02;p.y+=.03}
  for(let i=0;i<3;i++)feed(translated);
  assert.equal(model.params.MouthForm,1);
  assert.ok(model.params.BodyY>0);assert.equal(model.params.AngleZ,0);
  const tilted=JSON.parse(JSON.stringify(translated)),a=.2;
  for(const p of tilted.faceLandmarks[0]){
    const x=p.x-.52,y=p.y-.43;p.x=.52+x*Math.cos(a)-y*Math.sin(a);p.y=.43+x*Math.sin(a)+y*Math.cos(a);
  }
  for(let i=0;i<3;i++)feed(tilted);
  assert.equal(model.params.MouthForm,1);
  for(let i=0;i<12;i++)feed(frame());
  assert.equal(model.params.MouthOpen,0);
});
