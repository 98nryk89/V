const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const vm=require('node:vm');
const window={};
vm.runInNewContext(fs.readFileSync('viewer/tracking-input-v2.js','utf8'),{window,structuredClone});
const {IphoneMapper,Controller,parse,options}=window.L2DInput;
const data=(b={},extra={})=>({FaceFound:true,Hotkey:-1,Rotation:{x:0,y:0,z:0},Position:{x:0,y:0,z:0},BlendShapes:Object.entries(b).map(([k,v])=>({k,v})),...extra});
const setup=opts=>{opts={rotationDeadzone:0,positionDeadzone:0,positionScale:1,...opts};const mapper=new IphoneMapper(opts),model={setParams(p){this.params={...p}}},c=new Controller(model,opts);mapper.frame(data(),0);return {mapper,model,c}};
test('official payload permits unknown keys, bad values, and false faces',()=>{
 const f=parse(data({JawOpen:.6,EyeBlinkLeft:NaN},{future:{key:1}}));assert.equal(f.b.jawopen,.6);assert.equal(f.b.eyeblinkleft,0);assert.equal(parse([]),null);assert.equal(parse({FaceFound:false}).found,false);
});
test('pose clamps preserve original rotation and translation limits',()=>{
 const {mapper}=setup();const p=mapper.frame(data({}, {Rotation:{x:-100,y:-100,z:100},Position:{x:-10,y:10}}),100).params;
 assert.deepEqual(JSON.parse(JSON.stringify(p)),{AngleX:5,AngleY:-10,AngleZ:5,BodyX:1,BodyY:-1,EyeLOpen:1,EyeROpen:1,MouthForm:0,MouthOpen:0,Smile:0,Surprise:0});
});
test('calibration records pose, position, and jaw neutral; Euler wrapping is short',()=>{
 const {mapper}=setup();const raw=data({JawOpen:.2},{Rotation:{x:179,y:2,z:3},Position:{x:2,y:3}});mapper.frame(raw,100);assert.ok(mapper.calibrate());let p=mapper.frame(raw,120).params;
 for(const k of ['AngleX','AngleY','AngleZ','BodyX','BodyY','MouthOpen'])assert.ok(Math.abs(p[k])<1e-12);
 p=mapper.frame(data({JawOpen:.2},{...raw,Rotation:{x:-179,y:2,z:3}}),140).params;assert.equal(p.AngleX,-2);
 mapper.frame({FaceFound:false},160);assert.equal(mapper.calibrate(),false);
});
test('axis inversion and independent motion gains are configurable',()=>{
 const {mapper}=setup({invX:true,invY:true,invZ:true,gainX:2,positionScale:2});const p=mapper.frame(data({}, {Rotation:{x:1,y:2,z:1},Position:{x:.2,y:.3}}),20).params;
 assert.equal(p.AngleX,2);assert.equal(p.AngleY,-2);assert.equal(p.AngleZ,-1);assert.equal(p.BodyX,.4);assert.equal(p.BodyY,.6);
});
test('blink is crisp and independent for both eyes; wide eyes never trigger surprise',()=>{
 const {mapper,c}=setup({smoothingMs:500});c.accept(mapper.frame(data({EyeBlinkLeft:1,EyeBlinkRight:0,EyeWideLeft:1,EyeWideRight:1}),20),20);c.tick(20);
 assert.equal(c.values.EyeLOpen,0);assert.equal(c.values.EyeROpen,1);assert.equal(c.values.Surprise,0);
});
test('mouth has a dead zone, smooth opening, and only one integer phoneme at a time',()=>{
 const {mapper,c}=setup({smoothingMs:80});assert.equal(mapper.frame(data({JawOpen:.1}),20).params.MouthOpen,0);
 for(const [expected,b] of [[0,{JawOpen:.8}],[1,{JawOpen:.3,MouthStretchLeft:.8,MouthStretchRight:.8}],[2,{JawOpen:.45,MouthStretchLeft:.3,MouthStretchRight:.3}]]){
  for(let i=0;i<8;i++){const time=100+expected*1000+i*20;const f=mapper.frame(data(b),time);c.accept(f,time);c.tick(time);assert.ok([0,1,2].includes(c.values.MouthForm))}
  assert.equal(c.values.MouthForm,expected);assert.ok(c.values.MouthOpen>0);
 }
});
test('automatic smile requires both sides and a sustained strong expression',()=>{
 const {mapper}=setup();let f;for(let i=1;i<40;i++)f=mapper.frame(data({MouthSmileLeft:1,MouthSmileRight:.5}),i*20);assert.equal(f.params.Smile,0);
 for(let i=40;i<70;i++)f=mapper.frame(data({MouthSmileLeft:.9,MouthSmileRight:.9}),i*20);assert.equal(f.params.Smile,1);
 for(let i=70;i<95;i++)f=mapper.frame(data(),i*20);assert.equal(f.params.Smile,0);
});
test('smoothing is time based and zero disables it',()=>{
 function run(step){const {c}=setup({smoothingMs:100});c.previousTime=0;c.accept({found:true,hotkey:-1,params:{AngleX:5}},0);for(let t=step;t<=100;t+=step)c.tick(t);return c.values.AngleX}
 assert.ok(Math.abs(run(10)-run(20))<1e-12);assert.ok(run(10)>0&&run(10)<5);
 const {c}=setup({smoothingMs:0});c.accept({found:true,hotkey:-1,params:{AngleX:5}},0);c.tick(0);assert.equal(c.values.AngleX,5);
});
test('face loss and stale streams gradually neutralize pose mouth and expressions',()=>{
 for(const explicit of [false,true]){const {c}=setup({smoothingMs:0});c.action('surprise');c.accept({found:true,hotkey:-1,params:{AngleX:5,MouthOpen:1,EyeLOpen:0}},0);c.tick(0);
  if(explicit)c.accept({found:false,hotkey:-1},800);c.tick(800);assert.ok(c.values.AngleX>0&&c.values.AngleX<5);assert.ok(c.values.MouthOpen<1);assert.ok(c.values.Surprise<1);
  c.tick(10000);assert.equal(c.values.AngleX,0);assert.equal(c.values.MouthOpen,0);assert.equal(c.values.Surprise,0);assert.equal(c.values.EyeLOpen,1);
 }
});
test('hotkey 2 is surprise, repeated frames do not toggle; mappings 1–8 are editable',()=>{
 const {c}=setup({hotkeys:{8:'neutral',7:'auto'}});for(let i=0;i<5;i++)c.accept({found:true,hotkey:2,params:{}},i);c.tick(10);assert.equal(c.values.Surprise,1);assert.equal(c.autoSmile,false);
 c.accept({found:true,hotkey:8,params:{}},20);c.tick(20);assert.equal(c.values.Surprise,0);
 c.accept({found:true,hotkey:7,params:{Smile:1}},30);c.tick(30);assert.equal(c.autoSmile,true);assert.equal(c.values.Smile,1);
});
test('manual expression controls remain exclusive and override automatic smile',()=>{
 const {c}=setup();c.accept({found:true,hotkey:-1,params:{Smile:1}},0);c.action('surprise');c.tick(0);assert.equal(c.values.Smile,0);assert.equal(c.values.Surprise,1);
 c.action('smile',true);c.tick(20);assert.equal(c.values.Smile,1);assert.equal(c.values.Surprise,0);c.action('smile',true);c.tick(40);assert.equal(c.values.Smile,0);
 c.action('auto');c.tick(60);assert.equal(c.values.Smile,1);
});
test('settings reject nonfinite values and preserve safe bounds',()=>{assert.equal(options({smoothingMs:NaN}).smoothingMs,80);assert.equal(options({smoothingMs:-100}).smoothingMs,0);assert.equal(options({lostReturnMs:0}).lostReturnMs,100)});

