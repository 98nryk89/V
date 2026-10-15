import test from "node:test";
import assert from "node:assert/strict";
import { eyeWeights, mouthWeights, patchParams, OwlBlink } from "../src/patches.js";

const near = (a, b, e = 1e-9) => Math.abs(a - b) < e;

test("目: 開き 1 は元の目、0 は閉じ目、0.5 は半目だけ", () => {
  assert.equal(eyeWeights(1).base, 1);
  assert.equal(eyeWeights(0).closed, 1);
  const w = eyeWeights(0.5);
  assert.equal(w["50"], 1);
  assert.equal(w["25"] + w["75"] + w.closed + w.base, 0);
});

test("目: 境目の近くだけ 2 つが混ざり、合計は 1", () => {
  const w = eyeWeights(0.375);
  assert.ok(w["25"] > 0 && w["50"] > 0);
  assert.ok(near(Object.values(w).reduce((a, b) => a + b, 0), 1));
  const v = eyeWeights(0.3);
  assert.equal(v["25"], 1);
});

test("目: 驚きは見開き、笑いは笑いの閉じ目", () => {
  assert.equal(eyeWeights(1, "wide").wide, 1);
  assert.equal(eyeWeights(0, "laugh").smileclosed, 1);
  assert.equal(eyeWeights(1, "smile").smile, 1);
});

test("口: 閉じ・笑顔・への字・母音", () => {
  assert.equal(mouthWeights(0, 0).base, 1);
  assert.equal(mouthWeights(0, 0.6).smile, 1);
  assert.equal(mouthWeights(0, -0.6).frown, 1);
  assert.equal(mouthWeights(0.6, 0).a, 1);
  assert.equal(mouthWeights(0.6, 0, { funnel: 0.5 }).o, 1);
  assert.equal(mouthWeights(0.3, 0, { pucker: 0.6 }).u, 1);
  assert.equal(mouthWeights(1, 0, { mode: "laugh" }).big, 1);
});

test("パラメータ: 元の目は隠し度で消え、差分と足して 1", () => {
  const vals = { ParamEyeLOpen: 0.5, ParamEyeROpen: 1, ParamMouthOpenY: 0, ParamMouthForm: 0 };
  const p = patchParams((k) => vals[k]);
  assert.equal(p.ParamGP_eyeL_50, 1);
  assert.equal(p.ParamGP_eyeL_hide, 1);
  assert.equal(p.ParamGP_eyeR_hide, 0);
  assert.equal(p.ParamGP_mouth_hide, 0);
});

test("フクロウのまばたき: 数秒おきに閉じて、すぐ開く", () => {
  const b = new OwlBlink(() => 0);
  assert.equal(b.value(0), 0);
  assert.equal(b.value(1999), 0);
  b.value(2000);
  assert.equal(b.value(2100), 1);
  assert.equal(b.value(2400), 0);
});
