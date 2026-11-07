/* ふすまの中の Claude — キオスクの運転役(Raspberry Pi の Chromium で動く)。
 *
 * 絵は rig.js(LanternRig)が (時刻, 状態) だけから描く。ここは「状態」を持つ係:
 *   - Mac の中継(fusuma.lantern_bridge)から合図を受けて気分を変える(文字は来ない)
 *   - さわられたら、その場で「くすぐったい」演技を重ねる
 *   - Mac につながらないときや夜は、うとうとする
 * 使い方: kiosk.html?bridge=ws://<mac>.local:8781/lantern,ws://<mac-ip>:8781/lantern  (&role=family &debug=1 &fps=30)
 *   role=kitchen(既定): 台所の端末の顔。電話中は静かに、電話のあとは話す、を同じ合図でなぞる
 *   role=family       : 家族の机の上。便りが届いたことだけを受け取る(電話中かどうかは来ない)
 */
(function () {
  "use strict";
  const q = new URLSearchParams(location.search);
  const BRIDGES = (q.get("bridge") || "").split(",").map(s => s.trim()).filter(Boolean);
  const DEBUG = q.get("debug") === "1";
  const dbg = document.getElementById("debug");
  const FPS = Math.max(10, Math.min(60, +(q.get("fps") || 60)));
  const ROLE = q.get("role") === "family" ? "family" : "kitchen";   // family: 便りが届いたことだけを受け取る
  const NIGHT = q.get("night") !== "0";            // night=0: 夜でも、うとうとしない(撮影や確かめるとき)
  const now = () => performance.now() / 1000;

  // 明るさ(0〜1)から部屋の色: 昼のアイボリー → 温かい茶色 → ほとんど黒(電話のあいだ)
  const C_DAY = [244, 241, 234], C_MID = [91, 74, 62], C_NIGHT = [20, 17, 14];
  const bgEl = document.getElementById("bg"), floorEl = document.getElementById("floor");
  let lastBg = "";
  function paintRoom(g) {
    let k = Math.max(0, Math.min(1, (g - 0.03) / 0.4)); k = k * k * (3 - 2 * k);
    const c = C_DAY.map((d, i) => Math.round(k < 0.5 ? C_NIGHT[i] + (C_MID[i] - C_NIGHT[i]) * k * 2 : C_MID[i] + (d - C_MID[i]) * (k - 0.5) * 2));
    const hi = c.map((v, i) => Math.min(255, v + Math.round(7 * k * [1, 0.85, 0.6][i])));
    const bg = `radial-gradient(ellipse 75% 70% at 50% 46%, rgb(${hi.join(",")}) 0%, rgb(${c.join(",")}) 72%)`;
    if (bg !== lastBg) { bgEl.style.background = bg; lastBg = bg; }
    floorEl.style.opacity = (0.25 + 0.75 * k).toFixed(3);
    rig.el.style.opacity = (0.35 + 0.65 * Math.min(1, g / 0.5)).toFixed(3);   // 電話のあいだは、キャラも暗く
  }
  function placeFloor() {        // 床の影を、キャラの足もとの線にぴったり置く
    const r = stage.getBoundingClientRect(), k = Math.min(r.width / 430, r.height / 304);
    floorEl.style.top = (r.top + (r.height - 304 * k) / 2 + 263 * k - 23 * k) + "px";
    floorEl.style.width = (330 * k) + "px"; floorEl.style.height = (46 * k) + "px";
  }
  const rig = LanternRig.create(stage, { seed: 7 });
  addEventListener("resize", placeFloor);
  placeFloor();

  // ---------- 状態(LanternRig の契約どおり) ----------
  const s = { mood: "watch", since: now(), prev: "watch", speak: 0, gaze: 0,
              touchAt: null, touchN: 0, nodAt: null, letterAt: null, sleepy: 0, sus: 0, ask: 0 };
  const uneasy = { sus: 0, ask: 0 };      // Mac から来る目標値(0..1)。画面ではゆっくり近づける
  let speech = null;           // {t0, dur, hz, env, then}
  let awaiting = false;        // 返事を待っている(話し終えたら「聞く」顔に)
  let letterBackAt = null;     // 便りを渡し終えたら見守りに戻る時刻
  let gazeTween = null;        // {t0, from, to, dur, holdUntil}
  let link = { ok: false, upstream: false, lastMsg: 0, since: now() };
  let sleepyNow = 0;

  function setMood(m) {
    if (!LanternRig.MOODS.includes(m) || m === "touched") return;
    if (m === s.mood) return;
    const t = now();
    s.prev = s.mood; s.mood = m; s.since = t;
    if (m !== "listen") s.nodAt = null;
    if (m === "letter") { s.letterAt = t + 0.25; letterBackAt = t + 7.5; } else { letterBackAt = null; }
    if (m === "call") { speech = null; awaiting = false; }
  }

  function lookAt(target, dur, hold) {
    const t = now();
    gazeTween = { t0: t, from: s.gaze, to: target, dur: dur || 0.45, holdUntil: t + (hold || 2.2) };
  }

  function updateGaze(t) {
    if (!gazeTween) { s.gaze = 0; return; }
    const g = gazeTween;
    if (t < g.t0 + g.dur) {
      const x = (t - g.t0) / g.dur, e = x < .5 ? 2 * x * x : 1 - Math.pow(-2 * x + 2, 2) / 2;
      s.gaze = g.from + (g.to - g.from) * e;
    } else if (t < g.holdUntil) {
      s.gaze = g.to;
    } else if (t < g.holdUntil + 0.8) {
      const x = (t - g.holdUntil) / 0.8, e = x < .5 ? 2 * x * x : 1 - Math.pow(-2 * x + 2, 2) / 2;
      s.gaze = g.to * (1 - e);
    } else { s.gaze = 0; gazeTween = null; }
  }

  function speakLevel(t) {
    if (!speech) return 0;
    const x = (t - speech.t0) * speech.hz;
    if (x >= speech.env.length || t > speech.t0 + speech.dur + 0.15) {
      const then = speech.then; speech = null;
      setMood(awaiting || then === "listen" ? "listen" : (then || "watch"));
      return 0;
    }
    const i = Math.floor(x), f = x - i;
    const a = speech.env[i] || 0, b = speech.env[i + 1] || 0;
    return a + (b - a) * f;
  }

  // ---------- Mac からの合図 ----------
  function onMsg(m) {
    link.lastMsg = now();
    if (typeof m.upstream === "boolean") link.upstream = m.upstream;
    switch (m.type) {
      case "mood": setMood(m.mood); break;
      case "speak":
        setMood("after");
        speech = { t0: now(), dur: +m.dur || 0, hz: +m.hz || 20, env: Array.isArray(m.env) ? m.env : [], then: m.then };
        break;
      case "speak_stop": speech = null; break;
      case "await_answer": awaiting = true; if (!speech) setMood("listen"); break;
      case "nod": if (s.mood !== "listen") setMood("listen"); s.nodAt = now() + 0.05; break;
      case "letter": setMood("letter"); break;
      case "glance": lookAt(+m.gaze || -0.8, 0.35, 2.4); break;
      case "touch": poke(innerWidth / 2); break;          // 配線の確認用(Mac から「さわった」ことにする)
      case "uneasy": uneasy.sus = Math.max(0, Math.min(1, +m.sus || 0)); uneasy.ask = Math.max(0, Math.min(1, +m.ask || 0)); break;
      case "beat": break;
    }
    if (m.type === "mood" && m.mood === "watch") awaiting = false;
  }

  let ws = null, wsIdx = 0, backoff = 1;
  function connect() {
    if (!BRIDGES.length) return;
    const url = BRIDGES[wsIdx % BRIDGES.length];
    try { ws = new WebSocket(url); } catch (e) { return retry(); }
    ws.onopen = () => {
      link.ok = true; link.since = now(); backoff = 1;
      ws.send(JSON.stringify({ type: "hello", who: "fusuma-lantern", role: ROLE }));
    };
    ws.onmessage = ev => { try { onMsg(JSON.parse(ev.data)); } catch (e) { /* 壊れた合図は捨てる */ } };
    ws.onclose = () => { if (link.ok) link.since = now(); link.ok = false; retry(); };
    ws.onerror = () => { try { ws.close(); } catch (e) {} };
  }
  function retry() {
    wsIdx++;
    setTimeout(connect, backoff * 1000);
    backoff = Math.min(backoff * 1.6, 12);
  }
  setInterval(() => {                          // 合図が 15 秒途切れたら、繋ぎ直す
    if (link.ok && now() - link.lastMsg > 15) { try { ws.close(); } catch (e) {} }
  }, 3000);
  connect();

  // ---------- さわる ----------
  let wokeAt = -1e9;               // さわられたら、しばらく目を覚ます(居眠り中でも)
  function poke(x) {
    const t = now();
    wokeAt = t;
    s.touchAt = t; s.touchN = (s.touchN || 0) + 1;
    lookAt(Math.max(-1, Math.min(1, (x / innerWidth) * 2 - 1)) * 0.85, 0.18, 1.6);
    if (ws && ws.readyState === 1) ws.send(JSON.stringify({ type: "touch" }));
  }
  addEventListener("pointerdown", e => { e.preventDefault(); poke(e.clientX); }, { passive: false });
  addEventListener("contextmenu", e => e.preventDefault());

  // ---------- うとうと(Mac につながらない・夜) ----------
  function sleepTarget(t) {
    const h = new Date().getHours();
    const night = NIGHT && (h >= 22 || h < 6);
    document.body.classList.toggle("night", night);
    const lost = (!link.ok || !link.upstream) && t - link.since > 20;
    if (s.mood !== "watch" || t - wokeAt < 9) return 0;
    return lost ? 1 : night ? 0.65 : 0;
  }

  // ---------- 毎フレーム ----------
  let last = 0, frames = 0, fpsT = now(), fps = 0;
  function frame() {
    requestAnimationFrame(frame);
    const t = now();
    if (t - last < 1 / FPS - 0.002) return;
    last = t;
    if (letterBackAt && t > letterBackAt) setMood("watch");
    const target = sleepTarget(t);
    sleepyNow += (target - sleepyNow) * Math.min(1, (target < sleepyNow && t - wokeAt < 1 ? 6 : 0.9) / FPS);
    s.sleepy = Math.round(sleepyNow * 1000) / 1000;
    s.sus += (uneasy.sus - s.sus) * Math.min(1, 0.8 / FPS); s.ask += (uneasy.ask - s.ask) * Math.min(1, 0.8 / FPS);
    s.sus = Math.round(s.sus * 1000) / 1000; s.ask = Math.round(s.ask * 1000) / 1000;
    updateGaze(t);
    s.speak = speakLevel(t);
    rig.render(t, s);
    const g = LanternRig.glowOf(t, s);
    paintRoom(g);
    frames++;
    if (t - fpsT >= 1) { fps = frames / (t - fpsT); frames = 0; fpsT = t; }
    if (DEBUG) dbg.textContent = `mood ${s.mood}  glow ${g.toFixed(2)}  speak ${s.speak.toFixed(2)}\nlink ${link.ok ? "ok" : "--"} upstream ${link.upstream ? "ok" : "--"}  fps ${fps.toFixed(0)}\n${BRIDGES[wsIdx % Math.max(1, BRIDGES.length)] || "(no bridge)"}`;
  }
  window.__lantern = { state: s, setMood, poke, onMsg, fps: () => fps };   // 確認用
  requestAnimationFrame(frame);
})();