test('official VTS axes: nod uses Rotation.y only and turn uses Rotation.x only',()=>{
 const {mapper}=setup();
 let p=mapper.frame(data({}, {Rotation:{x:0,y:-8,z:0}}),20).params;
 assert.equal(p.AngleY,-8);for(const k of ['AngleX','BodyX','BodyY'])assert.ok(Math.abs(p[k])<1e-10);
 p=mapper.frame(data({}, {Rotation:{x:-4,y:0,z:0}}),40).params;
 assert.equal(p.AngleX,4);assert.equal(p.AngleY,0);assert.ok(Math.abs(p.BodyX)<1e-10);
 p=mapper.frame(data({}, {Rotation:{x:0,y:8,z:0}}),60).params;assert.equal(p.AngleY,5);
 p=mapper.frame(data({}, {Rotation:{x:0,y:-30,z:0}}),80).params;assert.equal(p.AngleY,-10);
});

test('v2 defaults reject center noise and do not amplify a small raw position change to maximum',()=>{
 const mapper=new IphoneMapper();
 const base={Rotation:{x:6.86,y:-18.55,z:-26.01},Position:{x:-4.206932,y:.1654541,z:-1.639135}};
 mapper.frame(data({},base),0);
 for(let i=1;i<20;i++){
  const sign=i%2?1:-1;
  const p=mapper.frame(data({}, {Rotation:{x:base.Rotation.x+sign*.2,y:base.Rotation.y+sign*.25,z:base.Rotation.z+sign*.1},Position:{x:base.Position.x+sign*.04,y:base.Position.y+sign*.03,z:base.Position.z}}),i*20).params;
  for(const k of ['AngleX','AngleY','AngleZ','BodyX','BodyY'])assert.ok(Math.abs(p[k])<1e-10,k);
 }
 const p=mapper.frame(data({}, {...base,Position:{...base.Position,x:base.Position.x+.2}}),420).params;
 assert.ok(Math.abs(p.BodyX+.02)<1e-10);assert.ok(Math.abs(p.BodyX)<.1);
});

