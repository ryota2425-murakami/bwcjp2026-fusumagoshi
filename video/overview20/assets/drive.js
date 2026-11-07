/* キャラの状態を「時刻の関数」として組み立てる(HyperFrames は 1 フレームずつ好きな時刻に飛ぶので、前のフレームを覚えない)。
   track = { moods: [[t, mood], ...], gaze: [[t, g], ...], touch: [[t, n], ...], nod: [t, ...], letter: [t, ...],
             speak: [{ t0, hz, env: [...] }, ...], sleepy: [[t, v], ...] } */
(function () {
  function lastAt(list, t) { let r = null; for (const x of list || []) { if ((Array.isArray(x) ? x[0] : x) <= t) r = x; else break; } return r; }
  function smooth(x) { return x <= 0 ? 0 : x >= 1 ? 1 : x * x * (3 - 2 * x); }
  function curve(keys, t, dflt) {
    if (!keys || !keys.length) return dflt;
    if (t <= keys[0][0]) return keys[0][1];
    for (let i = 1; i < keys.length; i++) {
      const [t1, v1] = keys[i], [t0, v0] = keys[i - 1];
      if (t < t1) return v0 + (v1 - v0) * smooth((t - t0) / Math.max(1e-6, t1 - t0));
    }
    return keys[keys.length - 1][1];
  }
  function speakAt(segs, t) {
    for (const s of segs || []) {
      const x = (t - s.t0) * s.hz;
      if (x >= 0 && x < s.env.length - 1) { const i = Math.floor(x), f = x - i; return s.env[i] + (s.env[i + 1] - s.env[i]) * f; }
    }
    return 0;
  }
  function stateAt(t, tr) {
    const ms = tr.moods || [[0, "watch"]];
    let idx = -1;
    for (let i = 0; i < ms.length; i++) if (ms[i][0] <= t) idx = i;
    const cur = idx >= 0 ? ms[idx] : [0, ms[0][1]];
    const prev = idx > 0 ? ms[idx - 1][1] : cur[1];
    const tc = lastAt(tr.touch, t);
    return { mood: cur[1], since: cur[0], prev, speak: speakAt(tr.speak, t), gaze: curve(tr.gaze, t, 0),
             touchAt: tc ? tc[0] : null, touchN: tc ? tc[1] : 0, nodAt: lastAt(tr.nod, t), letterAt: lastAt(tr.letter, t),
             sleepy: curve(tr.sleepy, t, 0) };
  }
  window.HFDrive = { stateAt };
})();
