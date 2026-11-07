// ふすまごし ─ 台所の画面(WebSocket で端末のイベントを受けて、通話明細に記帳する)
const $ = (id) => document.getElementById(id);
const esc = (s) => String(s ?? "").replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
const clamp = (v, a, b) => Math.max(a, Math.min(b, v));

// 1920x1080 の舞台を窓に合わせて縮める(録画は 1920x1080 そのまま)
function fit() {
  const s = Math.min(innerWidth / 1920, innerHeight / 1080);
  $("stage").style.transform = `translate(${(innerWidth - 1920 * s) / 2}px, ${(innerHeight - 1080 * s) / 2}px) scale(${s})`;
}
addEventListener("resize", fit); fit();

const S = { call: null, utts: [], marks: [], listener: null, rebuttal: null, decision: null, dialog: null, turn: null,
  chars: 0, state: "idle", models: {}, lastLine: "", st: null, thinking: null };
const STAGES = {
  scam: ["接触", "信頼形成", "要求", "約束", "口止め"],
  solicitation: ["案内", "強い勧め", "申込の約束", "支払い・定期購入の約束"],
};
const TRACK = { scam: "詐欺のおそれ", solicitation: "勧誘・契約", normal: "ふつうの電話", unknown: "まだ分からない" };
const ACTION = { silent: "黙って記録", evening: "夕方の便り", immediate: "今すぐ家族へ" };
const ACTION_MAIN = { silent: "黙って記録。", evening: "夕方の便りへ。", immediate: "今すぐ家族へ。" };
const ACTION_WHEN = { silent: "知らせない", evening: "18:00 の便り", immediate: "いま、便りで" };
const GENUINE = { low: "低い", medium: "中くらい", high: "高い" };
const RESP = { refused: "断った", promised: "約束した", disclosed: "話した", undecided: "保留", unknown: "" };
const KIND = { did: "したこと", want: "やりたいこと", concern: "気になること", plan: "予定" };
const WEEK = ["日", "月", "火", "水", "木", "金", "土"];
const SRC = (url) => (url || "").includes("caa.go.jp") ? "消費者庁" : (url || "").includes("kokusen") ? "国民生活センター" : (url || "").includes("npa.go.jp") ? "警察庁" : (url || "").includes("zenginkyo") ? "全国銀行協会" : "出典";
const short = (s, n) => { s = String(s || ""); return s.length > n ? s.slice(0, n - 1) + "…" : s; };
// 長い文は、文の終わりか読点で切る(語の途中で切らない)
const clip = (s, n) => {
  s = String(s || "");
  if (s.length <= n) return s;
  const head = s.slice(0, n);
  const end = Math.max(head.lastIndexOf("。"), head.lastIndexOf("？"));
  if (end >= n * .5) return s.slice(0, end + 1);
  const comma = head.lastIndexOf("、");
  return comma >= n * .4 ? s.slice(0, comma + 1) + "…" : short(s, n);
};
const secOf = (c) => { const p = String(c || "0:0:0").split(":").map(Number); return p[0] * 3600 + p[1] * 60 + (p[2] || 0); };
const pad = (n) => String(n).padStart(2, "0");
const hm = (sec) => { sec = ((sec % 86400) + 86400) % 86400; return `${pad(Math.floor(sec / 3600))}:${pad(Math.floor(sec / 60) % 60)}`; };
const hms = (sec) => { sec = ((Math.round(sec) % 86400) + 86400) % 86400; return `${hm(sec)}:${pad(sec % 60)}`; };
const signed = (v) => v == null || isNaN(v) ? "—" : v > 0.5 ? `+${Math.round(v)}` : v < -0.5 ? `−${Math.abs(Math.round(v))}` : "±0";
const fact = (dt, dd, small = "") => `<div><dt>${dt}</dt><dd>${dd}${small ? `<small>${small}</small>` : ""}</dd></div>`;
const sec = (lab, body, cls = "", note = "") => `<div class="sec ${cls}"><div class="lab"><h2>${lab}</h2>${note ? `<div class="lab-note">${note}</div>` : ""}</div><div class="body">${body}</div></div>`;

// ---------------- 日付 ----------------
function today() { return S.call?.date || new Date(); }
function dateRender() {
  const d = today();
  $("rDate").textContent = `${d.getMonth() + 1}月${d.getDate()}日(${WEEK[d.getDay()]})`;
}

