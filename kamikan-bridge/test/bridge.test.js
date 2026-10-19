import test from 'node:test';
import assert from 'node:assert/strict';
import dgram from 'node:dgram';
import http from 'node:http';
import { once } from 'node:events';
import { mkdtemp, mkdir, writeFile, readFile, symlink, rm } from 'node:fs/promises';
import os from 'node:os';
import path from 'node:path';
import { setTimeout as delay } from 'node:timers/promises';
import { WebSocket } from 'ws';
import { createBridge, loadConfig } from '../src/bridge.js';

const names = `EyeBlinkLeft EyeLookDownLeft EyeLookInLeft EyeLookOutLeft EyeLookUpLeft EyeSquintLeft EyeWideLeft
EyeBlinkRight EyeLookDownRight EyeLookInRight EyeLookOutRight EyeLookUpRight EyeSquintRight EyeWideRight
JawForward JawRight JawLeft JawOpen MouthClose MouthFunnel MouthPucker MouthLeft MouthRight
MouthSmileLeft MouthSmileRight MouthFrownLeft MouthFrownRight MouthDimpleLeft MouthDimpleRight
MouthStretchLeft MouthStretchRight MouthRollLower MouthRollUpper MouthShrugLower MouthShrugUpper
MouthPressLeft MouthPressRight MouthLowerDownLeft MouthLowerDownRight MouthUpperUpLeft MouthUpperUpRight
BrowDownLeft BrowDownRight BrowInnerUp CheekPuff CheekSquintLeft CheekSquintRight NoseSneerLeft NoseSneerRight
BrowOuterUpLeft BrowOuterUpRight TongueOut`.split(/\s+/);
const tracking = {
  Timestamp: 1792480000123, Hotkey: 8, FaceFound: true,
  Rotation: { x: -3, y: 4, z: 2 }, Position: { x: .1, y: .2, z: .3 },
  EyeLeft: { x: 1, y: 2, z: 3 }, EyeRight: { x: 3, y: 2, z: 1 },
  BlendShapes: names.map(k => ({ k, v: k === 'EyeBlinkLeft' ? .375 : k === 'JawOpen' ? .625 : .1 })),
  FutureField: { nested: ['unknown', { keep: true }] },
};

async function until(predicate, timeout = 5000) {
  const deadline = Date.now() + timeout;
  while (!predicate()) {
    if (Date.now() > deadline) throw new Error('Timed out waiting for bridge');
    await delay(20);
  }
}
async function bind(socket, port = 0) {
  await new Promise((resolve, reject) => {
    socket.once('error', reject);
    socket.bind(port, '127.0.0.1', () => { socket.off('error', reject); resolve(); });
  });
}
async function closeUdp(socket) {
  await new Promise(resolve => { try { socket.close(resolve); } catch { resolve(); } });
}
async function send(socket, text, port) {
  await new Promise((resolve, reject) => socket.send(text, port, '127.0.0.1', error => error ? reject(error) : resolve()));
}
async function fixture(t) {
  const directory = await mkdtemp(path.join(os.tmpdir(), 'kamikan-test-'));
  const htmlDir = path.join(directory, 'html');
  await mkdir(htmlDir);
  const html = '<!doctype html><meta charset="utf-8"><p>既存モデルの代わりのテスト画像</p>';
  await writeFile(path.join(htmlDir, 'owl_prince.html'), html);
  const phone = dgram.createSocket('udp4');
  await bind(phone);
  const requests = [], logs = [];
  phone.on('message', (bytes, remote) => requests.push({ data: JSON.parse(bytes), remote, time: Date.now() }));
  const bridge = createBridge({ iphoneIp: '127.0.0.1', htmlDir,
    iphonePort: phone.address().port, udpPort: 0, httpPort: 0 }, { log: line => logs.push(line) });
  t.after(async () => {
    await bridge.stop(); await closeUdp(phone); await rm(directory, { recursive: true, force: true });
  });
  const ports = await bridge.start();
  const url = `http://localhost:${ports.httpPort}`;
  return { directory, htmlDir, html, phone, requests, logs, bridge, ports, url };
}
async function connect(t, port) {
  const ws = new WebSocket(`ws://localhost:${port}`, { origin: `http://localhost:${port}` });
  t.after(() => ws.terminate());
  await once(ws, 'open', { signal: AbortSignal.timeout(5000) });
  return ws;
}

