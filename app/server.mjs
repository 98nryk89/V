// V アプリのローカルサーバー: 静的ファイルの配信 + WebSocket の中継（追加のパッケージ不要）。
//   node app/server.mjs [ポート]    既定のポートは 8787
// - トラッキングのページ（Chrome・Web カメラ）が送った値を、OBS のブラウザソースのページへ中継する
import http from "node:http";
import crypto from "node:crypto";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const root = path.dirname(fileURLToPath(import.meta.url));
const repoRoot = path.resolve(root, "..");
const port = Number(process.argv[2] ?? process.env.PORT ?? 8787);

const TYPES = {
  ".html": "text/html; charset=utf-8", ".js": "text/javascript; charset=utf-8", ".mjs": "text/javascript; charset=utf-8",
  ".json": "application/json", ".wasm": "application/wasm", ".task": "application/octet-stream",
  ".iki": "application/json", ".png": "image/png", ".jpg": "image/jpeg", ".css": "text/css; charset=utf-8",
};

// 配信するフォルダ: app/ と、モデルのある model/
function resolveFile(urlPath) {
  const clean = decodeURIComponent(urlPath.split("?")[0]);
  const rel = clean === "/" ? "/index.html" : clean;
  const base = rel.startsWith("/model/") ? repoRoot : root;
  const file = path.normalize(path.join(base, rel));
  if (!file.startsWith(base + path.sep) || file.includes(`${path.sep}node_modules${path.sep}`) || file.endsWith("server.mjs")) return null;
  return file;
}

const server = http.createServer((req, res) => {
  const file = resolveFile(req.url ?? "/");
  if (!file || !fs.existsSync(file) || !fs.statSync(file).isFile()) {
    res.writeHead(404, { "content-type": "text/plain; charset=utf-8" });
    res.end("not found");
    return;
  }
  res.writeHead(200, { "content-type": TYPES[path.extname(file)] ?? "application/octet-stream", "cache-control": "no-store" });
  fs.createReadStream(file).pipe(res);
});

// ---- 最小限の WebSocket（テキストフレームのみ。受け取った内容を、他の全クライアントへ配る）----
const clients = new Set();
const GUID = "258EAFA5-E914-47DA-95CA-C5AB0DC85B11";

function frame(text) {
  const payload = Buffer.from(text);
  const n = payload.length;
  const head = n < 126 ? Buffer.from([0x81, n]) : n < 65536 ? Buffer.from([0x81, 126, n >> 8, n & 255]) : null;
  if (!head) return null; // 大きすぎるメッセージは配らない
  return Buffer.concat([head, payload]);
}

function broadcast(from, text) {
  const f = frame(text);
  if (!f) return;
  for (const c of clients) if (c !== from && !c.destroyed) c.write(f);
}

server.on("upgrade", (req, socket) => {
  const key = req.headers["sec-websocket-key"];
  if (!key) return socket.destroy();
  const accept = crypto.createHash("sha1").update(key + GUID).digest("base64");
  socket.write(`HTTP/1.1 101 Switching Protocols\r\nUpgrade: websocket\r\nConnection: Upgrade\r\nSec-WebSocket-Accept: ${accept}\r\n\r\n`);
  clients.add(socket);
  let buf = Buffer.alloc(0);
  socket.on("data", (chunk) => {
    buf = Buffer.concat([buf, chunk]);
    for (;;) {
      if (buf.length < 2) return;
      const opcode = buf[0] & 15;
      const masked = (buf[1] & 128) !== 0;
      let len = buf[1] & 127;
      let off = 2;
      if (len === 126) { if (buf.length < 4) return; len = buf.readUInt16BE(2); off = 4; }
      else if (len === 127) { if (buf.length < 10) return; len = Number(buf.readBigUInt64BE(2)); off = 10; }
      if (len > 1 << 20) return socket.destroy();
      const maskLen = masked ? 4 : 0;
      if (buf.length < off + maskLen + len) return;
      const mask = masked ? buf.subarray(off, off + 4) : null;
      const data = Buffer.from(buf.subarray(off + maskLen, off + maskLen + len));
      if (mask) for (let i = 0; i < data.length; i++) data[i] ^= mask[i & 3];
      buf = buf.subarray(off + maskLen + len);
      if (opcode === 8) { socket.end(); return; }
      if (opcode === 9) socket.write(Buffer.concat([Buffer.from([0x8a, data.length]), data])); // ping → pong
      if (opcode === 1) broadcast(socket, data.toString("utf8"));
    }
  });
  const drop = () => clients.delete(socket);
  socket.on("close", drop);
  socket.on("error", drop);
});

server.listen(port, "127.0.0.1", () => {
  console.log(`V アプリを起動しました`);
  console.log(`  トラッキング（Chrome で開く）: http://localhost:${port}/`);
  console.log(`  OBS のブラウザソース        : http://localhost:${port}/player.html`);
});