// ---------------- 右: いまの様子・行灯 ----------------
// 通話中は灯りを落とす(0.05)。灯るのは電話のあと、声をかけるとき
const GLOW = { idle: .62, ringing: .3, dialing: .3, in_call: .05, ended: .34, speaking: .96, after: .5 };
const IN_CALL = ["ringing", "dialing", "in_call"];
function setStatus(st) {
  S.state = st;
  const g = GLOW[st] ?? .6;
  document.documentElement.style.setProperty("--glow", g);
  document.body.classList.toggle("incall", IN_CALL.includes(st));
  document.body.classList.toggle("speaking", st === "speaking");
  const group = IN_CALL.includes(st) ? "call" : ["ended", "speaking", "after"].includes(st) ? "after" : "idle";
  document.querySelectorAll("#status li").forEach((el) => el.classList.toggle("on", el.dataset.s === group));
  $("speaker").textContent = st === "speaking" ? "声に出しています" : "";
  if (st !== "speaking") captionRender();
  dialogRender();
}
function captionSet(main, small = "", cls = "") {
  const el = $("andonCaption");
  el.className = cls;
  el.style.fontSize = "";
  el.innerHTML = main + (small ? `<small>${small}</small>` : "");
}
function captionRender() {
  const st = S.state;
  if (st === "idle") return captionSet(S.decision?.action === "silent" && S.call ? "ふつうの電話でした。" : "いつもの台所。",
    S.decision?.action === "silent" && S.call ? "何も言わず、記録だけ残します。" : "電話が鳴ったら、黙って聞きます。", "m quiet");
  if (st === "ringing") return captionSet("電話が鳴っています。", "ここからは、光らない・話さない。", "m quiet");
  if (st === "dialing") return captionSet("電話をかけています。", "ここからは、光らない・話さない。", "m quiet");
  if (st === "in_call") return captionSet("通話中は、<br>光らない・話さない。", "聞いているのは、祖母の声だけ。", "m quiet");
  if (st === "ended") return captionSet("電話が終わりました。", "台所が静かになってから、声をかけます。", "m quiet");
  if (st === "after" && S.lastSaid) return spoken(S.lastSaid, true);
}
function spoken(text, past = false) {
  // 文ごとに行を改める。文の中で折るときは、文節の切れ目で(word-break: auto-phrase)
  const sents = String(text).split(/(?<=[。？！?!])/).map((x) => x.trim()).filter(Boolean);
  const n = String(text).length;
  captionSet(`「${sents.map(esc).join("<br>")}」`, "", (n <= 24 ? "" : n <= 44 ? "m" : "s") + " said" + (past ? " quiet" : ""));
}
function dialogRender() {
  const el = $("dialog"), st = S.state;
  if (IN_CALL.includes(st)) { el.innerHTML = `<div class="note">祖母の声は、この Mac の中だけで文字にしています。音声は、外に出しません。</div>`; return; }
  const d = S.dialog;
  if (!d || !d.history?.length) {
    el.innerHTML = st === "ended" ? (S.decision ? `<div class="note">判断が出ました。台所が静かになったら、声をかけます。</div>` : `<div class="note">まとめ役の判断を待っています。話しかけるのは、それから。</div>`)
      : `<div class="note">話しかけるのは、電話のあとだけ。聞いたことは、お話のあとで消します。</div>`;
    return;
  }
  if (d.purged) { el.innerHTML = `<div class="note">電話のあとのお話は、短い要約をカルテに残して、消しました。</div>`; return; }
  const last = d.history[d.history.length - 1];
  const lastG = [...d.history].reverse().find((h) => h.who === "grandma");
  const reply = last.who === "fusuma" && !d.done
    ? `<div class="reply"><b>おばあちゃん</b><span class="blank">お返事を待っています</span></div>`
    : lastG ? `<div class="reply"><b>おばあちゃん</b><span class="said">「${esc(short(lastG.text, 30))}」</span></div>` : "";
  const intent = S.turn?.intent || "ask_what";
  const cur = d.done ? 3 : ["ask_what", "ask_detail"].includes(intent) ? 0 : intent === "ask_consent" ? 1 : 2;
  const steps = ["さっきの電話のこと", "家族に話していい?", "いつもの話へ"];
  const next = steps.map((s, i) => `<span class="${i === cur ? "cur" : i < cur ? "done" : ""}"><span class="t-num">${i + 1}</span>${s}</span>`).join("");
  el.innerHTML = reply + `<div class="next">${next}</div>`;
}

// 台所の音(静かなときだけ話しかける)
const levels = new Array(90).fill(-60);
let meterT = 0;
function level(db) {
  levels.shift(); levels.push(db);
  const now = performance.now();
  if (now - meterT < 90) return;
  meterT = now;
  const step = 712 / levels.length;            // 0.1 秒ごとの音の大きさを、中心線から上下に
  $("meterPath").setAttribute("d", levels.map((v, i) => {
    const x = (i * step + step / 2).toFixed(1), h = clamp((v + 62) * .62, .6, 20).toFixed(1);
    return `M${x} ${22 - h}V${22 + +h}`;
  }).join(""));
}

