// 土台の絵の上に重ねる差分パーツ（目・口・眉・フクロウの目）を、どの状態で出すかを決める。
// 重ね順は「開いている → 閉じている」。下の層は不透明のまま残し、上の層だけを出し入れするので、
// 切り替えの途中で土台（開いた目など）が透けて見えることがない。
// モデルに ParamGP_* が無ければ何もしない。

const clamp01 = (v) => Math.min(1, Math.max(0, v));

/** value が threshold を下回るほど 1。境目の前後 soft だけ滑らかにする。 */
const below = (value, threshold, soft = 0.08) => clamp01((threshold + soft / 2 - value) / soft);
/** value が threshold を上回るほど 1。 */
const above = (value, threshold, soft = 0.08) => clamp01((value - (threshold - soft / 2)) / soft);

export const EYE_STATES = ["wide", "smile", "75", "50", "25", "closed", "smileclosed"];
export const MOUTH_STATES = ["smile", "frown", "small", "u", "e", "i", "a", "o", "big"];
export const BROW_STATES = ["up", "troubled", "angry"];

/** 表情 id → 目と口の状態 */
export function modeFor(expression) {
  if (expression === "laugh") return { eye: "laugh", mouth: "laugh" };
  if (expression === "smile") return { eye: "smile", mouth: "normal" };
  if (expression === "surprised") return { eye: "wide", mouth: "surprised" };
  return { eye: "normal", mouth: "normal" };
}

/** 目: 開き具合 open（0..1）と表情から、各状態の不透明度を返す。 */
export function eyeAlphas(open, mode = "normal") {
  const happy = mode === "smile" || mode === "laugh";
  const closedAmt = below(open, 0.125);
  return {
    wide: mode === "wide" ? 1 : 0,
    smile: mode === "smile" ? 1 : 0,
    75: below(open, 0.875),
    50: below(open, 0.625),
    25: below(open, 0.375),
    closed: happy ? 0 : closedAmt,
    smileclosed: happy ? Math.max(closedAmt, mode === "laugh" ? 1 : 0) : 0,
  };
}

/** 口: 開き open（0..1）、形 form（-1..1）、母音の手がかりから、各状態の不透明度を返す。 */
export function mouthAlphas(open, form, { funnel = 0, pucker = 0, mode = "normal" } = {}) {
  const a = Object.fromEntries(MOUTH_STATES.map((k) => [k, 0]));
  a.smile = above(form, 0.3, 0.2) * (mode === "surprised" ? 0 : 1);
  a.frown = above(-form, 0.3, 0.2);
  const wide = mode === "laugh" ? 1 : above(open, 0.8, 0.1);
  const mid = above(open, 0.4, 0.1);
  const small = above(open, 0.12, 0.08);
  a.small = small;
  // 小さく開いたときの形: とがらせ→う、横に引く→え
  if (pucker > 0.35) a.u = small;
  else if (form > 0.35) a.e = small;
  // 大きく開いたときの形: すぼめ・驚き→お、横に引く→い、普通→あ
  let key = "a";
  if (funnel > 0.3 || mode === "surprised") key = "o";
  else if (form > 0.45) key = "i";
  a[key] = Math.max(a[key], mid);
  a.big = mode === "surprised" ? 0 : wide;
  for (const k of Object.keys(a)) a[k] = clamp01(a[k]);
  return a;
}

/** 眉: 上げ下げ y（-1..1）と角度 angle（-1..1）から、各状態の不透明度を返す。 */
export function browAlphas(y, angle) {
  const a = { up: 0, troubled: 0, angry: 0 };
  const angry = Math.max(above(angle, 0.2, 0.15), above(-y, 0.25, 0.15));
  const troubled = above(-angle, 0.2, 0.15);
  const up = above(y, 0.25, 0.15);
  a.angry = angry;
  a.troubled = angry > 0.5 ? 0 : troubled;
  a.up = angry > 0.5 || troubled > 0.5 ? 0 : up;
  return a;
}

/** モデルの ParamGP_* に書く値をまとめて返す（使わない状態は 0）。 */
export function patchParams(get, { expression = null, hints = {}, owlBlink = 0 } = {}) {
  const m = modeFor(expression);
  const out = {};
  for (const side of ["L", "R"]) {
    const e = eyeAlphas(get(`ParamEye${side}Open`) ?? 1, m.eye);
    for (const k of EYE_STATES) out[`ParamGP_eye${side}_${k}`] = e[k];
    const b = browAlphas(get(`ParamBrow${side}Y`) ?? 0, get(`ParamBrow${side}Angle`) ?? 0);
    for (const k of BROW_STATES) out[`ParamGP_brow${side}_${k}`] = b[k];
  }
  const mo = mouthAlphas(get("ParamMouthOpenY") ?? 0, get("ParamMouthForm") ?? 0, { ...hints, mode: m.mouth });
  for (const k of MOUTH_STATES) out[`ParamGP_mouth_${k}`] = mo[k];
  out.ParamGP_owlEyes_closed = owlBlink;
  return out;
}

/** フクロウのまばたき（本人とは別の周期）。0..1 を返す。 */
export class OwlBlink {
  constructor(rand = Math.random) {
    this.rand = rand;
    this.next = 0;
    this.start = -1;
  }
  value(now) {
    if (this.next === 0) this.next = now + 2000 + this.rand() * 4000;
    if (this.start < 0 && now >= this.next) this.start = now;
    if (this.start >= 0) {
      const t = now - this.start;
      if (t > 260) {
        this.start = -1;
        this.next = now + 2500 + this.rand() * 5000;
        return 0;
      }
      return t < 70 ? t / 70 : t < 190 ? 1 : 1 - (t - 190) / 70;
    }
    return 0;
  }
}
