import test from "node:test";
import assert from "node:assert/strict";
import { AngleCalibration, Smoother, bodyFromHead, combine, eulerFromMatrix, faceParams } from "../src/mapping.js";

const I = [1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1];

test("単位行列では向きがゼロ", () => {
  const e = eulerFromMatrix(I);
  assert.ok(Math.abs(e.yaw) < 1e-9 && Math.abs(e.pitch) < 1e-9 && Math.abs(e.roll) < 1e-9);
});

test("Y 軸まわりの回転が yaw になる", () => {
  const a = (30 * Math.PI) / 180;
  // 列優先: R(0,2)=sin, R(2,2)=cos
  const m = [Math.cos(a), 0, -Math.sin(a), 0, 0, 1, 0, 0, Math.sin(a), 0, Math.cos(a), 0, 0, 0, 0, 1];
  assert.ok(Math.abs(eulerFromMatrix(m).yaw - 30) < 1e-6);
});

test("まばたき: 0.18 以下は開、0.7 以上は閉", () => {
  assert.equal(faceParams({ eyeBlinkLeft: 0.1 }).ParamEyeLOpen, 1);
  assert.equal(faceParams({ eyeBlinkLeft: 0.9 }).ParamEyeLOpen, 0);
  const half = faceParams({ eyeBlinkLeft: 0.44 }).ParamEyeLOpen;
  assert.ok(half > 0.3 && half < 0.7);
});

test("左目だけ閉じると L だけ閉じる。swapLR で入れ替わる", () => {
  const b = { eyeBlinkLeft: 1, eyeBlinkRight: 0 };
  const p = faceParams(b);
  assert.equal(p.ParamEyeLOpen, 0);
  assert.equal(p.ParamEyeROpen, 1);
  const s = faceParams(b, { swapLR: true });
  assert.equal(s.ParamEyeLOpen, 1);
  assert.equal(s.ParamEyeROpen, 0);
});

test("口と笑顔", () => {
  assert.equal(faceParams({ jawOpen: 0 }).ParamMouthOpenY, 0);
  assert.ok(faceParams({ jawOpen: 0.6 }).ParamMouthOpenY > 0.95);
  assert.ok(faceParams({ mouthSmileLeft: 0.5, mouthSmileRight: 0.5 }).ParamMouthForm > 0.9);
  assert.ok(faceParams({ mouthFrownLeft: 0.5, mouthFrownRight: 0.5 }).ParamMouthForm < -0.9);
});

test("ニュートラルの基準を引くと、その表情が 0 になる", () => {
  const b = { mouthSmileLeft: 0.3, mouthSmileRight: 0.3, browInnerUp: 0.2 };
  const p = faceParams(b, { baseline: b });
  assert.equal(p.ParamMouthForm, 0);
  assert.equal(p.ParamBrowLY, 0);
});

test("視線: 本人が右を見ると X が正", () => {
  const p = faceParams({ eyeLookOutRight: 0.6, eyeLookInLeft: 0.6 });
  assert.ok(p.ParamEyeBallX > 0.5);
  const q = faceParams({ eyeLookOutLeft: 0.6, eyeLookInRight: 0.6 });
  assert.ok(q.ParamEyeBallX < -0.5);
});

test("キャリブレーション: 符号と倍率が決まり、中心は 0 になる", () => {
  const c = new AngleCalibration();
  c.setNeutral([{ yaw: 5, pitch: -3, roll: 1 }, { yaw: 5, pitch: -3, roll: 1 }]);
  assert.deepEqual(c.apply({ yaw: 5, pitch: -3, roll: 1 }), { ParamAngleX: 0, ParamAngleY: 0, ParamAngleZ: 0 });
  // 右を向いたとき、生の yaw は減る（符号が反転するケース）
  assert.ok(c.setAxis("yaw", [{ yaw: -10, pitch: -3, roll: 1 }], 24));
  assert.equal(c.sign.yaw, -1);
  const a = c.apply({ yaw: -10, pitch: -3, roll: 1 });
  assert.ok(Math.abs(a.ParamAngleX - 24) < 1e-6);
  // ほとんど動かないと失敗する
  assert.equal(c.setAxis("pitch", [{ yaw: 5, pitch: -2, roll: 1 }]), false);
});

test("角度は ±30 に収まる", () => {
  const c = new AngleCalibration();
  assert.equal(c.apply({ yaw: 100, pitch: 0, roll: 0 }).ParamAngleX, 30);
});

test("平滑化: 最初は値そのもの、その後は近づく", () => {
  const s = new Smoother({ a: 0.5 });
  assert.equal(s.update({ a: 1 }).a, 1);
  assert.equal(s.update({ a: 0 }).a, 0.5);
});

test("体は頭より小さく動く", () => {
  const b = bodyFromHead({ ParamAngleX: 30, ParamAngleY: -30, ParamAngleZ: 30 });
  assert.ok(Math.abs(b.ParamBodyAngleX) < 10 && Math.abs(b.ParamBodyAngleX) > 0);
});

test("合成: 表情の目の細まりとまばたき、口は大きい方", () => {
  const tracked = { ParamEyeLOpen: 1, ParamEyeROpen: 0, ParamMouthOpenY: 0.2, ParamMouthForm: 0.5, ParamBrowLY: 0, ParamBrowRY: 0, ParamBrowLAngle: 0, ParamBrowRAngle: 0 };
  const cur = { ParamEyeLOpen: 0.4, ParamEyeROpen: 1, ParamMouthOpenY: 0.9, ParamMouthForm: 1 };
  const m = combine(cur, tracked, true);
  assert.equal(m.ParamEyeLOpen, 0.4);
  assert.equal(m.ParamEyeROpen, 0);
  assert.equal(m.ParamMouthOpenY, 0.9);
  assert.equal(m.ParamMouthForm, 1); // 表情 1 + 追跡 0.5*0.5 → 上限 1
  const n = combine(cur, tracked, false);
  assert.equal(n.ParamMouthForm, 0.5); // 表情が無いときは追跡だけ
  assert.equal(n.ParamEyeLOpen, 1); // 待機モーションの自動まばたき（cur の 0.4）は使わない
  assert.equal(n.ParamEyeROpen, 0);
});
