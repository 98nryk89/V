// トラッキングのページ（Chrome で開く）: Web カメラ → 顔の動き → キャラ（プレビュー）と、OBS 用のページへの送信。
import { Avatar } from "./avatar.js";
import { FaceTracker } from "./tracker.js";
import { AngleCalibration, Smoother, SMOOTH_ALPHAS, bodyFromHead, faceParams } from "./mapping.js";

const $ = (id) => document.getElementById(id);
const q = new URLSearchParams(location.search);

const avatar = new Avatar($("avatar"), { zoom: Number(q.get("zoom") ?? 1), cx: 0, cy: 0 });
const tracker = new FaceTracker($("cam"));
const smoother = new Smoother(SMOOTH_ALPHAS);

// ---- 保存される設定 ---------------------------------------------------
const store = {
  load() {
    try { return JSON.parse(localStorage.getItem("v.calib.v2") ?? "null") ?? {}; } catch { return {}; }
  },
  save(s) {
    try { localStorage.setItem("v.calib.v2", JSON.stringify(s)); } catch { /* 保存できなくても動く */ }
  },
};
const saved = store.load();
const calib = new AngleCalibration(saved.angle);
const state = { swapLR: saved.swapLR ?? false, baseline: saved.baseline ?? {}, calibrating: false, samples: [] };
const persist = () => store.save({ angle: calib.toJSON(), swapLR: state.swapLR, baseline: state.baseline });

// ---- WebSocket（OBS 用のページへ送る）---------------------------------
let ws = null;
function connect() {
  ws = new WebSocket(`ws://${location.host}`);
  ws.onopen = () => ($("ws").textContent = "OBS 用ページへ送信中");
  ws.onclose = () => { $("ws").textContent = "接続待ち…"; setTimeout(connect, 1000); };
}
connect();
const send = (obj) => { if (ws?.readyState === 1) ws.send(JSON.stringify(obj)); };

// ---- 表情 ---------------------------------------------------------------
const EXPRESSIONS = [
  ["neutral", "真顔", "1"], ["smile", "笑顔", "2"], ["surprised", "驚き", "3"],
  ["angry", "怒り", "4"], ["sad", "困り", "5"], ["laugh", "笑い", "6"],
];
function setExpression(id) {
  avatar.playExpression(id);
  send({ t: "e", e: id });
  document.querySelectorAll("[data-expr]").forEach((b) => b.classList.toggle("on", b.dataset.expr === id));
}
for (const [id, label, key] of EXPRESSIONS) {
  const b = document.createElement("button");
  b.dataset.expr = id;
  b.textContent = `${label} (${key})`;
  b.onclick = () => setExpression(id);
  $("expressions").appendChild(b);
}
window.addEventListener("keydown", (e) => {
  if (e.target instanceof HTMLInputElement) return;
  const hit = EXPRESSIONS.find(([, , key]) => key === e.key);
  if (hit) setExpression(hit[0]);
});

// ---- キャリブレーション -----------------------------------------------
const STEPS = [
  { text: "正面を向いて、無表情で", run: (s) => {
      calib.setNeutral(s.map((x) => x.angles));
      const base = {};
      for (const k of ["browInnerUp", "browDownLeft", "browDownRight", "browOuterUpLeft", "browOuterUpRight", "mouthSmileLeft", "mouthSmileRight", "mouthFrownLeft", "mouthFrownRight"]) {
        base[k] = s.reduce((a, x) => a + (x.blend[k] ?? 0), 0) / Math.max(1, s.length);
      }
      state.baseline = base;
      return true;
    } },
  { text: "左目だけ、ウインクして（鏡のように、あなたの左目）", run: (s) => {
      const peak = (k) => s.reduce((a, x) => Math.max(a, x.blend[k] ?? 0), 0);
      const l = peak("eyeBlinkLeft"), r = peak("eyeBlinkRight");
      if (Math.abs(l - r) < 0.2) return false;
      state.swapLR = r > l; // 本人の左目で「右」が強く出るなら、左右を入れ替える
      return true;
    } },
  { text: "顔を、あなたの右に向けて", run: (s) => calib.setAxis("yaw", s.map((x) => x.angles)) },
  { text: "顔を、上に向けて", run: (s) => calib.setAxis("pitch", s.map((x) => x.angles)) },
  { text: "首を、あなたの右にかしげて", run: (s) => calib.setAxis("roll", s.map((x) => x.angles)) },
];
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

