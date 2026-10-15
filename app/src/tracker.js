// Web カメラ + MediaPipe Face Landmarker で、顔の向きと表情の係数を取り出す。
import { FaceLandmarker, FilesetResolver } from "@mediapipe/tasks-vision";
import { blendshapeMap, eulerFromMatrix } from "./mapping.js";

export class FaceTracker {
  constructor(video) {
    this.video = video;
    this.landmarker = null;
    this.lastVideoTime = -1;
  }

  async init(base = ".") {
    const fileset = await FilesetResolver.forVisionTasks(`${base}/vendor/wasm`);
    const make = (delegate) =>
      FaceLandmarker.createFromOptions(fileset, {
        baseOptions: { modelAssetPath: `${base}/vendor/face_landmarker.task`, delegate },
        runningMode: "VIDEO",
        numFaces: 1,
        outputFaceBlendshapes: true,
        outputFacialTransformationMatrixes: true,
      });
    try {
      this.landmarker = await make("GPU");
      this.delegate = "GPU";
    } catch (e) {
      console.warn("GPU で初期化できないため CPU を使います:", e);
      this.landmarker = await make("CPU");
      this.delegate = "CPU";
    }
  }

  async startCamera(deviceId) {
    const stream = await navigator.mediaDevices.getUserMedia({
      video: { width: { ideal: 640 }, height: { ideal: 480 }, frameRate: { ideal: 60 }, ...(deviceId ? { deviceId: { exact: deviceId } } : {}) },
      audio: false,
    });
    this.video.srcObject = stream;
    await this.video.play();
    return stream;
  }

  /** 新しいフレームがあれば { blend, angles } を返す。顔が写っていなければ { none: true }。無ければ null */
  detect(now = performance.now()) {
    const v = this.video;
    if (!this.landmarker || v.readyState < 2 || v.currentTime === this.lastVideoTime) return null;
    this.lastVideoTime = v.currentTime;
    const r = this.landmarker.detectForVideo(v, now);
    if (!r.faceBlendshapes?.length) return { none: true };
    const blend = blendshapeMap(r.faceBlendshapes[0].categories);
    const m = r.facialTransformationMatrixes?.[0];
    const angles = m ? eulerFromMatrix(m.data) : { yaw: 0, pitch: 0, roll: 0 };
    return { blend, angles };
  }
}
