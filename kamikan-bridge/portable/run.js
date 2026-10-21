import { spawn } from 'node:child_process';
import { access } from 'node:fs/promises';
import { APP_ID, createPortableServer } from './server.js';

function openUrl(url) {
  if (process.env.KAMIKAN_NO_OPEN === '1') return;
  const launch = (command, args) => { const child = spawn(command, args, { stdio: 'ignore', detached: true }); child.on('error', error => console.log(`ブラウザを開けません: ${error.message}\n${url}`)); child.unref(); };
  if (process.platform === 'darwin') {
    access('/Applications/Google Chrome.app').then(() => launch('/usr/bin/open', ['-a', 'Google Chrome', url]))
      .catch(() => { console.log('モデル画面はGoogle Chromeで開いてください。'); launch('/usr/bin/open', [url]); });
  } else if (process.platform === 'win32') launch('explorer.exe', [url]);
  else launch('xdg-open', [url]);
}

let app;
try {
  if (Number(process.versions.node.split('.')[0]) < 22) throw new Error('Node.js 22以上が必要です。');
  const url = 'http://localhost:8765/';
  let existing;
  try { existing = await (await fetch(`${url}api/status`, { signal: AbortSignal.timeout(1000) })).json(); } catch { /* not our running server */ }
  if (existing?.appId === APP_ID) {
    console.log('すでに起動中のフクロウの王子を開きます。'); openUrl(url);
  } else {
    app = await createPortableServer({ htmlDir: process.env.KAMIKAN_HTML_DIR,
      settingsFile: process.env.KAMIKAN_SETTINGS_FILE });
    await app.start();
    console.log('\nフクロウの王子：設定画面を開きます。ターミナルへの入力は不要です。');
    console.log('終了するまで、このウィンドウは閉じないでください。\n' + url);
    openUrl(url);
    for (const signal of ['SIGINT', 'SIGTERM', 'SIGHUP']) process.once(signal, () => app.stop());
  }
} catch (error) {
  console.error('\n起動できません: ' + (error.code || '') + ' ' + error.message);
  if (error.code === 'EADDRINUSE') console.error('以前のkamikan-bridgeや別の中継を終了してから、もう一度「起動.command」を開いてください。');
  console.error('Node.jsは https://nodejs.org/ja/download からLTS版を入れられます。');
  await app?.stop(); process.exitCode = 1;
}
