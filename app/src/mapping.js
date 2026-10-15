// MediaPipe の結果 → iki のパラメータへの変換（ブラウザにも Node にも依存しない純粋な関数）。
export const clamp = (v, lo, hi) => Math.min(hi, Math.max(lo, v));

/** blendshape のカテゴリ配列 → { 名前: スコア } */
export function blendshapeMap(categories) {
  const o = {};
  for (const c of categories ?? []) o[c.categoryName] = c.score;
  return o;
}

/** 4x4 の変換行列（列優先, MediaPipe）→ 顔の向き（度）。符号と中心は、キャリブレーションで決める */
export function eulerFromMatrix(data) {
  const R = (r, c) => data[c * 4 + r];
  const pitch = Math.asin(clamp(-R(1, 2), -1, 1));
  const yaw = Math.atan2(R(0, 2), R(2, 2));
  const roll = Math.atan2(R(1, 0), R(1, 1));
  const deg = 180 / Math.PI;
  return { yaw: yaw * deg, pitch: pitch * deg, roll: roll * deg };
}

const smooth01 = (v, lo, hi) => clamp((v - lo) / (hi - lo), 0, 1);

/**
 * blendshape → 表情まわりのパラメータ。左右は「本人の左」を iki の L（画面の左）に対応させる
 * （鏡と同じ向き）。swapLR が true のときは左右を入れ替える。
 */
export function faceParams(b, { swapLR = false, baseline = {} } = {}) {
  const g = (k) => clamp((b[k] ?? 0) - (baseline[k] ?? 0), -1, 1);
  const raw = (k) => b[k] ?? 0;
  const L = swapLR ? "Right" : "Left";
  const R = swapLR ? "Left" : "Right";

  const eyeOpen = (side) => 1 - smooth01(raw(`eyeBlink${side}`), 0.18, 0.7);
  const squintL = g(`eyeSquint${L}`);
  const squintR = g(`eyeSquint${R}`);

  const jaw = raw("jawOpen");
  // 開いた口は「閉じた口との重ね合わせ」なので、半開きの時間を短くする（半透明の口が見えないように）
  const mouthOpen = smooth01(jaw + raw("mouthFunnel") * 0.2, 0.1, 0.32);
  const smile = (g(`mouthSmile${L}`) + g(`mouthSmile${R}`)) / 2;
  const frown = (g(`mouthFrown${L}`) + g(`mouthFrown${R}`)) / 2 + raw("mouthPucker") * 0.2;
  const mouthForm = clamp(smile * 1.2 - frown * 1.2, -0.7, 0.7);

  const browUp = (side) => Math.max(g(`browOuterUp${side}`), g("browInnerUp") * 0.9);
  const browLY = clamp(browUp(L) * 0.9 - g(`browDown${L}`) * 0.9, -0.6, 0.6);
  const browRY = clamp(browUp(R) * 0.9 - g(`browDown${R}`) * 0.9, -0.6, 0.6);
  const browLAngle = clamp(g(`browDown${L}`) * 0.7 - g("browInnerUp") * 0.7, -0.5, 0.5);
  const browRAngle = clamp(-(g(`browDown${R}`) * 0.7) + g("browInnerUp") * 0.7, -0.5, 0.5);

  // 視線: 本人が右を見る = 画面の右（鏡と同じ）
  const gx = ((raw("eyeLookOutRight") + raw("eyeLookInLeft")) - (raw("eyeLookOutLeft") + raw("eyeLookInRight"))) / 2;
  const gy = ((raw("eyeLookUpLeft") + raw("eyeLookUpRight")) - (raw("eyeLookDownLeft") + raw("eyeLookDownRight"))) / 2;
  const sw = swapLR ? -1 : 1;

  return {
    ParamEyeLOpen: clamp(eyeOpen(L) + squintL * -0.0, 0, 1),
    ParamEyeROpen: clamp(eyeOpen(R) + squintR * -0.0, 0, 1),
    ParamEyeBallX: clamp(gx * 1.2 * sw, -0.7, 0.7),
    ParamEyeBallY: clamp(gy * 1.2, -0.7, 0.7),
    ParamMouthOpenY: mouthOpen,
    ParamMouthForm: mouthForm,
    ParamBrowLY: browLY,
    ParamBrowRY: browRY,
    ParamBrowLAngle: browLAngle,
    ParamBrowRAngle: browRAngle,
    // 口の形の手がかり（モデルのパラメータではない。差分パーツの選択に使う）
    HintFunnel: raw("mouthFunnel"),
    HintPucker: raw("mouthPucker"),
  };
}

export const ANGLE_LIMIT = { x: 15, y: 12, z: 10 };