async function runCalibration() {
  if (state.calibrating) return;
  state.calibrating = true;
  const fails = [];
  for (let i = 0; i < STEPS.length; i++) {
    $("prompt").textContent = `(${i + 1}/${STEPS.length}) ${STEPS[i].text}`;
    await sleep(1400);
    state.samples = [];
    await sleep(1800); // この間のフレームを集める
    const ok = STEPS[i].run(state.samples.slice());
    if (!ok) fails.push(i + 1);
  }
  state.calibrating = false;
  smoother.reset();
  persist();
  $("prompt").textContent = fails.length ? `完了（うまく取れなかった手順: ${fails.join(", ")}。もう一度やり直してください）` : "完了しました";
  setTimeout(() => { if (!state.calibrating) $("prompt").textContent = ""; }, 4000);
}
$("calibrate").onclick = runCalibration;
$("resetCalib").onclick = () => { localStorage.removeItem("v.calib.v2"); location.reload(); };

// ---- 毎フレーム ---------------------------------------------------------
let frames = 0, lastFps = performance.now(), lastFace = 0;
function onResult(r, now) {
  if (r.none) {
    if (now - lastFace > 500) { send({ t: "p", p: null }); $("face").textContent = "顔が見つかりません"; }
    return;
  }
  lastFace = now;
  $("face").textContent = "追跡中";
  if (state.calibrating) state.samples.push(r);
  const face = faceParams(r.blend, { swapLR: state.swapLR, baseline: state.baseline });
  const ang = calib.apply(r.angles);
  const merged = { ...face, ...ang };
  const sm = smoother.update(merged);
  const params = { ...sm, ...bodyFromHead(sm) };
  avatar.setTracked(params);
  send({ t: "p", p: params });
  frames++;
  if (now - lastFps > 1000) { $("fps").textContent = `${frames} fps (${tracker.delegate})`; frames = 0; lastFps = now; }
  if ($("debug").checked) $("values").textContent = Object.entries(params).map(([k, v]) => `${k.replace("Param", "")}: ${v.toFixed(2)}`).join("\n");
}
function loop(now) {
  const r = window.__v.paused ? null : tracker.detect(now);
  if (r) onResult(r, now);
  requestAnimationFrame(loop);
}

// ---- 起動 ---------------------------------------------------------------
function fit() {
  const el = $("avatar");
  avatar.resize(el.clientWidth, el.clientHeight, window.devicePixelRatio || 1);
}
window.addEventListener("resize", fit);

$("bg").onchange = (e) => ($("stage").dataset.bg = e.target.value);
$("zoom").oninput = (e) => { avatar.view.zoom = Number(e.target.value); avatar.applyView(); };
$("mirror").onchange = (e) => ($("cam").style.transform = e.target.checked ? "scaleX(-1)" : "none");

async function boot() {
  $("status").textContent = "モデルを読み込み中…";
  await avatar.load(q.get("model") ?? "/model/iki/model.iki");
  fit();
  avatar.start();
  $("status").textContent = "顔の認識モデルを読み込み中…";
  await tracker.init(".");
  $("status").textContent = "「カメラを開始」を押してください";
  $("start").disabled = false;
}
$("start").onclick = async () => {
  try {
    $("start").disabled = true;
    await tracker.startCamera();
    $("status").textContent = "動作中";
    requestAnimationFrame(loop);
    if (!saved.angle) $("prompt").textContent = "最初に「キャリブレーション」を押してください";
  } catch (e) {
    $("status").textContent = `カメラを開始できません: ${e.message}`;
    $("start").disabled = false;
  }
};

// 自動テスト用（人がいない環境で、決まった入力を流す）
window.__v = { avatar, tracker, calib, state, onResult, setExpression, paused: false };
boot().catch((e) => { $("status").textContent = `エラー: ${e.message}`; console.error(e); });
