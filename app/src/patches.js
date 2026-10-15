// 生成した差分パーツ（目・口・フクロウの目）を、どの状態でどれだけ出すかを決める。
// モデルに ParamGP_* が無ければ何もしない（古いモデルでも動く）。

const clamp01 = (v) => Math.min(1, Math.max(0, v));

/** 隣り合う状態の切り替え: 境目の前後 width/2 だけ重ねる（半透明の時間を短くして、二重に見えないようにする） */
function bands(value, stops, width) {
  // stops: [{ at, key }] を at の昇順で。value に最も近い状態を 1、境目付近だけ 2 つを混ぜる
  const w = {};
  for (const s of stops) w[s.key] = 0;
  for (let i = 0; i < stops.length; i++) {
    const lo = i === 0 ? -Infinity : (stops[i - 1].at + stops[i].at) / 2;
    const hi = i === stops.length - 1 ? Infinity : (stops[i].at + stops[i + 1].at) / 2;
    const up = Number.isFinite(lo) ? clamp01((value - (lo - width / 2)) / width) : 1;
    const down = Number.isFinite(hi) ? clamp01(((hi + width / 2) - value) / width) : 1;
    w[stops[i].key] += Math.min(up, down); // 同じ状態が 2 か所に出るときは足す
  }
  return w;
}

/**
 * 目: 開き具合 open(0..1) と表情から、各状態の重みを返す。base は元の目（変形で動く目）。
 *   mode: "normal" | "smile"（笑顔: 開いているときは笑い目、閉じたら笑いの閉じ目）| "wide"（驚き）| "laugh"
 */
export function eyeWeights(open, mode = "normal") {
  const closedKey = mode === "laugh" || mode === "smile" ? "smileclosed" : "closed";
  const openKey = mode === "wide" ? "wide" : mode === "smile" ? "smile" : "base";
  const w = bands(open, [
    { at: 0, key: closedKey }, { at: 0.25, key: "25" }, { at: 0.5, key: "50" }, { at: 0.75, key: "75" }, { at: 1, key: openKey },
  ], 0.06);
  return w;
}

/**
 * 口: 開き具合 open(0..1)、形 form(-1..1)、母音の手がかり（funnel: すぼめ、pucker: とがらせ）から重みを返す。
 *   base は元の口（閉じた線）。
 */
export function mouthWeights(open, form, { funnel = 0, pucker = 0, mode = "normal" } = {}) {
  let closedKey = "base";
  if (form > 0.3) closedKey = "smile";
  else if (form < -0.3) closedKey = "frown";
  let smallKey = "small";
  if (pucker > 0.35) smallKey = "u";
  else if (form > 0.35) smallKey = "e";
  let midKey = "a";
  if (funnel > 0.3 || mode === "surprised") midKey = "o";
  else if (form > 0.45) midKey = "i";
  const bigKey = mode === "laugh" || form > 0.2 ? "big" : midKey;
  return bands(open, [{ at: 0, key: closedKey }, { at: 0.3, key: smallKey }, { at: 0.6, key: midKey }, { at: 0.95, key: bigKey }], 0.08);
}

/** 表情 id → 目と口の状態 */
export function modeFor(expression) {
  if (expression === "laugh") return { eye: "laugh", mouth: "laugh" };
  if (expression === "smile") return { eye: "smile", mouth: "normal" };
  if (expression === "surprised") return { eye: "wide", mouth: "surprised" };
  return { eye: "normal", mouth: "normal" };
}

/** パーツの重みを、モデルのパラメータの値にする（同じ状態のキーが重なったら足す）。 */
export function patchParams(get, { expression = null, hints = {}, owlBlink = 0 } = {}) {
  const m = modeFor(expression);
  const out = {};
  for (const side of ["L", "R"]) {
    const w = eyeWeights(get(`ParamEye${side}Open`) ?? 1, m.eye);
    let shown = 0;
    for (const [k, v] of Object.entries(w)) {
      if (k === "base") continue;
      out[`ParamGP_eye${side}_${k}`] = (out[`ParamGP_eye${side}_${k}`] ?? 0) + v;
      shown += v;
    }
    out[`ParamGP_eye${side}_hide`] = clamp01(shown);
  }
  const mw = mouthWeights(get("ParamMouthOpenY") ?? 0, get("ParamMouthForm") ?? 0, { ...hints, mode: m.mouth });
  let shown = 0;
  for (const [k, v] of Object.entries(mw)) {
    if (k === "base") continue;
    out[`ParamGP_mouth_${k}`] = (out[`ParamGP_mouth_${k}`] ?? 0) + v;
    shown += v;
  }
  out.ParamGP_mouth_hide = clamp01(shown);
  out.ParamGP_owlEyes_closed = owlBlink;
  for (const k of Object.keys(out)) out[k] = clamp01(out[k]);
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
