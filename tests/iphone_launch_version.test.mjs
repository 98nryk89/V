import {test} from 'node:test';
import assert from 'node:assert/strict';
import {mkdtemp,mkdir,writeFile,rm} from 'node:fs/promises';
import os from 'node:os';
import path from 'node:path';
import {ensureCurrentServer} from '../kamikan-bridge/portable-motion/run.js';
import {APP_ID,distributionIdentity,createPortableServer,MODEL_FILE} from '../kamikan-bridge/portable-motion/server.js';
import {createPortableServer as createOldServer} from '../kamikan-bridge/portable/server.js';

test('the same folder and exact HTML can reuse its server',async()=>{
 let starts=0;const result=await ensureCurrentServer({url:'http://127.0.0.1:8765/',identity:{instanceKey:'same'},
  start:async()=>{starts++},fetchImpl:async()=>({ok:true,json:async()=>({appId:APP_ID,instanceKey:'same'})})});
 assert.equal(result.reused,true);assert.equal(starts,0);
});
test('an older own server is stopped through its API before starting the new folder',async()=>{
 let requests=0,started=false,stopped=false;
 const result=await ensureCurrentServer({url:'http://127.0.0.1:8765/',identity:{instanceKey:'new'},start:async()=>{assert.ok(stopped);started=true;return 'new'},
  fetchImpl:async(url,opts)=>{requests++;if(requests===1)return {ok:true,json:async()=>({appId:APP_ID})};
   if(url.endsWith('/api/stop')){assert.equal(opts.headers.Origin,'http://127.0.0.1:8765');stopped=true;return {ok:true}}
   throw new Error('old socket closed');}});
 assert.ok(started);assert.equal(result.app,'new');assert.equal(result.reused,false);
});
test('an unrelated server is never sent a stop request',async()=>{
 let calls=0;await assert.rejects(ensureCurrentServer({url:'http://127.0.0.1:8765/',identity:{instanceKey:'new'},
  start:async()=>{throw new Error('port busy')},fetchImpl:async()=>{calls++;return {ok:true,json:async()=>({appId:'unrelated'})}}}),/port busy/);
 assert.equal(calls,1);
});
test('failure to stop our old server does not pretend that the new model started',async()=>{
 let starts=0;await assert.rejects(ensureCurrentServer({url:'http://127.0.0.1:8765/',identity:{instanceKey:'new'},
  start:async()=>{starts++},fetchImpl:async(url)=>url.endsWith('/api/stop')?{ok:false}:{ok:true,json:async()=>({appId:APP_ID})}}),/停止できません/);
 assert.equal(starts,0);
});
test('real HTTP: old distribution is replaced, same version in another folder is not reused',async t=>{
 const tmp=await mkdtemp(path.join(os.tmpdir(),'motion launch '));t.after(()=>rm(tmp,{recursive:true,force:true}));
 const oldDir=path.join(tmp,'old','html'),aDir=path.join(tmp,'newA','html'),bDir=path.join(tmp,'newB','html');
 for(const dir of [oldDir,aDir,bDir]){await mkdir(dir,{recursive:true});await writeFile(path.join(dir,'owl_prince_tracking_config.json'),'{}');await writeFile(path.join(dir,'owl_prince_tracking_config_v3.json'),'{}');await writeFile(path.join(dir,MODEL_FILE),'<title>MOTION-3</title>')}
 const settingsFile=path.join(tmp,'settings','connection.json');
 const old=await createOldServer({htmlDir:oldDir,settingsFile,httpPort:0,udpPort:0,log:()=>{}});t.after(()=>old.stop());
 const oldPorts=await old.start(),url=`http://127.0.0.1:${oldPorts.httpPort}/`;
 const identityA=await distributionIdentity(aDir),identityB=await distributionIdentity(bDir);
 assert.equal(identityA.modelSha256,identityB.modelSha256);assert.notEqual(identityA.instanceKey,identityB.instanceKey);
 let current;
 const start=dir=>async()=>{current=await createPortableServer({htmlDir:dir,settingsFile,httpPort:oldPorts.httpPort,udpPort:0,log:()=>{}});await current.start();return current};
 const a=await ensureCurrentServer({url,identity:identityA,start:start(aDir)});t.after(()=>a.app.stop());
 let state=await (await fetch(url+'api/status')).json();assert.equal(state.instanceKey,identityA.instanceKey);assert.equal(state.modelVersion,'MOTION-3');
 assert.equal(await (await fetch(url+MODEL_FILE)).text(),'<title>MOTION-3</title>');
 const reused=await ensureCurrentServer({url,identity:identityA,start:()=>{throw Error('must not start')}});assert.ok(reused.reused);
 const b=await ensureCurrentServer({url,identity:identityB,start:start(bDir)});t.after(()=>b.app.stop());
 state=await (await fetch(url+'api/status')).json();assert.equal(state.instanceKey,identityB.instanceKey);assert.equal(state.folderName,'newB');
 const response=await fetch(url+'owl_prince_tracking_config_v3.json');const config=await response.json();assert.equal(config.wsUrl,`ws://localhost:${oldPorts.httpPort}`);
});
