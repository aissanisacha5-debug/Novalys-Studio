// Noyau visuel JARVIS : canvas 2D léger. Son état vient UNIQUEMENT des événements réels du backend
// (tâche, outil, modèle, confirmation, erreur, micro) — jamais d'activité simulée.
const COLORS = {
  emerald: [0, 214, 160], bright: [56, 245, 179], deep: [7, 91, 72], champagne: [215, 188, 131], amber: [244, 184, 96], red: [255, 93, 104],
};
const STATES = {
  attente:      { label: "En attente",           c: "emerald",   energy: 0.18, speed: 0.15, pulse: 0.25, arcs: 0 },
  ecoute:       { label: "Écoute active",         c: "bright",    energy: 0.55, speed: 0.3,  pulse: 1.0,  arcs: 1 },
  reflexion:    { label: "Réflexion",             c: "emerald",   energy: 0.45, speed: 0.55, pulse: 0.35, arcs: 2 },
  outil:        { label: "Utilise un outil",      c: "bright",    energy: 0.7,  speed: 1.1,  pulse: 0.3,  arcs: 3, focus: true },
  tache:        { label: "Tâche en cours",        c: "emerald",   energy: 0.55, speed: 0.7,  pulse: 0.3,  arcs: 2, progress: true },
  autorisation: { label: "Attend votre accord",   c: "champagne", energy: 0.4,  speed: 0.2,  pulse: 0.6,  arcs: 1 },
  erreur:       { label: "Erreur",                c: "red",       energy: 0.35, speed: 0.1,  pulse: 0.8,  arcs: 0 },
  termine:      { label: "Réponse terminée",      c: "emerald",   energy: 0.3,  speed: 0.2,  pulse: 0.2,  arcs: 0 },
};

