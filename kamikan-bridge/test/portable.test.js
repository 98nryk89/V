import test from 'node:test';
import assert from 'node:assert/strict';
import { mkdtemp, mkdir, writeFile, readFile, rm } from 'node:fs/promises';
import path from 'node:path';
import os from 'node:os';
import dgram from 'node:dgram';
import { once } from 'node:events';
import { setTimeout as delay } from 'node:timers/promises';
import { WebSocket } from 'ws';
import { APP_ID, createPortableServer } from '../portable/server.js';

async function fixture(t, overrides = {}) {
  const directory = await mkdtemp(path.join(os.tmpdir(), 'kamikan-portable-'));
  const htmlDir = path.join(directory, 'html'); await mkdir(htmlDir);
  await writeFile(path.join(htmlDir, 'owl_prince_tracking_config.json'), '{"smoothingMs":80}');
  await writeFile(path.join(htmlDir, 'owl_prince_iphone_test.html'), '<!doctype html><p>unchanged model</p>');
  const phone = dgram.createSocket('udp4');
  await new Promise(resolve => phone.bind(0, '127.0.0.1', resolve));
  const requests = []; phone.on('message', data => requests.push(JSON.parse(data)));
  const settingsFile = path.join(directory, 'settings', 'connection.json');
  const opts = { htmlDir, settingsFile, httpPort: 0, udpPort: 0, iphonePort: phone.address().port,
    requestIntervalMs: 40, statusIntervalMs: 60, log: () => {}, ...overrides };
  const app = await createPortableServer(opts), ports = await app.start();
  const url = `http://localhost:${ports.httpPort}`;
  t.after(async () => { await app.stop(); await new Promise(resolve => phone.close(resolve)); await rm(directory, { recursive: true, force: true }); });
  const post = (route, data, origin = url) => fetch(url + route, { method: 'POST',
    headers: { 'Content-Type': 'application/json', ...(origin ? { Origin: origin } : {}) }, body: JSON.stringify(data) });
  return { directory, phone, requests, app, opts, ports, settingsFile, url, post };
}

test('portable setup starts without an IP, saves from GUI, forwards raw UDP and restores saved settings', async t => {
  const f = await fixture(t); await delay(100); assert.equal(f.requests.length, 0);
  const status = await (await fetch(f.url + '/api/status')).json(); assert.equal(status.appId, APP_ID); assert.equal(status.iphoneIp, '');
  assert.match(await (await fetch(f.url)).text(), /保存して接続/);
  const saved = await f.post('/api/connection', { iphoneIp: ' 127.0.0.1 ' }); assert.equal(saved.status, 200);
  assert.deepEqual(JSON.parse(await readFile(f.settingsFile, 'utf8')), { iphoneIp: '127.0.0.1' });
  await delay(100); assert.ok(f.requests.length >= 2); assert.equal(f.requests[0].ports[0], f.ports.udpPort);
  const socket = new WebSocket(`ws://localhost:${f.ports.httpPort}`, { origin: f.url });
  t.after(() => socket.terminate()); await once(socket, 'open');
  const message = JSON.stringify({ FaceFound: true, Hotkey: 2, BlendShapes: [{ k: 'JawOpen', v: .6 }], FutureField: { keep: true } });
  const received = once(socket, 'message'); f.phone.send(message, f.ports.udpPort, '127.0.0.1');
  assert.equal((await received)[0].toString(), message);
  assert.equal(f.app.getStatus().faceFound, true); assert.equal(f.app.getStatus().jawOpen, '0.600');
  const config = await (await fetch(f.url + '/owl_prince_tracking_config.json')).json();
  assert.equal(config.wsUrl, `ws://localhost:${f.ports.httpPort}`); assert.equal(config.smoothingMs, 80);
  socket.terminate(); await f.app.stop();
  const next = await createPortableServer(f.opts); t.after(() => next.stop()); await next.start();
  assert.equal(next.getStatus().iphoneIp, '127.0.0.1');
});

