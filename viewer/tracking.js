/* Webcam face tracking -> model params, using MediaPipe Face Landmarker (loaded from CDN in the user's browser).
 * NOTE: this file could not be exercised in the headless dev container (no camera / no CDN access);
 * signs are therefore exposed as invert checkboxes in the UI and a "calibrate" button sets the neutral pose.
 */
(function (global) {
  'use strict';
  const CDN = 'https://cdn.jsdelivr.net/npm/@mediapipe/tasks-vision@0.10.14';
  const MODEL = 'https://storage.googleapis.com/mediapipe-models/face_landmarker/face_landmarker/float16/1/face_landmarker.task';
  const clamp = (v, a, b) => Math.max(a, Math.min(b, v));

  class Tracker {
    constructor(model, opts = {}) {
      this.m = model; this.opts = Object.assign({ invX: false, invY: false, invZ: false, smooth: 0.45, gainX: 1, gainY: 1 }, opts);
      this.neutral = { yaw: 0, pitch: 0.45 };
      this.raw = null; this.state = {}; this.running = false;
    }

    async start(video, onStatus = () => {}) {
      onStatus('カメラを起動中…');
      const stream = await navigator.mediaDevices.getUserMedia({ video: { width: 640, height: 480, facingMode: 'user' }, audio: false });
      video.srcObject = stream; await video.play();
      onStatus('MediaPipe を読み込み中…');
      const vision = await import(CDN + '/vision_bundle.mjs');
      const fileset = await vision.FilesetResolver.forVisionTasks(CDN + '/wasm');
      this.landmarker = await vision.FaceLandmarker.createFromOptions(fileset, {
        baseOptions: { modelAssetPath: MODEL, delegate: 'GPU' },
        outputFaceBlendshapes: true, runningMode: 'VIDEO', numFaces: 1,
      });
      this.video = video; this.running = true; this._lastT = -1;
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
      const res = this.landmarker.detectForVideo(v, performance.now());
      if (!res.faceLandmarks || !res.faceLandmarks.length) return;
      const L = res.faceLandmarks[0];
      const P = i => L[i];
      // raw (un-mirrored) camera image: landmark 33 = user's right eye (image-left), 263 = user's left eye (image-right)
      const eR = P(33), eL = P(263), nose = P(1), chin = P(152), mouthC = [(P(61).x + P(291).x) / 2, (P(61).y + P(291).y) / 2];
      const mid = { x: (eR.x + eL.x) / 2, y: (eR.y + eL.y) / 2 };
      const eyeDist = Math.hypot(eL.x - eR.x, eL.y - eR.y) || 1e-3;
      const yaw = (nose.x - mid.x) / eyeDist;                       // + = nose toward image-right
      const pitch = (nose.y - mid.y) / ((chin.y - mid.y) || 1e-3);  // larger = looking down
      const roll = Math.atan2(eL.y - eR.y, eL.x - eR.x) * 180 / Math.PI;
      this.raw = { yaw, pitch };
      const o = this.opts;
      // mirrored preview: user turning to their right (nose to image-left) => avatar turns to screen-right (+AngleX)
      let ax = -(yaw - this.neutral.yaw) * 18 * o.gainX;
      let ay = -(pitch - this.neutral.pitch) * 30 * o.gainY;
      let az = -roll * 0.25;
      if (o.invX) ax = -ax; if (o.invY) ay = -ay; if (o.invZ) az = -az;
      const t = {
        AngleX: clamp(ax, -7, 7), AngleY: clamp(ay, -7, 7), AngleZ: clamp(az, -7, 7),
      };
      const bs = {};
      if (res.faceBlendshapes && res.faceBlendshapes[0]) for (const c of res.faceBlendshapes[0].categories) bs[c.categoryName] = c.score;
      const g = k => bs[k] || 0;
      // mirror: user's left eye shows on screen-left -> EyeL
      const open = b => clamp(1 - (b - 0.15) / 0.5, 0, 1);
      t.EyeLOpen = open(g('eyeBlinkLeft')); t.EyeROpen = open(g('eyeBlinkRight'));
      t.MouthOpen = clamp((g('jawOpen') - 0.05) / 0.45, 0, 1);
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
    }
  }
  global.L2DTracker = Tracker;
})(window);
