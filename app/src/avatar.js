// iki のモデルを読み込んで描画し、待機モーション（呼吸・まばたき・髪の揺れ）と表情を動かす。
import { IkiPlayer, IkiMotion } from "@ikijs/engine";
import { loadIkiModel } from "@ikijs/format";
import { combine } from "./mapping.js";

export class Avatar {
  constructor(canvas, { zoom = 1, cx = 0, cy = 0 } = {}) {
    this.canvas = canvas;
    this.player = new IkiPlayer(canvas);
    this.view = { zoom, cx, cy };
    this.tracked = null; // { params, time }
    this.expression = null;
    this.autoBlink = true;
  }

  async load(url) {
    const res = await fetch(url);
    if (!res.ok) throw new Error(`モデルを読み込めません: ${url} (${res.status})`);
    this.model = loadIkiModel(await res.text());
    const result = await this.player.load(this.model);
    if (result.failedTextures.length) console.warn("読み込めなかったテクスチャ:", result.failedTextures);
    const player = this.player;
    this.motion = new IkiMotion(this.model, (id) => player.getParameter(id), (id, v) => player.setParameter(id, v));
    this.paramIds = new Set(player.getParameters().map((p) => p.id));
    this.applyView();
    return this.model;
  }

  applyView() {
    if (!this.model) return;
    const { width: W, height: H } = this.model.canvas;
    const { zoom, cx, cy } = this.view;
    const aspect = this.canvas.width / Math.max(1, this.canvas.height);
    // 縦をモデルの高さに合わせ、横は画面の比率に合わせる（拡大・移動はモデルの大きさに対する割合）
    const h = H / zoom;
    this.player.setView({ x: cx * W, y: cy * H, width: h * aspect, height: h });
  }

  resize(width, height, dpr = 1) {
    this.canvas.width = Math.max(1, Math.round(width * dpr));
    this.canvas.height = Math.max(1, Math.round(height * dpr));
    this.applyView();
  }

  setTracked(params) {
    this.tracked = params ? { params, time: performance.now() } : null;
  }

  playExpression(id) {
    if (!id || id === "neutral") {
      this.motion?.stopExpression();
      this.expression = null;
    } else if (this.motion?.playExpression(id)) {
      this.expression = id;
    }
  }

  start() {
    this.player.start();
    const tick = (now) => {
      this.motion.update(now);
      const t = this.tracked;
      if (t && now - t.time < 400) {
        const cur = {};
        for (const id of this.paramIds) cur[id] = this.player.getParameter(id);
        const merged = combine(cur, t.params, this.expression !== null);
        for (const [k, v] of Object.entries(merged)) if (this.paramIds.has(k)) this.player.setParameter(k, v);
      }
      requestAnimationFrame(tick);
    };
    requestAnimationFrame(tick);
  }
}
