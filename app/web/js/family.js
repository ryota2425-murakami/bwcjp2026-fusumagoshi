// 家族の画面: 便りができるまで(Managed Agents の動き)と、家族のスマホに届いた便り
const $ = (id) => document.getElementById(id);
const esc = (s) => String(s ?? "").replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
const WEEK = ["日", "月", "火", "水", "木", "金", "土"];
const RISK = { low: "低", medium: "中", high: "高" };
const SRC = (u) => (u || "").includes("caa.go.jp") ? "消費者庁" : (u || "").includes("kokusen") ? "国民生活センター" : (u || "").includes("npa.go.jp") ? "警察庁" : (u || "").includes("zenginkyo") ? "全国銀行協会" : "出典";
const pad = (n) => String(n).padStart(2, "0");
const short = (s, n) => { s = String(s || "").replace(/\s+/g, " "); return s.length > n ? s.slice(0, n - 1) + "…" : s; };
let cards = {}, ctx = {}, evals = [];

function fit() {
  const s = Math.min(innerWidth / 1920, innerHeight / 1080);
  $("stage").style.transform = `translate(${(innerWidth - 1920 * s) / 2}px, ${(innerHeight - 1080 * s) / 2}px) scale(${s})`;
}
addEventListener("resize", fit); fit();