test('portable mutations reject unrelated origins and invalid IP without changing settings', async t => {
  const f = await fixture(t);
  assert.equal((await f.post('/api/connection', { iphoneIp: '127.0.0.1' }, 'https://unrelated.example')).status, 403);
  assert.equal((await f.post('/api/connection', { iphoneIp: '127.0.0.1' }, '')).status, 403);
  assert.equal((await f.post('/api/connection', { iphoneIp: 'not an IP' })).status, 400);
  assert.equal((await f.post('/api/connection', null)).status, 400);
  assert.equal(f.app.getStatus().iphoneIp, ''); assert.equal(f.requests.length, 0);
  assert.equal((await f.post('/api/connection', { iphoneIp: '127.0.0.1' })).status, 200);
  assert.equal((await f.post('/api/connection', { iphoneIp: '1.2.3.999' })).status, 400);
  assert.equal(f.app.getStatus().iphoneIp, '127.0.0.1');
  assert.equal(JSON.parse(await readFile(f.settingsFile, 'utf8')).iphoneIp, '127.0.0.1');
  assert.equal((await fetch(f.url + '/api/connection')).status, 404);
});

test('portable stop button releases HTTP and UDP; settings outside htmlDir are not served', async t => {
  const f = await fixture(t); await f.post('/api/connection', { iphoneIp: '127.0.0.1' });
  assert.equal((await fetch(f.url + '/settings/connection.json')).status, 404);
  assert.equal((await fetch(f.url + '/owl_prince_iphone_test.html')).status, 200);
  assert.equal((await f.post('/api/stop', {}, 'https://unrelated.example')).status, 403);
  assert.equal((await f.post('/api/stop', {})).status, 200); await delay(150);
  assert.equal(f.app.getStatus().running, false);
  const next = await createPortableServer({ ...f.opts, httpPort: f.ports.httpPort, udpPort: f.ports.udpPort });
  t.after(() => next.stop()); await next.start(); assert.equal(next.getStatus().running, true);
});

test('portable failed persistence does not activate an unsaved iPhone address', async t => {
  const f = await fixture(t); await writeFile(path.join(f.directory, 'settings'), 'not a directory');
  const result = await f.post('/api/connection', { iphoneIp: '127.0.0.1' }); assert.equal(result.status, 500);
  assert.equal(f.app.getStatus().iphoneIp, '');
});

test('changing the saved iPhone IP retargets requests and rejects the old phone without restarting', async t => {
  const f = await fixture(t); await f.post('/api/connection', { iphoneIp: '127.0.0.1' });
  const second = dgram.createSocket('udp4');
  await new Promise(resolve => second.bind(f.phone.address().port, '127.0.0.2', resolve));
  t.after(() => new Promise(resolve => second.close(resolve)));
  const socket = new WebSocket(`ws://localhost:${f.ports.httpPort}`, { origin: f.url });
  t.after(() => socket.terminate()); await once(socket, 'open');
  const request = once(second, 'message', { signal: AbortSignal.timeout(3000) });
  assert.equal((await f.post('/api/connection', { iphoneIp: '127.0.0.2' })).status, 200);
  assert.equal(JSON.parse((await request)[0]).ports[0], f.ports.udpPort);
  f.phone.send('{"FaceFound":true,"oldPhone":true}', f.ports.udpPort, '127.0.0.1');
  await delay(80); assert.equal(f.app.getStatus().receivedTotal, 0);
  const forwarded = once(socket, 'message', { signal: AbortSignal.timeout(3000) });
  second.send('{"FaceFound":true,"newPhone":true}', f.ports.udpPort, '127.0.0.1');
  assert.equal((await forwarded)[0].toString(), '{"FaceFound":true,"newPhone":true}');
  assert.equal(f.app.getStatus().httpPort, f.ports.httpPort); assert.equal(f.app.getStatus().udpPort, f.ports.udpPort);
});
