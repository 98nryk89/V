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
test('mouth uses only E and ignores smile/pucker classifications',()=>{
  const {model,feed}=fixture();
  feed(frame(0,0,0,{jawOpen:0,mouthSmileLeft:1,mouthSmileRight:1,mouthPucker:1}));
  assert.equal(model.params.VowelE,0);
  feed(frame(0,0,0,{jawOpen:.4,mouthFunnel:1,mouthStretchRight:1}));
  assert.ok(model.params.VowelE>0 && model.params.VowelE<1);
  for(const key of ['VowelA','VowelI','VowelU','VowelO','Smile'])assert.equal(model.params[key],undefined);
});
test('E mouth has monotonic intermediate motion and settles fully open/closed',()=>{
  const {model,feed}=fixture();let prev=0;
  for(let i=0;i<12;i++){feed(frame(0,0,0,{jawOpen:.4}));assert.ok(model.params.VowelE>=prev);prev=model.params.VowelE;}
  assert.equal(model.params.VowelE,1);
  feed(frame(0,0,0,{jawOpen:0}));assert.ok(model.params.VowelE>0 && model.params.VowelE<1);
  prev=model.params.VowelE;
  for(let i=0;i<12;i++){feed(frame(0,0,0,{jawOpen:0}));assert.ok(model.params.VowelE<=prev);prev=model.params.VowelE;}
  assert.equal(model.params.VowelE,0);
  for(let i=0;i<20;i++)feed(frame(0,0,0,{jawOpen:.22}));
  assert.ok(Math.abs(model.params.VowelE-.5)<.001);
});
test('tracking preserves manual smile while independently opening the E mouth',()=>{
  const {model,feed}=fixture();model.params.Smile=1;
  for(let i=0;i<12;i++)feed(frame(0,0,0,{jawOpen:.6}));
  assert.equal(model.params.Smile,1);assert.equal(model.params.VowelE,1);
  model.params.Smile=0;
  for(let i=0;i<12;i++)feed(frame(0,0,0,{jawOpen:0,mouthSmileLeft:1,mouthSmileRight:1}));
  assert.equal(model.params.Smile,0);assert.equal(model.params.VowelE,0);
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
