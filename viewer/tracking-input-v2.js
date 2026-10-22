/* iPhone pose v2: VTS Rotation.x=yaw, y=pitch. Legacy input stays unchanged. */
(function(global) {
  'use strict';
  const clamp=(v,a,b)=>Math.max(a,Math.min(b,v));
  const finite=(v,d=0)=>typeof v==='number'&&Number.isFinite(v)?v:d;
  const defaults={wsUrl:'ws://localhost:8765',smoothingMs:80,lostReturnMs:500,staleMs:750,
    gainX:1,gainY:1,gainMove:1,positionScale:.2,rotationDeadzone:.35,positionDeadzone:.1,
    invX:false,invY:false,invZ:false,
    hotkeys:{1:'smile',2:'surprise',3:'neutral',4:'auto',5:'none',6:'none',7:'none',8:'none'}};
  const rest={AngleX:0,AngleY:0,AngleZ:0,BodyX:0,BodyY:0,EyeLOpen:1,EyeROpen:1,MouthOpen:0,MouthForm:0,Smile:0,Surprise:0};
  const ranges={AngleX:[-5,5],AngleY:[-10,5],AngleZ:[-5,5],BodyX:[-1,1],BodyY:[-1,1],EyeLOpen:[0,1],EyeROpen:[0,1],MouthOpen:[0,1],Smile:[0,1],Surprise:[0,1]};
  function options(o={}) {
    const r={...defaults,...o,hotkeys:{...defaults.hotkeys,...o.hotkeys}};
    for(const [key,a,b] of [['smoothingMs',0,500],['lostReturnMs',100,3000],['staleMs',100,5000],['gainX',.1,10],['gainY',.1,10],['gainMove',.1,10],['positionScale',.01,1000],['rotationDeadzone',0,2],['positionDeadzone',0,1]])r[key]=clamp(finite(r[key],defaults[key]),a,b);
    return r;
  }
  const angleDelta=(a,b)=>((a-b+180)%360+360)%360-180;
  const deadzone=(v,width)=>Math.abs(v)<=width?0:Math.sign(v)*(Math.abs(v)-width);
  const median=values=>{const a=[...values].sort((x,y)=>x-y),i=Math.floor(a.length/2);return a.length%2?a[i]:(a[i-1]+a[i])/2};
  function parse(frame) {
    if(!frame||typeof frame!=='object'||Array.isArray(frame))return null;
    const read=(o,k)=>o?.[k]??o?.[k[0].toLowerCase()+k.slice(1)];
    const b={};const raw=read(frame,'BlendShapes');
    if(Array.isArray(raw))for(const item of raw)if(typeof item?.k==='string')b[item.k.toLowerCase()]=clamp(finite(item.v),0,1);
    const vector=k=>{const v=read(frame,k);return {x:finite(v?.x),y:finite(v?.y),z:finite(v?.z)}};
    return {found:read(frame,'FaceFound')===true,rotation:vector('Rotation'),position:vector('Position'),
      b,hotkey:finite(read(frame,'Hotkey'),-1)};
  }
  class IphoneMapper {
    constructor(opts={}){this.opts=options(opts);this.neutral=null;this.latest=null;this.resetTemporal()}
    resetTemporal(){this.active=false;this.form=0;this.candidate=0;this.candidateMs=0;this.smiling=false;this.smileHold=0;this.smileRelease=0;this.previousTime=null;this.history=[]}
    calibrate(stable=false){
      if(!this.latest?.found)return false;
      const samples=this.history;
      if(stable){
        if(samples.length<5||samples.at(-1).time-samples[0].time<240)return false;
        for(const key of ['x','y','z']){
          const differences=samples.map(s=>angleDelta(s.frame.rotation[key],this.latest.rotation[key]));
          if(Math.max(...differences)-Math.min(...differences)>2)return false;
        }
      }
      this.neutral=structuredClone(this.latest);
      if(stable)for(const key of ['x','y','z']){
        this.neutral.rotation[key]=this.latest.rotation[key]+median(samples.map(s=>angleDelta(s.frame.rotation[key],this.latest.rotation[key])));
        this.neutral.position[key]=median(samples.map(s=>s.frame.position[key]));
      }
      if(stable)this.neutral.b.jawopen=median(samples.map(s=>s.frame.b.jawopen||0));
      this.calibrationSamples=stable?samples.length:1;this.resetTemporal();return true;
    }
    frame(raw,time) {
      const f=parse(raw);if(!f)return null;
      this.latest=f;
      if(!f.found){this.resetTemporal();return {found:false,hotkey:f.hotkey}}
      this.history.push({frame:f,time});this.history=this.history.filter(s=>time-s.time<=320);
      if(!this.neutral)this.calibrate();
      const dt=this.previousTime==null?0:clamp(time-this.previousTime,0,100);this.previousTime=time;
      const n=this.neutral,o=this.opts,g=k=>f.b[k.toLowerCase()]||0;
      const jaw=Math.max(0,g('JawOpen')-(n.b.jawopen||0));
      const stretch=(g('MouthStretchLeft')+g('MouthStretchRight'))/2;
      // ARKit has no phoneme labels. These three shapes are approximations.
      if(this.active){if(jaw<.12&&stretch<.25)this.active=false}
      else if(jaw>.18||stretch>.40)this.active=true;
      const desired=jaw>.56?0:stretch>.40&&jaw<.38?1:stretch>.25&&jaw>.28?2:stretch<.18?0:this.form;
      if(desired!==this.candidate){this.candidate=desired;this.candidateMs=0}else this.candidateMs+=dt;
      if(this.candidateMs>=50)this.form=desired;
      const score=Math.min(g('MouthSmileLeft'),g('MouthSmileRight'));
      if(!this.smiling){this.smileHold=score>.80?this.smileHold+dt:0;if(this.smileHold>=450){this.smiling=true;this.smileRelease=0}}
      else{this.smileRelease=score<.55?this.smileRelease+dt:0;if(this.smileRelease>=350){this.smiling=false;this.smileHold=0}}
      const open=b=>clamp(1-(b-.15)/.5,0,1);
      return {found:true,hotkey:f.hotkey,params:{
        // Official receiver uses Unity Euler(-Rotation.y, -Rotation.x, Rotation.z).
        // Model AngleY is positive UP, opposite Unity's positive-X down rotation.
        AngleX:clamp(-deadzone(angleDelta(f.rotation.x,n.rotation.x)*o.gainX,o.rotationDeadzone)*(o.invX?-1:1),-5,5),
        AngleY:clamp(deadzone(angleDelta(f.rotation.y,n.rotation.y)*o.gainY,o.rotationDeadzone)*(o.invY?-1:1),-10,5),
        AngleZ:clamp(deadzone(angleDelta(f.rotation.z,n.rotation.z),o.rotationDeadzone)*(o.invZ?-1:1),-5,5),
        BodyX:clamp(-deadzone(f.position.x-n.position.x,o.positionDeadzone)*o.positionScale*o.gainMove*(o.invX?-1:1),-1,1),
        BodyY:clamp(-deadzone(f.position.y-n.position.y,o.positionDeadzone)*o.positionScale*o.gainMove*(o.invY?-1:1),-1,1),
        EyeLOpen:open(g('EyeBlinkLeft')),EyeROpen:open(g('EyeBlinkRight')),
        MouthForm:this.form,MouthOpen:this.active?Math.max(clamp((jaw-.13)/.42,0,1),this.form?clamp((stretch-.25)/.5,0,1):0):0,
        Smile:this.smiling?1:0,Surprise:0}};
    }
  }
  class Controller {
    constructor(model,opts={}) {
      this.model=model;this.opts=options(opts);this.target={...rest};this.values={...rest};
      this.autoSmile=true;this.manual=null;this.found=false;this.lastFrame=-Infinity;this.lastHotkey=-1;this.previousTime=null;
    }
    action(action,toggle=false) {
      if(action==='auto'){this.autoSmile=true;this.manual=null}
      else if(['smile','surprise','neutral'].includes(action)){
        this.autoSmile=false;this.manual=toggle&&this.manual===action?'neutral':action;
      }
    }
    accept(frame,time) {
      if(!frame)return;
      this.found=frame.found;this.lastFrame=time;
      // Hotkeys are commands, not per-frame toggles. -1 releases the key.
      if(frame.hotkey!==this.lastHotkey){this.lastHotkey=frame.hotkey;this.action(this.opts.hotkeys[frame.hotkey])}
      if(frame.found&&frame.params)for(const [key,value] of Object.entries(frame.params)){
        if(key==='MouthForm')this.target[key]=[0,1,2].includes(value)?value:0;
        else if(ranges[key])this.target[key]=clamp(finite(value,rest[key]),...ranges[key]);
      }
    }
    tick(time) {
      const dt=this.previousTime==null?16.667:Math.max(0,time-this.previousTime);this.previousTime=time;
      const lost=!this.found||time-this.lastFrame>this.opts.staleMs;
      const t=lost?{...rest}:{...this.target};
      if(!lost){t.Surprise=this.manual==='surprise'?1:0;t.Smile=this.manual==='smile'?1:this.manual||!this.autoSmile?0:t.Smile}
      for(const key of Object.keys(rest)){
        if(key==='MouthForm'){if(!lost||this.values.MouthOpen<.005)this.values[key]=t[key];continue}
        const tau=lost?this.opts.lostReturnMs:(key==='EyeLOpen'||key==='EyeROpen'||key==='Smile'||key==='Surprise'?0:this.opts.smoothingMs);
        this.values[key]+=(t[key]-this.values[key])*(tau?1-Math.exp(-dt/tau):1);
        if(Math.abs(t[key]-this.values[key])<.0001)this.values[key]=t[key];
      }
      this.model.setParams(this.values);return {lost,values:this.values};
    }
    recenter(){for(const key of ['AngleX','AngleY','AngleZ','BodyX','BodyY','MouthOpen'])this.target[key]=this.values[key]=0;this.manual=null;this.autoSmile=true;this.target.Smile=0;this.target.Surprise=0}
  }
  class IphoneInput {
    constructor(controller,status=()=>{}){this.c=controller;this.mapper=new IphoneMapper(controller.opts);this.status=status;this.running=false;this.generation=0}
    start(){if(this.running)return;this.running=true;this.generation++;this.connect(this.generation)}
    connect(generation){
      if(!this.running||generation!==this.generation)return;
      this.status('iPhone中継へ接続中…');
      let socket;
      try{socket=new WebSocket(this.c.opts.wsUrl)}catch(e){this.status('接続設定エラー: '+e.message);this.retry(generation);return}
      this.socket=socket;
      socket.onopen=()=>this.status('接続済み・iPhoneの顔データ待ち');
      socket.onmessage=e=>{if(!this.running||generation!==this.generation)return;try{
        const f=this.mapper.frame(JSON.parse(e.data),performance.now());this.c.accept(f,performance.now());
        if(f)this.status(f.found?'iPhone追跡中':'顔を検出できません・正面へ戻しています');
      }catch{/* Malformed frames must not stop the input. */}};
      socket.onerror=()=>socket.close();
      socket.onclose=()=>{if(this.running&&generation===this.generation){this.c.found=false;this.mapper.resetTemporal();this.c.lastHotkey=-1;this.status('中継と未接続・1秒後に再接続');this.retry(generation)}};
    }
    retry(generation){this.timer=setTimeout(()=>this.connect(generation),1000)}
    stop(){this.running=false;this.generation++;clearTimeout(this.timer);this.socket?.close();this.c.found=false;this.status('停止中')}
    calibrate(){if(!this.c.found||performance.now()-this.c.lastFrame>this.c.opts.staleMs||!this.mapper.calibrate(true))return false;this.c.recenter();return true}
  }
  // Called only for ?source=webcam. The legacy script itself stays external.
  class WebcamInput {
    constructor(controller,video,status=()=>{},script='./tracking_webcam_legacy.js'){this.c=controller;this.video=video;this.status=status;this.script=script;this.running=false;this.generation=0}
    async start(){
      if(this.running)return;this.running=true;const generation=++this.generation;
      try{
        if(!global.L2DTracker)await new Promise((resolve,reject)=>{const s=document.createElement('script');s.src=this.script;s.onload=resolve;s.onerror=()=>{s.remove();reject(new Error('Webカメラ用スクリプトを読み込めません'))};document.head.append(s)});
        if(!this.running||generation!==this.generation)return;
        const collector={params:{...rest},setParam(k,v){this.params[k]=v},setParams(p){Object.assign(this.params,p)}};
        const tr=this.tracker=new global.L2DTracker(collector,{smooth:0,autoSmile:this.c.autoSmile,autoSurprise:false,...this.c.opts});
        tr.opts.autoSurprise=false;
        const feed=tr.feed.bind(tr);
        tr.feed=(source,time)=>{const auto=this.c.autoSmile&&this.c.manual==null;if(tr.opts.autoSmile!==auto)tr.setAutoSmile(auto);const found=feed(source,time);this.c.accept({found,hotkey:-1,params:{...collector.params}},time);return found};
        await tr.start(this.video,this.status);
        if(!this.running||generation!==this.generation){this.cleanup(tr);return}
        this.video.style.display='block';
      }catch(e){this.running=false;this.cleanup(this.tracker);this.status('起動失敗: '+e.message);throw e}
    }
    cleanup(tr){tr?.stop();tr?.landmarker?.close();this.video.srcObject?.getTracks().forEach(t=>t.stop());this.video.srcObject=null;this.video.style.display='none'}
    stop(){this.running=false;this.generation++;this.cleanup(this.tracker);this.c.found=false;this.status('停止中')}
    calibrate(){if(!this.c.found||performance.now()-this.c.lastFrame>this.c.opts.staleMs)return false;this.tracker.calibrate();this.c.recenter();return true}
  }
  global.L2DInput={defaults,options,parse,IphoneMapper,Controller,IphoneInput,WebcamInput};
})(window);