function atena() {   // 「誠さん、健太さんへ」(家族の文脈から名前を拾う)
  const f = ctx.family || "";
  const names = [...f.matchAll(/(?:息子|娘|孫|夫|妻)の([^\s(（、。]{1,4})/g)].map((m) => m[1]);
  const uniq = [...new Set(names)];
  const order = uniq.sort((a, b) => f.indexOf("息子の" + b) - f.indexOf("息子の" + a));
  return order.length ? order.map((n) => n + "さん").join("、") + "へ" : "家族のみなさんへ";
}
// 期限の「〜日以内」に印
const mark = (s) => esc(s).replace(/([^、。]*?\d+\s*日以内)/, "<u>$1</u>");
const CHECK = `<svg width="16" height="16" viewBox="0 0 16 16" aria-hidden="true"><path d="M3.5 8.2l3 3 6-6.4" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/></svg>`;

function letterHTML(l, ts, via) {
  const t = new Date(ts.replace(" ", "T"));
  const evening = l.urgency === "evening";
  const time = evening ? "18:00" : `${pad(t.getHours())}:${pad(t.getMinutes())}`;
  const kind = l.urgency === "immediate" ? "今すぐの便り" : l.urgency === "weekly" ? "週の便り" : "夕方の便り";
  const srcs = (l.source_links || (l.sources || []).map((id) => cards[id] ? { id, title: cards[id].title, url: cards[id].source_url } : null).filter(Boolean));
  const fn = (i) => srcs.length > i ? `⁠<span class="fn">※${i + 1}</span>` : "";   // 注の番号を、前の文字から離さない
  const m = l._meta || {};
  const grade = m.grade === "satisfied" ? `<div class="grade">${CHECK}<span><b>採点役 ${m.iterations > 1 ? `書き直し ${m.iterations - 1} 回のあと合格` : "合格"}</b> ・ 別の Claude が、届ける前に確かめました</span></div>`
    : m.held ? `<div class="grade"><b>採点役が合格を出さなかったので、中身は届けていません。</b></div>` : "";
  const talk = (l.suggested_talk || "").split(/(?<=[。?？!！])/).filter((x) => x.trim());
  return `<article class="letter ${l.urgency}${m.held ? " held" : ""}">
    <div class="meta"><span class="kind">${kind}</span><time>${t.getMonth() + 1}月${t.getDate()}日(${WEEK[t.getDay()]}) ${time}</time></div>
    <div class="atena">${esc(atena())}</div>
    <h3>${esc(l.title)}</h3>
    ${l.daily?.length ? `<div class="lbl">今日のおばあちゃん</div><div class="body">${l.daily.map(esc).join("")}</div>` : ""}
    ${(l.calls || []).map((c, i) => `<div class="lbl">電話のこと<small>気にかけたい度 <b>${RISK[c.risk] || c.risk}</b></small></div><div class="body">${esc(c.summary)}${i === 0 ? fn(1) : ""}<span class="why">${esc(c.why)}</span></div>`).join("")}
    ${talk.length ? `<div class="talk"><div class="k">話しかけ方の例<span>責めずに、聞くところから</span></div><div class="line">「${talk.map((x) => esc(x.trim())).join("")}」</div></div>` : ""}
    ${l.deadline || l.consult ? `<div class="memo"><div class="lbl">期限と相談先</div>${l.deadline ? `<p>${mark(l.deadline)}${fn(0)}</p>` : ""}${l.consult ? `<p>相談は ${esc(l.consult)}${fn(2)}</p>` : ""}</div>` : ""}
    ${l.closing ? `<div class="close">${esc(l.closing)}</div>` : ""}
    <div class="sign">台所の行灯(ふすまごし)より</div>
    ${srcs.length ? `<div class="srcs">${srcs.map((s, i) => `<div><b>※${i + 1}</b><a href="${esc(s.url)}" target="_blank" rel="noopener">${SRC(s.url)}「${esc(String(s.title).split("(")[0])}」</a></div>`).join("")}</div>` : ""}
    ${grade}
  </article>
  <div class="note-ma">${via === "managed-agents" ? `便り係(<b>Claude Managed Agents</b>)が、記憶ストアの要約だけを読んで書きました` : "端末から送った便りです"}</div>`;
}

async function load(scrollFromTop = false) {
  try { cards = Object.fromEntries((await (await fetch("/api/cards")).json()).map((c) => [c.id, c])); } catch (e) { /* 出典は letter の source_links を使う */ }
  const st = await (await fetch("/api/state")).json();
  ctx = st.context || {};
  const ls = st.letters.slice().reverse();
  const th = $("thread");
  th.innerHTML = ls.map((x) => letterHTML(x.body, x.ts, x.via)).join("") || `<div class="empty">まだ便りはありません。<br>毎日 18:00 に、台所の行灯から届きます。</div>`;
  const last = th.querySelectorAll(".letter");
  if (!last.length) return;
  const el = last[last.length - 1];
  th.style.scrollBehavior = "auto";
  th.scrollTop = el.offsetTop - 8;
  th.style.scrollBehavior = "smooth";
  if (scrollFromTop) setTimeout(() => { th.scrollTop = th.scrollHeight; }, 6500);   // 届いたら、上から読んで下まで
}

const ORDER = ["schedule", "synced", "write", "grade", "done"];
const now = () => { const d = new Date(); return `${pad(d.getHours())}:${pad(d.getMinutes())}:${pad(d.getSeconds())}`; };
function step(k, cls = "on") {
  const idx = ORDER.indexOf(k);
  document.querySelectorAll("#flow tbody tr").forEach((el) => {
    const i = ORDER.indexOf(el.dataset.k);
    const ok = i < idx || (i === idx && cls === "ok"), on = i === idx && cls === "on";
    const s = el.querySelector(".s");
    if (ok && !el.classList.contains("ok")) s.innerHTML = `${CHECK}完了 <span class="t-num">${now()}</span>`;
    if (on) s.textContent = "実行中";
    if (!ok && !on) s.textContent = "";
    el.classList.toggle("ok", ok);
    el.classList.toggle("on", on);
  });
}
function graderRender(final) {
  const g = $("grader");
  if (!evals.length) { g.innerHTML = final === "wait" ? `<div class="wait">採点役が、約束をひとつずつ確かめています</div>` : ""; return; }
  const ok = evals[evals.length - 1].result === "satisfied";
  g.innerHTML = evals.map((e, i) => `<div class="row"><span class="k">${i + 1} 回目</span><span class="v ${e.result === "satisfied" ? "" : "ng"}">${e.result === "satisfied" ? "合格" : "書き直し"}</span><span class="q">「${esc(short(gist(e), 64))}」</span></div>`).join("");
  $("rubric").classList.toggle("checked", ok);
}
// 採点役の説明(英語の前置き + 日本語の本文)から、決め手の一文だけを拾う
function gist(e) {
  const body = String(e.explanation || "").replace(/^[\s\S]*?\((?:partially |not )?met\):\s*/, "");
  const sents = body.split(/(?<=。)/).map((x) => x.trim()).filter(Boolean);
  if (e.result === "satisfied") return (sents.find((x) => /\d+\s*字/.test(x) && /以内/.test(x)) || sents[0] || "").replace(/^[(（]\d+[)）]\s*/, "");
  const tot = sents.find((x) => /合計/.test(x) && /\d+\s*字/.test(x));
  const over = sents.find((x) => /超え/.test(x) && x !== tot);
  if (tot && over) return "…" + tot.slice(tot.indexOf("合計")) + over;     // 記録の文のまま(合計の所から)
  return (over || sents.find((x) => /満たして(い)?ません|ただし/.test(x)) || sents[0] || "").replace(/^([(（]\d+[)）]\s*|\d+\.\s*|ただし、?|また、?|なお、?)/, "");
}

function handle(ev) {
  if (ev.type === "thinking" && ev.who === "letter") { step("schedule"); evals = []; graderRender(); $("rubric").classList.remove("checked"); }
  if (ev.type === "managed") {
    if (ev.stage === "synced") step("synced");
    if (ev.stage === "session") step("synced");
    if (ev.stage === "tool") step(/write|edit/i.test(ev.name || "") ? "write" : "synced");
    if (ev.stage === "grading") { step("grade"); graderRender("wait"); }
    if (ev.stage === "grade") { evals.push({ result: ev.result, explanation: ev.explanation || "" }); graderRender(); if (ev.result !== "satisfied") step("write"); }
    if (ev.stage === "done") { if (ev.evaluations?.length) evals = ev.evaluations.map((e) => ({ result: e.result, explanation: e.explanation || "" })); graderRender(); step("done", "ok"); }
  }
  if (ev.type === "letter") { load(true); step("done", "ok"); }
  if (ev.type === "error" && ["letter", "evening", "memory_sync"].includes(ev.where)) {
    $("grader").innerHTML = `<div class="err">止まりました ─ ${esc(ev.message).slice(0, 140)}</div>`;   // 便りが書けなかったことを、家族の画面にも出す
  }
}

function connect() {
  const ws = new WebSocket(`ws://${location.host}/ws`);
  ws.onmessage = (m) => { const ev = JSON.parse(m.data); if (ev.type !== "hello" && ev.type !== "level") handle(ev); };
  ws.onclose = () => setTimeout(connect, 1500);
}
$("callBtn").onclick = () => { const t = $("callBtn").querySelector("span"); t.textContent = "発信中…"; setTimeout(() => (t.textContent = "ばあちゃんに電話する"), 2500); };
load(); connect();
