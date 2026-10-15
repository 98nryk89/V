// iki のモデルを読み込んで描画し、待機モーション（呼吸・まばたき・髪の揺れ）と表情を動かす。
import { IkiPlayer, IkiMotion } from "@ikijs/engine";
import { loadIkiModel } from "@ikijs/format";
import { combine } from "./mapping.js";
import { OwlBlink, patchParams } from "./patches.js";

const TRACKED_IDS = [
  "ParamEyeLOpen", "ParamEyeROpen", "ParamMouthOpenY", "ParamMouthForm",
  "ParamBrowLY", "ParamBrowRY", "ParamBrowLAngle", "ParamBrowRAngle",
];

export class Avatar {
  constructor(canvas, { zoom = 1, cx = 0, cy = 0 } = {}) {
    this.canvas = canvas;
    this.player = new IkiPlayer(canvas);
    this.view = { zoom, cx, cy };
    this.tracked = null; // { params, time }
    this.expression = null;
    this.autoBlink = true;
    this.owl = new OwlBlink();
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
    this.defaults = Object.fromEntries(this.model.parameters.map((p) => [p.id, p.default]));
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
      // 追跡で動かすパラメータは、毎フレーム初期値に戻してから待機モーション・表情を適用する。
      // こうしないと、前のフレームに自分で書いた値が「表情の値」として残り、口が開いたまま・目が閉じたままになる
      if (this.tracked) for (const id of TRACKED_IDS) if (this.paramIds.has(id)) this.player.setParameter(id, this.defaults[id] ?? 0);
      this.motion.update(now);
      const t = this.tracked;
      if (t && now - t.time < 400) {
        const cur = {};
        for (const id of this.paramIds) cur[id] = this.player.getParameter(id);
        const merged = combine(cur, t.params, this.expression !== null);
        for (const [k, v] of Object.entries(merged)) if (this.paramIds.has(k)) this.player.setParameter(k, v);
      }
      // 生成した差分パーツ（目・口・フクロウの目）の切り替え。モデルに無ければ何もしない
      if (this.paramIds.has("ParamGP_eyeL_hide")) {
        const p = this.tracked?.params ?? {};
        const gp = patchParams((id) => this.player.getParameter(id), {
          expression: this.expression,
          hints: { funnel: p.HintFunnel ?? 0, pucker: p.HintPucker ?? 0 },
          owlBlink: this.owl.value(now),
        });
        for (const [k, v] of Object.entries(gp)) if (this.paramIds.has(k)) this.player.setParameter(k, v);
      }
      requestAnimationFrame(tick);
    };
    requestAnimationFrame(tick);
  }
}