// ---------------- 右: 行灯の画面(みずち) ----------------
// Pi のキオスク(lantern/kiosk.js)と同じ rig.js を、中継(fusuma/lantern_bridge.py)と同じ決め方で動かす
const MOOD_JA = { watch: "見守り", call: "通話中", after: "電話のあと", listen: "聞いている", letter: "便り", touched: "さわられた", think: "考え中" };
const LN = { mood: "watch", dialog: false, inCall: false, sus: 0, ask: 0, awaiting: false, speech: null, letterBack: null };
const LS = { mood: "watch", since: 0, prev: "watch", speak: 0, gaze: 0, touchAt: null, touchN: 0, nodAt: null, letterAt: null, sleepy: 0, sus: 0, ask: 0 };
const lnow = () => performance.now() / 1000;
const rig = window.LanternRig ? LanternRig.create($("mizuchi"), { seed: 7 }) : null;
function lnMood(m) {
  if (m === LS.mood) return;
  const t = lnow();
  LS.prev = LS.mood; LS.mood = m; LS.since = t; LN.mood = m;
  if (m !== "listen") LS.nodAt = null;
  if (m === "letter") { LS.letterAt = t + 0.25; LN.letterBack = t + 7.5; } else LN.letterBack = null;
  if (m === "call") { LN.speech = null; LN.awaiting = false; }
  $("moodName").textContent = MOOD_JA[m] || m;
}
function mouthEnv(text, dur, hz = 20) {   // 話す文のモーラ数から口の開き(0〜1)を作る(中継の mouth_envelope と同じ考え方)
  const PAUSE = { "、": .18, "。": .3, "？": .3, "?": .3, "！": .3, "!": .3, "…": .3 };
  const units = [];
  for (const ch of String(text)) {
    if (PAUSE[ch]) units.push(["p", PAUSE[ch]]);
    else if (/[ぁぃぅぇぉゃゅょゎっァィゥェォャュョヮッ]/.test(ch)) continue;
    else if (/[ぁ-んァ-ヶー]/.test(ch)) units.push(["m", ch === "ー" ? .75 : 1]);
    else if (/[一-鿿]/.test(ch)) units.push(["m", 1.6]);
    else if (/[A-Za-z0-9]/.test(ch)) units.push(["m", 1]);
  }
  const n = Math.max(1, Math.round(dur * hz)), env = new Array(n).fill(0);
  const pt = units.filter((u) => u[0] === "p").reduce((a, u) => a + u[1], 0), mt = units.filter((u) => u[0] === "m").reduce((a, u) => a + u[1], 0);
  if (!mt || dur <= 0) return env;
  const pScale = pt ? Math.min(pt, dur * .35) / pt : 0, perM = (dur - pt * pScale) / mt;
  let t = 0;
  units.forEach(([k, v], i) => {
    const len = k === "p" ? v * pScale : v * perM;
    if (k === "m") for (let j = Math.floor(t * hz); j < Math.min(n, Math.ceil((t + len) * hz)); j++) env[j] = Math.max(env[j], Math.sin(Math.PI * clamp((j / hz - t) / len, 0, 1)) * (.62 + .3 * ((i * 7) % 5) / 4));
    t += len;
  });
  return env;
}
function lanternOn(ev) {
  const t = ev.type;
  if (t === "state") {
    if (["ringing", "dialing", "in_call"].includes(ev.state)) { LN.dialog = false; if (!LN.inCall) { LN.sus = 0; LN.ask = 0; } LN.inCall = true; lnMood("call"); }
    else if (["ended", "idle"].includes(ev.state)) { if (LN.inCall) LN.sus = 0; LN.inCall = false; lnMood("watch"); }
  } else if (t === "listener" && LN.inCall && !ev.final) {
    const o = ev.out || {};
    LN.sus = Math.max({ low: .15, medium: .6, high: 1 }[o.risk] || 0, Math.min(1, +o.score || 0));
    LN.ask = Math.min(1, (o.to_ask || []).length / 2) * (o.risk === "low" ? .4 : 1);
  } else if (t === "thinking" && !LN.inCall && !LN.dialog) lnMood("think");
  else if (t === "decision" && !LN.inCall) { lnMood("watch"); LN.sus = 0; LN.ask = (ev.decision || {}).action && ev.decision.action !== "silent" ? 1 : 0; }
  else if (t === "speak") {
    LN.sus = 0; LN.ask = 0; lnMood("after");
    const dur = +ev.dur || 0;
    LN.speech = { t0: lnow(), dur, hz: 20, env: mouthEnv(ev.text || "", dur), then: LN.dialog ? "listen" : "watch" };
  } else if (t === "speak_stopped") { LN.speech = null; lnMood("call"); }
  else if (t === "dialog") { LN.dialog = true; LN.awaiting = true; if (!LN.speech) lnMood("listen"); }
  else if (t === "room_utt" && LN.dialog) { if (LS.mood !== "listen") lnMood("listen"); LS.nodAt = lnow() + .05; }
  else if (["dialog_done", "dialog_closed", "dialog_skipped", "reset"].includes(t)) { LN.dialog = false; LN.sus = 0; LN.ask = 0; LN.awaiting = false; lnMood("watch"); }
  else if (t === "letter") lnMood("letter");
}
function speakLevel(t) {
  const sp = LN.speech;
  if (!sp) return 0;
  const x = (t - sp.t0) * sp.hz;
  if (x >= sp.env.length || t > sp.t0 + sp.dur + .15) { LN.speech = null; lnMood(LN.awaiting || sp.then === "listen" ? "listen" : sp.then || "watch"); return 0; }
  const i = Math.floor(x), f = x - i, a = sp.env[i] || 0, b = sp.env[i + 1] || 0;
  return a + (b - a) * f;
}
const C_DAY = [244, 241, 234], C_MID = [91, 74, 62], C_NIGHT = [20, 17, 14];
function paintScreen(g) {   // 画面の明るさ(0〜1)から背景の色: 昼のアイボリー → 温かい茶色 → ほとんど黒(通話中)
  let k = clamp((g - .03) / .4, 0, 1); k = k * k * (3 - 2 * k);
  const c = C_DAY.map((d, i) => Math.round(k < .5 ? C_NIGHT[i] + (C_MID[i] - C_NIGHT[i]) * k * 2 : C_MID[i] + (d - C_MID[i]) * (k - .5) * 2));
  const hi = c.map((v, i) => Math.min(255, v + Math.round(7 * k * [1, .85, .6][i])));
  $("screen").style.background = `radial-gradient(ellipse 75% 70% at 50% 46%, rgb(${hi}) 0%, rgb(${c}) 72%)`;
  $("floor").style.opacity = (.25 + .75 * k).toFixed(3);
  rig.el.style.opacity = (.35 + .65 * Math.min(1, g / .5)).toFixed(3);
}
let lnLast = 0;
function lanternFrame() {
  requestAnimationFrame(lanternFrame);
  const t = lnow();
  if (t - lnLast < 1 / 30) return;
  lnLast = t;
  if (LN.letterBack && t > LN.letterBack) lnMood("watch");
  LS.sus += (LN.sus - LS.sus) * .03; LS.ask += (LN.ask - LS.ask) * .03;
  LS.speak = speakLevel(t);
  rig.render(t, LS);
  paintScreen(LanternRig.glowOf(t, LS));
}
if (rig) { LS.since = lnow(); requestAnimationFrame(lanternFrame); }

