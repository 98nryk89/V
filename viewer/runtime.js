/* live2d_ai runtime: renders a rig.json (parts = textured meshes + parametric effects + physics) with WebGL2.
 *
 * Effects (applied in order per part, on vertex positions in source-image pixels):
 *   head3d    pseudo-3D head turn: vertices lie on a sphere around `center`; yaw/pitch/roll params rotate it
 *   translate param -> dx,dy (piecewise-linear `map` of [p,dx,dy])
 *   rotate    param -> degrees about `pivot`; optional per-vertex `weight` (bend for hair etc.)
 *   scale     param -> sx,sy about `pivot` (blink, breathing)
 *   opacity   param -> alpha
 * Weights: {mode:'y'|'x'|'dist', from,to | pivot,len, pow}
 */
(function (global) {
  'use strict';
  const clamp = (v, a, b) => Math.max(a, Math.min(b, v));
  const DEG = Math.PI / 180;

  function mapLinear(map, p) {            // map: [[p, v0, v1..], ...] sorted by p
    if (p <= map[0][0]) return map[0].slice(1);
    const n = map.length;
    if (p >= map[n - 1][0]) return map[n - 1].slice(1);
    for (let i = 0; i < n - 1; i++) {
      const a = map[i], b = map[i + 1];
      if (p >= a[0] && p <= b[0]) {
        const t = (p - a[0]) / (b[0] - a[0] || 1);
        const out = [];
        for (let k = 1; k < a.length; k++) out.push(a[k] + (b[k] - a[k]) * t);
        return out;
      }
    }
    return map[0].slice(1);
  }

  function weightOf(w, x, y) {
    if (!w) return 1;
    let t;
    if (w.mode === 'y') t = (y - w.from) / (w.to - w.from);
    else if (w.mode === 'x') t = (x - w.from) / (w.to - w.from);
    else if (w.mode === 'dist') t = Math.hypot(x - w.pivot[0], y - w.pivot[1]) / w.len;
    else t = 1;
    t = clamp(t, 0, 1);
    if (w.pow) t = Math.pow(t, w.pow);
    return t;
  }

  const VS = `#version 300 es
in vec2 aPos; in vec2 aUV;
uniform vec2 uScale; uniform vec2 uOff;
out vec2 vUV;
void main(){ vec2 p = aPos*uScale + uOff; gl_Position = vec4(p.x, -p.y, 0.0, 1.0); vUV = aUV; }`;
  const FS = `#version 300 es
precision highp float;
in vec2 vUV; uniform sampler2D uTex; uniform float uOpacity; uniform float uCut;
out vec4 o;
void main(){ vec4 c = texture(uTex, vUV); if (uCut > 0.0 && c.a < uCut) discard; o = c * uOpacity; }`;

  class Model {
    constructor(canvas, rig, base, opts = {}) {
      this.canvas = canvas; this.rig = rig; this.base = base; this.opts = opts;
      const gl = this.gl = canvas.getContext('webgl2', { antialias: true, alpha: true, stencil: true, premultipliedAlpha: true, preserveDrawingBuffer: !!opts.preserve });
      if (!gl) throw new Error('WebGL2 not available');
      this.prog = this._program(VS, FS);
      this.loc = {
        aPos: gl.getAttribLocation(this.prog, 'aPos'), aUV: gl.getAttribLocation(this.prog, 'aUV'),
        uScale: gl.getUniformLocation(this.prog, 'uScale'), uOff: gl.getUniformLocation(this.prog, 'uOff'),
        uTex: gl.getUniformLocation(this.prog, 'uTex'), uOpacity: gl.getUniformLocation(this.prog, 'uOpacity'),
        uCut: gl.getUniformLocation(this.prog, 'uCut'),
      };
      this.params = {}; this.paramDefs = {};
      for (const p of rig.params) { this.params[p.id] = p.default; this.paramDefs[p.id] = p; }
      this.parts = rig.parts.slice().sort((a, b) => a.z - b.z);
      this.byId = {}; for (const p of this.parts) this.byId[p.id] = p;
      this.phys = (rig.physics || []).map(d => ({ d, a: 0, av: 0, prevIn: 0, prevInV: 0 }));
      this.time = 0; this.auto = { blink: true, breath: true, idle: true, physics: true };
      this.blink = { next: 2.5, t: -1 };
      this.wire = false;
    }

    _program(vs, fs) {
      const gl = this.gl;
      const mk = (t, s) => { const sh = gl.createShader(t); gl.shaderSource(sh, s); gl.compileShader(sh); if (!gl.getShaderParameter(sh, gl.COMPILE_STATUS)) throw new Error(gl.getShaderInfoLog(sh)); return sh; };
      const p = gl.createProgram(); gl.attachShader(p, mk(gl.VERTEX_SHADER, vs)); gl.attachShader(p, mk(gl.FRAGMENT_SHADER, fs)); gl.linkProgram(p);
      if (!gl.getProgramParameter(p, gl.LINK_STATUS)) throw new Error(gl.getProgramInfoLog(p));
      return p;
    }

    async load() {
      const gl = this.gl;
      await Promise.all(this.parts.map(async part => {
        const img = new Image(); img.src = this.base + part.tex;
        await img.decode();
        const tex = gl.createTexture(); gl.bindTexture(gl.TEXTURE_2D, tex);
        gl.pixelStorei(gl.UNPACK_PREMULTIPLY_ALPHA_WEBGL, true);
        gl.texImage2D(gl.TEXTURE_2D, 0, gl.RGBA, gl.RGBA, gl.UNSIGNED_BYTE, img);
        gl.generateMipmap(gl.TEXTURE_2D);
        gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MIN_FILTER, gl.LINEAR_MIPMAP_LINEAR);
        gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MAG_FILTER, gl.LINEAR);
        gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_S, gl.CLAMP_TO_EDGE);
        gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_T, gl.CLAMP_TO_EDGE);
        part._tex = tex;
        part._rest = Float32Array.from(part.mesh.verts);
        part._pos = new Float32Array(part._rest.length);
        part._uv = Float32Array.from(part.mesh.uvs);
        if (part.mesh.z) { part._z = Float32Array.from(part.mesh.z); let sz = 0; for (const v of part._z) sz += v; part._zmean = sz / part._z.length; }
        part._idx = Uint16Array.from(part.mesh.tris);
        part._vbo = gl.createBuffer(); part._ubo = gl.createBuffer(); part._ibo = gl.createBuffer();
        gl.bindBuffer(gl.ARRAY_BUFFER, part._ubo); gl.bufferData(gl.ARRAY_BUFFER, part._uv, gl.STATIC_DRAW);
        gl.bindBuffer(gl.ELEMENT_ARRAY_BUFFER, part._ibo); gl.bufferData(gl.ELEMENT_ARRAY_BUFFER, part._idx, gl.STATIC_DRAW);
        gl.bindBuffer(gl.ARRAY_BUFFER, part._vbo); gl.bufferData(gl.ARRAY_BUFFER, part._pos.byteLength, gl.DYNAMIC_DRAW);
        part._vao = gl.createVertexArray(); gl.bindVertexArray(part._vao);
        gl.bindBuffer(gl.ARRAY_BUFFER, part._vbo); gl.enableVertexAttribArray(this.loc.aPos); gl.vertexAttribPointer(this.loc.aPos, 2, gl.FLOAT, false, 0, 0);
        gl.bindBuffer(gl.ARRAY_BUFFER, part._ubo); gl.enableVertexAttribArray(this.loc.aUV); gl.vertexAttribPointer(this.loc.aUV, 2, gl.FLOAT, false, 0, 0);
        gl.bindBuffer(gl.ELEMENT_ARRAY_BUFFER, part._ibo);
        gl.bindVertexArray(null);
      }));
      return this;
    }

    setParam(id, v) {
      const d = this.paramDefs[id]; if (!d) return;
      this.params[id] = clamp(v, d.min, d.max);
    }
    setParams(o) { for (const k in o) this.setParam(k, o[k]); }
    reset() { for (const p of this.rig.params) this.params[p.id] = p.default; for (const s of this.phys) { s.a = 0; s.av = 0; } }

    // ---- animation drivers ------------------------------------------------
    _drive(dt) {
      this.time += dt;
      const P = this.params, t = this.time;
      if (this.auto.breath && this.paramDefs.Breath) P.Breath = 0.5 + 0.5 * Math.sin(t * 1.9);
      if (this.auto.blink && this.paramDefs.EyeLOpen) {
        const b = this.blink;
        if (b.t < 0) { b.next -= dt; if (b.next <= 0) { b.t = 0; } }
        else {
          b.t += dt; const dur = 0.18; const k = b.t / dur;
          const open = k < 0.5 ? 1 - k * 2 : (k < 1 ? (k - 0.5) * 2 : 1);
          P.EyeLOpen = open; P.EyeROpen = open;
          if (b.t >= dur) { b.t = -1; b.next = 2.2 + Math.random() * 3.5; P.EyeLOpen = 1; P.EyeROpen = 1; }
        }
      }
      if (this.auto.idle && this.paramDefs.AngleZ) {
        P.IdleX = Math.sin(t * 0.6) * 0.5 + Math.sin(t * 0.37 + 1) * 0.3;
        P.IdleY = Math.sin(t * 0.5 + 2) * 0.5;
      } else { P.IdleX = 0; P.IdleY = 0; }
      if (this.auto.physics) this._physics(dt);
      else for (const s of this.phys) { P[s.d.output] = 0; }
    }

    _physics(dt) {
      // Damped spring (pendulum hung from the head). Input u = sum(param*gain) in "degrees of head motion"; the base
      // acceleration u'' drives the spring: th'' = -K*u'' - 2*zeta*w*th' - w^2*th (+ drag*u'). Output th is clamped to -1..1.
      const P = this.params;
      const steps = Math.max(1, Math.ceil(dt / 0.008)); const h = dt / steps;
      let pi = 0;
      for (const s of this.phys) {
        const d = s.d; pi++;
        let inp = 0;
        for (const i of d.inputs) inp += (P[i.param] || 0) * i.gain;
        if (d.idle) inp += (P.IdleX || 0) * d.idle;
        const iv = (inp - s.prevIn) / Math.max(dt, 1e-4);
        const ia = (iv - s.prevInV) / Math.max(dt, 1e-4);
        s.prevIn = inp; s.prevInV = iv;
        const w = (d.freq || 2.2) * 2 * Math.PI, z = d.damp != null ? d.damp : 0.35;
        const K = d.inertia != null ? d.inertia : 0.5, drag = d.drag || 0;
        const iaC = clamp(ia, -3000, 3000), ivC = clamp(iv, -300, 300);
        for (let k = 0; k < steps; k++) {
          const amb = d.sway ? d.sway * w * w * Math.sin(this.time * 2 * Math.PI * (0.28 + 0.07 * (pi % 4)) + pi * 1.7) : 0;   // gentle ambient sway
          const acc = -w * w * s.a - 2 * z * w * s.av - K * iaC * 0.01 - drag * ivC * 0.01 + amb;
          s.av += acc * h; s.a += s.av * h;
          s.a = clamp(s.a, -1.2, 1.2);
        }
        P[d.output] = clamp(s.a, -1, 1);
      }
    }

    // ---- deformation ------------------------------------------------------
    _deform(part) {
      const P = this.params, pos = part._pos, rest = part._rest, n = rest.length / 2;
      pos.set(rest);
      let opacity = part.opacity != null ? part.opacity : 1;
      for (const e of part.effects || []) {
        const pv = e.param != null ? (P[e.param] || 0) : 0;
        switch (e.type) {
          case 'head3d': {
            // Head as an ellipsoid (Rx,Ry,Rz). Each vertex is carried by the surface point under it.
            // rigid (0..1): blend toward the linearisation (Jacobian) of the map at `anchor`, i.e. the part moves/scales/shears
            // as ONE piece instead of being warped non-linearly (what an illustrator does for eyes, hair locks, ornaments).
            const g = e.gain != null ? e.gain : 1;
            const yaw = ((P[e.yaw] || 0) + (P.IdleX || 0) * (e.idle || 0)) * DEG * g;
            const pit = ((P[e.pitch] || 0) + (P.IdleY || 0) * (e.idle || 0)) * DEG * g;
            const rol = (P[e.roll] || 0) * DEG * (e.rgain != null ? e.rgain : 1);
            const cy = Math.cos(yaw), sy = Math.sin(yaw), cp = Math.cos(pit), sp = Math.sin(pit);
            const cr = Math.cos(rol), sr = Math.sin(rol);
            const [cx, cyy] = e.center;
            const Rx = e.Rx || e.R, Ry = e.Ry || e.R, Rz = e.Rz || e.R, k = e.k != null ? e.k : 1, zoff = e.zoff || 0;
            const zmin = e.zmin || 0;
            const pv2 = e.pivot || e.center;
            const zA = e.vz ? part._z : null;
            const map = (x, y, out, zv) => {
              const u = x - cx, v = y - cyy;
              let z;
              if (zv !== undefined) z = zoff + k * zv;
              else { const r2 = (u / Rx) * (u / Rx) + (v / Ry) * (v / Ry); z = zoff + k * Rz * Math.sqrt(Math.max(1 - r2, zmin)); }
              const x1 = u * cy + z * sy, z1 = -u * sy + z * cy;
              const y1 = v * cp - z1 * sp;
              const X = cx + x1, Y = cyy + y1, dx = X - pv2[0], dy = Y - pv2[1];
              out[0] = pv2[0] + dx * cr - dy * sr; out[1] = pv2[1] + dx * sr + dy * cr;
            };
            const rigid = e.rigid || 0;
            let a0 = null, J = null;
            if (rigid > 0) {
              let ax, ay;
              if (e.anchor) { ax = e.anchor[0]; ay = e.anchor[1]; }
              else { if (!part._anchor) { let sx = 0, sy2 = 0; for (let i = 0; i < n; i++) { sx += rest[2 * i]; sy2 += rest[2 * i + 1]; } part._anchor = [sx / n, sy2 / n]; } [ax, ay] = part._anchor; }
              const o0 = [0, 0], o1 = [0, 0], o2 = [0, 0], h = 6;
              const za = zA ? part._zmean : undefined;
              map(ax, ay, o0, za); map(ax + h, ay, o1, za); map(ax, ay + h, o2, za);
              a0 = [ax, ay, o0[0], o0[1]];
              J = [(o1[0] - o0[0]) / h, (o2[0] - o0[0]) / h, (o1[1] - o0[1]) / h, (o2[1] - o0[1]) / h];
            }
            const o = [0, 0];
            for (let i = 0; i < n; i++) {
              const x = pos[2 * i], y = pos[2 * i + 1];
              const w = weightOf(e.weight, x, y);
              if (w <= 0) continue;
              map(x, y, o, zA ? zA[i] : undefined);
              let X = o[0], Y = o[1];
              if (rigid > 0) {
                const lx = a0[2] + J[0] * (x - a0[0]) + J[1] * (y - a0[1]);
                const ly = a0[3] + J[2] * (x - a0[0]) + J[3] * (y - a0[1]);
                X += (lx - X) * rigid; Y += (ly - Y) * rigid;
              }
              pos[2 * i] = x + (X - x) * w; pos[2 * i + 1] = y + (Y - y) * w;
            }
            break;
          }
          case 'translate': {
            const [dx, dy] = mapLinear(e.map, pv);
            for (let i = 0; i < n; i++) {
              const w = weightOf(e.weight, pos[2 * i], pos[2 * i + 1]);
              pos[2 * i] += dx * w; pos[2 * i + 1] += dy * w;
            }
            break;
          }
          case 'rotate': {
            const [deg] = mapLinear(e.map, pv);
            const [px, py] = e.pivot;
            for (let i = 0; i < n; i++) {
              const x = pos[2 * i], y = pos[2 * i + 1];
              const a = deg * DEG * weightOf(e.weight, x, y);
              const c = Math.cos(a), s = Math.sin(a), dx = x - px, dy = y - py;
              pos[2 * i] = px + dx * c - dy * s; pos[2 * i + 1] = py + dx * s + dy * c;
            }
            break;
          }
          case 'scale': {
            const [sx, sy] = mapLinear(e.map, pv);
            const [px, py] = e.pivot;
            for (let i = 0; i < n; i++) {
              const w = weightOf(e.weight, pos[2 * i], pos[2 * i + 1]);
              pos[2 * i] = px + (pos[2 * i] - px) * (1 + (sx - 1) * w);
              pos[2 * i + 1] = py + (pos[2 * i + 1] - py) * (1 + (sy - 1) * w);
            }
            break;
          }
          case 'opacity': opacity *= mapLinear(e.map, pv)[0]; break;
        }
      }
      part._opacity = opacity;
    }

    // ---- drawing ----------------------------------------------------------
    resize() {
      const c = this.canvas, dpr = Math.min(window.devicePixelRatio || 1, 2);
      const w = Math.round(c.clientWidth * dpr), h = Math.round(c.clientHeight * dpr);
      if (c.width !== w || c.height !== h) { c.width = w; c.height = h; }
    }

    _drawPart(part, cut) {
      const gl = this.gl;
      gl.bindVertexArray(part._vao);
      gl.bindBuffer(gl.ARRAY_BUFFER, part._vbo); gl.bufferSubData(gl.ARRAY_BUFFER, 0, part._pos);
      gl.activeTexture(gl.TEXTURE0); gl.bindTexture(gl.TEXTURE_2D, part._tex);
      gl.uniform1i(this.loc.uTex, 0);
      gl.uniform1f(this.loc.uOpacity, cut ? 1 : part._opacity);
      gl.uniform1f(this.loc.uCut, cut || 0);
      gl.drawElements(this.wire ? gl.LINES : gl.TRIANGLES, part._idx.length, gl.UNSIGNED_SHORT, 0);
    }

    render() {
      const gl = this.gl; this.resize();
      const [W, H] = this.rig.size, cw = this.canvas.width, ch = this.canvas.height;
      const view = this.opts.view || [0, 0, W, H];       // x,y,w,h of image shown
      const s = Math.min(cw / view[2], ch / view[3]);
      const ox = (cw - view[2] * s) / 2, oy = (ch - view[3] * s) / 2;
      gl.viewport(0, 0, cw, ch);
      gl.clearColor(0, 0, 0, 0); gl.clearStencil(0); gl.clear(gl.COLOR_BUFFER_BIT | gl.STENCIL_BUFFER_BIT);
      gl.enable(gl.BLEND); gl.blendFunc(gl.ONE, gl.ONE_MINUS_SRC_ALPHA);
      gl.useProgram(this.prog);
      // image px -> clip space
      gl.uniform2f(this.loc.uScale, 2 * s / cw, 2 * s / ch);
      gl.uniform2f(this.loc.uOff, (2 * (ox - view[0] * s)) / cw - 1, (2 * (oy - view[1] * s)) / ch - 1);
      for (const part of this.parts) this._deform(part);
      for (const part of this.parts) {
        if (part.maskOnly || part._opacity <= 0.001) continue;
        if (part.clip && this.byId[part.clip]) {
          gl.enable(gl.STENCIL_TEST); gl.clear(gl.STENCIL_BUFFER_BIT);
          gl.colorMask(false, false, false, false);
          gl.stencilFunc(gl.ALWAYS, 1, 0xff); gl.stencilOp(gl.KEEP, gl.KEEP, gl.REPLACE);
          this._drawPart(this.byId[part.clip], 0.5);
          gl.colorMask(true, true, true, true);
          gl.stencilFunc(gl.EQUAL, 1, 0xff); gl.stencilOp(gl.KEEP, gl.KEEP, gl.KEEP);
          this._drawPart(part, 0);
          gl.disable(gl.STENCIL_TEST);
        } else this._drawPart(part, 0);
      }
    }

    start() {
      let last = performance.now();
      const loop = now => {
        const dt = Math.min((now - last) / 1000, 0.05); last = now;
        this._drive(dt); this.render();
        this._raf = requestAnimationFrame(loop);
      };
      this._raf = requestAnimationFrame(loop);
    }
    stop() { cancelAnimationFrame(this._raf); }
    // deterministic single frame for headless previews (physics settled by stepping)
    renderStill(settle = 0) {
      for (let i = 0; i < settle; i++) this._drive(1 / 60);
      this.render();
    }
  }

  global.L2D = { Model, mapLinear };
})(window);