/** 顔の向きのキャリブレーション（中心・符号・倍率）。 */
export class AngleCalibration {
  constructor(state) {
    this.neutral = state?.neutral ?? { yaw: 0, pitch: 0, roll: 0 };
    this.sign = state?.sign ?? { yaw: 1, pitch: 1, roll: 1 };
    this.gain = state?.gain ?? { yaw: 1.0, pitch: 1.0, roll: 0.8 };
  }
  toJSON() {
    return { neutral: this.neutral, sign: this.sign, gain: this.gain };
  }
  /** 平均から中心を決める */
  setNeutral(samples) {
    const m = (k) => samples.reduce((a, s) => a + s[k], 0) / Math.max(1, samples.length);
    this.neutral = { yaw: m("yaw"), pitch: m("pitch"), roll: m("roll") };
  }
  /** 「右・上・右にかしげる」を行ったときのサンプルから、符号と倍率を決める。target は、そのとき出したい角度（度） */
  setAxis(axis, samples, target = 14) {
    let peak = 0;
    for (const s of samples) {
      const d = s[axis] - this.neutral[axis];
      if (Math.abs(d) > Math.abs(peak)) peak = d;
    }
    if (Math.abs(peak) < 3) return false; // ほとんど動いていない
    this.sign[axis] = peak > 0 ? 1 : -1;
    this.gain[axis] = clamp(target / Math.abs(peak), 0.4, 1.5);
    return true;
  }
  apply(raw) {
    // 1 枚絵から作ったモデルは、大きく回すと顔が崩れるので、範囲を狭くしている
    const f = (k, lim) => clamp(this.sign[k] * (raw[k] - this.neutral[k]) * this.gain[k], -lim, lim);
    return { ParamAngleX: f("yaw", ANGLE_LIMIT.x), ParamAngleY: f("pitch", ANGLE_LIMIT.y), ParamAngleZ: f("roll", ANGLE_LIMIT.z) };
  }
}

/** 指数移動平均。キーごとに追従の速さを変えられる。 */
export class Smoother {
  constructor(alphas = {}, fallback = 0.4) {
    this.alphas = alphas;
    this.fallback = fallback;
    this.v = {};
  }
  update(values) {
    const out = {};
    for (const [k, x] of Object.entries(values)) {
      const a = this.alphas[k] ?? this.fallback;
      this.v[k] = this.v[k] === undefined ? x : this.v[k] + (x - this.v[k]) * a;
      out[k] = this.v[k];
    }
    return out;
  }
  reset() {
    this.v = {};
  }
}

export const SMOOTH_ALPHAS = {
  ParamAngleX: 0.35, ParamAngleY: 0.35, ParamAngleZ: 0.35,
  ParamEyeLOpen: 0.7, ParamEyeROpen: 0.7,
  ParamEyeBallX: 0.5, ParamEyeBallY: 0.5,
  ParamMouthOpenY: 0.6, ParamMouthForm: 0.3,
  ParamBrowLY: 0.3, ParamBrowRY: 0.3, ParamBrowLAngle: 0.3, ParamBrowRAngle: 0.3,
};

/** 顔の向きから体の動きを作る（頭よりも小さく、遅れて付いてくる）。 */
export function bodyFromHead(p) {
  return {
    ParamBodyAngleX: clamp(p.ParamAngleX * 0.3, -10, 10),
    ParamBodyAngleY: clamp(p.ParamAngleY * 0.25, -10, 10),
    ParamBodyAngleZ: clamp(p.ParamAngleZ * 0.3, -10, 10),
  };
}

/**
 * motion.update() の後（表情・待機モーション・物理演算が書き込んだ後）で呼ぶ。
 *  current: そのときのパラメータの値、tracked: 顔の追跡から得た値
 *  expressionActive: 表情ボタンで表情を出している間は、眉と口の形を表情に足し合わせる
 */
export function combine(current, tracked, expressionActive) {
  const out = { ...tracked };
  const c = (k) => current[k] ?? 0;
  // 目: 表情を出している間は、表情の目の開き具合（笑い目など）と本人のまばたきの小さい方。
  // 出していないときは、本人のまばたきだけ（待機モーションの自動まばたきは使わない）
  if (expressionActive) {
    out.ParamEyeLOpen = Math.min(current.ParamEyeLOpen ?? 1, tracked.ParamEyeLOpen);
    out.ParamEyeROpen = Math.min(current.ParamEyeROpen ?? 1, tracked.ParamEyeROpen);
  }
  // 口の開き: 大きい方
  out.ParamMouthOpenY = Math.max(c("ParamMouthOpenY"), tracked.ParamMouthOpenY);
  if (expressionActive) {
    for (const k of ["ParamMouthForm", "ParamBrowLY", "ParamBrowRY", "ParamBrowLAngle", "ParamBrowRAngle"]) {
      out[k] = clamp(c(k) + tracked[k] * 0.5, -1, 1);
    }
  }
  return out;
}
