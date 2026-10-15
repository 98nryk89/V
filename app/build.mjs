// src/ → dist/ にまとめる（配信には dist/ だけが要る）。  node app/build.mjs
import { build } from "esbuild";
import path from "node:path";
import { fileURLToPath } from "node:url";

const root = path.dirname(fileURLToPath(import.meta.url));
await build({
  entryPoints: { main: path.join(root, "src/main.js"), player: path.join(root, "src/player.js") },
  outdir: path.join(root, "dist"),
  bundle: true,
  format: "esm",
  target: "es2022",
  sourcemap: false,
  minify: true,
  logLevel: "info",
});