// ---------------- 左: 通話明細 ----------------
const PRIVATE = /住所|番地|丁目|号室|郵便番号|電話番号|口座|暗証|カード番号|生年月日/;
const PX = 7.2;                                // 間と声の横棒: 1 秒あたりの長さ
function clockOffset() {                       // 耳の時刻(秒) → 壁の時計(秒)
  const u = S.utts.find((x) => x.clock);
  return u ? secOf(u.clock) - u.t : null;
}
function uttAt(clock) {                        // 聞き役の「発話の時刻」から、その発話を探す
  const off = clockOffset();
  if (off == null || !clock) return -1;
  const te = secOf(clock) - off;
  let best = -1, bd = 1e9;
  S.utts.forEach((u, i) => { const d = Math.abs(u.t - te); if (d < bd && d < 2.5) { bd = d; best = i; } });
  return best;
}
function headRender() {
  const c = S.call;
  if (!c) {
    const st = S.st;
    $("headLab").textContent = "記録";
    $("title").textContent = "台所の記録";
    $("callId").textContent = "";
    const calls = (st?.calls || []).filter((x) => x.karte);
    const memos = (st?.memos || []).filter((m) => !m.secret);
    $("facts").innerHTML = fact("通話カルテ", `${calls.length} 件`) + fact("暮らしのメモ", `${memos.length} 件`)
      + fact("文字起こし", "聞き取りのあとに消す") + fact("音声", "外に出さない");
    return;
  }
  $("headLab").textContent = "通話";
  $("title").textContent = "通話明細";
  $("callId").textContent = c.id ? `No. ${c.id.slice(4, 8)}-${c.id.slice(9, 13)}` : "";
  const t0 = c.clock0 ? c.clock0.slice(0, 8) : "";
  const span = c.clockEnd ? `${t0} – ${c.clockEnd.slice(0, 8)}` : `${t0} –`;
  const mins = c.mins ? `約 ${c.mins} 分` : "通話中";
  $("facts").innerHTML = fact("時間", `<span class="t-num">${span}</span>`, mins)
    + fact("方向", c.direction === "outgoing" ? "かけた電話" : "かかってきた電話")
    + fact("名乗り", c.caller ? esc(c.caller) : "—", "祖母のことばから")
    + fact("聞いたもの", "祖母の声だけ", "相手の声は聞かない");
}
function sheetRender() {
  headRender();
  if (!S.call) return indexRender();
  const utts = S.utts, t0 = S.call.t0;
  // 間(沈黙)を数える。秒数は耳が測った「直前の間」(pre_pause)を使う(小計の 5 秒以上の回数・最長の沈黙と一致させる)
  let prevE = t0;
  const gaps = utts.map((u) => { const g = u.pre_pause ?? (u.t - prevE); prevE = Math.max(prevE, u.end); return g; });
  let maxI = -1;
  gaps.forEach((g, i) => { if (i > 0 && g >= 6 && (maxI < 0 || g > gaps[maxI])) maxI = i; });
  // 聞き役が見つけた断りの言葉 / 小さな声での約束。文字起こしを消したあとも、注記は同じ発話に残す
  const acts = (S.listener?.speech_acts || []).map((a) => ({ ...a, i: uttAt(a.t) })).filter((a) => a.i >= 0);
  if (acts.length) {
    const refusals = acts.filter((a) => a.kind === "refusal");
    const lastRef = refusals[refusals.length - 1];
    const pros = acts.filter((a) => a.kind === "promise" && (!lastRef || a.i > lastRef.i));
    const promise = pros.find((a) => /お願い|頼|ください/.test(a.text || "")) || pros[0];
    S.redI = { ref: lastRef?.i, pro: promise?.i };
  }
  const R = S.redI || {};
  const refRow = {};
  (S.refs || []).forEach((r) => {             // まとめ役が見つけた前の記録と、つながる発話
    if (r.i == null || r.i < 0) r.i = S.utts.findIndex((u) => u.text && r.keys.some((kw) => kw && u.text.includes(kw)));
    if (r.i >= 0) (refRow[r.i] = refRow[r.i] || []).push(r.n);
  });
  // 聞き役が読んだ段階を、読んだ時点の行の前に差し込む
  const off = clockOffset();
  const marksAt = {};
  S.marks.forEach((m, j) => {
    const k = utts.filter((u) => u.end <= m.t + 0.05).length;
    (marksAt[k] = marksAt[k] || []).push({ ...m, j });
  });
  const live = S.call.tEnd == null;
  const stageRow = (m) => `<tr class="stg${live && m.j === S.marks.length - 1 ? " cur" : ""}"><td colspan="6">聞き役が読んだ段階<b>${esc(m.stage)}</b>${off != null ? `<span class="t-num">${hms(m.t + off)}</span>` : ""}</td></tr>`;
  const rows = [];
  utts.forEach((u, i) => {
    (marksAt[i] || []).forEach((m) => rows.push(stageRow(m)));
    const g = gaps[i], db = u.db_rel;
    const long = i > 0 && g >= 5, max = i === maxI;
    const ow = clamp(g, 0, 16) * PX, vw = Math.max(3, clamp(u.end - u.t, 0, 12) * PX);
    const vh = clamp(5 + ((db ?? 0) + 13) * .55, 3, 16);
    const bar = `<div class="span">${g > .25 ? `<i class="o${long ? " long" : ""}${max ? " max" : ""}" style="width:${ow.toFixed(1)}px"></i>` : ""}<i class="g" style="width:${vw.toFixed(1)}px;height:${vh.toFixed(1)}px"></i></div>`;
    let words;
    if (!u.text) {                            // 文字起こしを消したあと: 言葉だけ消し、長さの形は残す
      const w = clamp((u.morae || (u.end - u.t) * 6) * 9, 18, 300);
      words = `<span class="gone" style="width:${w}px" title="消しました"></span>`;
    } else if (PRIVATE.test(u.text)) {        // 住所・番号などは、画面にも書きとめない
      words = `${esc(short(u.text.split(/[、,は]/)[0], 6))}…<span class="hide">(住所・番号は書きとめません)</span>`;
    } else words = esc(short(u.text, u.backchannel ? 10 : 22));
    const tags = [];
    if (u.backchannel) tags.push(`<span class="tag mute">あいづち</span><span class="tx mute">同意と数えない</span>`);
    if (max) tags.push(`<span class="tag shu">最長の沈黙</span>`);
    if (i === R.ref) tags.push(`<span class="tag shu">断り</span>${S.call.tEnd != null ? `<span class="tx">以後なし</span>` : ""}`);
    if (i === R.pro && (db ?? 0) <= -6) tags.push(`<span class="tag shu">約束</span><span class="tx">小さな声</span>`);
    (refRow[i] || []).forEach((n) => tags.push(`<span class="tag ref">※${n}</span>`));
    rows.push(`<tr class="${u.backchannel ? "bc" : ""}${u._new ? " new" : ""}">
      <td class="t">${esc((u.clock || "").slice(0, 8))}</td><td>${bar}</td>
      <td class="gap r${long ? " long" : ""}${max ? " max" : ""}">${g.toFixed(1)}</td><td class="v r">${signed(db)}</td>
      <td class="w">${words}</td><td class="nt">${tags.join("")}</td></tr>`);
    u._new = false;
  });
  (marksAt[utts.length] || []).forEach((m) => rows.push(stageRow(m)));
  const head = `<thead><tr><th style="width:92px">時刻</th><th style="width:206px">相手の時間 ／ 祖母の声</th><th class="r" style="width:64px">間 秒</th><th class="r" style="width:72px">声量 dB</th><th>祖母のことば${S.purgedLo ? " ─ 聞き取りのあとに消しました" : ""}</th><th style="width:186px">注記</th></tr></thead>`;
  const body = utts.length ? rows.join("") : `<tr><td colspan="6" class="nt" style="color:var(--ink-3)">${S.state === "ringing" || S.state === "dialing" ? "受話器をとるのを待っています" : "祖母が話すと、1 発話ずつ記帳します"}</td></tr>`;
  const legend = `<p><i class="sw o"></i>相手の時間<br>(推定)</p><p><i class="sw g"></i>祖母の声</p><p>声量 = いつもの声との差</p><p>相手の声は聞いていません</p>`;
  const closed = S.call.tEnd != null && utts.length ? " closed" : "";   // 通話が終わったら、明細を二重線で締める
  let html = sec("明細", `<div class="rows" id="rows"><table class="tbl${closed}">${head}<tbody>${body}</tbody></table></div>`, "detail", legend);
  html += refsHTML();
  html += tallyHTML();
  $("sheet").innerHTML = html;
  fitRows();
}
// 行が多いときは、行の高さを詰め、それでも入らなければ最新の行を見せる
function fitRows() {
  const box = $("rows");
  if (!box) return;
  const tb = box.querySelector("tbody");
  const avail = box.clientHeight - box.querySelector("thead").offsetHeight;
  const trs = [...tb.rows];
  const need = trs.reduce((a, r) => a + r.offsetHeight, 0);
  if (need > avail) {
    const f = Math.max(.66, avail / need);
    trs.forEach((r) => { [...r.cells].forEach((c) => (c.style.height = `${Math.floor(c.offsetHeight * f)}px`)); });
  }
  const need2 = trs.reduce((a, r) => a + r.offsetHeight, 0);
  if (need2 > avail) {
    let hidden = 0, h = need2;
    while (h > avail - 26 && hidden < trs.length - 1) { h -= trs[hidden].offsetHeight; trs[hidden].style.display = "none"; hidden++; }
    const n = trs.slice(0, hidden).filter((r) => !r.classList.contains("stg")).length;
    tb.insertAdjacentHTML("afterbegin", `<tr class="more"><td colspan="6">これより前の ${n} 行は、上に続いています</td></tr>`);
  }
}

