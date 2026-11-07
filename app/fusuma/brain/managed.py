"""Claude Managed Agents: 夕方の便り係(fusuma-family)。

- 端末(Mac)はカルテと暮らしのメモ(要約だけ)を記憶ストア fusuma-memory に書く。音声と全文は送らない。
  本人が「内緒」と言ったメモは送らない(書かないだけでなく、渡さない)。送った中身はプライバシー台帳に残す。
- 毎日 18:00 JST に定期実行(scheduled deployment)が便り係のセッションを起こす。端末は通話が終わるたびに記憶ストアへ
  同期し(server.py)、18:05 以降に定期実行のセッションから便りを取りに行く(fetch_scheduled_letter)。デモでは手動実行もできる。
- 家族に届けるのは、採点役が合格を出した便りだけ(gate)。合格しなかった日は、中身のない短いお知らせに差し替える。
- 本人が「家族に伝えないで」と言った電話(consent=no)は、安全に関わる(今すぐの便りにした)ものを除いて記憶ストアに送らない。
- 便りは Outcomes のルーブリック(断定しない・責めない・内緒は書かない…)を、独立した採点役に見てもらい、最大 3 回書き直す。
- エージェント・環境・記憶ストア・スキル・定期実行は managed/ のファイルを `ant apply` で同期したもの(ID は claude-lock.json)。
"""
from __future__ import annotations

import hashlib
import json
import threading
import time
from datetime import datetime
from zoneinfo import ZoneInfo
from pathlib import Path
from typing import Callable

from .. import config
from ..store import Store
from . import llm

LOCK = config.APP / "managed" / "claude-lock.json"
BASE = "./agents/fusuma-family/"
BETA = ["managed-agents-2026-04-01"]
JST = ZoneInfo("Asia/Tokyo")
_synced: dict[str, str] = {}     # 記憶ストアに最後に書いた中身(変わっていなければ書かない)
_sync_lock = threading.Lock()    # 同期は 1 つずつ(通話ごとの同期と、手動の便りの同期が重ならないように)


def ids() -> dict:
    res = json.loads(LOCK.read_text())["resources"]
    return {k.replace(BASE, "").split(".")[0].replace("skills/", ""): v["id"] for k, v in res.items()}


# ---------- 記憶ストアへ同期(端末 → クラウド。要約だけ) ----------
def _karte_md(c: dict) -> str:
    k = c["karte"]
    d = c.get("decision") or {}
    keep = {key: k.get(key) for key in ("caller_normalized", "category", "product", "amount", "subscription", "request",
                                        "deadline", "secrecy", "response", "stage_max", "risk", "risk_reason",
                                        "linked_calls", "storyline", "life_link", "contract")}
    lines = [f"# 通話カルテ {c['call_id']}", "", f"- 日時: {c['started']}", f"- 向き: {'着信' if c['direction'] == 'incoming' else '発信'}",
             f"- 端末の判断: {d.get('action')}(理由: {d.get('restraint_note')})", f"- 要約: {d.get('headline')}"]
    if c.get("told_by_person"):
        lines.append(f"- 電話のあと本人が話したこと: {c['told_by_person']}")
    if c.get("consent"):
        lines.append(f"- 家族に伝える同意: {c['consent']}")
    lines += ["", "```json", json.dumps(keep, ensure_ascii=False, indent=1), "```"]
    return "\n".join(lines)


def sync_memory(store: Store, day: str | None = None, reset_day: bool = False) -> dict:
    """端末の正本(SQLite)に合わせて、その日のカルテを記憶ストアに鏡写しにする。
    reset_day=True ならその日の便りも消す(デモを最初からやり直すとき)。消した版も memory_versions に残る。"""
    with _sync_lock:
        return _sync_memory(store, day, reset_day)


