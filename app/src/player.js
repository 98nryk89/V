// OBS のブラウザソース用: トラッキングのページから WebSocket で値を受け取って動かす。背景は透過。
import { Avatar } from "./avatar.js";

const q = new URLSearchParams(location.search);
const canvas = document.getElementById("avatar");
const avatar = new Avatar(canvas, { zoom: Number(q.get("zoom") ?? 1), cx: Number(q.get("cx") ?? 0), cy: Number(q.get("cy") ?? 0) });

function fit() {
  avatar.resize(window.innerWidth, window.innerHeight, window.devicePixelRatio || 1);
}
window.addEventListener("resize", fit);
fit();

await avatar.load(q.get("model") ?? "/model/iki/upper_s.iki");
fit();
avatar.start();

function connect() {
  const ws = new WebSocket(`ws://${location.host}`);
  ws.onmessage = (ev) => {
    let m;
    try { m = JSON.parse(ev.data); } catch { return; }
    if (m.t === "p") avatar.setTracked(m.p ?? null);
    else if (m.t === "e") avatar.playExpression(m.e);
  };
  ws.onclose = () => setTimeout(connect, 1000);
}
connect();
window.__avatar = avatar;
