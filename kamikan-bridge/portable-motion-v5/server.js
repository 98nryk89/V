import { readFile, writeFile, mkdir, rename, unlink, realpath } from 'node:fs/promises';
import { isIPv4 } from 'node:net';
import path from 'node:path';
import os from 'node:os';
import { randomUUID, createHash } from 'node:crypto';
import { fileURLToPath } from 'node:url';
import { createBridge } from '../src/bridge.js';

export const APP_ID = 'KamikanPortable:owl-prince';
export const VERSION = '5.0.0';
export const MODEL_FILE = 'owl_prince_iphone_motion_v5.html';
export const MODEL_VERSION = 'MOTION-5';

export async function resolveHtmlDir(htmlDir) {
  if(htmlDir)return realpath(htmlDir);
  const bundled=fileURLToPath(new URL('../../html/',import.meta.url));
  try{return await realpath(bundled)}catch{return realpath(fileURLToPath(new URL('../../dist/',import.meta.url)))}
}
export async function distributionIdentity(htmlDir) {
  const root=await resolveHtmlDir(htmlDir),html=await readFile(path.join(root,MODEL_FILE));
  const modelSha256=createHash('sha256').update(html).digest('hex');
  let expected;
  try{expected=JSON.parse(await readFile(new URL('./model-identity.json',import.meta.url),'utf8'))}catch(error){if(error.code!=='ENOENT')throw error}
  if(expected&&expected.modelSha256!==modelSha256)throw new Error('モデルHTMLが中継の配布版と一致しません。html・bridgeの両方を同じセットから入れてください。');
  const instanceKey=createHash('sha256').update(root+'\0'+VERSION+'\0'+modelSha256).digest('hex');
  return {root,modelFile:MODEL_FILE,modelVersion:MODEL_VERSION,modelSha256,instanceKey,folderName:path.basename(path.dirname(root))};
}

export function defaultSettingsFile() {
  const base = process.platform === 'darwin' ? path.join(os.homedir(), 'Library', 'Application Support')
    : process.platform === 'win32' ? (process.env.APPDATA || path.join(os.homedir(), 'AppData', 'Roaming'))
      : (process.env.XDG_CONFIG_HOME || path.join(os.homedir(), '.config'));
  return path.join(base, 'KamikanBridge', 'owl-prince', 'connection.json');
}

function json(res, code, value) {
  res.writeHead(code, { 'Content-Type': 'application/json; charset=utf-8', 'Cache-Control': 'no-store',
    'X-Content-Type-Options': 'nosniff' });
  res.end(JSON.stringify(value));
}
async function body(req) {
  let text = '';
  for await (const chunk of req) {
    text += chunk;
    if (Buffer.byteLength(text) > 4096) throw new Error('設定データが大きすぎます。');
  }
  return JSON.parse(text);
}

export async function createPortableServer({ htmlDir, settingsFile = defaultSettingsFile(),
  httpPort = 8765, udpPort = 11125, iphonePort = 21412, requestIntervalMs = 1000,
  statusIntervalMs = 1000, log = console.log } = {}) {
  const identity=await distributionIdentity(htmlDir);htmlDir=identity.root;
  let iphoneIp = '', warning = '', saving = false;
  try {
    const saved = JSON.parse(await readFile(settingsFile, 'utf8'));
    if (isIPv4(saved.iphoneIp)) iphoneIp = saved.iphoneIp;
    else if (saved.iphoneIp) warning = '保存済みのIPが不正です。入力し直してください。';
  } catch (error) {
    if (error.code !== 'ENOENT') warning = '保存済みの設定を読めません。IPを入力し直してください。';
  }
  const setupHtml = await readFile(new URL('./ui/index.html', import.meta.url));
  const trackingConfig = JSON.parse(await readFile(path.join(htmlDir, 'owl_prince_tracking_config_v5.json'), 'utf8'));
  let bridge;
  async function handler(req, res) {
    const pathname = new URL(req.url, 'http://localhost').pathname;
    if (pathname === '/') {
      if (!['GET', 'HEAD'].includes(req.method)) { json(res, 405, { error: 'Method not allowed' }); return true; }
      res.writeHead(200, { 'Content-Type': 'text/html; charset=utf-8', 'Cache-Control': 'no-store' });
      res.end(req.method === 'HEAD' ? undefined : setupHtml); return true;
    }
    if (pathname === '/owl_prince_tracking_config_v5.json' && req.method === 'GET') {
      json(res, 200, { ...trackingConfig, wsUrl: `ws://localhost:${bridge.getStatus().httpPort}` }); return true;
    }
    if (!pathname.startsWith('/api/')) return false;
    if (pathname === '/api/status' && req.method === 'GET') {
      const {root,...publicIdentity}=identity;
      json(res, 200, { appId: APP_ID, version: VERSION, warning, ...bridge.getStatus(), ...publicIdentity }); return true;
    }
    if (!['/api/connection', '/api/stop'].includes(pathname) || req.method !== 'POST') {
      json(res, 404, { error: 'Not found' }); return true;
    }
    // Only the local setup page may change settings or stop the process.
    if (req.headers.origin !== `http://${req.headers.host}`
      || !/^application\/json(?:;|$)/i.test(req.headers['content-type'] || '')) {
      json(res, 403, { error: '設定画面から操作してください。' }); return true;
    }
    if (pathname === '/api/stop') {
      json(res, 200, { stopped: true });
      setTimeout(() => bridge.stop().catch(log), 30); return true;
    }
    if (saving) { json(res, 409, { error: '保存中です。少し待ってください。' }); return true; }
    saving = true;
    let temporary;
    try {
      const data = await body(req);
      const address = typeof data?.iphoneIp === 'string' ? data.iphoneIp.trim() : '';
      if (!isIPv4(address)) { json(res, 400, { error: 'iPhoneのIPv4アドレスを入力してください（例：192.168.1.100）。' }); return true; }
      await mkdir(path.dirname(settingsFile), { recursive: true, mode: 0o700 });
      temporary = `${settingsFile}.${randomUUID()}.tmp`;
      await writeFile(temporary, JSON.stringify({ iphoneIp: address }, null, 2) + '\n', { mode: 0o600 });
      await rename(temporary, settingsFile); temporary = undefined;
      bridge.setIphoneIp(address); warning = '';
      json(res, 200, { saved: true, iphoneIp: address });
    } catch (error) {
      const message = error instanceof SyntaxError ? '入力データを確認してください。'
        : error.code ? `設定を保存できません（${error.code}）。フォルダの書き込み権限を確認してください。`
          : error.message;
      json(res, error.code ? 500 : 400, { error: message });
    } finally {
      saving = false;
      if (temporary) await unlink(temporary).catch(() => {});
    }
    return true;
  }
  bridge = createBridge({ iphoneIp: iphoneIp || '127.0.0.1', requestsEnabled: !!iphoneIp,
    htmlDir, httpPort, udpPort, iphonePort, requestIntervalMs, statusIntervalMs }, { log, httpHandler: handler });
  return { start: bridge.start, stop: bridge.stop, getStatus: bridge.getStatus, settingsFile };
}
