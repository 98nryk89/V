import dgram from 'node:dgram';
import http from 'node:http';
import { isIPv4 } from 'node:net';
import { createReadStream } from 'node:fs';
import { readFile, realpath, stat, readdir } from 'node:fs/promises';
import path from 'node:path';
import { performance } from 'node:perf_hooks';
import { WebSocketServer, WebSocket } from 'ws';

const localHosts = new Set(['localhost', '127.0.0.1', '[::1]']);
const mimeTypes = {
  '.html': 'text/html; charset=utf-8', '.js': 'text/javascript; charset=utf-8',
  '.css': 'text/css; charset=utf-8', '.json': 'application/json; charset=utf-8',
  '.png': 'image/png', '.jpg': 'image/jpeg', '.jpeg': 'image/jpeg',
  '.svg': 'image/svg+xml', '.webp': 'image/webp', '.ico': 'image/x-icon',
  '.wasm': 'application/wasm', '.woff2': 'font/woff2', '.txt': 'text/plain; charset=utf-8',
};

export async function loadConfig(filename) {
  const file = path.resolve(filename);
  const config = JSON.parse(await readFile(file, 'utf8'));
  if (!config || typeof config !== 'object' || Array.isArray(config)) {
    throw new Error('config.json は iphoneIp と htmlDir を持つJSONオブジェクトにしてください。');
  }
  if (!isIPv4(config.iphoneIp)) {
    throw new Error('config.json の iphoneIp に、iPhoneのIPv4アドレスを指定してください。');
  }
  if (typeof config.htmlDir !== 'string' || !config.htmlDir.trim()) {
    throw new Error('config.json の htmlDir に、配信するHTMLフォルダを指定してください。');
  }
  return { iphoneIp: config.iphoneIp, htmlDir: path.resolve(path.dirname(file), config.htmlDir) };
}

function isInside(root, filename) {
  const relative = path.relative(root, filename);
  return relative === '' || (!relative.startsWith(`..${path.sep}`) && relative !== '..' && !path.isAbsolute(relative));
}

function escapeHtml(text) {
  return text.replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[c]);
}

function reply(res, status, message) {
  res.writeHead(status, { 'Content-Type': 'text/plain; charset=utf-8' });
  res.end(message);
}

async function serveFolder(root, req, res) {
  if (!['GET', 'HEAD'].includes(req.method)) {
    res.setHeader('Allow', 'GET, HEAD');
    reply(res, 405, 'Method not allowed');
    return;
  }
  let pathname;
  try { pathname = decodeURIComponent(new URL(req.url, 'http://localhost').pathname); }
  catch { reply(res, 400, 'Invalid URL'); return; }
  if (pathname.includes('\0') || pathname.includes('\\') || pathname.split('/').some(p => p.startsWith('.'))) {
    reply(res, 403, 'Forbidden'); return;
  }
  const candidate = path.resolve(root, `.${pathname}`);
  if (!isInside(root, candidate)) { reply(res, 403, 'Forbidden'); return; }
  let filename;
  try { filename = await realpath(candidate); }
  catch (error) {
    if (['ENOENT', 'ENOTDIR'].includes(error.code)) { reply(res, 404, 'Not found'); return; }
    throw error;
  }
  // Also prevent a symlink within htmlDir from exposing files outside it.
  if (!isInside(root, filename)) { reply(res, 403, 'Forbidden'); return; }
  let info = await stat(filename);
  if (info.isDirectory()) {
    const index = path.join(filename, 'index.html');
    try {
      filename = await realpath(index);
      if (!isInside(root, filename)) { reply(res, 403, 'Forbidden'); return; }
      info = await stat(filename);
    } catch (error) {
      if (error.code !== 'ENOENT') throw error;
      if (candidate !== root) { reply(res, 404, 'Not found'); return; }
      // No files are created: the root lists existing top-level HTML files.
      const names = (await readdir(root, { withFileTypes: true }))
        .filter(e => e.isFile() && /\.html$/i.test(e.name)).map(e => e.name).sort();
      const links = names.map(name => `<li><a href="/${encodeURIComponent(name)}">${escapeHtml(name)}</a></li>`).join('');
      const body = '<!doctype html><meta charset="utf-8"><title>KamikanBridge</title>'
        + '<h1>KamikanBridge</h1><p>表示するHTMLを選んでください。iPhone連携の試験版は owl_prince_iphone_test.html です。</p>'
        + (links ? `<ul>${links}</ul>` : '<p>このフォルダにはHTMLファイルがありません。config.json の htmlDir を確認してください。</p>');
      res.writeHead(200, { 'Content-Type': mimeTypes['.html'], 'Cache-Control': 'no-store' });
      res.end(req.method === 'HEAD' ? undefined : body);
      return;
    }
  }
  if (!info.isFile()) { reply(res, 404, 'Not found'); return; }
  res.writeHead(200, {
    'Content-Type': mimeTypes[path.extname(filename).toLowerCase()] || 'application/octet-stream',
    'Content-Length': info.size, 'Cache-Control': 'no-store', 'X-Content-Type-Options': 'nosniff',
  });
  if (req.method === 'HEAD') { res.end(); return; }
  const stream = createReadStream(filename);
  stream.on('error', () => res.destroy());
  res.on('close', () => stream.destroy());
  stream.pipe(res);
}