test('turn away and return to saved front has no automatic baseline creep',()=>{
 const mapper=new IphoneMapper();mapper.frame(data(),0);const saved=JSON.stringify(mapper.neutral);
 for(let i=1;i<=100;i++)mapper.frame(data({}, {Rotation:{x:-12,y:-15,z:4},Position:{x:3,y:-3,z:0}}),i*20);
 const p=mapper.frame(data(),2020).params;
 for(const k of ['AngleX','AngleY','AngleZ','BodyX','BodyY'])assert.ok(Math.abs(p[k])<1e-10,k);
 assert.equal(JSON.stringify(mapper.neutral),saved);
});

test('manual calibration takes the median of stable recent frames, not a single outlier',()=>{
 const mapper=new IphoneMapper();
 for(let i=0;i<=17;i++)mapper.frame(data({JawOpen:i===17?.8:0}, {Rotation:{x:i===17?.9:0,y:0,z:0},Position:{x:i===17?20:0,y:0,z:0}}),i*20);
 assert.equal(mapper.calibrate(true),true);assert.ok(mapper.calibrationSamples>=12);
 assert.ok(Math.abs(mapper.neutral.rotation.x)<1e-10);assert.equal(mapper.neutral.position.x,0);assert.equal(mapper.neutral.b.jawopen,0);
 assert.ok(Math.abs(mapper.frame(data(),360).params.AngleX)<1e-10);
});

test('calibration refuses moving or freshly reacquired faces and handles Euler wrapping',()=>{
 const mapper=new IphoneMapper();mapper.frame(data(),0);const original=JSON.stringify(mapper.neutral);
 assert.equal(mapper.calibrate(true),false);
 for(let i=1;i<=20;i++)mapper.frame(data({}, {Rotation:{x:i,y:0,z:0}}),i*20);
 assert.equal(mapper.calibrate(true),false);assert.equal(JSON.stringify(mapper.neutral),original);
 mapper.frame({FaceFound:false},420);mapper.frame(data(),440);assert.equal(mapper.calibrate(true),false);
 for(let i=1;i<=18;i++)mapper.frame(data({}, {Rotation:{x:i%2?179.9:-179.9,y:0,z:0}}),440+i*20);
 assert.equal(mapper.calibrate(true),true);
 const p=mapper.frame(data({}, {Rotation:{x:180,y:0,z:0}}),820).params;
 assert.ok(Math.abs(p.AngleX)<.01);
});
