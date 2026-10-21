const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const vm=require('node:vm');
const window={};
vm.runInNewContext(fs.readFileSync('viewer/tracking-input.js','utf8'),{window,structuredClone});
const {IphoneMapper,Controller,parse,options}=window.L2DInput;
const data=(b={},extra={})=>({FaceFound:true,Hotkey:-1,Rotation:{x:0,y:0,z:0},Position:{x:0,y:0,z:0},BlendShapes:Object.entries(b).map(([k,v])=>({k,v})),...extra});
const setup=opts=>{const mapper=new IphoneMapper(opts),model={setParams(p){this.params={...p}}},c=new Controller(model,opts);mapper.frame(data(),0);return {mapper,model,c}};
test('official payload permits unknown keys, bad values, and false faces',()=>{
 const f=parse(data({JawOpen:.6,EyeBlinkLeft:NaN},{future:{key:1}}));assert.equal(f.b.jawopen,.6);assert.equal(f.b.eyeblinkleft,0);assert.equal(parse([]),null);assert.equal(parse({FaceFound:false}).found,false);
});
test('pose clamps preserve original rotation and translation limits',()=>{
 const {mapper}=setup();const p=mapper.frame(data({}, {Rotation:{x:100,y:-100,z:100},Position:{x:-10,y:10}}),100).params;
 assert.deepEqual(JSON.parse(JSON.stringify(p)),{AngleX:5,AngleY:-10,AngleZ:5,BodyX:1,BodyY:-1,EyeLOpen:1,EyeROpen:1,MouthForm:0,MouthOpen:0,Smile:0,Surprise:0});
});
test('calibration records pose, position, and jaw neutral; Euler wrapping is short',()=>{
 const {mapper}=setup();const raw=data({JawOpen:.2},{Rotation:{x:2,y:179,z:3},Position:{x:2,y:3}});mapper.frame(raw,100);assert.ok(mapper.calibrate());let p=mapper.frame(raw,120).params;
 for(const k of ['AngleX','AngleY','AngleZ','BodyX','BodyY','MouthOpen'])assert.ok(Math.abs(p[k])<1e-12);
 p=mapper.frame(data({JawOpen:.2},{...raw,Rotation:{x:2,y:-179,z:3}}),140).params;assert.equal(p.AngleX,-2);
 mapper.frame({FaceFound:false},160);assert.equal(mapper.calibrate(),false);
});
test('axis inversion and independent motion gains are configurable',()=>{
 const {mapper}=setup({invX:true,invY:true,invZ:true,gainX:2,positionScale:2});const p=mapper.frame(data({}, {Rotation:{x:2,y:1,z:1},Position:{x:.2,y:.3}}),20).params;
 assert.equal(p.AngleX,2);assert.equal(p.AngleY,2);assert.equal(p.AngleZ,-1);assert.equal(p.BodyX,.4);assert.equal(p.BodyY,.6);
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