function refsHTML() {
  const refs = S.refs || [];
  if (!refs.length) return "";
  const base = today();
  const ago = (d) => Math.max(0, Math.round((new Date(base.getFullYear(), base.getMonth(), base.getDate()) - new Date(d.getFullYear(), d.getMonth(), d.getDate())) / 864e5));
  const rows = refs.map((r) => `<div class="ref"><span class="n">※${r.n}</span><span class="d">${r.head} <span class="t-num">${r.d.getMonth() + 1}/${r.d.getDate()}</span>(${ago(r.d)} 日前)</span><span>${esc(r.lines.filter(Boolean).join(""))}</span></div>`).join("");
  return sec("照合", `<div class="refs">${rows}</div>`, "", "まとめ役が記憶から見つけた記録");
}

function tallyHTML() {
  const ma = S.ma;
  const proc = `<div class="proc" style="margin-top:14px"><b>耳</b>(この Mac の中だけ) 呼出音 YAMNet ・ 声の区切り Silero VAD ・ 文字起こし whisper.cpp ・ 声の様子 Praat(いつもの声と比べる)
    <div class="line">耳 → Claude に渡した、さいごの一行 ${esc(PRIVATE.test(S.lastLine) ? S.lastLine.replace(/「[^」]*」/, "「…(住所・番号は書きとめません)」") : S.lastLine || "—")}</div></div>`;
  if (!ma) return sec("小計", `<div class="sum"><div class="share"><span class="k">祖母の声 ／ 相手の時間</span><span class="v">—</span></div></div>${proc}`);
  const self = Math.round(ma.self_ratio * 100), other = Math.round(ma.other_ratio_est * 100);
  const lateZero = ma.refusal_late === 0 && ma.refusal_early > 0;
  const sum = `<div class="sum">
    <div class="share"><span class="k">${S.call.tEnd != null ? `約 ${Math.max(1, Math.round(ma.elapsed / 60))} 分のうち` : "いまのところ"}</span>
      <div class="bar2"><i class="s" style="width:${self}%"></i><i class="o" style="width:${100 - self}%"></i></div>
      <div class="lg"><span>祖母の声<b>${self}%</b></span><span>相手の時間(推定)<b>${other}%</b></span></div></div>
    <div><span class="k">最長の沈黙</span><span class="v shu">${ma.max_gap}<small>秒</small></span></div>
    <div><span class="k">5 秒以上の沈黙</span><span class="v">${ma.long_gaps}<small>回</small></span></div>
    <div><span class="k">断りの言葉 前半 → 後半</span><span class="v${lateZero ? " shu" : ""}">${ma.refusal_early} → ${ma.refusal_late}</span></div></div>`;
  return sec("小計", sum + proc);
}

