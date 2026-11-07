/* みずち (Mizuchi) — a little axolotl-ish water creature: a cousin of the coral block in the same flat art style.
 * Final v3 (from candidate c + the panel's fixes and grafts).
 * Classic script, no deps. window.LanternRig = { create, MOODS, glowOf, version }.
 * render(t, s) is pure: the picture depends only on (t, s).
 */
(function (root) {
  'use strict';
  var NS = 'http://www.w3.org/2000/svg';
  var MOODS = ['watch', 'call', 'after', 'listen', 'letter', 'touched', 'think'];
  var COL = {
    head: '#E58A6C', body: '#DB8064', shade: '#C2684D', paw: '#C4694E',
    gill: '#CF5E47', gillTip: '#DD7259', gillLit: '#F0A084', fin: '#E39A80',
    belly: '#F0B497', line: '#2B211C', blush: '#F7B4A0',
    paper: '#FAF9F5', muted: '#6B6458', back: '#D27C60', backBody: '#C97257', tailBack: '#C06A50'
  };
  var GLOW = { watch: 0.5, call: 0.05, after: 0.95, listen: 0.6, letter: 0.7, touched: 0.8, think: 0.62 };

  // ---- geometry (body space: origin = underside of the torso, y up is negative)
  var XOFF = -10;                            // body sits a little left so body + tail are optically centred
  var TH = 80, TWT = 118, TWB = 152;         // low pear torso, narrower at the neck
  var HW = 188, HH = 114;                    // big soft bun head (wider than the torso)
  var HTOP = -174, HCY = HTOP + HH / 2, HBOT = HTOP + HH;   // HCY = -117, HBOT = -60
  var LEG_L = 12;
  var FOOT_X = [-44, 44], FOOT_W = 38;
  var EYE_W = 24, EYE_H = 29, EYE_X = 46;
  var EYE_CY = HCY + 4;                      // a bit below the head's middle: wide-set, axolotl-like
  var MOUTH_Y = EYE_CY + 28;
  var PAW_W = 18, PAW_H = 14, PAW_X = 45, PAW_Y = -40;   // little paws at the edges of the belly patch
  var LETTER_T = 2.6;
  var ENV_Y = -38;
  // gill fronds per side: anchor (x from head edge, y), angle above horizontal, length, thickness
  var GILLS = [
    { ax: -17, ay: HCY - 33, a: 54, L: 36, w: 22, c: 'gillTip' },
    { ax: -11, ay: HCY - 11, a: 17, L: 46, w: 24.5, c: 'gill' },
    { ax: -13, ay: HCY + 11, a: -18, L: 30, w: 20, c: 'gillTip' }
  ];

  // ---- maths
  function clamp(x, a, b) { return x < a ? a : x > b ? b : x; }
  function lerp(a, b, u) { return a + (b - a) * u; }
  function sm(a, b, x) { var u = clamp((x - a) / (b - a), 0, 1); return u * u * (3 - 2 * u); }
  function bump(x, a, b) { return (x <= a || x >= b) ? 0 : Math.sin(Math.PI * (x - a) / (b - a)); }
  function spring(k, w, d) {
    if (k <= 0) return 0;
    return 1 - Math.exp(-d * k) * (Math.cos(w * k) + (d / w) * Math.sin(w * k));
  }
  function backOut(u) { u = clamp(u, 0, 1); var c = 2.2; return 1 + (c + 1) * Math.pow(u - 1, 3) + c * Math.pow(u - 1, 2); }
  function hash(a, b, c) {
    var x = (Math.imul(a | 0, 0x9E3779B1) ^ Math.imul((b | 0) + 0x7f4a7c15, 0x85EBCA77) ^ Math.imul((c | 0) + 0x165667B1, 0xC2B2AE3D)) | 0;
    x = (x + 0x6D2B79F5) | 0;
    var r = Math.imul(x ^ (x >>> 15), 1 | x);
    r = (r + Math.imul(r ^ (r >>> 7), 61 | r)) ^ r;
    return ((r ^ (r >>> 14)) >>> 0) / 4294967296;
  }
  function f(x) { return Math.round(x * 100) / 100; }
  function spow(v, p) { return (v < 0 ? -1 : 1) * Math.pow(Math.abs(v), p); }
  function hex(c) { return [parseInt(c.slice(1, 3), 16), parseInt(c.slice(3, 5), 16), parseInt(c.slice(5, 7), 16)]; }
  function mixCol(a, b, u) {
    if (u <= 0.005) return a;
    if (u >= 0.995) return b;
    var X = hex(a), Y = hex(b);
    return 'rgb(' + Math.round(lerp(X[0], Y[0], u)) + ',' + Math.round(lerp(X[1], Y[1], u)) + ',' + Math.round(lerp(X[2], Y[2], u)) + ')';
  }

  // ---- static shapes
  // soft bun: a superellipse, rounder on top than at the chin
  function bunPath(a, b, cy, nTop, nBot) {
    var d = '', N = 96;
    for (var i = 0; i < N; i++) {
      var th = 2 * Math.PI * i / N, c = Math.cos(th), s = Math.sin(th);
      var n = s < 0 ? nTop : nBot;
      var x = a * spow(c, 2 / n), y = cy + b * spow(s, 2 / n);
      d += (i ? 'L' : 'M') + f(x) + ',' + f(y);
    }
    return d + 'Z';
  }
  // pear torso: superellipse whose half-width grows from the neck to the floor
  function pearPath(top, bot, wt, wb, n) {
    var d = '', N = 80, cy = (top + bot) / 2, b = (bot - top) / 2;
    for (var i = 0; i < N; i++) {
      var th = 2 * Math.PI * i / N, c = Math.cos(th), s = Math.sin(th);
      var y = cy + b * spow(s, 2 / n);
      var a = lerp(wt, wb, sm(0, 0.75, (y - top) / (bot - top))) / 2;
      d += (i ? 'L' : 'M') + f(a * spow(c, 2 / n)) + ',' + f(y);
    }
    return d + 'Z';
  }

  // ---- pose
  function basePose() {
    return {
      x: 0, hop: 0, sq: 0, tilt: 0, legExt: 1, flip: 1,
      hr: 0, hy: 0,
      open: 1, escale: 1, arc: 0, arcMix: 0, gx: 0, gy: 0, hi: 0,
      blush: 0, mouth: 0, mw: 1, mh: 1, mtop: 0, mtg: 1, smile: 0,
      lx: -PAW_X, ly: PAW_Y, lr: 12, lext: 0, lsz: 1,
      rx: PAW_X, ry: PAW_Y, rr: -12, rext: 0, rsz: 1,
      env: 0, ex: 0, ey: ENV_Y, er: 0,
      f0: 0, f1: 0, zz: 0, lis: 0, thk: 0,
      gsL: 0, gsR: 0, gfl: 0.15, glen: 1, hkL: 0, hkR: 0,
      tw: 0, tu: 0, tc: 0
    };
  }
  var KEYS = Object.keys(basePose());
  function mix(X, Y, u) { var o = {}; for (var i = 0; i < KEYS.length; i++) { var k = KEYS[i]; o[k] = X[k] + (Y[k] - X[k]) * u; } return o; }
  function copy(X) { var o = {}; for (var i = 0; i < KEYS.length; i++) o[KEYS[i]] = X[KEYS[i]]; return o; }

  function breathe(P, t, amt) {
    var b = Math.sin(2 * Math.PI * t / 4);
    P.sq += 0.02 * b * amt;
    P.hy += 1.2 * Math.sin(2 * Math.PI * t / 4 - 0.5) * amt;
    P.ly += 1.4 * b * amt;
    P.ry += 1.4 * Math.sin(2 * Math.PI * t / 4 - 0.6) * amt;
    P.gsL += 3 * Math.sin(2 * Math.PI * t / 4 - 0.3) * amt;
    P.gsR += 3 * Math.sin(2 * Math.PI * t / 4 - 0.9) * amt;
  }

  // glances, sway, foot taps, gill ruffles, tail flicks
  function idle(P, t, seed, amt) {
    P.tilt += 0.9 * Math.sin(2 * Math.PI * t / 9.5) * amt;
    P.hr += 1.2 * Math.sin(2 * Math.PI * t / 7.1 + 1) * amt;
    P.lr += 5 * Math.sin(t * 0.83 + 0.4) * amt;
    P.rr -= 5 * Math.sin(t * 0.71 + 2.1) * amt;
    P.tw += 6 * Math.sin(2 * Math.PI * t / 3.3) * amt;
    var G = 4.6, n = Math.floor(t / G), u = t - n * G;
    if (hash(seed, n, 11) < 0.6) {
      var dir = hash(seed, n, 12) < 0.5 ? -1 : 1;
      var st = 0.5 + hash(seed, n, 13) * 1.6, dur = 0.8 + hash(seed, n, 14) * 1.2;
      var e = sm(st, st + 0.16, u) * (1 - sm(st + dur, st + dur + 0.22, u));
      var eb = sm(st + 0.08, st + 0.5, u) * (1 - sm(st + dur + 0.05, st + dur + 0.55, u));
      var up = (hash(seed, n, 15) - 0.6) * 9;
      P.gx += 12 * dir * e * amt; P.gy += up * e * amt;
      P.x += 3 * dir * eb * amt; P.hr += 4 * dir * eb * amt;
      // the gill fan on the side it looks at perks a little
      if (dir > 0) P.gsR += 8 * eb * amt; else P.gsL += 8 * eb * amt;
    }
    var F = 6.8, m = Math.floor((t + 2.3) / F), v = t + 2.3 - m * F;
    if (hash(seed, m, 21) < 0.75) {
      var s2 = 1 + hash(seed, m, 23) * 3.4, kind = hash(seed, m, 22);
      if (kind < 0.36) {
        var leg = hash(seed, m, 24) < 0.5 ? 0 : 1;
        P['f' + leg] += 6 * (bump(v, s2, s2 + 0.2) + 0.8 * bump(v, s2 + 0.28, s2 + 0.48)) * amt;
        P.tilt += (leg ? 1 : -1) * 0.8 * bump(v, s2 - 0.05, s2 + 0.55) * amt;
      } else if (kind < 0.68) {
        // a quick double ruffle of one gill fan (like a bird shaking a wing)
        var rf = 13 * (bump(v, s2, s2 + 0.16) + 0.85 * bump(v, s2 + 0.2, s2 + 0.36)) * amt;
        if (hash(seed, m, 25) < 0.5) P.gsL += rf; else P.gsR += rf;
        P.hr += 1.5 * bump(v, s2 - 0.05, s2 + 0.45) * (hash(seed, m, 25) < 0.5 ? -1 : 1) * amt;
      } else {
        // tail flick: up, over, settle
        P.tu += 26 * (bump(v, s2, s2 + 0.35) - 0.3 * bump(v, s2 + 0.35, s2 + 0.7)) * amt;
        P.tw += 14 * bump(v, s2 + 0.05, s2 + 0.45) * amt;
      }
    }
  }

  function restVar(t, seed) {
    var n = Math.floor(t / 8);
    function bnd(m) { return 8 * m + (hash(seed, m, 61) - 0.5) * 2; }
    function val(m, c) { return hash(seed, m, c) * 2 - 1; }
    var cur = t >= bnd(n) ? n : n - 1;
    var u = sm(bnd(cur), bnd(cur) + 1.4, t);
    return {
      tilt: 1.5 * lerp(val(cur - 1, 62), val(cur, 62), u),
      gx: 3 * lerp(val(cur - 1, 63), val(cur, 63), u),
      gy: 1.5 * lerp(val(cur - 1, 64), val(cur, 64), u)
    };
  }

  function blinkAt(x) { if (x < 0 || x > 0.2) return 0; if (x < 0.055) return x / 0.055; if (x < 0.09) return 1; return 1 - (x - 0.09) / 0.11; }
  function blink(t, seed) {
    var B = 5, n = Math.floor(t / B), u = t - n * B;
    var st = 1 + hash(seed, n, 31) * 2;
    var c = blinkAt(u - st);
    if (hash(seed, n, 32) < 0.28) c = Math.max(c, blinkAt(u - st - 0.27));
    return c;
  }

  var MOUTHS = {
    o:      { w: 0.62, h: 1.00, top: 0.9,  tg: 0 },
    wide:   { w: 1.35, h: 0.78, top: 0.1,  tg: 0.5 },
    small:  { w: 0.70, h: 0.42, top: 0.0,  tg: 0 },
    smile:  { w: 1.15, h: 0.72, top: -0.6, tg: 0.6 },
    flat:   { w: 1.20, h: 0.26, top: 0.05, tg: 0 },
    ee:     { w: 1.40, h: 0.40, top: -0.35, tg: 0 },
    big:    { w: 1.05, h: 1.25, top: 0.35, tg: 0.9 },
    tongue: { w: 1.00, h: 0.95, top: 0.25, tg: 1.3 }
  };
  function speakShape(sp, seed, i) {
    var v = hash(seed, i, 41);
    if (sp < 0.3) return MOUTHS[v < 0.45 ? 'small' : v < 0.75 ? 'flat' : 'o'];
    if (sp < 0.65) return MOUTHS[v < 0.25 ? 'smile' : v < 0.47 ? 'o' : v < 0.67 ? 'wide' : v < 0.85 ? 'ee' : 'flat'];
    return MOUTHS[v < 0.24 ? 'wide' : v < 0.44 ? 'o' : v < 0.6 ? 'big' : v < 0.74 ? 'tongue' : v < 0.88 ? 'smile' : 'ee'];
  }

  // a point given in head space (face coordinates) -> body space, for paws that touch the face
  function h2b(x, y, hr, hy) {
    var a = hr * Math.PI / 180, c = Math.cos(a), sn = Math.sin(a), dy = y - HBOT;
    return [x * c - dy * sn, HBOT + x * sn + dy * c + hy];
  }

  // listening side, continuous in gaze: +1 (right, the default when gaze is 0) .. -1 (left)
  function listenSide(g) { return 1 - 2 * sm(-0.03, -0.3, g); }

  function moodPose(mood, t, s, seed) {
    var P = basePose();
    var g = +s.gaze || 0;
    if (mood === 'watch') {
      breathe(P, t, 1); idle(P, t, seed, 1);
      var rv = restVar(t, seed);
      P.tilt += rv.tilt; P.gx += rv.gx + 4 * g; P.gy += rv.gy;
    } else if (mood === 'call') {
      // しーっ: sinks low, both paws over the mouth, gills folded flat, tail tucked, eyes gently closed
      var sb = Math.sin(2 * Math.PI * t / 6.5), sb2 = Math.sin(2 * Math.PI * t / 6.5 - 0.5);
      P.legExt = 0.1 + 0.07 * sb; P.sq = 0.06 + 0.012 * sb; P.hy = 4 - 1.2 * sb;
      P.arcMix = 1; P.arc = -1.0; P.hi = 0; P.gy = 2;
      P.gsL = -70 + 2 * sb; P.gsR = -72 + 2 * sb2; P.glen = 0.74; P.gfl = 0;
      P.tc = 1; P.tw = 2 * Math.sin(2 * Math.PI * t / 13);
      // both little arms come up from the chest and meet over the mouth (a soft V: "shh")
      P.lx = -12.5; P.ly = MOUTH_Y + P.hy + 15 - 0.8 * sb; P.lr = 15; P.lsz = 1.3; P.lext = 14;
      P.rx = 13; P.ry = MOUTH_Y + P.hy + 17 - 0.8 * sb2; P.rr = -13; P.rsz = 1.3; P.rext = 13;
      P.smile = 0;
      P.tilt = 0.7 * Math.sin(2 * Math.PI * t / 13);
    } else if (mood === 'after') {
      var sp = clamp(+s.speak || 0, 0, 1);
      breathe(P, t, 1); idle(P, t, seed, 0.5);
      var syl = t * 7, si = Math.floor(syl), sf = syl - si;
      var Ma = speakShape(sp, seed, si), Mb = speakShape(sp, seed, si + 1), u = sm(0.62, 1, sf);
      P.mouth = sp; P.mw = lerp(Ma.w, Mb.w, u); P.mh = lerp(Ma.h, Mb.h, u);
      P.mtop = lerp(Ma.top, Mb.top, u); P.mtg = lerp(Ma.tg, Mb.tg, u);
      P.smile = 0.55; P.hi = 1; P.escale = 1.06;
      // gills flutter with the voice; loud syllables pop them out (readable across the room)
      var loud = sm(0.55, 0.9, sp);
      P.gsL += 10 + 8 * sp * hash(seed, si, 46) + 9 * loud; P.gsR += 10 + 8 * sp * hash(seed, si, 47) + 9 * loud;
      P.gfl = 0.3 + 0.9 * sp * sp;
      P.hop += 4 * sp * sp; P.sq -= 0.04 * sp;
      P.ly -= 8 * sp; P.lr += 10 * sp;
      P.ry -= 4 * sp * (0.5 + hash(seed, si, 43)); P.rr -= 12 * sp * hash(seed, si, 44);
      P.hr += 2.4 * Math.sin(t * 1.7) + 2 * sp * (hash(seed, si, 45) - 0.5);
      P.tw += 10 * Math.sin(t * 3.1); P.tu += 8;
    } else if (mood === 'listen') {
      var sd = listenSide(g), wR = (sd + 1) / 2, wL = 1 - wR;
      breathe(P, t, 0.8);
      P.tilt = 5 * sd + 0.5 * Math.sin(t * 0.9);
      P.hr = 5 * sd;
      P.x = 5 * sd;
      P.gx = 6 * sd + 4 * g; P.gy = -2;
      P.smile = 0.2; P.hi = 0; P.lis = sd;
      // the gill fan on the voice side stands tall and turns toward it; the far one relaxes
      var fan = 22 + 3 * Math.sin(t * 2.2);
      P.gsR = lerp(-6, fan, wR); P.gsL = lerp(-6, fan, wL);
      // the near paw comes up to the side of the head, under the fan, like a hand to the ear
      var cy = -95 + 2 * Math.sin(t * 1.3), cR = h2b(89, cy, P.hr, P.hy), cL = h2b(-89, cy, P.hr, P.hy);
      P.rx = lerp(P.rx, cR[0], wR); P.ry = lerp(P.ry, cR[1], wR); P.rr = lerp(P.rr, 28, wR); P.rext = 14 * wR;
      P.lx = lerp(P.lx, cL[0], wL); P.ly = lerp(P.ly, cL[1], wL); P.lr = lerp(P.lr, -28, wL); P.lext = 14 * wL;
      P.gfl = 0.25; P.tw = 5 * sd;
      if (s.nodAt != null) {
        var d = t - s.nodAt, nb = bump(d, 0, 0.5), nb2 = 0.5 * bump(d, 0.48, 0.85);
        P.gy += 7 * (nb + nb2); P.hy += 7 * (nb + nb2); P.sq += 0.05 * (nb + nb2); P.open *= 1 - 0.35 * nb;
        P.hr -= 3 * sd * nb; P.gsL += 10 * nb; P.gsR += 10 * nb;
      }
    } else if (mood === 'think') {
      // 考え中: looks up and away, a paw taps the chin, the gills ripple like turning gears,
      // the top gill on the look side curls into a little "?", a foot keeps a second rhythm
      breathe(P, t, 0.7);
      var wan = Math.sin(2 * Math.PI * t / 3.7);
      var n2 = Math.floor(t / 2.3), u2 = t - n2 * 2.3, sN = (n2 % 2) ? 1 : -1;
      P.gx = -9 + 5 * lerp(-sN, sN, sm(0, 0.25, u2)) + 1.5 * wan; P.gy = -9 + 1.2 * Math.sin(t * 1.1);
      P.hr = -6 + 1.4 * Math.sin(2 * Math.PI * t / 5.3);
      P.tilt = -1;
      P.x = -3;
      P.open = 0.88; P.hi = 0.6; P.smile = 0;
      P.mouth = 0.1; P.mw = 0.55; P.mh = 0.9; P.mtop = 0.6; P.mtg = 0;
      var ti = Math.floor(t * 2.6), tp = t * 2.6 - ti;
      var tap = bump(tp, 0, 0.42) * (hash(seed, ti, 71) < 0.25 ? 0.15 : 1);
      var cp = h2b(27, -69 - 3.5 * tap, P.hr, P.hy);
      P.rx = cp[0]; P.ry = cp[1]; P.rr = -56 + 5 * tap; P.rext = 16; P.rsz = 0.95;
      P.lr = 16;
      var fu = t % 1.6;
      P.f0 += 5 * (bump(fu, 0.1, 0.27) + 0.7 * bump(fu, 0.36, 0.52));
      P.tw = 6 * Math.sin(2 * Math.PI * t / 1.2); P.tu = 6;
      P.gsL = 6; P.gsR = 2; P.gfl = 0;
      P.hkL = 0.9 + 0.1 * Math.sin(2 * Math.PI * t / 2.4);
      P.thk = 1;
    } else if (mood === 'letter') {
      var La = t - (s.letterAt != null ? s.letterAt : (s.since || 0));
      var T = LETTER_T;
      breathe(P, t, 0.7);
      P.env = La < 0 ? 0 : backOut(La / 0.38);
      P.arcMix = 1; P.arc = 1; P.smile = 0.7; P.blush = 0.12; P.hi = 0;
      P.gsL += 14; P.gsR += 14; P.gfl = 0.3; P.tw += 8 * Math.sin(t * 2.4); P.tu += 6;
      var hold = { lx: -28, ly: ENV_Y + 5, lr: -24, rx: 28, ry: ENV_Y + 4, rr: 22 };
      var fling = { lx: -40, ly: -82, lr: -26, rx: 42, ry: -86, rr: 28 };
      var wu = sm(T - 0.48, T - 0.14, La) * (1 - sm(T - 0.06, T + 0.04, La));
      var fl = sm(T - 0.0, T + 0.18, La), back = sm(T + 0.4, T + 1.0, La);
      var out = sm(T - 0.06, T + 0.04, La) * (1 - fl);
      P.lx = lerp(lerp(hold.lx, fling.lx, fl) - 14 * out, P.lx, back); P.ly = lerp(lerp(hold.ly + 9 * wu, fling.ly, fl), P.ly, back);
      P.lr = lerp(lerp(hold.lr, fling.lr, fl), 12, back); P.lext = 14 * fl * (1 - back);
      P.rx = lerp(lerp(hold.rx, fling.rx, fl) + 14 * out, P.rx, back); P.ry = lerp(lerp(hold.ry + 9 * wu, fling.ry, fl), P.ry, back);
      P.rr = lerp(lerp(hold.rr, fling.rr, fl), -12, back); P.rext = 14 * fl * (1 - back);
      P.legExt = 1 - 0.45 * wu;
      // wind-up: gills fold back, then flare on the throw
      P.gsL += -24 * wu + 26 * bump(La, T - 0.02, T + 0.7); P.gsR += -24 * wu + 26 * bump(La, T, T + 0.75);
      P.gfl += 0.9 * bump(La, T, T + 1.2);
      P.tu += 30 * bump(La, T - 0.05, T + 0.6);
      // a happy little flutter + tail wag after the toss, then a satisfied settle
      var hap = bump(La, T + 0.55, T + 1.75);
      P.gfl += 0.8 * hap; P.tw += 16 * Math.sin(2 * Math.PI * 3 * La) * hap;
      if (La < -0.2) { P.lx = -PAW_X; P.ly = PAW_Y; P.rx = PAW_X; P.ry = PAW_Y; P.lr = 12; P.rr = -12; P.arcMix = 0; P.smile = 0.3; }
      P.ey = ENV_Y + 1.5 * Math.sin(t * 3.1); P.er = 4 * Math.sin(t * 2.3);
      var rel = La - (T + 0.07);
      var tx = 0, ty = 0;
      if (rel > 0) {
        P.ex = 330 * rel; P.ey = -110 - 1250 * rel + 280 * rel * rel; P.er = -20 + 520 * rel;
        tx = clamp(P.ex / 120, 0, 1); ty = clamp((-110 - P.ey) / 220, 0, 1);
        if (rel > 1.3) P.env = 0;
      } else if (La > T - 0.5) {
        P.ey += 9 * wu - 60 * sm(T - 0.05, T + 0.07, La);
      }
      var open = sm(T - 0.42, T - 0.22, La);
      P.arcMix = lerp(P.arcMix, 0, open); P.smile = lerp(P.smile, 0.5, open); P.blush = lerp(P.blush, 0, open);
      var ret = 1 - sm(T + 1.3, T + 2.0, La);
      P.gx += (3 * wu + 5 * tx + 9 * ty) * ret; P.gy += (-3 * wu - 4 * tx - 9 * ty) * ret;
      P.hi = lerp(P.hi, 0.8, sm(T, T + 0.15, La) * ret);
      P.hr += 5 * ty * ret;
      if (La > T + 1.2) idle(P, t, seed, sm(T + 1.2, T + 2.5, La));
    }
    return P;
  }

  // entry takes (anticipation -> action -> overshoot; the blend spring adds the settle)
  function takes(P, mood, k, t, s) {
    if (k < 0) return;
    if (mood === 'watch') {
      P.sq += 0.05 * bump(k, 0, 0.3) - 0.02 * bump(k, 0.3, 0.6);
      P.gsL += 8 * bump(k, 0.1, 0.6); P.gsR += 8 * bump(k, 0.16, 0.66);
    } else if (mood === 'call') {
      // small inhale (gills lift), then sink and fold
      P.sq += -0.07 * bump(k, 0.0, 0.5) + 0.06 * bump(k, 0.5, 1.0);
      P.hop += 4 * bump(k, 0.0, 0.5);
      P.gy -= 4 * bump(k, 0, 0.45);
      P.gsL += 30 * bump(k, 0, 0.5); P.gsR += 30 * bump(k, 0.05, 0.55);
      P.arcMix = Math.min(P.arcMix, sm(0.12, 0.75, k));   // eyes close gently, after the inhale
    } else if (mood === 'after') {
      P.sq += 0.13 * bump(k, 0, 0.16) - 0.1 * bump(k, 0.14, 0.42) + 0.15 * bump(k, 0.56, 0.78) - 0.03 * bump(k, 0.78, 1.0);
      P.hop += 34 * bump(k, 0.15, 0.58) + 6 * bump(k, 0.8, 1.02);
      P.escale += 0.12 * bump(k, 0.1, 0.6);
      P.gsL += -20 * bump(k, 0, 0.18) + 30 * bump(k, 0.16, 0.8); P.gsR += -20 * bump(k, 0.02, 0.2) + 30 * bump(k, 0.2, 0.85);
      P.gfl += 0.7 * bump(k, 0.2, 1.4);
      P.tu += 30 * bump(k, 0.18, 0.75);
      P.ly -= 16 * bump(k, 0.12, 0.7); P.ry -= 20 * bump(k, 0.16, 0.76);
      P.lr += 25 * bump(k, 0.12, 0.7); P.rr -= 25 * bump(k, 0.16, 0.76);
    } else if (mood === 'think') {
      P.sq += 0.05 * bump(k, 0, 0.25) - 0.03 * bump(k, 0.25, 0.5);
      P.gy -= 3 * bump(k, 0, 0.4);
      P.gsL -= 14 * bump(k, 0, 0.4); P.gsR -= 14 * bump(k, 0.05, 0.45);
    } else if (mood === 'listen') {
      var sd = listenSide(+s.gaze || 0);
      P.hr -= 3 * sd * bump(k, 0, 0.22);
      P.sq += 0.04 * bump(k, 0, 0.22);
      var pk = 14 * bump(k, 0.1, 0.5);
      P.gsR += pk * (sd + 1) / 2; P.gsL += pk * (1 - sd) / 2;
    } else if (mood === 'letter') {
      var La = t - (s.letterAt != null ? s.letterAt : (s.since || 0)), T = LETTER_T;
      P.sq += 0.08 * bump(La, 0.3, 0.48) - 0.1 * bump(La, 0.46, 0.66) + 0.1 * bump(La, 0.86, 1.04);
      P.hop += 28 * bump(La, 0.48, 0.88) + 4 * bump(La, 1.04, 1.2);
      P.sq += 0.12 * sm(T - 0.4, T - 0.1, La) * (1 - sm(T - 0.04, T + 0.06, La)) - 0.12 * bump(La, T - 0.02, T + 0.3) + 0.1 * bump(La, T + 0.42, T + 0.66);
      P.hop += 16 * bump(La, T, T + 0.42);
    }
  }

  function touchOverlay(P, t, s) {
    if (s.touchAt == null) return P;
    var tt = t - s.touchAt;
    if (tt < 0 || tt > 2.3) return P;
    var v = (((s.touchN | 0) % 3) + 3) % 3;
    var g = +s.gaze || 0, side = clamp(g / 0.3, -1, 1);
    var w = sm(0, 0.05, tt) * (1 - sm(1.8, 2.25, tt));
    var O = copy(P);
    var sur = sm(0, 0.05, tt) * (1 - sm(0.36, 0.56, tt));
    O.escale = 1 + 0.4 * sur; O.open = 1; O.arcMix = 0; O.hi = 1; O.lis = 0; O.thk = 0; O.hkL = 0; O.hkR = 0;
    O.gx = 10 * side; O.gy = -3 * sur;
    O.mouth = 0.5 * bump(tt, 0.04, 0.5); O.mw = 0.55; O.mh = 1; O.mtop = 0.7; O.mtg = 0; O.smile = 0;
    O.sq += 0.14 * bump(tt, 0, 0.12) - 0.12 * bump(tt, 0.1, 0.32) + 0.12 * bump(tt, 0.4, 0.58);
    O.hop += 24 * bump(tt, 0.11, 0.42);
    O.legExt = Math.max(O.legExt, sm(0, 0.15, tt));
    // gills shoot straight out (longer, so the jump reads from across the room), tail pops up
    O.gsL = lerp(O.gsL, 30, sur); O.gsR = lerp(O.gsR, 30, sur); O.glen = lerp(O.glen, 1.2, sur); O.gfl = lerp(O.gfl, 0.2, sur);
    O.tu += 34 * bump(tt, 0.04, 0.6); O.tc *= 1 - sur;
    O.lx = lerp(O.lx, -PAW_X - 26, sur); O.ly = lerp(O.ly, PAW_Y - 22, sur); O.lr = lerp(O.lr, -40, sur); O.lext = lerp(O.lext, 10, sur); O.lsz = lerp(O.lsz, 1, sur);
    O.rx = lerp(O.rx, PAW_X + 26, sur); O.ry = lerp(O.ry, PAW_Y - 24, sur); O.rr = lerp(O.rr, 42, sur); O.rext = lerp(O.rext, 10, sur); O.rsz = lerp(O.rsz, 1, sur);
    O.blush = 0;
    var g2 = sm(0.4, 0.6, tt);
    if (v === 0) { // giggle: gills flutter like laughter
      var gig = Math.abs(Math.sin(2 * Math.PI * 3.3 * tt)) * (1 - sm(1.5, 1.95, tt));
      O.arcMix = g2; O.arc = 1; O.blush = 0.25 * g2;
      O.mouth = Math.max(O.mouth, g2 * (0.35 + 0.3 * gig)); O.mw = lerp(O.mw, 1.15, g2);
      O.mtop = lerp(O.mtop, -0.4, g2); O.mtg = lerp(O.mtg, 0.8, g2);
      O.hop += g2 * 6 * gig; O.sq -= g2 * 0.03 * gig;
      O.hr += g2 * 5 * Math.sin(2 * Math.PI * 2.4 * (tt - 0.4));
      O.gfl = lerp(O.gfl, 1, g2); O.gsL = lerp(O.gsL, 14, g2); O.gsR = lerp(O.gsR, 14, g2);
      O.tw += g2 * 12 * Math.sin(2 * Math.PI * 3 * tt);
      O.lx = lerp(O.lx, -PAW_X, g2); O.ly = lerp(O.ly, PAW_Y - 6, g2); O.rx = lerp(O.rx, PAW_X, g2); O.ry = lerp(O.ry, PAW_Y - 6, g2);
      O.lext = lerp(O.lext, 0, g2); O.rext = lerp(O.rext, 0, g2);
      O.lr = lerp(O.lr, 12 + 14 * Math.sin(2 * Math.PI * 4.6 * tt), g2); O.rr = lerp(O.rr, -12 + 14 * Math.sin(2 * Math.PI * 4.6 * tt + 1.6), g2);
      O.gx = lerp(O.gx, 4 * side, g2);
    } else if (v === 1) { // bashful: both paws cover the face, then the one on the touch side lowers to peek
      var sd = side >= 0 ? 1 : -1, g3 = sm(0.48, 0.7, tt);
      var peek = sm(1.0, 1.22, tt) * (1 - sm(1.62, 1.82, tt));
      O.hy += 3 * g2;
      O.hr += g2 * (-5 * sd + 2.5 * Math.sin(2 * Math.PI * 0.9 * (tt - 0.4)));
      O.gx = lerp(lerp(O.gx, 0, g2), 10 * sd, peek); O.gy = lerp(O.gy, 3, g2);
      var cL = h2b(-EYE_X - 1 + O.gx, EYE_CY + 3 + O.gy, O.hr, O.hy), cR = h2b(EYE_X + 1 + O.gx, EYE_CY + 3 + O.gy, O.hr, O.hy);
      var pk = h2b(sd * (EYE_X + 16), EYE_CY + 34, O.hr, O.hy);
      O.lx = lerp(O.lx, cL[0], g2); O.ly = lerp(O.ly, cL[1], g2); O.lr = lerp(O.lr, 12, g2); O.lsz = lerp(O.lsz, 2.15, g2); O.lext = lerp(O.lext, 0, g2);
      O.rx = lerp(O.rx, cR[0], g3); O.ry = lerp(O.ry, cR[1], g3); O.rr = lerp(O.rr, -12, g3); O.rsz = lerp(O.rsz, 2.15, g3); O.rext = lerp(O.rext, 0, g3);
      if (sd > 0) { O.rx = lerp(O.rx, pk[0], peek); O.ry = lerp(O.ry, pk[1], peek); O.rsz = lerp(O.rsz, 1.3, peek); O.rr = lerp(O.rr, -30, peek); }
      else { O.lx = lerp(O.lx, pk[0], peek); O.ly = lerp(O.ly, pk[1], peek); O.lsz = lerp(O.lsz, 1.3, peek); O.lr = lerp(O.lr, 30, peek); }
      O.escale = lerp(O.escale, 1, g2); O.open = lerp(O.open, 0.9, g2);
      O.arcMix = g2 * (1 - peek); O.arc = 1;
      O.blush = 0.5 * g2; O.smile = lerp(O.smile, 0.75, g2); O.mouth *= 1 - g2;
      O.gsL = lerp(O.gsL, -22, g2); O.gsR = lerp(O.gsR, -22, g2); O.gfl = lerp(O.gfl, 0.12, g2);
      O.tc = lerp(O.tc, 0.6, g2);
      O.x += -4 * sd * g2;
      O.f1 += 6 * bump(tt, 0.8, 1.05) + 5 * bump(tt, 1.2, 1.45);
    } else { // happy spin-hop (a full turn: the back of the head and the tail toward us at mid-spin)
      O.sq += 0.12 * bump(tt, 0.44, 0.6) - 0.13 * bump(tt, 0.58, 0.9) + 0.15 * bump(tt, 1.24, 1.44) - 0.03 * bump(tt, 1.44, 1.65);
      O.hop += 48 * bump(tt, 0.58, 1.26);
      O.flip = Math.cos(Math.PI * (sm(0.62, 0.86, tt) + sm(0.98, 1.2, tt)));
      var hap = sm(1.15, 1.32, tt);
      O.arcMix = lerp(O.arcMix, 1, hap); O.arc = 1; O.blush = 0.15 * hap;
      O.mouth = Math.max(O.mouth, 0.55 * bump(tt, 1.2, 2.0)); O.mw = lerp(O.mw, 1.2, hap);
      O.mtop = lerp(O.mtop, -0.5, hap); O.mtg = lerp(O.mtg, 0.8, hap);
      O.gsL -= 30 * bump(tt, 0.58, 1.1); O.gsR -= 30 * bump(tt, 0.6, 1.12);
      O.gsL += 26 * bump(tt, 1.2, 1.9); O.gsR += 26 * bump(tt, 1.22, 1.92); O.gfl += 0.8 * bump(tt, 1.2, 2.1);
      O.tu += 20 * bump(tt, 0.6, 1.3);
      O.ly -= 20 * bump(tt, 0.58, 1.3); O.ry -= 22 * bump(tt, 0.6, 1.32);
      O.lr += 30 * bump(tt, 0.58, 1.3); O.rr -= 30 * bump(tt, 0.6, 1.32);
    }
    return mix(P, O, w);
  }

  function sleepyOverlay(P, t, s) {
    var sl = clamp(+s.sleepy || 0, 0, 1);
    if (sl <= 0) return;
    var d = (t + 1.3) % 6.5;
    var dip = sm(2.2, 4.3, d) * (1 - sm(4.45, 4.75, d));
    P.open = lerp(P.open, 0.2 * (1 - dip) + 0.04, sl);
    P.arcMix *= 1 - sl; P.escale = lerp(P.escale, 1, sl); P.hi *= 1 - sl;
    P.gx *= 1 - sl; P.gy += (4 + 6 * dip) * sl;
    P.hy += (3 + 7 * dip) * sl;
    P.sq += (0.03 + 0.04 * dip) * sl; P.hop -= 3 * dip * sl;
    P.hr += (2.5 * Math.sin(2 * Math.PI * t / 8) + 4 * dip) * sl;
    P.ly += 6 * sl; P.ry += 6 * sl;
    P.legExt = lerp(P.legExt, 0.4, sl);
    P.gsL = lerp(P.gsL, -40 - 8 * dip, sl); P.gsR = lerp(P.gsR, -42 - 8 * dip, sl); P.gfl *= 1 - sl;
    P.tc = lerp(P.tc, 0.7, sl); P.tw *= 1 - 0.7 * sl; P.tu *= 1 - sl;
    P.mouth = lerp(P.mouth, 0.1 + 0.07 * Math.sin(2 * Math.PI * t / 4), sl); P.mw = lerp(P.mw, 0.5, sl); P.smile *= 1 - sl;
    P.mh = lerp(P.mh, 1, sl); P.mtop = lerp(P.mtop, 0, sl); P.mtg = lerp(P.mtg, 0, sl);
    P.lis *= 1 - sl; P.thk *= 1 - sl; P.hkL *= 1 - sl; P.hkR *= 1 - sl;
    P.zz = sl;
  }

  function resolve(s) {
    var mood = s.mood || 'watch', prev = s.prev || mood;
    if (mood === 'touched') { mood = (s.prev && s.prev !== 'touched') ? s.prev : 'watch'; prev = mood; }
    if (prev === 'touched') prev = 'watch';
    if (MOODS.indexOf(mood) < 0) mood = 'watch';
    if (MOODS.indexOf(prev) < 0) prev = mood;
    return { mood: mood, prev: prev };
  }

  // 通話中・電話のあとの「あやしい」「聞きたい」(s.sus / s.ask は 0..1。Mac が数値だけ送る。文字は来ない)
  //  sus: ときどき薄目をあけて電話のほうを横目で見る。えらがぴくっ、しっぽの先がぴくっ
  //  ask: 口を押さえた手がむずむず、ほっぺがふくらむ、しっぽが速くゆれる、小さくそわそわ跳ねる
  function uneasyOverlay(P, t, s, mood, prev, k, seed) {
    var sus = clamp(+s.sus || 0, 0, 1), ask = clamp(+s.ask || 0, 0, 1);
    if (sus <= 0.01 && ask <= 0.01) return;
    var wc = mood === 'call' ? sm(0.6, 2.0, k) : (prev === 'call' ? 1 - sm(0, 0.5, k) : 0);
    var ww = mood === 'watch' ? sm(0.2, 1.0, k) : 0;
    if (wc > 0) {
      // peek: a window every ~3.4 s; more often and longer when more suspicious
      var W = 3.4, n = Math.floor(t / W), u = t - n * W, e = 0;
      if (hash(seed, n, 71) < 0.25 + 0.65 * Math.max(sus, 0.6 * ask)) {
        var st = 0.3 + hash(seed, n, 72) * 1.1, dur = 0.8 + 0.7 * sus;
        e = sm(st, st + 0.16, u) * (1 - sm(st + dur, st + dur + 0.22, u)) * wc;
      }
      var toFront = ask > sus ? 1 : 0;               // 聞きたいときは前(祖母)を、あやしいときは横(電話)を見る
      var es = e * Math.max(sus, ask);
      P.arcMix = lerp(P.arcMix, 0, es); P.open = lerp(P.open, toFront ? 0.72 : 0.36, es);
      P.hi = lerp(P.hi, toFront ? 0.9 : 0.2, es);
      P.gx += (toFront ? -2 : 11) * es; P.gy += (toFront ? -3 : 1.5) * es;
      P.hr += (toFront ? -1.5 : 4) * es;
      P.gsR += (22 * sus + 8 * Math.sin(t * 23) * sus) * e + 12 * sus * wc; P.gsL += 10 * sus * wc;
      P.gfl += 0.35 * sus * wc;
      var fl = hash(seed, n, 73) < 0.5 ? bump(u, 2.2, 2.55) : 0;
      P.tu += 18 * fl * sus * wc;
      // むずむず
      var fid = Math.abs(Math.sin(2 * Math.PI * t * 1.55));
      P.ly -= 2.2 * fid * ask * wc; P.ry -= 2.2 * Math.abs(Math.sin(2 * Math.PI * t * 1.55 + 1.3)) * ask * wc;
      P.lsz += 0.08 * fid * ask * wc; P.rsz += 0.08 * fid * ask * wc;
      P.hop += 2.4 * Math.pow(Math.max(0, Math.sin(2 * Math.PI * t / 0.95)), 2) * ask * wc;
      P.tw += 9 * Math.sin(t * 7.2) * ask * wc;
      P.blush += 0.32 * ask * wc; P.gfl += 0.4 * ask * wc;
      P.gsL += 9 * ask * wc * (0.5 + 0.5 * Math.sin(t * 5.1)); P.gsR += 9 * ask * wc * (0.5 + 0.5 * Math.sin(t * 5.1 + 1));
    }
    if (ww > 0 && ask > 0.01) {
      // 電話のあと、話しかけたくてそわそわ: 前を見て、目がきらきら、手を胸の前で合わせて小さく跳ねる
      var a = ask * ww, b = Math.pow(Math.max(0, Math.sin(2 * Math.PI * t / 0.85)), 2);
      P.gx = lerp(P.gx, 0, a); P.gy = lerp(P.gy, -2, a); P.escale += 0.07 * a; P.hi = lerp(P.hi, 1, a);
      P.hop += 3.5 * b * a; P.sq -= 0.02 * b * a; P.hy -= 2 * a;
      P.ly -= 7 * a + 3 * b * a; P.ry -= 7 * a + 3 * b * a; P.lr -= 14 * a; P.rr += 14 * a;
      P.gsL += 14 * a; P.gsR += 14 * a; P.gfl += 0.5 * a;
      P.tw += 10 * Math.sin(t * 6.5) * a; P.tu += 6 * a;
      P.blush += 0.22 * a; P.smile = lerp(P.smile, 0.35, a);
    }
  }

  function poseAt(t, s, seed) {
    var r = resolve(s), mood = r.mood, prev = r.prev;
    var since = +s.since || 0;
    var k = t - since;
    var B = moodPose(mood, t, s, seed);
    var P;
    if (prev !== mood && k < 2.5) {
      var Q = moodPose(prev, t, s, seed);
      P = mix(Q, B, spring(k, 9.5, 5.2));
      P.arcMix = clamp(P.arcMix, 0, 1); P.legExt = clamp(P.legExt, 0, 1.08);
      P.lis = clamp(P.lis, -1, 1); P.thk = clamp(P.thk, 0, 1);
      P.hkL = clamp(P.hkL, 0, 1); P.hkR = clamp(P.hkR, 0, 1);
      P.lext = Math.max(0, P.lext); P.rext = Math.max(0, P.rext);
      P.tc = clamp(P.tc, 0, 1); P.gfl = Math.max(0, P.gfl);
    } else P = B;
    if (mood === 'letter') takes(P, mood, 99, t, s);
    else if (k < 2.5) takes(P, mood, k, t, s);
    uneasyOverlay(P, t, s, mood, prev, k, seed);
    P = touchOverlay(P, t, s);
    sleepyOverlay(P, t, s);
    return P;
  }

  function energy(t, s, slow) {
    var r = resolve(s), mood = r.mood, prev = r.prev;
    var gA = GLOW[prev] != null ? GLOW[prev] : 0.5, gB = GLOW[mood] != null ? GLOW[mood] : 0.5;
    var k = t - (+s.since || 0);
    var g = lerp(gA, gB, sm(0, (mood === 'call' ? 1.4 : 0.7) * (slow ? 1.8 : 1), k));
    if (mood === 'after') g += 0.05 * clamp(+s.speak || 0, 0, 1) - 0.025;
    // 通話中にあやしい・聞きたいときは、暗い画面が少しだけ明るくなる(動きが見える程度。光りはしない)
    if (mood === 'call') g += (0.09 * clamp(+s.sus || 0, 0, 1) + 0.06 * clamp(+s.ask || 0, 0, 1)) * sm(0.6, 2.0, k);
    if (s.touchAt != null) {
      var tt = t - s.touchAt;
      if (tt >= 0 && tt < 2.3) {
        if (slow) g += (0.95 - g) * 0.85 * sm(0.05, 0.7, tt) * (1 - sm(1.7, 2.3, tt));
        else g += (0.85 - g) * 0.7 * sm(0, 0.08, tt) * (1 - sm(1.6, 2.25, tt));
      }
    }
    var sl = clamp(+s.sleepy || 0, 0, 1);
    g = lerp(g, Math.min(g, 0.22), sl);
    return clamp(g, 0, 1);
  }
  function glowOf(t, s) { return energy(+t || 0, s || {}, false); }

  // ---- DOM
  var uid = 0;
  function el(tag, attrs, parent) {
    var e = document.createElementNS(NS, tag);
    for (var k in attrs) e.setAttribute(k, attrs[k]);
    if (parent) parent.appendChild(e);
    return e;
  }
  function A(e, k, v) {
    v = '' + v;
    var c = e.__lr || (e.__lr = {});
    if (c[k] !== v) { c[k] = v; e.setAttribute(k, v); }
  }

  // tail: a flat paddle along a quadratic centreline, base hidden behind the torso.
  // fin > 0 widens it into the soft fin that sits behind (mostly along the top edge).
  function tailPath(P, fin) {
    var tc = clamp(P.tc, 0, 1);
    var wag = P.tw, up = P.tu;
    var bx = 30, by = -24;
    var cx = lerp(106, 78, tc) + 0.4 * wag, cy = lerp(-6, -13, tc);
    var tx = lerp(132, 88, tc) + wag, ty = lerp(-50, -26, tc) - up * (1 - 0.6 * tc);
    var N = 9, Lp = [], Rp = [];
    for (var i = 0; i <= N; i++) {
      var u = i / N, a = 1 - u;
      var px = a * a * bx + 2 * a * u * cx + u * u * tx, py = a * a * by + 2 * a * u * cy + u * u * ty;
      var dx = 2 * a * (cx - bx) + 2 * u * (tx - cx), dy = 2 * a * (cy - by) + 2 * u * (ty - cy);
      var dl = Math.sqrt(dx * dx + dy * dy) || 1, nx = dy / dl, ny = -dx / dl;
      var w = 6 + 10.5 * Math.sin(Math.PI * (0.2 + 0.62 * u)) * (1 - 0.3 * u);
      // soft fin: a low crest along the top that peaks mid-tail and fades out before the tip
      var ft = fin * sm(0.12, 0.45, u) * (1 - 0.8 * sm(0.62, 1, u));
      Lp.push([px + nx * (w + 11 * ft), py + ny * (w + 11 * ft)]);
      Rp.push([px - nx * (w + 3 * ft), py - ny * (w + 3 * ft)]);
    }
    var d = 'M' + f(Lp[0][0]) + ',' + f(Lp[0][1]);
    for (i = 1; i <= N; i++) d += 'L' + f(Lp[i][0]) + ',' + f(Lp[i][1]);
    var e = Rp[N], s0 = Lp[N];
    var r = Math.sqrt((s0[0] - e[0]) * (s0[0] - e[0]) + (s0[1] - e[1]) * (s0[1] - e[1])) / 2;
    var ddx = tx - cx, ddy = ty - cy, dd = Math.sqrt(ddx * ddx + ddy * ddy) || 1;
    var qx = (s0[0] + e[0]) / 2 + ddx / dd * r * 2, qy = (s0[1] + e[1]) / 2 + ddy / dd * r * 2;
    d += 'Q' + f(qx) + ',' + f(qy) + ' ' + f(e[0]) + ',' + f(e[1]);
    for (i = N - 1; i >= 0; i--) d += 'L' + f(Rp[i][0]) + ',' + f(Rp[i][1]);
    return d + 'Z';
  }

  // hind foot: a stubby leg with a rounded, three-toed front edge
  function footPath(cx, top, bot, w) {
    if (bot < top + 2) bot = top + 2;
    var h = bot - top, wt = w - 6;
    var x0 = cx - w / 2, x1 = cx + w / 2, r = Math.min(10, h / 2);
    var tb = Math.min(6, h * 0.35), notch = tb * 0.5;
    var d = 'M' + f(cx - wt / 2) + ',' + f(top + r) + 'Q' + f(cx - wt / 2) + ',' + f(top) + ' ' + f(cx - wt / 2 + r) + ',' + f(top)
      + 'L' + f(cx + wt / 2 - r) + ',' + f(top) + 'Q' + f(cx + wt / 2) + ',' + f(top) + ' ' + f(cx + wt / 2) + ',' + f(top + r)
      + 'L' + f(x1) + ',' + f(bot - tb - 3);
    var k = 3, tw = w / k;
    for (var i = 0; i < k; i++) {
      var xa = x1 - i * tw, xb = xa - tw, xm = (xa + xb) / 2;
      var yb = i === k - 1 ? bot - tb - 3 : bot - notch;
      d += 'Q' + f(xa) + ',' + f(bot) + ' ' + f(xm) + ',' + f(bot) + 'Q' + f(xb) + ',' + f(bot) + ' ' + f(xb) + ',' + f(yb);
    }
    return d + 'Z';
  }

  function create(container, opts) {
    opts = opts || {};
    var seed = (opts.seed == null ? 1 : opts.seed) | 0;
    var glowMul = opts.glow == null ? 1 : Math.max(0, +opts.glow);
    var id = 'lr' + (++uid);
    var svg = el('svg', { viewBox: '-215 -262 430 304', preserveAspectRatio: 'xMidYMid meet', width: '100%', height: '100%' });
    svg.style.display = 'block'; svg.style.overflow = 'visible';
    var defs = el('defs', {}, svg);
    var gGlow = el('radialGradient', { id: id + 'g', cx: '50%', cy: '50%', r: '50%' }, defs);
    el('stop', { offset: '0', 'stop-color': '#F6C3AE', 'stop-opacity': '0.9' }, gGlow);
    el('stop', { offset: '0.45', 'stop-color': '#F2A08A', 'stop-opacity': '0.35' }, gGlow);
    el('stop', { offset: '1', 'stop-color': '#F2A08A', 'stop-opacity': '0' }, gGlow);
    var gSh = el('radialGradient', { id: id + 's', cx: '50%', cy: '50%', r: '50%' }, defs);
    el('stop', { offset: '0', 'stop-color': '#2B211C', 'stop-opacity': '0.5' }, gSh);
    el('stop', { offset: '0.6', 'stop-color': '#2B211C', 'stop-opacity': '0.2' }, gSh);
    el('stop', { offset: '1', 'stop-color': '#2B211C', 'stop-opacity': '0' }, gSh);

    var glow = el('circle', { cx: 0, cy: -95, r: 250, fill: 'url(#' + id + 'g)' }, svg);
    var shadow = el('ellipse', { cx: 0, cy: 2, rx: 140, ry: 14, fill: 'url(#' + id + 's)' }, svg);
    var rootG = el('g', {}, svg);
    var feet = [0, 1].map(function () { return el('path', { fill: COL.shade }, rootG); });
    var bodyG = el('g', {}, rootG);
    var tailFin = el('path', { fill: COL.fin }, bodyG);
    var tail = el('path', { fill: COL.body }, bodyG);
    el('path', { d: pearPath(-TH, 0, TWT, TWB, 2.6), fill: COL.shade }, bodyG);
    var torso = el('path', { d: pearPath(-TH, -9, TWT, TWB - 4, 2.6), fill: COL.body }, bodyG);
    var belly = el('ellipse', { cx: 0, cy: -34, rx: 42, ry: 24, fill: COL.belly }, bodyG);
    var tailBack = el('path', { d: 'M-17,-44 Q0,-54 17,-44 Q22,-12 0,6 Q-22,-12 -17,-44Z', fill: COL.tailBack, opacity: 0 }, bodyG);
    var headG = el('g', {}, bodyG);
    var gills = [];
    [-1, 1].forEach(function (sx) {
      GILLS.forEach(function (G, i) {
        gills.push({ sx: sx, i: i, G: G, e: el('path', { fill: 'none', stroke: COL[G.c], 'stroke-width': G.w, 'stroke-linecap': 'round' }, headG) });
      });
    });
    var head = el('path', { d: bunPath(HW / 2, HH / 2, HCY, 2.35, 3.1), fill: COL.head }, headG);
    var face = el('g', {}, headG);
    var blushL = el('ellipse', { cx: -EYE_X - 17, cy: EYE_CY + 20, rx: 14, ry: 7.5, fill: COL.blush }, face);
    var blushR = el('ellipse', { cx: EYE_X + 17, cy: EYE_CY + 20, rx: 14, ry: 7.5, fill: COL.blush }, face);
    var eyes = [-1, 1].map(function (sx) {
      var g = el('g', {}, face);
      return {
        g: g,
        rect: el('rect', { x: -EYE_W / 2, width: EYE_W, rx: 10, fill: COL.line }, g),
        arc: el('path', { fill: 'none', stroke: COL.line, 'stroke-width': 7, 'stroke-linecap': 'round', 'stroke-linejoin': 'round' }, g),
        hl: el('rect', { width: 7, height: 7, rx: 3.5, fill: COL.paper }, g),
        sx: sx
      };
    });
    var mouthG = el('g', { transform: 'translate(0,' + MOUTH_Y + ')' }, face);
    var mouth = el('path', { fill: COL.line }, mouthG);
    var tongue = el('ellipse', { cx: 0, fill: '#E8826A' }, mouthG);
    var smile = el('path', { fill: 'none', stroke: COL.line, 'stroke-width': 5, 'stroke-linecap': 'round' }, mouthG);
    var earArcs = [
      el('path', { d: 'M0,-10 Q7.5,0 0,10', fill: 'none', stroke: COL.muted, 'stroke-width': 4, 'stroke-linecap': 'round' }, headG),
      el('path', { d: 'M10,-19 Q22,0 10,19', fill: 'none', stroke: COL.muted, 'stroke-width': 4, 'stroke-linecap': 'round' }, headG)
    ];
    var env = el('g', {}, bodyG);
    el('rect', { x: -27, y: -18, width: 54, height: 36, rx: 3.5, fill: COL.paper, stroke: COL.line, 'stroke-width': 3.2 }, env);
    el('path', { d: 'M-23.5,-14.5 L0,3.5 L23.5,-14.5', fill: 'none', stroke: COL.line, 'stroke-width': 3.2, 'stroke-linejoin': 'round', 'stroke-linecap': 'round' }, env);
    el('circle', { cx: 0, cy: 3, r: 6.8, fill: COL.gill, stroke: COL.line, 'stroke-width': 2.4 }, env);
    var arms = [-1, 1].map(function () {
      return el('rect', { x: -PAW_W / 2, y: -PAW_H / 2, width: PAW_W, height: PAW_H, rx: PAW_W / 2, ry: PAW_H / 2, fill: COL.paw }, bodyG);
    });
    var dots = [0, 1, 2].map(function () { return el('circle', { r: 9, fill: COL.muted }, svg); });
    var zs = [0, 1, 2].map(function () {
      var z = el('text', { 'font-family': 'ui-rounded, "Hiragino Maru Gothic ProN", "Arial Rounded MT Bold", system-ui, sans-serif', 'font-weight': 800, fill: COL.muted, 'text-anchor': 'middle' }, svg);
      z.textContent = 'z';
      return z;
    });
    container.appendChild(svg);

    function vyOf(Q) { return LEG_L * Q.legExt + Q.hop - Q.hy; }   // how high the head is (for gill drag)
    function openOf(q) { return clamp(q.open, 0, 1) * (1 - clamp(q.arcMix, 0, 1)); }

    function render(t, s) {
      s = s || {};
      t = +t || 0;
      var P = poseAt(t, s, seed);           // body
      var EL = poseAt(t + 0.04, s, seed);   // eyes lead
      var ER = poseAt(t + 0.012, s, seed);
      // no wink: while the eyes are closing / closed / just opening, the right eye blends onto the left eye's sample
      var FT = poseAt(t + 0.3, s, seed), PB = poseAt(t - 0.15, s, seed);
      var wO = 1 - sm(0.45, 0.62, Math.min(openOf(FT), openOf(PB), openOf(P)));
      if (wO >= 0.999) ER = EL; else if (wO > 0.001) ER = mix(ER, EL, wO);
      var HD = poseAt(t - 0.035, s, seed);  // head follows the body a touch
      var AL = poseAt(t - 0.06, s, seed);   // paws follow through
      var AR = poseAt(t - 0.11, s, seed);
      var LG = poseAt(t - 0.08, s, seed);   // feet, letter
      var GT = poseAt(t - 0.14, s, seed);   // gills + tail drag behind the most
      var bl = blink(t, seed) * (1 - clamp(+s.sleepy || 0, 0, 1));

      var sy = 1 - P.sq, sxq = 1 + P.sq * 0.85;
      var flip = P.flip; flip = (flip < 0 ? -1 : 1) * (0.44 + 0.56 * Math.abs(flip));
      var faceVis = sm(0.25, 0.5, P.flip);
      var backness = sm(0.2, 0.85, -P.flip);
      var legExt = clamp(P.legExt, 0, 1.1);
      var tiltRad = P.tilt * Math.PI / 180, sT = Math.sin(tiltRad), cT = Math.cos(tiltRad);
      var bodyBottom = -LEG_L * legExt - Math.max(0, P.hop);
      if (P.hop < 0) bodyBottom -= P.hop;
      var lowDrop = Math.abs(sT) * (TWB / 2) * sxq;
      bodyBottom -= Math.max(0, bodyBottom + lowDrop * 0.85);
      var xo = P.x + XOFF * clamp(P.flip, -1, 1);

      var air = clamp(P.hop / 220, 0, 0.8);
      var tcv = clamp(P.tc, 0, 1);
      A(shadow, 'rx', f((128 - 18 * tcv) * sxq * (1 - air * 0.8)));
      A(shadow, 'ry', f(14 * (1 - air * 0.5)));
      A(shadow, 'cx', f(xo + flip * (22 - 14 * tcv) * (1 - backness)));
      A(shadow, 'opacity', f(1 - air * 1.1));
      var gl = energy(t, s, false);
      A(glow, 'opacity', f((0.06 + 0.4 * gl) * glowMul));
      A(glow, 'r', f(230 + 30 * gl + 6 * Math.sin(t * 1.6)));

      A(rootG, 'transform', 'translate(' + f(xo) + ',0)');
      for (var i = 0; i < 2; i++) {
        var lx = FOOT_X[i] * sxq * Math.abs(flip) * (flip < 0 ? -1 : 1);
        var lift = Math.max(0, LG['f' + i]);
        var attachY = bodyBottom + lx * sT;
        var top = attachY - 18;
        // on the ground the foot reaches the floor; in the air it dangles (never below the floor)
        var ground = Math.min(0, attachY + LEG_L * Math.max(1.6, legExt) + 5);
        var dangle = attachY + LEG_L * (0.95 + 0.1 * Math.cos(t * 9 + i)) + 5;
        var bot = Math.min(0, lerp(ground, dangle, sm(0, 10, P.hop))) - lift;
        A(feet[i], 'd', footPath(lx * cT + (i ? 3 : -3), top, bot, FOOT_W * Math.max(0.6, Math.abs(flip))));
      }
      A(bodyG, 'transform', 'translate(0,' + f(bodyBottom) + ') rotate(' + f(P.tilt) + ') scale(' + f(sxq * flip) + ',' + f(sy) + ')');
      A(torso, 'fill', mixCol(COL.body, COL.backBody, backness));
      A(head, 'fill', mixCol(COL.head, COL.back, backness));
      A(belly, 'opacity', f(faceVis));
      A(face, 'opacity', f(faceVis));
      A(tailBack, 'opacity', f(backness));

      // head: its own small tilt + bob, lagging the body
      var hr = HD.hr + 0.35 * (HD.tilt - P.tilt), hy = HD.hy;
      A(headG, 'transform', 'translate(0,' + f(hy) + ') rotate(' + f(hr) + ',0,' + f(HBOT) + ')');

      // tail (+ its soft fin behind)
      var tOp = f(1 - backness);
      A(tailFin, 'd', tailPath(GT, 1)); A(tailFin, 'opacity', tOp);
      A(tail, 'd', tailPath(GT, 0)); A(tail, 'opacity', tOp);

      // gills: three fronds a side (long middle). spread / fold / flutter / think ripple / hook,
      // plus drag from vertical velocity (they trail down as it rises and lift as it drops), per-side delay
      var fl = Math.max(0, GT.gfl), thk = clamp(GT.thk, 0, 1), glen = GT.glen;
      var vNow = vyOf(P);
      var flopL = clamp(-(vNow - vyOf(AL)) / 0.06 * 0.075, -24, 20);
      var flopR = clamp(-(vNow - vyOf(AR)) / 0.11 * 0.075, -24, 20);
      var dark = 1 - sm(0.1, 0.4, gl);
      gills.forEach(function (Gi) {
        var G = Gi.G, sx = Gi.sx, i = Gi.i;
        var spread = sx < 0 ? GT.gsL : GT.gsR, flop = sx < 0 ? flopL : flopR;
        var hk = i === 0 ? clamp(sx < 0 ? GT.hkL : GT.hkR, 0, 1) : 0;
        var ph = i * 1.1 + (sx < 0 ? 0 : 2.3);
        var ang = G.a + spread * (i === 0 ? 1.15 : i === 1 ? 1 : 0.8)
          + 3 * Math.sin(2 * Math.PI * t / 3.1 + ph)
          + fl * 9 * Math.sin(2 * Math.PI * 5.2 * t + ph)
          + thk * 12 * Math.sin(2 * Math.PI * t / 1.2 - i * 1.3 - (sx < 0 ? 0 : 1.9))
          + flop * (0.8 + 0.15 * i) + 22 * hk;
        var bend = 9 + 0.9 * flop - 175 * hk;     // hook: up, then over and down on the outside, like a '?'
        var L = G.L * glen * (1 - 0.15 * clamp(-spread / 50, 0, 1)) * (1 + 0.5 * hk);
        var sw = G.w * (1 - 0.3 * hk);
        var hl = Math.max(3, (L - sw / 2 + 3) / 3);
        // centreline: three equal steps whose direction turns by bend/2 each (a cubic that curls evenly)
        var a0 = ang * Math.PI / 180, a1 = (ang + bend * 0.5) * Math.PI / 180, a2 = (ang + bend) * Math.PI / 180;
        var x0 = sx * (HW / 2 + G.ax), y0 = G.ay;
        var x1 = x0 + sx * Math.cos(a0) * hl, y1 = y0 - Math.sin(a0) * hl;
        var x2 = x1 + sx * Math.cos(a1) * hl, y2 = y1 - Math.sin(a1) * hl;
        var x3 = x2 + sx * Math.cos(a2) * hl, y3 = y2 - Math.sin(a2) * hl;
        A(Gi.e, 'd', 'M' + f(x0) + ',' + f(y0) + 'C' + f(x1) + ',' + f(y1) + ' ' + f(x2) + ',' + f(y2) + ' ' + f(x3) + ',' + f(y3));
        A(Gi.e, 'stroke-width', f(sw));
        A(Gi.e, 'stroke', mixCol(COL[G.c], COL.gillLit, 0.55 * dark));
      });

      [EL, ER].forEach(function (E, j) {
        var e = eyes[j];
        var open = clamp(E.open * (1 - bl), 0, 1), sc = E.escale, mixA = clamp(E.arcMix, 0, 1);
        var h = Math.max(4.5, EYE_H * sc * open * (1 - 0.85 * sm(0.15, 0.6, mixA)));
        var w = EYE_W * (0.92 + 0.1 * sc) * (1 + 0.12 * (1 - open));
        var bottom = EYE_CY + EYE_H * sc / 2 - (1 - open) * EYE_H * 0.4;
        var ex = e.sx * EYE_X + E.gx, ey = E.gy;
        A(e.g, 'transform', 'translate(' + f(ex) + ',' + f(ey) + ')');
        A(e.rect, 'x', f(-w / 2)); A(e.rect, 'width', f(w));
        A(e.rect, 'y', f(bottom - h)); A(e.rect, 'height', f(h));
        A(e.rect, 'rx', f(Math.min(w / 2, h / 2)));
        A(e.rect, 'opacity', f(1 - sm(0.45, 0.75, mixA)));
        var a = E.arc, aw = 12.5;
        A(e.arc, 'd', 'M' + f(-aw) + ',' + f(EYE_CY + 4 + a * 6) + ' Q0,' + f(EYE_CY + 4 - a * 15) + ' ' + f(aw) + ',' + f(EYE_CY + 4 + a * 6));
        A(e.arc, 'opacity', f(sm(0.4, 0.75, mixA)));
        A(e.hl, 'x', f(-w / 2 + 4.5)); A(e.hl, 'y', f(bottom - h + 4.5));
        A(e.hl, 'opacity', f(sm(0.2, 0.5, E.hi) * sm(0.5, 0.8, open) * (1 - sm(0.2, 0.5, mixA)) * sm(11, 17, h)));
      });

      var excite = clamp((energy(t, s, true) - 0.5) / 0.45, 0, 1);
      var bo = clamp(0.25 + 0.55 * excite + P.blush, 0, 1);
      A(blushL, 'opacity', f(bo * 0.9)); A(blushR, 'opacity', f(bo * 0.9));
      A(blushL, 'cx', f(-EYE_X - 17 + EL.gx * 0.4)); A(blushR, 'cx', f(EYE_X + 17 + EL.gx * 0.4));

      var m = clamp(P.mouth, 0, 1.2);
      var mw = (12 + 9 * m) * P.mw, mh = (5 + 24 * m) * Math.max(0.2, P.mh);
      A(mouthG, 'transform', 'translate(' + f(EL.gx * 0.5) + ',' + f(MOUTH_Y + EL.gy * 0.4) + ')');
      var mo = m > 0.04 ? 1 : 0;
      var topY = -2 - 3 * P.smile - 9 * P.mtop * sm(0.05, 0.3, m);
      A(mouth, 'd', 'M' + f(-mw) + ',0 Q0,' + f(topY) + ' ' + f(mw) + ',0 C' + f(mw) + ',' + f(mh * 1.25) + ' ' + f(-mw) + ',' + f(mh * 1.25) + ' ' + f(-mw) + ',0 Z');
      A(mouth, 'opacity', mo);
      A(tongue, 'cy', f(mh * 0.78));
      A(tongue, 'rx', f(mw * 0.55)); A(tongue, 'ry', f(Math.max(0, mh * 0.18)));
      A(tongue, 'opacity', f(mo * clamp(sm(0.35, 0.6, m) * P.mtg, 0, 1)));
      var so = clamp(P.smile, 0, 1) * (1 - sm(0.03, 0.12, m));
      var sw = 10 + 8 * P.smile;
      A(smile, 'd', 'M' + f(-sw) + ',' + f(-2) + ' Q0,' + f(-2 + 13 * P.smile) + ' ' + f(sw) + ',' + f(-2));
      A(smile, 'opacity', f(so));

      var envS = clamp(LG.env, 0, 1.3);
      if (envS < 0.01) envS = 0;
      A(env, 'transform', 'translate(' + f(LG.ex / sxq) + ',' + f(LG.ey / sy) + ') scale(' + f(envS / (sxq * flip)) + ',' + f(envS / sy) + ') rotate(' + f(LG.er - P.tilt) + ')');
      A(env, 'opacity', envS > 0 ? 1 : 0);

      var armOp = f(1 - backness);
      [AL, AR].forEach(function (Q, j) {
        var x = j ? Q.rx : Q.lx, y = j ? Q.ry : Q.ly, r = j ? Q.rr : Q.lr;
        var ext = clamp(j ? Q.rext : Q.lext, 0, 40), sz = clamp(j ? Q.rsz : Q.lsz, 0.5, 2.2);
        var w = PAW_W * sz, h = PAW_H * sz + ext;
        A(arms[j], 'transform', 'translate(' + f(x) + ',' + f(y) + ') rotate(' + f(r) + ')');
        A(arms[j], 'x', f(-w / 2)); A(arms[j], 'width', f(w));
        A(arms[j], 'y', f(-h / 2)); A(arms[j], 'height', f(h));
        A(arms[j], 'rx', f(w / 2)); A(arms[j], 'ry', f(Math.min(w, h) / 2));
        A(arms[j], 'opacity', armOp);
      });

      // listen: sound arcs just past the tips of the near gill fan; the side only flips while they are faded out
      var lisv = clamp(P.lis, -1, 1), lisA = Math.abs(lisv) * faceVis;
      var earSide = lisv < 0 ? -1 : 1;
      earArcs.forEach(function (p, j) {
        var ph = ((t / 1.5 - j * 0.28) % 1 + 1) % 1;
        var o = lisA > 0.02 ? lisA * lisA * (0.35 + 0.65 * Math.sin(Math.PI * ph)) : 0;
        A(p, 'transform', 'translate(' + f(earSide * (HW / 2 + 50 + 3 * ph)) + ',' + f(HCY - 44) + ') scale(' + earSide + ',1)');
        A(p, 'opacity', f(o * 0.85));
      });

      var th = clamp(P.thk, 0, 1) * faceVis;
      var headTop = bodyBottom + (HTOP - 6) * sy + P.hy;
      dots.forEach(function (d, j) {
        var ph = ((t / 1.2 - j * 0.18) % 1 + 1) % 1;
        var b = bump(ph, 0, 0.42);
        A(d, 'cx', f(xo - 36 + 28 * j));
        A(d, 'cy', f(headTop - 30 - 11 * b));
        A(d, 'r', f(8 + 2.5 * b));
        A(d, 'opacity', f(th > 0.02 ? th * (0.45 + 0.55 * b) : 0));
      });

      var sl = clamp(P.zz, 0, 1);
      zs.forEach(function (z, j) {
        var p = ((t / 2.6 + j / 3) % 1 + 1) % 1;
        var zo = sl * Math.sin(Math.PI * p) * (sl > 0.02 ? 1 : 0);
        A(z, 'x', f(xo + 72 + 40 * p + 7 * Math.sin(t * 2 + j)));
        A(z, 'y', f(HTOP + 16 - 50 * p));
        A(z, 'font-size', f(24 + 16 * p));
        A(z, 'opacity', f(zo));
      });
    }

    var api = { el: svg, render: render };
    render(0, { mood: 'watch', since: 0 });
    return api;
  }

  root.LanternRig = { create: create, MOODS: MOODS.slice(), glowOf: glowOf, version: 'v3-mizuchi-final' };
})(typeof window !== 'undefined' ? window : this);
