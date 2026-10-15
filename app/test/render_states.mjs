// 確認用: アプリと同じ切り替えのロジック（patches.js）を通して、状態ごとにモデルを描画し、一覧にする。
//   node app/test/render_states.mjs <モデル.iki> <出力フォルダ>
import { spawn } from "node:child_process";
import { createRequire } from "node:module";
import path from "node:path";
import fs from "node:fs";
import { fileURLToPath } from "node:url";

const here = path.dirname(fileURLToPath(import.meta.url));
const require = createRequire(import.meta.url);
const { chromium } = require("/opt/node-tools/node_modules/playwright");
const [model = "model/iki/model.iki", outDir = "/tmp/states"] = process.argv.slice(2);
fs.mkdirSync(outDir, { recursive: true });
const port = 8793;
const srv = spawn(process.execPath, [path.join(here, "../server.mjs"), String(port)], { stdio: "ignore" });
await new Promise((r) => setTimeout(r, 700));
const browser = await chromium.launch({
  executablePath: "/opt/pw-browsers/chromium-1194/chrome-linux/chrome",
  args: ["--no-sandbox", "--use-gl=angle", "--use-angle=swiftshader", "--enable-unsafe-swiftshader", "--ignore-gpu-blocklist"],
});
try {
  const page = await browser.newPage({ viewport: { width: 760, height: 760 } });
  page.on("pageerror", (e) => console.log("pageerror", e.message));
  await page.goto(`http://localhost:${port}/player.html?zoom=2.6&cy=0.28&model=/${model}`);
  await page.waitForFunction(() => window.__avatar?.paramIds, null, { timeout: 120000 });
  const states = JSON.parse(fs.readFileSync(path.join(here, "states.json"), "utf8"));
  for (const st of states) {
    await page.evaluate(async (st) => {
      const a = window.__avatar;
      a.playExpression(st.expression ?? "neutral");
      a.owl.value = () => st.owl ?? 0;
      const base = { ParamEyeLOpen: 1, ParamEyeROpen: 1, ParamMouthOpenY: 0, ParamMouthForm: 0, ParamBrowLY: 0, ParamBrowRY: 0, ParamBrowLAngle: 0, ParamBrowRAngle: 0,
        ParamAngleX: 0, ParamAngleY: 0, ParamAngleZ: 0, ParamBodyAngleX: 0, ParamBodyAngleY: 0, ParamBodyAngleZ: 0, ParamEyeBallX: 0, ParamEyeBallY: 0, HintFunnel: 0, HintPucker: 0 };
      // 本物のトラッキングと同じく、値を流し続ける（400ms 以上途切れると、アプリは追跡を無視する）
      clearInterval(window.__feed);
      window.__feed = setInterval(() => a.setTracked({ ...base, ...st.params }), 30);
      await new Promise((r) => setTimeout(r, 1200));
    }, st);
    await page.waitForTimeout(500);
    await page.screenshot({ path: path.join(outDir, `${st.name}.png`) });
  }
} finally {
  await browser.close();
  srv.kill();
}