function blendshape(data, name) {
  if (!Array.isArray(data?.BlendShapes)) return '--';
  const entry = data.BlendShapes.find(e => typeof e?.k === 'string' && e.k.toLowerCase() === name.toLowerCase());
  return typeof entry?.v === 'number' && Number.isFinite(entry.v) ? entry.v.toFixed(3) : '--';
}

export function createBridge({ iphoneIp, htmlDir, iphonePort = 21412, udpPort = 11125,
  httpPort = 8765, httpHost = '127.0.0.1', requestIntervalMs = 1000, statusIntervalMs = 1000 },
  { log = console.log } = {}) {
  if (!isIPv4(iphoneIp)) throw new Error('iPhoneのIPv4アドレスが必要です。');
  const udp = dgram.createSocket('udp4');
  const wss = new WebSocketServer({ noServer: true, perMessageDeflate: false, maxPayload: 65536 });
  let server, requestTimer, statusTimer, heartbeatTimer;
  let running = false, stopped = false, started = false, actualUdpPort, actualHttpPort;
  let frameCount = 0, invalidCount = 0, latest;
  let lastStatusAt = performance.now(), lastErrorAt = -Infinity;

  function warn(error) {
    // A disconnected network may produce an error every second. Keep retrying.
    const now = performance.now();
    if (now - lastErrorAt > 5000) {
      log(`[通信] ${error.code || error.message}（再要求は継続します）`);
      lastErrorAt = now;
    }
  }
  udp.on('error', error => { if (running) warn(error); });
  udp.on('message', (message, remote) => {
    if (!running || remote.address !== iphoneIp) return;
    const text = message.toString('utf8').replace(/^\uFEFF/, '');
    let data;
    try {
      data = JSON.parse(text);
      if (!data || typeof data !== 'object' || Array.isArray(data)) throw new Error('not an object');
    } catch { invalidCount++; return; }
    latest = data;
    frameCount++;
    for (const client of wss.clients) {
      // Do not accumulate old tracking frames behind a slow browser.
      if (client.readyState === WebSocket.OPEN && client.bufferedAmount < 256 * 1024) {
        client.send(text, { binary: false }, error => { if (error) warn(error); });
      }
    }
  });

  function requestTracking() {
    if (!running) return;
    const message = JSON.stringify({ messageType: 'iOSTrackingDataRequest', time: 5,
      sentBy: 'KamikanBridge', ports: [actualUdpPort] });
    try { udp.send(message, iphonePort, iphoneIp, error => { if (error && running) warn(error); }); }
    catch (error) { if (running) warn(error); }
  }

  function printStatus() {
    const now = performance.now();
    const fps = frameCount * 1000 / (now - lastStatusAt);
    const data = frameCount > 0 ? latest : undefined;
    const face = typeof data?.FaceFound === 'boolean' ? String(data.FaceFound) : '--';
    log(`受信fps=${fps.toFixed(1)} FaceFound=${face} eyeBlinkLeft=${blendshape(data, 'eyeBlinkLeft')}`
      + ` jawOpen=${blendshape(data, 'jawOpen')}`
      + (frameCount === 0 ? ' [受信待ち・再要求中]' : '')
      + (invalidCount ? ` [不正JSON=${invalidCount}件を無視]` : ''));
    frameCount = 0; invalidCount = 0; lastStatusAt = now;
  }

  async function stop() {
    if (stopped) return;
    stopped = true; running = false;
    clearInterval(requestTimer); clearInterval(statusTimer); clearInterval(heartbeatTimer);
    for (const client of wss.clients) client.terminate();
    const tasks = [new Promise(resolve => wss.close(resolve))];
    if (server?.listening) {
      tasks.push(new Promise(resolve => server.close(resolve)));
      server.closeAllConnections();
    }
    tasks.push(new Promise(resolve => {
      try { udp.close(resolve); } catch { resolve(); }
    }));
    await Promise.all(tasks);
  }

  async function start() {
    if (started || stopped) throw new Error('このブリッジは起動済み、または終了済みです。');
    started = true;
    try {
      const root = await realpath(htmlDir);
      if (!(await stat(root)).isDirectory()) throw new Error('htmlDir はフォルダを指定してください。');
      server = http.createServer((req, res) => {
        let host;
        try { host = new URL(`http://${req.headers.host}`).hostname; } catch { /* rejected below */ }
        if (!localHosts.has(host)) { reply(res, 403, 'Local access only'); return; }
        serveFolder(root, req, res).catch(error => {
          log(`[HTTP] ${error.code || error.message}`);
          if (!res.headersSent) reply(res, 500, 'Internal server error'); else res.destroy();
        });
      });
      server.on('upgrade', (req, socket, head) => {
        let allowed = false;
        try {
          const host = new URL(`http://${req.headers.host}`).hostname;
          const origin = req.headers.origin ? new URL(req.headers.origin) : undefined;
          allowed = localHosts.has(host) && req.url === '/'
            && (!origin || (origin.protocol === 'http:' && localHosts.has(origin.hostname)
              && Number(origin.port || 80) === actualHttpPort));
        } catch { /* rejected below */ }
        if (!allowed) { socket.end('HTTP/1.1 403 Forbidden\r\nConnection: close\r\n\r\n'); return; }
        wss.handleUpgrade(req, socket, head, client => wss.emit('connection', client, req));
      });
      wss.on('connection', client => {
        client.alive = true;
        client.on('pong', () => { client.alive = true; });
        client.on('error', warn);
      });
      await new Promise((resolve, reject) => {
        udp.once('error', reject);
        udp.bind(udpPort, '0.0.0.0', () => { udp.off('error', reject); resolve(); });
      });
      actualUdpPort = udp.address().port;
      await new Promise((resolve, reject) => {
        server.once('error', reject);
        server.listen(httpPort, httpHost, () => { server.off('error', reject); resolve(); });
      });
      server.on('error', warn);
      actualHttpPort = server.address().port;
      running = true; lastStatusAt = performance.now();
      requestTracking();
      requestTimer = setInterval(requestTracking, requestIntervalMs);
      statusTimer = setInterval(printStatus, statusIntervalMs);
      heartbeatTimer = setInterval(() => {
        for (const client of wss.clients) {
          if (!client.alive) { client.terminate(); continue; }
          client.alive = false; client.ping();
        }
      }, 30000);
      log(`KamikanBridge: iPhone ${iphoneIp}:${iphonePort} → UDP ${actualUdpPort}`);
      log(`HTTP http://localhost:${actualHttpPort}/  WebSocket ws://localhost:${actualHttpPort}`);
      log(`HTMLフォルダ: ${root}（読み取り専用）`);
      return { udpPort: actualUdpPort, httpPort: actualHttpPort };
    } catch (error) { await stop(); throw error; }
  }
  return { start, stop };
}
