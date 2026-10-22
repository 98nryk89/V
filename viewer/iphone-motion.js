/* Learn the three physical directions explicitly. No assumed raw Euler axes. */
(function(global){
 'use strict';
 const keys=['x','y','z'];
 const norm=v=>Math.hypot(...v),dot=(a,b)=>a.reduce((s,v,i)=>s+v*b[i],0);
 const cross=(a,b)=>[a[1]*b[2]-a[2]*b[1],a[2]*b[0]-a[0]*b[2],a[0]*b[1]-a[1]*b[0]];
 const multiply=(a,b)=>[
  a[3]*b[0]+a[0]*b[3]+a[1]*b[2]-a[2]*b[1],
  a[3]*b[1]-a[0]*b[2]+a[1]*b[3]+a[2]*b[0],
  a[3]*b[2]+a[0]*b[1]-a[1]*b[0]+a[2]*b[3],
  a[3]*b[3]-a[0]*b[0]-a[1]*b[1]-a[2]*b[2]];
 function quaternion(raw){
  // Official VTS Unity example: Euler(-raw.y,-raw.x,raw.z).
  // Unity applies Z, then X, then Y: q = qY * qX * qZ.
  const half=Math.PI/360,x=-raw.y*half,y=-raw.x*half,z=raw.z*half;
  return multiply(multiply([0,Math.sin(y),0,Math.cos(y)],[Math.sin(x),0,0,Math.cos(x)]),[0,0,Math.sin(z),Math.cos(z)]);
 }
 function rotationVector(rotation,neutral){
  const a=quaternion(rotation),b=quaternion(neutral);
  let q=multiply(a,[-b[0],-b[1],-b[2],b[3]]);
  if(q[3]<0)q=q.map(v=>-v);
  const size=Math.hypot(q[0],q[1],q[2]);if(size<1e-10)return [0,0,0];
  const scale=2*Math.atan2(size,q[3])*180/Math.PI/size;
  return q.slice(0,3).map(v=>v*scale);
 }
 function prepare(value){
  if(!value||value.schema!==2)return null;
  const vectors=['right','down','tilt'].map(key=>value[key]);
  if(vectors.some(v=>!Array.isArray(v)||v.length!==3||!v.every(Number.isFinite)||Math.abs(norm(v)-1)>.001))return null;
  const [right,down,tilt]=vectors.map(v=>[...v]);
  if(Math.max(Math.abs(dot(right,down)),Math.abs(dot(right,tilt)),Math.abs(dot(down,tilt)))>.65)return null;
  const det=dot(right,cross(down,tilt));if(Math.abs(det)<.45)return null;
  const inverse=[cross(down,tilt),cross(tilt,right),cross(right,down)].map(v=>v.map(x=>x/det));
  return {profile:{schema:2,right,down,tilt},inverse};
 }
 class Calibration {
  constructor(profile){const valid=prepare(profile);this.profile=valid?.profile||null;this.inverse=valid?.inverse||null;this.stage=valid?'ready':'front';this.samples={};this.origin=null}
  begin(){this.stage='front';this.samples={};this.origin=null}
  capture(rotation){
   if(!rotation||!keys.every(k=>Number.isFinite(rotation[k])))return {ok:false,error:'顔の回転を受信できていません。'};
   if(this.stage==='ready')return {ok:false,error:'合わせ直す場合は「動きの向きを合わせ直す」を押してください。'};
   if(this.stage==='front'){this.origin={...rotation};this.stage='down';return {ok:true,stage:this.stage}}
   const vector=rotationVector(rotation,this.origin),length=norm(vector);
   if(length<3)return {ok:false,error:'正面からもう少しだけ顔を動かして、静止してください。'};
   if(length>60)return {ok:false,error:'動きが大きすぎます。正面から軽く動かした姿勢で記録してください。'};
   const unit=vector.map(x=>x/length);
   if(Object.values(this.samples).some(v=>Math.abs(dot(v,unit))>.65))return {ok:false,error:'前に記録した動きと似ています。一度正面へ戻り、案内された別の動きで記録してください。'};
   if(this.stage==='down'){this.samples.down=unit;this.stage='right';return {ok:true,stage:this.stage}}
   if(this.stage==='right'){this.samples.right=unit;this.stage='tilt';return {ok:true,stage:this.stage}}
   const valid=prepare({schema:2,...this.samples,tilt:unit});
   if(!valid)return {ok:false,error:'3つの動きを分離できません。首をかしげる動きだけを記録し直してください。'};
   this.profile=valid.profile;this.inverse=valid.inverse;this.stage='ready';return {ok:true,stage:'ready',profile:this.profile};
  }
  map(rotation,neutral){
   if(this.stage!=='ready'||!this.inverse)return {right:0,down:0,tilt:0};
   const d=rotationVector(rotation,neutral);
   const [right,down,tilt]=this.inverse.map(row=>dot(row,d));return {right,down,tilt};
  }
 }
 global.L2DMotion={Calibration,validate:profile=>prepare(profile)?.profile||null};
})(window);
