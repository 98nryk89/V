// 耳飾り・リボンの独立した揺れ。吊り下げた振り子が、頭の動きに押されて遅れて揺れる。
const clamp = (v, lo, hi) => Math.min(hi, Math.max(lo, v));

export class Pendulum {
  /**
   * freq: 固有振動数 (Hz)、zeta: 減衰比、kick: 頭の角加速度に対する感度、
   * hang: 頭が傾いたとき、垂れ下がる向きを保とうとする割合、limit: 振れの上限（度）
   */
  constructor({ freq = 2.0, zeta = 0.18, kick = 0.15, hang = 0.5, limit = 26 } = {}) {
    Object.assign(this, { freq, zeta, kick, hang, limit });
    this.reset();
  }
  reset() { this.x = 0; this.v = 0; this.prev = null; }
  /** headX: 頭の横の向き（度、右が正）、roll: 頭の傾き（度、右が正）、now: ms。振れの角度（度）を返す。 */
  update(headX, roll, now) {
    const p = this.prev;
    this.prev = { headX, now, vel: p ? p.vel : 0 };
    if (!p) return 0;
    const dt = clamp((now - p.now) / 1000, 0.001, 0.05);
    const vel = (headX - p.headX) / dt;
    const acc = clamp((vel - p.vel) / dt, -4000, 4000);
    this.prev.vel = vel;
    const w = 2 * Math.PI * this.freq;
    const eq = -roll * this.hang;
    const a = -w * w * (this.x - eq) - 2 * this.zeta * w * this.v - this.kick * acc * w;
    this.v += a * dt;
    this.x = clamp(this.x + this.v * dt, -this.limit, this.limit);
    return this.x;
  }
}

/** 耳飾り（左右）とリボンの振り子をまとめて持つ。 */
export class Swing {
  constructor() {
    this.earL = new Pendulum({ freq: 2.3, zeta: 0.2 });
    this.earR = new Pendulum({ freq: 2.3, zeta: 0.2 });
    this.ribbon = new Pendulum({ freq: 1.5, zeta: 0.3, kick: 0.12 });
  }
  /** head: { ParamAngleX, ParamAngleZ } → モデルのパラメータ */
  update(head, now) {
    const x = head?.ParamAngleX ?? 0, z = head?.ParamAngleZ ?? 0;
    return {
      ParamEarL: this.earL.update(x, z, now),
      ParamEarR: this.earR.update(x, z, now),
      ParamRibbon: this.ribbon.update(x, z, now),
    };
  }
}