def _sync_memory(store: Store, day: str | None, reset_day: bool) -> dict:
    cl = llm.client()
    mid = ids()["memory_store-memory"]
    day = day or datetime.now(JST).strftime("%Y-%m-%d")      # 定期実行(Asia/Tokyo)と同じ日付で
    existing = {m.path: m for m in cl.beta.memory_stores.memories.list(mid, path_prefix="/") if getattr(m, "type", "") == "memory"}
    shareable = [c for c in store.calls(60) if c.get("karte") and (c.get("started") or "").startswith(day)
                 and (c.get("consent") != "no" or c.get("action") == "immediate")]   # 「伝えないで」と言われた電話は送らない
    keep = {f"/karte/{day}/{c['call_id']}.md" for c in shareable}
    for path, m in list(existing.items()):
        stale_karte = path.startswith(f"/karte/{day}/") and path not in keep
        if stale_karte or (reset_day and path == f"/letters/{day}.md"):
            cl.beta.memory_stores.memories.delete(m.id, memory_store_id=mid)
            existing.pop(path)
    docs: dict[str, str] = {}
    for c in shareable:
        docs[f"/karte/{day}/{c['call_id']}.md"] = _karte_md(c)
    life = ["# 暮らしのメモ(祖母が話したこと。内緒と判定したメモはここには入れていない)", ""]
    for m in store.memos(include_secret=False):
        life.append(f"- {m['ts'][:16]} [{m['kind']}] {m['text']}(本人「{m['said']}」)")
    docs[f"/life/{day}.md"] = "\n".join(life)
    docs["/family/context.md"] = "# 家族の文脈\n\n" + store.context_text()
    written = []
    for path, content in docs.items():
        h = hashlib.sha256(content.encode()).hexdigest()
        if path in existing and _synced.get(path) == h:
            continue                                   # 前に書いた中身と同じ
        if path in existing:
            cl.beta.memory_stores.memories.update(existing[path].id, memory_store_id=mid, content=content)
        else:
            cl.beta.memory_stores.memories.create(mid, path=path, content=content)
        _synced[path] = h
        written.append(path)
        llm.record_sent("memory-sync", f"{path}\n{content}", to="managed-agents/memory_store",
                        ref=path.rsplit("/", 1)[-1][:-3] if path.startswith("/karte/") else None)
    return {"memory_store": mid, "written": written}


# ---------- 夕方の便り ----------
def _watch(cl, sid: str, emit: Callable[[dict], None], timeout: float) -> list[dict]:
    """セッションのイベントを追い、採点の結果を集める。終わる(idle / terminated)まで待つ。"""
    seen: set[str] = set()
    evals: list[dict] = []
    t0 = time.time()
    done = False
    while not done and time.time() - t0 < timeout:
        time.sleep(2.5)
        for ev in cl.beta.sessions.events.list(sid, order="asc", limit=100):
            if ev.id in seen:
                continue
            seen.add(ev.id)
            et = ev.type
            if et == "span.outcome_evaluation_end":
                evals.append({"iteration": ev.iteration, "result": ev.result, "explanation": ev.explanation})
                emit({"type": "managed", "stage": "grade", "iteration": ev.iteration, "result": ev.result,
                      "explanation": (ev.explanation or "")[:400]})
            elif et == "span.outcome_evaluation_start":
                emit({"type": "managed", "stage": "grading", "iteration": ev.iteration})
            elif et == "agent.tool_use":
                inp = getattr(ev, "input", {}) or {}
                target = inp.get("file_path") or inp.get("path") or inp.get("pattern") or ""
                emit({"type": "managed", "stage": "tool", "name": getattr(ev, "name", ""), "target": str(target)[:120]})
            elif et == "agent.message":
                text = "".join(getattr(b, "text", "") for b in ev.content if getattr(b, "type", "") == "text")
                if text:
                    emit({"type": "managed", "stage": "message", "text": text[:300]})
            elif et == "session.status_idle":
                if getattr(ev.stop_reason, "type", "") != "requires_action":
                    done = True
            elif et in ("session.status_terminated", "session.error"):
                done = True
    return evals


def gate(letter: dict, evals: list[dict]) -> dict:
    """採点役が合格(satisfied)を出した便りだけを家族に届ける。合格しなかった日は、中身のない短いお知らせにする。"""
    last = evals[-1]["result"] if evals else None
    meta = {**(letter.get("_meta") or {}), "grade": last, "iterations": len(evals)}
    if last == "satisfied":
        return {**letter, "_meta": meta}
    return {"urgency": "evening", "title": "今日の便りはお休みです",
            "daily": ["便り係が書いた便りを、採点役が約束(断定しない・責めない・内緒は書かない…)で確かめきれなかったので、今日は中身を届けません。"],
            "calls": [], "suggested_talk": "今日はどうだった?", "deadline": None, "consult": None, "sources": [], "closing": "",
            "_meta": {**meta, "held": True}}