test('official UDP request and all raw fields reach multiple WebSocket clients unchanged', async t => {
  assert.equal(names.length, 52);
  const f = await fixture(t);
  const first = await connect(t, f.ports.httpPort), second = await connect(t, f.ports.httpPort);
  await until(() => f.requests.length > 0);
  assert.deepEqual(f.requests[0].data, { messageType: 'iOSTrackingDataRequest', time: 5,
    sentBy: 'KamikanBridge', ports: [f.ports.udpPort] });
  assert.equal(f.requests[0].remote.port, f.ports.udpPort);
  const text = JSON.stringify(tracking, null, 2);
  const received = [once(first, 'message'), once(second, 'message')];
  await send(f.phone, text, f.ports.udpPort);
  for (const result of await Promise.all(received)) {
    assert.equal(result[1], false);
    assert.equal(result[0].toString(), text);
    assert.deepEqual(JSON.parse(result[0]), tracking);
  }
  await until(() => f.logs.some(line => line.includes('FaceFound=true')));
  const status = f.logs.find(line => line.includes('FaceFound=true'));
  assert.match(status, /受信fps=[0-9.]+/);
  assert.match(status, /eyeBlinkLeft=0\.375 jawOpen=0\.625/);
});

test('bad UDP is ignored and FaceFound=false / hotkeys / lower-case blendshape names are retained', async t => {
  const f = await fixture(t), ws = await connect(t, f.ports.httpPort);
  for (const bad of ['not json', 'null', '[]']) await send(f.phone, bad, f.ports.udpPort);
  const frame = { FaceFound: false, Hotkey: 3, AddedLater: 'still here',
    BlendShapes: [{ k: 'eyeBlinkLeft', v: .25 }, { k: 'jawOpen', v: .5 }, null] };
  const received = once(ws, 'message');
  await send(f.phone, JSON.stringify(frame), f.ports.udpPort);
  assert.deepEqual(JSON.parse((await received)[0]), frame);
  await until(() => f.logs.some(line => line.includes('FaceFound=false')));
  const line = f.logs.find(line => line.includes('FaceFound=false'));
  assert.match(line, /eyeBlinkLeft=0\.250 jawOpen=0\.500/);
  assert.match(line, /不正JSON=3件/);
});

test('a roughly 60fps stream is forwarded without losing frames and stale status values are cleared', async t => {
  const f = await fixture(t), ws = await connect(t, f.ports.httpPort);
  const timestamps = [];
  ws.on('message', bytes => timestamps.push(JSON.parse(bytes).Timestamp));
  for (let i = 0; i < 60; i++) {
    await send(f.phone, JSON.stringify({ ...tracking, Timestamp: tracking.Timestamp + i }), f.ports.udpPort);
    await delay(16);
  }
  await until(() => timestamps.length === 60);
  assert.deepEqual(timestamps, Array.from({ length: 60 }, (_, i) => tracking.Timestamp + i));
  await until(() => f.logs.some(line => /受信fps=0\.0 FaceFound=-- eyeBlinkLeft=-- jawOpen=--/.test(line)));
});

test('requests continue every second through a phone outage and forwarding resumes without restarting', async t => {
  const f = await fixture(t), ws = await connect(t, f.ports.httpPort);
  await until(() => f.requests.length >= 2);
  assert.ok(f.requests[1].time - f.requests[0].time >= 800);
  assert.ok(f.logs.some(line => /受信fps=0\.0 FaceFound=--/.test(line)));
  const phonePort = f.phone.address().port;
  await closeUdp(f.phone);
  await delay(1250); // Requests still run while no iPhone is listening.
  const recovered = dgram.createSocket('udp4');
  t.after(() => closeUdp(recovered));
  await bind(recovered, phonePort);
  const request = once(recovered, 'message', { signal: AbortSignal.timeout(5000) });
  const [bytes] = await request;
  assert.equal(JSON.parse(bytes).time, 5);
  const received = once(ws, 'message', { signal: AbortSignal.timeout(5000) });
  await send(recovered, JSON.stringify(tracking), f.ports.udpPort);
  assert.deepEqual(JSON.parse((await received)[0]), tracking);
});