export class Core {
  constructor(canvas, { mini = false } = {}) {
    this.cv = canvas; this.ctx = canvas.getContext("2d"); this.mini = mini;
    this.state = "attente"; this.cur = { ...STATES.attente, rgb: COLORS.emerald.slice() };
    this.t = 0; this.last = performance.now(); this.visible = true;
    this.reduced = matchMedia("(prefers-reduced-motion: reduce)").matches;
    this.particles = Array.from({ length: mini ? 0 : 70 }, () => ({ a: Math.random() * Math.PI * 2, r: 0.55 + Math.random() * 0.4, s: 0.2 + Math.random() * 0.8, z: Math.random() }));
    this.resize(); addEventListener("resize", () => this.resize());
    document.addEventListener("visibilitychange", () => { this.visible = !document.hidden; if (this.visible) this.loop(); });
    this.loop();
  }
  setMotion(m) { this.reduced = m === "aucune" || matchMedia("(prefers-reduced-motion: reduce)").matches; this.draw(); }
  resize() {
    const r = this.cv.getBoundingClientRect(); const dpr = Math.min(2, devicePixelRatio || 1);
    if (r.width) { this.cv.width = r.width * dpr; this.cv.height = r.height * dpr; }
    this.draw();
  }
  set(state) { if (STATES[state]) this.state = state; if (this.reduced) this.draw(); }
  label() { return STATES[this.state].label; }
  loop() {
    if (!this.visible || this.raf) return;
    const step = (now) => {
      this.raf = null;
      const dt = Math.min(0.05, (now - this.last) / 1000); this.last = now;
      const tgt = STATES[this.state]; const k = Math.min(1, dt * 3);
      for (const key of ["energy", "speed", "pulse", "arcs"]) this.cur[key] += (tgt[key] - this.cur[key]) * k;
      const rgb = COLORS[tgt.c]; for (let i = 0; i < 3; i++) this.cur.rgb[i] += (rgb[i] - this.cur.rgb[i]) * k;
      this.cur.focus = tgt.focus; this.cur.progress = tgt.progress;
      this.t += dt * (this.reduced ? 0 : 1);
      this.draw();
      if (!this.reduced && this.visible) this.raf = requestAnimationFrame(step);
    };
    this.raf = requestAnimationFrame(step);
  }
  draw() {
    const { ctx, cv } = this; const W = cv.width, H = cv.height; if (!W) return;
    const cx = W / 2, cy = H / 2, R = Math.min(W, H) / 2 * (this.mini ? 0.92 : 0.86);
    const c = this.cur, [r, g, b] = c.rgb.map(Math.round), t = this.t;
    const col = (a) => `rgba(${r},${g},${b},${a})`;
    ctx.clearRect(0, 0, W, H);
    const breathe = 1 + Math.sin(t * (1.2 + c.pulse * 2.2)) * 0.035 * (0.4 + c.pulse);
    // halo
    const halo = ctx.createRadialGradient(cx, cy, R * 0.08, cx, cy, R * 1.0);
    halo.addColorStop(0, col(0.22 + c.energy * 0.25)); halo.addColorStop(0.35, col(0.08 + c.energy * 0.08)); halo.addColorStop(1, col(0));
    ctx.fillStyle = halo; ctx.beginPath(); ctx.arc(cx, cy, R, 0, Math.PI * 2); ctx.fill();
    // anneaux concentriques (profondeur simulée par ellipses inclinées)
    const rings = this.mini ? 2 : 4;
    for (let i = 0; i < rings; i++) {
      const rr = R * (0.42 + i * 0.13) * breathe;
      ctx.save(); ctx.translate(cx, cy); ctx.rotate(t * c.speed * (i % 2 ? -0.35 : 0.25) + i);
      ctx.scale(1, 0.34 + 0.16 * Math.sin(i * 1.7 + t * 0.15 * c.speed));
      ctx.strokeStyle = col(0.10 + 0.05 * (rings - i)); ctx.lineWidth = Math.max(1, R * 0.006);
      ctx.beginPath(); ctx.arc(0, 0, rr, 0, Math.PI * 2); ctx.stroke(); ctx.restore();
    }
    // arcs lumineux (réflexion / outil / tâche)
    const arcs = Math.round(c.arcs);
    for (let i = 0; i < arcs; i++) {
      const rr = R * (0.6 + i * 0.09);
      const start = t * c.speed * (c.focus ? 2.2 : 1) * (i % 2 ? -1 : 1) + i * 2.1;
      const len = c.progress ? (0.6 + ((t * 0.18) % 1) * 4.8) : (c.focus ? 0.9 : 1.6);
      ctx.strokeStyle = col(0.55); ctx.lineWidth = Math.max(1.4, R * 0.014); ctx.lineCap = "round";
      ctx.shadowColor = col(0.8); ctx.shadowBlur = R * 0.06;
      ctx.beginPath(); ctx.arc(cx, cy, rr, start, start + len); ctx.stroke(); ctx.shadowBlur = 0;
    }
    // particules orbitales
    for (const p of this.particles) {
      const a = p.a + t * c.speed * p.s * 0.6; const rr = R * p.r * breathe;
      const x = cx + Math.cos(a) * rr, y = cy + Math.sin(a) * rr * (0.42 + p.z * 0.4);
      ctx.fillStyle = col(0.12 + 0.5 * p.z * (0.4 + c.energy)); ctx.beginPath(); ctx.arc(x, y, Math.max(0.6, R * 0.006 * (0.5 + p.z)), 0, Math.PI * 2); ctx.fill();
    }
    // noyau
    const core = ctx.createRadialGradient(cx, cy, 0, cx, cy, R * 0.3 * breathe);
    core.addColorStop(0, `rgba(233,255,246,${0.85})`); core.addColorStop(0.18, col(0.95)); core.addColorStop(0.6, col(0.35)); core.addColorStop(1, col(0));
    ctx.fillStyle = core; ctx.beginPath(); ctx.arc(cx, cy, R * 0.3 * breathe, 0, Math.PI * 2); ctx.fill();
    ctx.strokeStyle = col(0.5); ctx.lineWidth = Math.max(1, R * 0.008);
    ctx.beginPath(); ctx.arc(cx, cy, R * 0.18 * breathe, 0, Math.PI * 2); ctx.stroke();
  }
}
export const CORE_LABELS = Object.fromEntries(Object.entries(STATES).map(([k, v]) => [k, v.label]));
