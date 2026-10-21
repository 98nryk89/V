import dgram from 'node:dgram';
import readline from 'node:readline';
import { pathToFileURL } from 'node:url';
import path from 'node:path';
const root = process.argv[2];
const { createPortableServer } = await import(pathToFileURL(path.join(root, 'bridge/portable/server.js')));
const phone = dgram.createSocket('udp4');
await new Promise(resolve => phone.bind(0, '127.0.0.1', resolve));
let destination, frame = { FaceFound: true, Hotkey: -1, Rotation: { x: 0, y: 0, z: 0 }, Position: { x: 0, y: 0, z: 0 }, BlendShapes: [] };
phone.on('message', (message, remote) => { destination = { port: JSON.parse(message).ports[0], address: remote.address }; });
const app = await createPortableServer({ htmlDir: path.join(root, 'html'), settingsFile: process.argv[3],
  httpPort: 0, udpPort: 0, iphonePort: phone.address().port, log: () => {} });
const ports = await app.start(); console.log(JSON.stringify(ports));
const timer = setInterval(() => { if (destination) phone.send(JSON.stringify(frame), destination.port, destination.address); }, 16);
readline.createInterface({ input: process.stdin }).on('line', line => { frame = JSON.parse(line); });
process.on('SIGTERM', async () => { clearInterval(timer); await app.stop(); phone.close(); process.exit(0); });
