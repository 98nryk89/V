import test from "node:test";
import assert from "node:assert/strict";
import { eyeAlphas, mouthAlphas, browAlphas, patchParams, OwlBlink, EYE_STATES, MOUTH_STATES, BROW_STATES } from "../src/patches.js";

test("目: 開いていれば何も重ねない。閉じるほど下から順に重なる", () => {
  const open = eyeAlphas(1);
  for (const k of EYE_STATES) assert.equal(open[k], 0, k);
  const half = eyeAlphas(0.5);
  assert.equal(half["75"], 1);
  assert.equal(half["50"], 1);
  assert.equal(half["25"], 0);
  const shut = eyeAlphas(0);
  assert.equal(shut["75"] + shut["50"] + shut["25"] + shut.closed, 4);
});

test("目: 途中でも、土台より下の層は不透明のまま（透けない）", () => {
  const a = eyeAlphas(0.63); // 50 と 75 の境目付近
  assert.equal(a["75"], 1);
  assert.ok(a["50"] > 0 && a["50"] < 1);
});

test("目: 驚きは見開き、笑顔は笑い目、笑いは笑い閉じ目", () => {
  assert.equal(eyeAlphas(1, "wide").wide, 1);
  assert.equal(eyeAlphas(1, "smile").smile, 1);
  assert.equal(eyeAlphas(1, "laugh").smileclosed, 1);
  assert.equal(eyeAlphas(0, "smile").smileclosed, 1);
  assert.equal(eyeAlphas(0, "smile").closed, 0);
});

test("口: 閉じていれば何も重ねない。笑顔・への字・母音", () => {
  const z = mouthAlphas(0, 0);
  for (const k of MOUTH_STATES) assert.equal(z[k], 0, k);
  assert.equal(mouthAlphas(0, 0.6).smile, 1);
  assert.equal(mouthAlphas(0, -0.6).frown, 1);
  assert.equal(mouthAlphas(0.6, 0).a, 1);
  assert.equal(mouthAlphas(0.6, 0, { funnel: 0.5 }).o, 1);
  assert.equal(mouthAlphas(0.3, 0, { pucker: 0.6 }).u, 1);
  assert.equal(mouthAlphas(1, 0, { mode: "laugh" }).big, 1);
});

test("眉: 普通は何も重ねない。上げる・怒り・困り", () => {
  const n = browAlphas(0, 0);
  for (const k of BROW_STATES) assert.equal(n[k], 0);
  assert.equal(browAlphas(0.6, 0).up, 1);
  assert.equal(browAlphas(-0.5, 0.5).angry, 1);
  assert.equal(browAlphas(0, -0.6).troubled, 1);
  assert.equal(browAlphas(-0.5, 0.5).up, 0);
});

test("パラメータ: すべての状態が返る（前の値が残らない）", () => {
  const vals = { ParamEyeLOpen: 1, ParamEyeROpen: 1, ParamMouthOpenY: 0, ParamMouthForm: 0, ParamBrowLY: 0, ParamBrowRY: 0 };
  const p = patchParams((k) => vals[k]);
  for (const side of ["L", "R"]) {
    for (const k of EYE_STATES) assert.equal(p[`ParamGP_eye${side}_${k}`], 0);
    for (const k of BROW_STATES) assert.equal(p[`ParamGP_brow${side}_${k}`], 0);
  }
  for (const k of MOUTH_STATES) assert.equal(p[`ParamGP_mouth_${k}`], 0);
  const w = patchParams((k) => vals[k], { expression: "surprised" });
  assert.equal(w.ParamGP_eyeL_wide, 1);
  assert.equal(patchParams((k) => vals[k]).ParamGP_eyeL_wide, 0);
});

test("フクロウのまばたき: 数秒おきに閉じて、すぐ開く", () => {
  const b = new OwlBlink(() => 0);
  assert.equal(b.value(0), 0);
  assert.equal(b.value(1999), 0);
  b.value(2000);
  assert.equal(b.value(2100), 1);
  assert.equal(b.value(2400), 0);
});
