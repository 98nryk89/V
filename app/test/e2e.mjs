// ブラウザでの動作確認（人のいない環境用）。偽のカメラ映像（顔写真）を流して、顔の追跡 → キャラの描画 → OBS 用ページへの中継までを通す。
//   node app/test/e2e.mjs <顔写真を y4m にしたファイル> <出力フォルダ>
import { spawn } from "node:child_process";
import { createRequire } from "node:module";
import path from "node:path";
import fs from "node:fs";
import { fileURLToPath } from "node:url";

const here = path.dirname(fileURLToPath(import.meta.url));
const require = createRequire(import.meta.url);
const { chromium } = require(process.env.PLAYWRIGHT_PATH ?? "/opt/node-tools/node_modules/playwright");
const [video, outDir = "/tmp/e2e"] = process.argv.slice(2);
fs.mkdirSync(outDir, { recursive: true });

const port = 8791;
const srv = spawn(process.execPath, [path.join(here, "../server.mjs"), String(port)], { stdio: "inherit" });
await new Promise((r) => setTimeout(r, 800));
const fail = [];
const check = (ok, msg) => { console.log(`${ok ? "PASS" : "FAIL"} ${msg}`); if (!ok) fail.push(msg); };

const browser = await chromium.launch({
  executablePath: "/opt/pw-browsers/chromium-1194/chrome-linux/chrome",
  args: ["--no-sandbox", "--use-gl=angle", "--use-angle=swiftshader", "--enable-unsafe-swiftshader", "--ignore-gpu-blocklist",
    "--use-fake-ui-for-media-stream", "--use-fake-device-for-media-stream", ...(video ? [`--use-file-for-fake-video-capture=${video}`] : [])],
});
try {
  const ctx = await browser.newContext({ viewport: { width: 1280, height: 800 }, permissions: ["camera"] });
  const tracker = await ctx.newPage();
  const logs = [];
  tracker.on("console", (m) => logs.push(`[tracker ${m.type()}] ${m.text()}`));
  tracker.on("pageerror", (e) => logs.push(`[tracker error] ${e.message}`));
  const player = await ctx.newPage();
  player.on("console", (m) => logs.push(`[player ${m.type()}] ${m.text()}`));
  player.on("pageerror", (e) => logs.push(`[player error] ${e.message}`));
  await player.setViewportSize({ width: 600, height: 700 });
  await player.goto(`http://localhost:${port}/player.html`);
  await tracker.goto(`http://localhost:${port}/`);

  await tracker.waitForFunction(() => document.getElementById("start") && !document.getElementById("start").disabled, null, { timeout: 120000 });
  check(true, "モデルと顔認識モデルの読み込み");
  await tracker.click("#start");
  await tracker.waitForFunction(() => document.getElementById("face").textContent === "追跡中", null, { timeout: 60000 }).catch(() => {});
  const face = await tracker.textContent("#face");
  check(face === "追跡中", `偽のカメラ映像で顔を検出 (${face})`);
  await tracker.waitForTimeout(1500);
  await tracker.screenshot({ path: path.join(outDir, "tracker.png") });

  // 追跡した値（ニュートラルの顔写真なので、ほぼ 0 になるはず）
  const vals = await tracker.evaluate(() => {
    const a = window.__v.avatar;
    return Object.fromEntries([...a.paramIds].map((id) => [id, a.player.getParameter(id)]));
  });
  console.log(JSON.stringify(vals));
  check(Math.abs(vals.ParamAngleX) < 25, "顔の向きの値が範囲内");

  // 合成した入力で、表情・向き・まばたき・口が反映されるか
  const synth = await tracker.evaluate(async () => {
    const v = window.__v;
    v.paused = true; // 本物のカメラ映像の処理を止めて、合成した入力だけを流す
    const out = {};
    const read = () => Object.fromEntries([...v.avatar.paramIds].map((id) => [id, v.avatar.player.getParameter(id)]));
    const run = async (blend, angles) => {
      for (let i = 0; i < 12; i++) { v.onResult({ blend, angles }, performance.now()); await new Promise((r) => setTimeout(r, 40)); }
      return read();
    };
    out.blink = await run({ eyeBlinkLeft: 1, eyeBlinkRight: 1 }, { yaw: 0, pitch: 0, roll: 0 });
    out.mouth = await run({ jawOpen: 0.7 }, { yaw: 0, pitch: 0, roll: 0 });
    out.smile = await run({ mouthSmileLeft: 0.6, mouthSmileRight: 0.6 }, { yaw: 0, pitch: 0, roll: 0 });
    return out;
  });
  check(synth.blink.ParamEyeLOpen < 0.2 && synth.blink.ParamEyeROpen < 0.2, "まばたきが反映される");
  check(synth.mouth.ParamMouthOpenY > 0.6, "口の開きが反映される");
  check(synth.smile.ParamMouthForm > 0.5, "笑顔が反映される");

  // OBS 用ページ: 中継された値で動くか（表情ボタン → 中継）と、背景が透過か
  await tracker.click('[data-expr="surprised"]');
  await player.waitForTimeout(1200);
  const pv = await player.evaluate(() => {
    const a = window.__avatar;
    return Object.fromEntries([...a.paramIds].map((id) => [id, a.player.getParameter(id)]));
  });
  check(pv.ParamMouthOpenY > 0.5, `OBS 用ページに表情が中継される (MouthOpenY=${pv.ParamMouthOpenY?.toFixed(2)})`);
  await player.screenshot({ path: path.join(outDir, "player.png"), omitBackground: true });
  const alpha = await player.evaluate(async () => {
    const c = document.getElementById("avatar");
    const t = document.createElement("canvas"); t.width = c.width; t.height = c.height;
    const g = t.getContext("2d"); g.drawImage(c, 0, 0);
    const d = g.getImageData(0, 0, 4, 4).data;
    return { corner: Array.from(d.slice(0, 4)), size: [c.width, c.height] };
  });
  check(alpha.corner[3] === 0, `OBS 用ページの背景が透過 (corner alpha=${alpha.corner[3]})`);

  const errors = logs.filter((l) => /error/i.test(l) && !/GPU|WebGL|swiftshader|GL Driver|Automatic fallback|INFO:|OpenGL|gl_context/i.test(l));
  fs.writeFileSync(path.join(outDir, "console.log"), logs.join("\n"));
  check(errors.length === 0, `コンソールにエラーがない (${errors.length})`);
  if (errors.length) console.log(errors.slice(0, 5).join("\n"));
} finally {
  await browser.close();
  srv.kill();
}
console.log(fail.length ? `\n失敗 ${fail.length} 件` : "\nすべて合格");
process.exit(fail.length ? 1 : 0);