test('the same HTTP server serves an unchanged HTML folder, root links, assets and HEAD', async t => {
  const f = await fixture(t);
  await mkdir(path.join(f.htmlDir, 'assets'));
  await writeFile(path.join(f.htmlDir, 'assets', 'test.js'), 'console.log("asset");');
  const root = await fetch(f.url);
  assert.equal(root.status, 200);
  assert.match(await root.text(), /href="\/owl_prince\.html"/);
  const model = await fetch(`${f.url}/owl_prince.html`);
  assert.equal(await model.text(), f.html);
  const head = await fetch(`${f.url}/owl_prince.html`, { method: 'HEAD' });
  assert.equal(head.status, 200);
  assert.equal(await head.text(), '');
  assert.equal(Number(head.headers.get('content-length')), Buffer.byteLength(f.html));
  const asset = await fetch(`${f.url}/assets/test.js`);
  assert.match(asset.headers.get('content-type'), /javascript/);
  assert.equal(await asset.text(), 'console.log("asset");');
  assert.equal((await fetch(`${f.url}/missing.html`)).status, 404);
  assert.equal((await fetch(f.url, { method: 'POST' })).status, 405);
  assert.equal(await readFile(path.join(f.htmlDir, 'owl_prince.html'), 'utf8'), f.html);
  await writeFile(path.join(f.htmlDir, 'index.html'), '<p>index</p>');
  assert.equal(await (await fetch(f.url)).text(), '<p>index</p>');
});

test('HTTP cannot read config files outside htmlDir, including through symlinks', async t => {
  const f = await fixture(t);
  await writeFile(path.join(f.directory, 'private.json'), '{"private":true}');
  assert.equal((await fetch(`${f.url}/%2e%2e%2fprivate.json`)).status, 403);
  await symlink(path.join(f.directory, 'private.json'), path.join(f.htmlDir, 'link.json'));
  assert.equal((await fetch(`${f.url}/link.json`)).status, 403);
  assert.equal((await fetch(`${f.url}/.hidden`)).status, 403);
});

test('WebSocket rejects a connection originating on an unrelated website', async t => {
  const f = await fixture(t);
  const ws = new WebSocket(`ws://localhost:${f.ports.httpPort}`, { origin: 'https://example.com' });
  t.after(() => ws.terminate());
  ws.on('error', () => {});
  const [, response] = await once(ws, 'unexpected-response', { signal: AbortSignal.timeout(5000) });
  assert.equal(response.statusCode, 403);
  response.resume(); ws.terminate();
});

test('a busy HTTP port fails clearly and releases the already bound UDP socket', async t => {
  const f = await fixture(t);
  const occupied = http.createServer();
  await new Promise(resolve => occupied.listen(0, '127.0.0.1', resolve));
  t.after(() => new Promise(resolve => occupied.close(resolve)));
  const probe = dgram.createSocket('udp4');
  await bind(probe); const udpPort = probe.address().port; await closeUdp(probe);
  const bridge = createBridge({ iphoneIp: '127.0.0.1', htmlDir: f.htmlDir,
    udpPort, httpPort: occupied.address().port }, { log() {} });
  await assert.rejects(bridge.start(), { code: 'EADDRINUSE' });
  const reusable = dgram.createSocket('udp4');
  t.after(() => closeUdp(reusable));
  await bind(reusable, udpPort);
  await bridge.stop(); // Also safe after a failed start.
});

test('config paths resolve relative to config.json and invalid phone IPs fail before binding', async t => {
  const f = await fixture(t), file = path.join(f.directory, 'config.json');
  await writeFile(file, JSON.stringify({ iphoneIp: '127.0.0.1', htmlDir: './html' }));
  assert.deepEqual(await loadConfig(file), { iphoneIp: '127.0.0.1', htmlDir: f.htmlDir });
  await writeFile(file, JSON.stringify({ iphoneIp: 'YOUR_IPHONE_IP', htmlDir: './html' }));
  await assert.rejects(loadConfig(file), /IPv4/);
  const missing = createBridge({ iphoneIp: '127.0.0.1', htmlDir: path.join(f.directory, 'missing') });
  await assert.rejects(missing.start(), { code: 'ENOENT' });
});
