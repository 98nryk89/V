/* Webcam face tracking -> model params, using MediaPipe Face Landmarker (loaded from CDN in the user's browser).
 * Verified in the headless dev container with a closed-loop test (tools/track_test.py): the model is rendered at known
 * poses, mirrored like a webcam selfie, fed through MediaPipe, and the recovered params are compared with the input.
 * A real camera was NOT available there; the invert checkboxes and the "calibrate" button remain for per-setup tuning.
 */
(function (global) {
  'use strict';
  const OVR = global.L2D_MP || {};      // tests / offline use can point these at local copies
  const CDN = OVR.cdn || 'https://cdn.jsdelivr.net/npm/@mediapipe/tasks-vision@0.10.14';
  const MODEL = OVR.model || 'https://storage.googleapis.com/mediapipe-models/face_landmarker/face_landmarker/float16/1/face_landmarker.task';
  const clamp = (v, a, b) => Math.max(a, Math.min(b, v));

  class Tracker {
    constructor(model, opts = {}) {
      this.m = model; this.opts = Object.assign({ invX: false, invY: false, invZ: false, smooth: 0.45, gainX: 1, gainY: 1 }, opts);
      this.neutral = { yaw: 0, pitch: 0.45 };
      this.raw = null; this.state = {}; this.running = false;
    }

    async load(delegate = 'GPU') {
      const vision = await import(CDN + '/vision_bundle.mjs');
      const fileset = await vision.FilesetResolver.forVisionTasks(CDN + '/wasm');
      this.landmarker = await vision.FaceLandmarker.createFromOptions(fileset, {
        baseOptions: { modelAssetPath: MODEL, delegate },
        outputFaceBlendshapes: true, outputFacialTransformationMatrixes: true, runningMode: 'VIDEO', numFaces: 1,
      });
    }

    async start(video, onStatus = () => {}) {
      onStatus('カメラを起動中…');
      const stream = await navigator.mediaDevices.getUserMedia({ video: { width: 640, height: 480, facingMode: 'user' }, audio: false });
      video.srcObject = stream; await video.play();
      onStatus('MediaPipe を読み込み中…');
      await this.load();
      this.video = video; this.running = true; this._lastT = -1; this._onStatus = onStatus; this._miss = 0;
      onStatus('トラッキング中');
      const loop = () => { if (!this.running) return; this._step(); requestAnimationFrame(loop); };
      loop();
    }

    stop() {
      this.running = false;
      if (this.video && this.video.srcObject) this.video.srcObject.getTracks().forEach(t => t.stop());
    }

    calibrate() { if (this.raw) { this.neutral = { yaw: this.raw.yaw, pitch: this.raw.pitch }; } }

    _step() {
      const v = this.video; if (!v || v.readyState < 2 || v.currentTime === this._lastT) return;
      this._lastT = v.currentTime;
      const ok = this.feed(v, performance.now());
      if (!ok) { if (++this._miss === 30 && this._onStatus) this._onStatus('顔が検出できません。明るさ・カメラの向きを確認してください'); }
      else { if (this._miss >= 30 && this._onStatus) this._onStatus('トラッキング中'); this._miss = 0; }
    }

    // process one frame (video element, canvas or image) taken by an UN-mirrored camera
    feed(source, tsMs) {
      const res = this.landmarker.detectForVideo(source, tsMs);
      if (!res.faceLandmarks || !res.faceLandmarks.length) return false;
      const L = res.faceLandmarks[0];
      this.lastMatrix = res.facialTransformationMatrixes && res.facialTransformationMatrixes[0] ? Array.from(res.facialTransformationMatrixes[0].data) : null;
      const P = i => L[i];
      // raw (un-mirrored) camera image: landmark 33 = user's right eye (image-left), 263 = user's left eye (image-right)
      const eR = P(33), eL = P(263), nose = P(1), chin = P(152), mouthC = [(P(61).x + P(291).x) / 2, (P(61).y + P(291).y) / 2];
      const mid = { x: (eR.x + eL.x) / 2, y: (eR.y + eL.y) / 2 };
      const eyeDist = Math.hypot(eL.x - eR.x, eL.y - eR.y) || 1e-3;
      // measure in the head's own frame (x along the eye line) so head tilt does not leak into turn/nod
      const ex = (eL.x - eR.x) / eyeDist, ey = (eL.y - eR.y) / eyeDist;       // unit vector along the eyes
      const nx = nose.x - mid.x, ny = nose.y - mid.y, cx = chin.x - mid.x, cy = chin.y - mid.y;
      const yaw = (nx * ex + ny * ey) / eyeDist;                              // + = nose toward the user's left eye (image-right)
      const downNose = -nx * ey + ny * ex, downChin = -cx * ey + cy * ex;     // components along "down" in the head frame
      const pitch = downNose / (downChin || 1e-3);                            // larger = looking down
      const roll = Math.atan2(eL.y - eR.y, eL.x - eR.x) * 180 / Math.PI;
      this.raw = { yaw, pitch };
      const o = this.opts;
      // mirrored preview: user turning to their right (nose to image-left) => avatar turns to screen-right (+AngleX)
      let ax = -(yaw - this.neutral.yaw) * 13 * o.gainX;
      let ay = -(pitch - this.neutral.pitch) * 30 * o.gainY;
      let az = -roll * 0.18;
      if (o.invX) ax = -ax; if (o.invY) ay = -ay; if (o.invZ) az = -az;
      const t = {
        AngleX: clamp(ax, -5, 5), AngleY: clamp(ay, -10, 5), AngleZ: clamp(az, -5, 5),
      };
      const bs = {};
      if (res.faceBlendshapes && res.faceBlendshapes[0]) for (const c of res.faceBlendshapes[0].categories) bs[c.categoryName] = c.score;
      const g = k => bs[k] || 0;
      // mirror: user's left eye shows on screen-left -> EyeL
      const open = b => clamp(1 - (b - 0.15) / 0.5, 0, 1);
      t.EyeLOpen = open(g('eyeBlinkLeft')); t.EyeROpen = open(g('eyeBlinkRight'));
      t.MouthOpen = clamp((g('jawOpen') - 0.05) / 0.45, 0, 1);
      Object.assign(t, vowelWeights(bs));
      t.MouthOpen = 0;                // the vowel shapes replace the generic opening
      t.Smile = clamp(((g('mouthSmileLeft') + g('mouthSmileRight')) / 2 - 0.2) / 0.5, 0, 1);
      t.EyeBallX = clamp(((g('eyeLookOutRight') + g('eyeLookInLeft')) - (g('eyeLookOutLeft') + g('eyeLookInRight'))) / 1.2, -1, 1);
      t.EyeBallY = clamp(((g('eyeLookUpLeft') + g('eyeLookUpRight')) - (g('eyeLookDownLeft') + g('eyeLookDownRight'))) / 1.2, -1, 1);
      const k = 1 - o.smooth;
      for (const key in t) {
        const prev = this.state[key] != null ? this.state[key] : t[key];
        // blinks should be fast: no smoothing for eye open params
        const kk = (key === 'EyeLOpen' || key === 'EyeROpen') ? 0.85 : k;
        this.state[key] = prev + (t[key] - prev) * kk;
        this.m.setParam(key, this.state[key]);
      }
      return true;
    }
  }
  // Vowel classification from MediaPipe blendshapes -> weights for あ/い/う/え/お (sum <= 1, 0 when the mouth is closed).
  // jaw = jawOpen, fun = mouthFunnel, puc = mouthPucker, str = mouthStretch (avg L/R), smi = mouthSmile (avg L/R)
  function vowelWeights(bs, opts = {}) {
    const g = k => bs[k] || 0, cl = (v, a, b) => Math.max(0, Math.min(1, (v - a) / (b - a)));
    const jaw = g('jawOpen'), fun = g('mouthFunnel'), puc = g('mouthPucker');
    const str = (g('mouthStretchLeft') + g('mouthStretchRight')) / 2, smi = (g('mouthSmileLeft') + g('mouthSmileRight')) / 2;
    const wide = Math.max(str, smi * 0.8);                       // lateral stretch
    const round = Math.max(fun, puc);                            // lips rounded forward
    const amp = Math.max(cl(jaw, 0.06, 0.3), cl(round, 0.15, 0.45), cl(wide, 0.2, 0.5) * 0.8);   // how "open" the mouth is at all
    const raw = {
      A: cl(jaw, 0.25, 0.55) * (1 - cl(round, 0.2, 0.5)) * (1 - cl(wide, 0.3, 0.6)),
      I: cl(wide, 0.25, 0.55) * (1 - cl(jaw, 0.25, 0.55)) * (1 - cl(round, 0.2, 0.5)),
      U: cl(puc, 0.2, 0.5) * (1 - cl(jaw, 0.3, 0.6)),
      E: cl(wide, 0.2, 0.5) * cl(jaw, 0.1, 0.35) * (1 - cl(round, 0.2, 0.5)),
      O: cl(fun, 0.2, 0.5) * cl(jaw, 0.08, 0.3) * (1 - cl(puc, 0.4, 0.7)),
    };
    let sum = 0; for (const k in raw) sum += raw[k];
    const out = {};
    for (const k in raw) out['Vowel' + k] = sum > 1e-3 ? (raw[k] / Math.max(sum, 1)) * amp : 0;
    return out;
  }
  Tracker.vowelWeights = vowelWeights;
  global.L2DTracker = Tracker;
})(window);
