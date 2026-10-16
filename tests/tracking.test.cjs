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
