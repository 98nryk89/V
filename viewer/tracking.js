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

  // MediaPipe uses a column-major 4x4 face transform. Translation and scale
  // must not masquerade as neck rotation. Euler angles are in camera degrees.
  function rotationFromMatrix(data) {
    if (!data || data.length !== 16 || !Array.from(data).every(Number.isFinite)) return null;
    if (Math.hypot(data[0],data[1],data[2]) < .5 || Math.hypot(data[6],data[10]) < .1) return null;
    const degrees = 180 / Math.PI;
    return {
      yaw: Math.atan2(-data[2], Math.hypot(data[0],data[1])) * degrees,
      pitch: Math.atan2(data[6],data[10]) * degrees,
      roll: Math.atan2(data[1],data[0]) * degrees,
    };
  }

  class Tracker {
    constructor(model, opts = {}) {
      this.m = model; this.opts = Object.assign({ invX: false, invY: false, invZ: false, smooth: 0.45, gainX: 1, gainY: 1, gainMove: 1, autoSmile: true }, opts);
      this.neutral = { yaw: 0, pitch: 0.45, x: null, y: null, eyeDist: null, rotation: null };
      this.raw = null; this.state = {}; this.running = false;
      this.smileHold = 0; this.smileRelease = 0; this.autoSmiling = false; this.lastSmileTime = null;
      this.mouthActive = false; this.mouthForm = 0; this.mouthCandidate = 0; this.mouthCandidateFrames = 0;
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

    setAutoSmile(enabled) {
      this.opts.autoSmile = !!enabled;
      this.smileHold = 0; this.smileRelease = 0; this.autoSmiling = false; this.lastSmileTime = null;
      if (enabled) this.m.setParam('Smile',0);
    }

    calibrate() {
      if (!this.raw) return;
      this.neutral = { ...this.raw };
      for (const key of ['BodyX','BodyY','AngleX','AngleY','AngleZ']) this.state[key] = 0;
      this.m.setParams({ BodyX: 0, BodyY: 0, AngleX: 0, AngleY: 0, AngleZ: 0 });
      this.setAutoSmile(this.opts.autoSmile);
    }

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
      if (!res.faceLandmarks || !res.faceLandmarks.length) {
        if (this.opts.autoSmile) this.setAutoSmile(true);
        return false;
      }
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
      const rotation = rotationFromMatrix(this.lastMatrix);
      const mouthWidth = Math.hypot(P(291).x-P(61).x,P(291).y-P(61).y) / eyeDist;
      const aspect = Math.hypot(P(14).x-P(13).x,P(14).y-P(13).y)/(mouthWidth*eyeDist || 1e-3);
      this.raw = { yaw, pitch, x: mid.x, y: mid.y, eyeDist, rotation, mouthWidth, lipAspect: aspect };
      if (this.neutral.lipAspect == null) this.neutral.lipAspect = aspect;
      if (this.neutral.mouthWidth == null) this.neutral.mouthWidth = mouthWidth;
      if (rotation && !this.neutral.rotation) this.neutral.rotation = { ...rotation };
      if (this.neutral.x == null) Object.assign(this.neutral, { x: mid.x, y: mid.y, eyeDist });
      const o = this.opts;
      // mirrored preview: user turning to their right (nose to image-left) => avatar turns to screen-right (+AngleX)
      let ax = -(yaw - this.neutral.yaw) * 13 * o.gainX;
      let ay = -(pitch - this.neutral.pitch) * 30 * o.gainY;
      let az = -roll * 0.18;
      if (rotation) {
        const n = this.neutral.rotation;
        // Mirror camera yaw, positive camera pitch looks down, camera roll
        // already has the mirrored screen tilt sign. Keep the specified caps.
        const delta = (a,b) => ((a-b+540)%360)-180;
        ax = -delta(rotation.yaw,n.yaw) * o.gainX;
        ay = -delta(rotation.pitch,n.pitch) * o.gainY;
        az = delta(rotation.roll,n.roll);
      }
      if (o.invX) ax = -ax; if (o.invY) ay = -ay; if (o.invZ) az = -az;
      // Translation comes from face position, independently of nose/eye angles.
      const bx = -(mid.x - this.neutral.x) / this.neutral.eyeDist * 1.5 * o.gainMove * (o.invX ? -1 : 1);
      const by = (mid.y - this.neutral.y) / this.neutral.eyeDist * 1.5 * o.gainMove * (o.invY ? -1 : 1);
      const t = {
        AngleX: clamp(ax, -5, 5), AngleY: clamp(ay, -10, 5), AngleZ: clamp(az, -5, 5),
        BodyX: clamp(bx, -1, 1), BodyY: clamp(by, -1, 1),
      };
      const bs = {};
      if (res.faceBlendshapes && res.faceBlendshapes[0]) for (const c of res.faceBlendshapes[0].categories) bs[c.categoryName] = c.score;
      const g = k => bs[k] || 0;
      if (o.autoSmile) {
        const dt = this.lastSmileTime != null && tsMs>this.lastSmileTime ? Math.min((tsMs-this.lastSmileTime)/1000,.1) : 1/30;
        this.lastSmileTime = tsMs;
        const score = Math.min(g('mouthSmileLeft'),g('mouthSmileRight'));
        if (this.m.params.Surprise>.5) {
          this.autoSmiling = false; this.smileHold = 0; this.smileRelease = 0;
        } else if (!this.autoSmiling) {
          this.smileHold = score>.86 ? this.smileHold+dt : 0;
          if (this.smileHold>=.6) { this.autoSmiling = true; this.smileRelease = 0; }
        } else {
          this.smileRelease = score<.55 ? this.smileRelease+dt : 0;
          if (this.smileRelease>=.35) { this.autoSmiling = false; this.smileHold = 0; }
        }
        this.m.setParam('Smile',this.autoSmiling ? 1 : 0);
      }
      // mirror: user's left eye shows on screen-left -> EyeL
      const open = b => clamp(1 - (b - 0.15) / 0.5, 0, 1);
      t.EyeLOpen = open(g('eyeBlinkLeft')); t.EyeROpen = open(g('eyeBlinkRight'));
      // A dead zone and separate release threshold reject small lip motion.
      // Shape is discrete; only the opening amount is smoothed.
      const jaw = g('jawOpen'), stretch = (g('mouthStretchLeft')+g('mouthStretchRight'))/2;
      const widthRatio = mouthWidth/(this.neutral.mouthWidth || mouthWidth || 1);
      const lipDelta = Math.max(0, aspect-(this.neutral.lipAspect || 0));
      if (this.mouthActive) {
        if (jaw<.14 && lipDelta<.07) this.mouthActive = false;
      } else if (jaw>.22 || lipDelta>.11) this.mouthActive = true;
      const wide = stretch>.40 || widthRatio>1.15;
      const spread = stretch>.25 || widthRatio>1.08;
      const tall = jaw>.56 || aspect>.36;
      let desired = tall ? 0 : (wide && aspect<.20 && jaw<.38 ? 1 :
        (spread && (jaw>.28 || lipDelta>.12) ? 2 :
          (stretch<.18 && widthRatio<1.04 ? 0 : this.mouthForm)));
      if (!this.mouthActive) desired = this.mouthForm;
      if (desired!==this.mouthCandidate) { this.mouthCandidate = desired; this.mouthCandidateFrames = 1; }
      else this.mouthCandidateFrames++;
      if (this.mouthCandidateFrames>=3) this.mouthForm = desired;
      this.m.setParam('MouthForm',this.mouthForm);
      const baseOpen = this.mouthActive ? clamp((jaw-.16)/(.60-.16),0,1) : 0;
      const lipOpen = this.mouthActive ? clamp((lipDelta-.07)/.23,0,1) : 0;
      t.MouthOpen = this.mouthForm===0 ? baseOpen : Math.max(baseOpen,lipOpen);
      t.EyeBallX = clamp(((g('eyeLookOutRight') + g('eyeLookInLeft')) - (g('eyeLookOutLeft') + g('eyeLookInRight'))) / 1.2, -1, 1);
      t.EyeBallY = clamp(((g('eyeLookUpLeft') + g('eyeLookUpRight')) - (g('eyeLookDownLeft') + g('eyeLookDownRight'))) / 1.2, -1, 1);
      const k = 1 - o.smooth;
      for (const key in t) {
        const prev = this.state[key] != null ? this.state[key] : (key === 'MouthOpen' ? 0 : t[key]);
        // blinks should be fast: no smoothing for eye open params
        const kk = key === 'MouthOpen' ? 0.45 : ((key === 'EyeLOpen' || key === 'EyeROpen') ? 1 : k);
        this.state[key] = prev + (t[key] - prev) * kk;
        if (key === 'MouthOpen') {
          if (t[key] === 0 && this.state[key] < 0.005) this.state[key] = 0;
          if (t[key] === 1 && this.state[key] > 0.995) this.state[key] = 1;
        }
        this.m.setParam(key, this.state[key]);
      }
      return true;
    }
  }
  global.L2DTracker = Tracker;
})(window);