// 記憶の照合(まとめ役の判断が出たら、前の記録から)
function refsBuild() {
  const k = S.decision?.karte;
  if (!k || !S.call) { S.refs = []; return; }
  if (S.refsFor === S.call.id && S.refsFixed) return;   // 一度決めた照合は、文字起こしを消したあとも変えない
  const st = S.st || { calls: [], memos: [] };
  const items = [];
  const linked = (k.linked_calls || []).map((id) => st.calls.find((c) => c.call_id === id)).filter(Boolean)[0];
  if (linked?.karte) {
    const lk = linked.karte;
    const prod = String(lk.product || "").split(/[(（]/)[0];
    items.push({ head: "前の電話", d: new Date(linked.started),
      lines: [`同じ「${short(lk.caller_claimed || lk.caller_normalized, 8)}」から、${short(prod, 11)}の電話。`, lk.response === "refused" ? "断って、自分から切っていた。" : `${RESP[lk.response] || "話を聞いた"}。`],
      keys: [lk.caller_claimed].filter(Boolean) });
  }
  if (k.life_link) {
    const grams = (s) => new Set([...String(s)].map((c, i, a) => c + (a[i + 1] || "")));
    const lg = grams(k.life_link);
    const said = S.utts.map((u) => u.text || "").join(" ");
    const hit = (x) => (x.text.match(/[一-鿿]+/g) || []).some((w) => said.includes(w));
    const m = (st.memos || []).filter((x) => !x.secret).map((x) => ({ x, sc: [...grams(x.text)].filter((g) => lg.has(g)).length + (hit(x) ? 6 : 0) })).sort((a, b) => b.sc - a.sc)[0];
    if (m && m.sc >= 2) {
      const kan = (m.x.text.match(/[一-鿿]+/g) || []).slice(0, 3);
      const sent = String(m.x.said || m.x.text).split(/(?<=。)/).map((x) => x.trim()).filter(Boolean).slice(0, 2).join("");
      items.push({ head: "おしゃべり", d: new Date(m.x.ts), lines: [`「${short(sent, 30)}」`], keys: kan });
    }
  }
  S.refs = items.map((it, j) => ({ ...it, n: j + 1 }));
  S.refsFor = S.call.id;
  S.refsFixed = !!S.st && items.length > 0;
}

// いつもの日: これまでの電話・暮らしのメモ・暦
function indexRender() {
  const st = S.st;
  if (!st) { $("sheet").innerHTML = ""; return; }
  const calls = st.calls.filter((c) => c.karte).slice(0, 6);
  const memos = (st.memos || []).filter((m) => !m.secret).slice(0, 7);
  const d = today(), y = d.getFullYear(), mo = d.getMonth();
  const ago = (x) => { const n = Math.round((new Date(y, mo, d.getDate()) - new Date(x.getFullYear(), x.getMonth(), x.getDate())) / 864e5); return n <= 0 ? "今日" : `${n} 日前`; };
  const crow = (c) => {
    const k = c.karte, x = new Date(c.started);
    return `<tr><td class="t">${x.getMonth() + 1}/${x.getDate()} ${pad(x.getHours())}:${pad(x.getMinutes())}</td><td class="v">${ago(x)}</td>
      <td class="w">${esc(short(k.caller_claimed || k.caller_normalized || "名乗りなし", 10))}</td><td class="nt" style="font-size:15px">${esc(short((k.product || "").split("(")[0], 16)) || "—"}</td>
      <td class="nt" style="font-size:15px">${RESP[k.response] || "—"}</td><td class="nt" style="font-size:15px;font-weight:${c.action === "silent" ? 400 : 700}">${ACTION[c.action] || "—"}</td></tr>`;
  };
  const callsT = calls.length ? `<div class="rows ix"><table class="tbl"><thead><tr><th style="width:110px">日時</th><th style="width:80px"></th><th style="width:230px">名乗り</th><th>内容</th><th style="width:110px">応答</th><th style="width:130px">判断</th></tr></thead><tbody>${calls.map(crow).join("")}</tbody></table></div>`
    : `<div class="empty">まだ電話の記録はありません。電話のあと、短いカルテだけをここに残します(文字起こしは消します)。</div>`;
  const marks = {};
  calls.forEach((c) => { const x = new Date(c.started); if (x.getMonth() === mo) marks[x.getDate()] = "call"; });
  memos.forEach((m) => { const x = new Date(m.ts); if (x.getMonth() === mo && !marks[x.getDate()]) marks[x.getDate()] = "memo"; });
  const first = new Date(y, mo, 1).getDay(), days = new Date(y, mo + 1, 0).getDate();
  let cal = WEEK.map((w, i) => `<span class="h ${i ? "" : "sun"}">${w}</span>`).join("");
  for (let i = 0; i < first; i++) cal += `<span></span>`;
  for (let dd = 1; dd <= days; dd++) {
    const dow = (first + dd - 1) % 7;
    cal += `<span class="${dow === 0 ? "sun" : ""} ${dd === d.getDate() ? "today" : ""} ${marks[dd] || ""}">${dd}</span>`;
  }
  const memoT = memos.length ? `<table class="tbl" style="width:100%"><thead><tr><th style="width:64px">日付</th><th style="width:118px">種類</th><th>メモ</th></tr></thead><tbody>${memos.map((m) => {
    const x = new Date(m.ts);
    return `<tr><td class="t">${x.getMonth() + 1}/${x.getDate()}</td><td class="nt" style="font-size:15px">${KIND[m.kind] || "—"}</td><td class="w" style="font-size:16px">${esc(short(m.text, 26))}</td></tr>`;
  }).join("")}</tbody></table>` : `<div class="empty">暮らしのメモはまだありません。</div>`;
  $("sheet").innerHTML = sec("通話", callsT)
    + sec("暦", `<div class="ix-two"><div class="cal"><div class="m">${mo + 1}月<small><i class="mk call"></i>電話<i class="mk memo"></i>おしゃべり</small></div><div class="g">${cal}</div></div><div>${memoT}</div></div>`);
}

// ---------------- 右: 判定(3 つの役) ----------------
function councilRender() {
  const lo = S.listener, r = S.rebuttal, d = S.decision, th = S.thinking;
  const inCall = !!S.call;
  const model = (k, dflt) => esc(S.models[k] ? modelName(S.models[k]) : dflt);
  // 聞き役
  let main, sub = "", kv = "", cls = "";
  if (!lo) {
    main = inCall ? `<span class="wait thinking">聞いています</span>` : `<span class="wait">電話を待っています</span>`;
  } else {
    const list = STAGES[lo.track] || [];
    const prev = S.marks.length > 1 ? S.marks[S.marks.length - 2].stage : null;
    main = !list.length ? `${TRACK[lo.track] || "まだ分からない"}。`
      : prev && prev !== lo.stage && list.indexOf(prev) >= 0 && list.indexOf(prev) < list.indexOf(lo.stage) ? `${prev}のあと、<br>${lo.stage}。` : `${lo.stage}。`;
    if (main.replace(/<br>/g, "").length > 14) cls = "sm";
    const acts = lo.speech_acts || [];
    const ref = [...acts].reverse().find((a) => a.kind === "refusal" && a.text);
    const pros = ref ? acts.filter((a) => a.kind === "promise" && a.text && secOf(a.t) > secOf(ref.t)) : [];
    const pro = pros.find((a) => /お願い|頼|ください/.test(a.text)) || pros[0];
    if (S.purgedLo) sub = "判定は、段階と危険度だけを残しました。";
    else if (ref && pro) sub = `「${esc(short(ref.text, 16))}」のあとに、「${esc(short(pro.text, 16))}」`;
    else if (lo.evidence?.[0]) sub = esc(clip(lo.evidence[0].note, 44));
    kv = `<dl class="kv"><dt>流れ</dt><dd>${TRACK[lo.track] || "—"}</dd><dt>怪しい度</dt><dd class="num">${(lo.score ?? 0).toFixed(2)}</dd><dt>今すぐ家族へ</dt><dd>${lo.notify_now ? "知らせる" : "知らせない"}</dd></dl>`;
  }
  $("listenerBody").innerHTML = `<div class="who"><b>聞き役</b><span>${model("listener", "Haiku 5.5")}</span></div>
    <div class="how">通話中、10 発話か 60 秒ごとに読む。決まった書式で</div>
    <div class="main ${cls}">${main}</div>${kv}<div class="sub">${sub}</div>`;
  // 反証役
  let cite = "";
  if (th === "rebuttal") { main = `<span class="wait thinking">本物かもしれない理由を、出典にあたって探しています</span>`; sub = ""; }
  else if (!r) { main = `<span class="wait">呼ばれるのは、怪しいときだけ。</span>`; sub = "聞き役の結論は、知らされません。"; }
  else {
    main = `本物の可能性は、${GENUINE[r.genuine_likelihood] || "—"}。`;
    const items = r.genuine_likelihood === "high" ? r.for_genuine : r.against_genuine;
    const it = (items || [])[0];
    sub = S.purgedReb ? "検討の中身は伏せて、見立てと出典だけを残しました。" : it ? esc(clip(it.text, 50)) : "";
    const src = it?.cites?.[0]?.source || r.citations?.[0]?.source;
    const title = (r.citations || []).find((c) => c.source === src)?.title || "";
    if (src) cite = `<div class="cite">出典 <b>${SRC(src)}</b><br>「${esc(short(title.split("(")[0], 22))}」</div>`;
  }
  $("rebuttalBody").innerHTML = `<div class="who"><b>反証役</b><span>${model("rebuttal", "Sonnet 5.5")}</span></div>
    <div class="how">聞き役の結論を見ずに、別に考える。出典を引用</div>
    <div class="main">${main}</div><div class="sub">${sub}</div>${cite}`;
  // まとめ役
  const choices = `<div class="choice">${["silent", "evening", "immediate"].map((a) => `<span class="${d?.action === a ? "pick" : ""}">${ACTION[a]}</span>`).join("")}</div>`;
  kv = "";
  if (th === "family") { main = `<span class="wait thinking">前の電話と、暮らしのメモを照らしています</span>`; sub = ""; }
  else if (!d) { main = `<span class="wait">電話のあとで決めます。</span>`; sub = "急ぐのは、今日お金やカードが動くとき・知らない人が来るとき・口止めのときだけ。"; }
  else {
    main = ACTION_MAIN[d.action] || d.action;
    sub = esc(clip(d.restraint_note || d.headline || "", 52));
    kv = `<dl class="kv"><dt>知らせ方</dt><dd>${ACTION_WHEN[d.action] || "—"}</dd></dl>`;
  }
  $("familyBody").innerHTML = `<div class="who"><b>まとめ役</b><span>${model("family", "Sonnet 5.5")}</span></div>
    <div class="how">記憶と照らして決める。待つ理由も書きのこす</div>
    ${choices}<div class="main">${main}</div>${kv}<div class="sub">${sub}</div>`;
  ["listenerBody", "rebuttalBody", "familyBody"].forEach((id) => $(id).classList.toggle("active",
    (id === "rebuttalBody" && th === "rebuttal") || (id === "familyBody" && th === "family") || (id === "listenerBody" && th === "listener")));
}
function modelName(m) {
  const x = String(m).match(/claude-(\w+)-(\d+)-(\d+)/);
  return x ? `${x[1][0].toUpperCase()}${x[1].slice(1)} ${x[2]}.${x[3]}` : m;
}

// ---------------- 台帳・状態 ----------------
function footRender(spent) {
  if (spent != null) S.spent = spent;
  $("foot").innerHTML = `<span class="lab2">台帳</span>
    <span class="it">音声<b>0</b>バイト</span>
    <span class="it">Claude に渡した文字<b>${S.chars.toLocaleString()}</b>字</span>
    <span class="it">費用<b>$${(S.spent || 0).toFixed(2)}</b></span>
    <span class="note">音声は外に出しません。Claude に渡すのは、文字と数字だけです。</span>`;
}
async function refreshState() {
  try {
    const st = await (await fetch("/api/state")).json();
    S.st = st; S.models = st.models || {};
    footRender(st.spent_usd);
    if (S.call && S.decision) refsBuild();
    sheetRender();
    councilRender();
  } catch (e) { console.warn(e); }
}
function toast(html, ms = 6000) {
  const t = $("toast"); t.innerHTML = html; t.classList.add("show");
  clearTimeout(t._h); t._h = setTimeout(() => t.classList.remove("show"), ms);
}
function newCall(ev) {
  S.call = { id: ev.call_id, t0: ev.t, tEnd: null, direction: ev.state === "dialing" ? "outgoing" : "incoming", date: new Date(), clock0: ev.clock, caller: null };
  Object.assign(S, { utts: [], marks: [], listener: null, rebuttal: null, decision: null, dialog: null, turn: null, ma: null, lastLine: "",
    thinking: null, refs: [], refsFor: null, refsFixed: false, purgedLo: false, purgedReb: false, lastSaid: null, redI: null });
  dateRender(); sheetRender(); councilRender();
}

// ---------------- イベント ----------------
function handle(ev) {
  if (rig && ev.type !== "level") lanternOn(ev);
  switch (ev.type) {
    case "level": level(ev.db); break;
    case "state":
      if (ev.state === "ended" && S.call && ev.call_id && S.call.id !== ev.call_id) break;   // 前の電話の遅れた「終わった」
      if (ev.clock) $("clock").textContent = ev.clock.slice(0, 5);
      if (ev.state === "ringing" || ev.state === "dialing") newCall(ev);
      if (ev.state === "in_call" && S.call) { S.call.t0 = ev.t; }
      if (ev.state === "ended" && S.call) {
        const lastU = S.utts[S.utts.length - 1];
        S.call.endReason = ev.reason;
        // 無音が続いて「終わった」と判断したときは、無音の尻尾(相手の時間ではない)を数えず、集計も最後の発話までの値を使う
        S.call.tEnd = ev.reason === "silence" && lastU ? lastU.end + 2 : ev.t;
        if (ev.ma && !(ev.reason === "silence" && S.ma)) S.ma = ev.ma;
        S.call.mins = Math.max(1, Math.round((ev.ma?.elapsed ?? (ev.t - S.call.t0)) / 60));
        const off = clockOffset();
        S.call.clockEnd = ev.reason === "silence" && lastU && off != null ? hms(lastU.end + off) : ev.clock;
      }
      if (ev.state === "idle" && S.state === "speaking") break;
      setStatus(ev.state === "ended" ? "ended" : ev.state === "idle" ? (S.call && S.decision && S.decision.action !== "silent" ? "after" : "idle") : ev.state);
      sheetRender();
      break;
    case "utt":
      if (ev.clock) $("clock").textContent = ev.clock.slice(0, 5);
      if (!S.call) newCall({ call_id: ev.call_id, t: ev.t - 1, clock: ev.clock, state: "ringing" });
      S.utts.push({ ...ev, _new: true }); S.ma = ev.ma || S.ma; S.lastLine = ev.line || S.lastLine;
      sheetRender();
      break;
    case "listener": {
      S.listener = ev.out;
      const lastU = S.utts[S.utts.length - 1];
      const t = lastU ? lastU.end : S.call?.t0 ?? 0;
      if (ev.out?.stage && (!S.marks.length || S.marks[S.marks.length - 1].stage !== ev.out.stage)) S.marks.push({ t, stage: ev.out.stage });
      if (ev.out?.claimed_caller && S.call) S.call.caller = short(ev.out.claimed_caller, 14);
      if (S.thinking === "listener") S.thinking = null;
      councilRender(); sheetRender();
      break;
    }
    case "thinking":
      if (ev.who === "rebuttal" || ev.who === "family") { S.thinking = ev.who; councilRender(); }
      if (ev.who === "letter") toast("<b>夕方の便りを書いています</b>", 4000);
      break;
    case "rebuttal": S.rebuttal = ev.out; S.thinking = null; councilRender(); break;
    case "decision":
      S.decision = { ...ev.decision, karte: ev.karte || ev.decision.karte }; S.thinking = null;
      councilRender(); refreshState();
      if (ev.decision.action === "silent") { setStatus("idle"); }
      break;
    case "dialog":
      S.dialog = { history: ev.history, cid: ev.call_id, done: false, purged: false };
      if (ev.turn) S.turn = ev.turn;
      if (ev.turn?.done) S.dialog.done = true;
      dialogRender();
      break;
    case "speak":
      S.lastSaid = ev.text; setStatus("speaking"); spoken(ev.text);
      $("meterL").textContent = "静か。だから声をかけました";
      clearTimeout(S._sp);
      S._sp = setTimeout(() => { if (S.state === "speaking") setStatus("after"); }, (ev.dur || 3) * 1000 + 300);
      break;
    case "speak_stopped": setStatus("after"); break;
    case "dialog_done":
      if (S.dialog) S.dialog.done = true;
      dialogRender(); refreshState();
      break;
    case "purged":   // 文字起こしを消したら、言葉だけ消す(声の線・間・数字は残す)
      if (S.call && S.call.id === ev.call_id) {
        S.utts = S.utts.map((u) => ({ ...u, text: "", line: "" }));
        S.lastLine = "(この電話の文字起こしは消しました。残すのは短いカルテだけ)";
        S.purgedLo = true; S.purgedReb = true;
        if (S.listener) S.listener = { ...S.listener, speech_acts: [], evidence: [] };
        sheetRender(); councilRender();
      }
      if (S.dialog && S.dialog.cid === ev.call_id) { S.dialog.purged = true; dialogRender(); }
      refreshState(); break;
    case "letter":
      refreshState();
      if (!IN_CALL.includes(S.state)) toast(`<b>${ev.letter.urgency === "immediate" ? "今すぐの便り" : "夕方の便り"}を家族に送りました</b> ─ ${esc(ev.letter.title)}`, 8000);
      break;
    case "claude":
      S.chars += ev.chars || 0; footRender(ev.spent);
      if (ev.role === "listener" && S.call) { S.thinking = null; }
      break;
    case "reset": location.reload(); break;
    case "error":
      console.warn(ev);
      if (["letter", "evening", "memory_sync", "immediate_letter"].includes(ev.where) && !IN_CALL.includes(S.state))
        toast(`<b>便りが止まりました</b>(${esc(ev.where)}) ${esc(ev.message).slice(0, 100)}`, 9000);
      break;
  }
}

function connect() {
  const ws = new WebSocket(`ws://${location.host}/ws`);
  ws.onmessage = (m) => { const ev = JSON.parse(m.data); if (ev.type !== "hello") handle(ev); };
  ws.onclose = () => setTimeout(connect, 1500);
}
$("clock").textContent = new Date().toTimeString().slice(0, 5);
dateRender(); setStatus("idle"); footRender(0); councilRender(); sheetRender(); refreshState(); connect();