def _finish(cl, sid: str, evals: list[dict], emit: Callable[[dict], None], trigger: str) -> tuple[dict, dict]:
    sess = cl.beta.sessions.retrieve(sid)
    try:
        letter = _fetch_letter(cl, sid)
    except RuntimeError:
        letter, evals = {}, evals + [{"iteration": len(evals), "result": "no_letter", "explanation": "letter.json が出力にない"}]
    meta = {"session_id": sid, "trigger": trigger, "evaluations": evals, "grade": evals[-1]["result"] if evals else None,
            "status": sess.status, "usage": json.loads(sess.usage.model_dump_json()) if getattr(sess, "usage", None) else None,
            "console": f"https://platform.claude.com/workspaces/default/sessions/{sid}"}
    _record_cost(meta)
    emit({"type": "managed", "stage": "done", **meta})
    body = gate(letter, evals)
    body["_meta"].update({"session_id": sid, "trigger": trigger})
    return body, meta


def evening_letter(store: Store, emit: Callable[[dict], None] = lambda e: None, timeout: float = 600,
                   reset_day: bool = False) -> tuple[dict, dict]:
    """定期実行を手動で起こして、便りを受け取る(デモ用。毎日の便りは fetch_scheduled_letter が取りに行く)。"""
    cl = llm.client()
    i = ids()
    synced = sync_memory(store, reset_day=reset_day)
    emit({"type": "managed", "stage": "synced", "written": synced["written"]})
    run = cl.beta.deployments.run(i["deployment-evening"])
    sid = run.session_id
    emit({"type": "managed", "stage": "session", "session_id": sid, "deployment_id": i["deployment-evening"]})
    evals = _watch(cl, sid, emit, timeout)
    return _finish(cl, sid, evals, emit, "manual")


def fetch_scheduled_letter(store: Store, emit: Callable[[dict], None] = lambda e: None,
                           day: str | None = None) -> tuple[dict, dict] | None:
    """18:00 の定期実行が書いた便りを取りに行く。まだ書いている・もう取り込んだ・今日の実行がない なら None。"""
    cl = llm.client()
    day = day or datetime.now(JST).strftime("%Y-%m-%d")
    imported = {((l.get("body") or {}).get("_meta") or {}).get("session_id") for l in store.letters(50)}
    for run in cl.beta.deployment_runs.list(deployment_id=ids()["deployment-evening"]):
        sid = getattr(run, "session_id", None)
        trig = getattr(getattr(run, "trigger_context", None), "type", None)
        created = getattr(run, "created_at", None)
        if not sid or sid in imported or trig != "schedule" or created is None:
            continue
        if isinstance(created, str):
            created = datetime.fromisoformat(created.replace("Z", "+00:00"))
        if created.astimezone(JST).strftime("%Y-%m-%d") != day:
            continue
        if cl.beta.sessions.retrieve(sid).status in ("running", "rescheduling"):
            return None                                 # まだ書いている。少しあとでまた来る
        evals = _watch(cl, sid, lambda e: None, timeout=60)
        return _finish(cl, sid, evals, emit, "schedule")
    return None


def _fetch_letter(cl, sid: str) -> dict:
    for attempt in range(6):
        files = cl.beta.files.list(scope_id=sid, betas=BETA)
        for f in files.data:
            if f.filename.endswith("letter.json"):
                raw = cl.beta.files.download(f.id, betas=BETA).read()
                body = json.loads(raw.decode("utf-8"))
                out = config.RUNS / "letters"
                out.mkdir(parents=True, exist_ok=True)
                (out / f"{datetime.now().strftime('%Y%m%d-%H%M%S')}_managed.json").write_bytes(raw)
                return body
        time.sleep(2)
    raise RuntimeError("letter.json が出力に見つからない")


def _record_cost(meta: dict) -> None:
    """セッションの list_cost を費用台帳に足す(予算管理を Messages API と共通にする)。"""
    u = meta.get("usage") or {}
    usd = None
    lc = u.get("list_cost") if isinstance(u, dict) else None
    if isinstance(lc, dict) and lc.get("amount") is not None:
        usd = float(lc["amount"]) / 100 if str(lc.get("amount")).isdigit() else float(lc["amount"])
    rec = {"ts": datetime.now().isoformat(timespec="seconds"), "role": "managed-evening-letter", "model": "claude-sonnet-5-5",
           "session": meta["session_id"], "usd": round(usd, 6) if usd is not None else 0.0, "usage": u}
    with (config.RUNS / "ledger.jsonl").open("a") as f:
        f.write(json.dumps(rec, ensure_ascii=False, default=str) + "\n")
