import { spawn } from 'node:child_process';
import { access } from 'node:fs/promises';
import { pathToFileURL } from 'node:url';
import { APP_ID, createPortableServer, distributionIdentity } from './server.js';

const pause=ms=>new Promise(resolve=>setTimeout(resolve,ms));
export async function ensureCurrentServer({url,identity,start,fetchImpl=fetch}) {
  let existing;
  try {const r=await fetchImpl(url+'api/status',{signal:AbortSignal.timeout(1000)});if(r.ok)existing=await r.json()}catch{/* absent or unrelated */}
  if(existing?.appId===APP_ID&&existing.instanceKey===identity.instanceKey)return {reused:true};
  if(existing?.appId===APP_ID){
    // Only stop our own bridge, through its existing same-origin stop API.
    const r=await fetchImpl(url+'api/stop',{method:'POST',headers:{Origin:new URL(url).origin,'Content-Type':'application/json'},body:'{}',signal:AbortSignal.timeout(2000)});
    if(!r.ok)throw new Error('旧版の中継を停止できません。接続画面の「中継を終了する」を押してください。');
    let stopped=false;
    for(let i=0;i<40;i++){
      await pause(100);
      try {const check=await fetchImpl(url+'api/status',{signal:AbortSignal.timeout(300)});if(!check.ok)throw new Error('port taken by another service')}
      catch(error){if(error.message==='port taken by another service')throw error;stopped=true;break}
    }
    if(!stopped)throw new Error('旧版の中継が終了しませんでした。新しい版はまだ起動していません。');
  }
  const app=await start();return {reused:false,app};
}

function openUrl(url) {
  if(process.env.KAMIKAN_NO_OPEN==='1')return;
  const launch=(command,args)=>{const child=spawn(command,args,{stdio:'ignore',detached:true});child.on('error',error=>console.log(`ブラウザを開けません: ${error.message}\n${url}`));child.unref()};
  if(process.platform==='darwin')access('/Applications/Google Chrome.app').then(()=>launch('/usr/bin/open',['-a','Google Chrome',url])).catch(()=>launch('/usr/bin/open',[url]));
  else if(process.platform==='win32')launch('explorer.exe',[url]);
  else launch('xdg-open',[url]);
}
export async function main(){
  let app;
  try {
    if(Number(process.versions.node.split('.')[0])<22)throw new Error('Node.js 22以上が必要です。');
    const url='http://127.0.0.1:8765/',htmlDir=process.env.KAMIKAN_HTML_DIR;
    const identity=await distributionIdentity(htmlDir);
    const result=await ensureCurrentServer({url,identity,start:async()=>{
      app=await createPortableServer({htmlDir:identity.root,settingsFile:process.env.KAMIKAN_SETTINGS_FILE});await app.start();return app;
    }});
    console.log(`\n${identity.modelVersion}：${result.reused?'この版は起動済みです。':'このフォルダのモデルを起動しました。'}\n${identity.folderName}\n${url}`);
    openUrl(url);
    if(app)for(const signal of ['SIGINT','SIGTERM','SIGHUP'])process.once(signal,()=>app.stop());
  }catch(error){
    console.error('起動できません: '+error.message);
    if(error.code==='EADDRINUSE')console.error('別のサーバーがポートを使用しています。無関係なサーバーは自動終了しません。');
    await app?.stop();process.exitCode=1;
  }
}
if(process.argv[1]&&import.meta.url===pathToFileURL(process.argv[1]).href)await main();
