"""ふすまごし 端末サーバー(Mac 上で動く)。

  uvicorn fusuma.server:app --port 8780   (app/ で実行)

- 耳は常時動く(仮想の部屋 or マイク: FUSUMA_INPUT=mic)。脳は Claude API。画面は web/(WebSocket で更新)。
- 画面とイベントはこの Mac の中だけ(Origin が localhost 以外のページからの WebSocket・POST は断る)。
- 通話が終わって文字起こしを消すたびに、カルテ(要約)を Managed Agents の記憶ストアへ同期する。
  18:05 以降は、18:00 の定期実行が書いた便りを取りに行き、家族の画面へ出す(FUSUMA_MANAGED=0 で止める)。
"""
from __future__ import annotations

import asyncio
import json
import os
import threading
import time
from datetime import datetime, timedelta
from pathlib import Path
from urllib.parse import urlparse
from zoneinfo import ZoneInfo

from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from . import config
from .brain import letters, llm
from .devices import Speaker, VirtualRoom
from .ear.pipeline import Ear, baseline_path
from .ear.prosody import Baseline
from .orchestrator import Fusuma, SilenceViolation
from .store import Store, redact_event

WEB = config.APP / "web"
SCEN = {s["id"]: s for s in json.loads(config.SCENARIOS.read_text())["scenarios"]}

app = FastAPI(title="fusumagoshi")
LOCAL_HOSTS = {"localhost", "127.0.0.1", "::1"}


def _local_origin(origin: str | None, host: str | None = None) -> bool:
    """ブラウザからの要求は、この画面と同じオリジン(localhost の同じポート)からだけ受ける。Origin がない(curl など)は通す。"""
    if origin is None:
        return True
    u = urlparse(origin)
    return u.hostname in LOCAL_HOSTS and (host is None or u.netloc == host)


@app.middleware("http")
async def _only_local_pages(request: Request, call_next):
    if request.method not in ("GET", "HEAD", "OPTIONS") and not _local_origin(request.headers.get("origin"), request.headers.get("host")):
        return JSONResponse({"error": "forbidden origin"}, status_code=403)
    return await call_next(request)
app.mount("/static", StaticFiles(directory=WEB), name="static")
app.mount("/media", StaticFiles(directory=config.DATA), name="media")


EVENTS = config.RUNS / "events.jsonl"


class Hub:
    def __init__(self):
        self.clients: set[WebSocket] = set()
        self.loop: asyncio.AbstractEventLoop | None = None
        self.recent: list[dict] = []
        self._flock = threading.Lock()
        self.purged: set[str] = set()          # 文字起こしを消した通話(あとから届いたイベントも伏せる)

    def redact(self, call_id: str) -> None:
        """その通話の文字起こしを消すとき、画面の履歴とイベントログ(runs/events.jsonl)の原文も伏せる。"""
        def red(ev: dict) -> dict:
            return redact_event(ev) if call_id in (ev.get("call_id"), ev.get("ref")) else ev
        with self._flock:
            self.purged.add(call_id)
            self.recent = [red(e) for e in self.recent]
            if EVENTS.exists():
                rows = []
                for line in EVENTS.read_text().splitlines():
                    try:
                        rows.append(json.dumps(red(json.loads(line)), ensure_ascii=False, default=str))
                    except json.JSONDecodeError:
                        continue
                tmp = EVENTS.with_suffix(".tmp")
                tmp.write_text("".join(r + "\n" for r in rows))
                tmp.replace(EVENTS)

    def emit(self, ev: dict) -> None:
        ev = {**ev, "_ts": time.time()}
        if ev.get("type") != "level":
            with self._flock:
                if self.purged and (ev.get("call_id") in self.purged or ev.get("ref") in self.purged) and ev.get("type") != "purged":
                    ev = redact_event(ev)
                self.recent = (self.recent + [ev])[-400:]
                with EVENTS.open("a") as f:
                    f.write(json.dumps(ev, ensure_ascii=False, default=str) + "\n")
        if self.loop is None:
            return
        data = json.dumps(ev, ensure_ascii=False, default=str)
        for ws in list(self.clients):
            asyncio.run_coroutine_threadsafe(self._send(ws, data), self.loop)

    async def _send(self, ws: WebSocket, data: str) -> None:
        try:
            await ws.send_text(data)
        except Exception:
            self.clients.discard(ws)


hub = Hub()
store = Store()
AUDIBLE = os.getenv("FUSUMA_AUDIBLE", "1") == "1"   # 0 にするとスピーカーから音を出さない(テスト用)
SAVE_SPEECH = os.getenv("FUSUMA_SAVE_SPEECH", "0") == "1"   # 1 のときだけ、話した音声を残す(デモ動画の編集用)
speaker = Speaker(audible=AUDIBLE, save=SAVE_SPEECH)
ear = Ear(lambda e: fz.on_ear(e), start_wall=datetime.now(), realtime=True)
fz = Fusuma(store, emit=hub.emit, speak=speaker.say, ear=ear)
fz.on_purge.append(hub.redact)
INPUT = os.getenv("FUSUMA_INPUT", "virtual")                 # virtual(デモの部屋の音) | mic(マイク)
LOCK = config.APP / "managed" / "claude-lock.json"


def managed_enabled() -> bool:
    """Managed Agents を作ってあるか(ant apply の claude-lock.json)。起動したあとに作っても、そのつど確かめる。"""
    return os.getenv("FUSUMA_MANAGED", "1") == "1" and LOCK.exists()
JST = ZoneInfo("Asia/Tokyo")
_sync_lock = threading.Lock()


def _sync_memory(_cid: str | None = None) -> None:
    """カルテ(要約)を記憶ストアへ同期する。18:00 の定期実行は、この同期した記憶を読んで便りを書く。"""
    if not managed_enabled():
        return

    def go():
        if not _sync_lock.acquire(blocking=False):
            return
        try:
            from .brain import managed
            r = managed.sync_memory(store)
            if r["written"]:
                hub.emit({"type": "managed", "stage": "synced", "written": r["written"], "auto": True})
        except Exception as e:
            hub.emit({"type": "error", "where": "memory_sync", "message": f"{type(e).__name__}: {e}"})
        finally:
            _sync_lock.release()
    threading.Thread(target=go, daemon=True).start()


fz.on_purge.append(_sync_memory)


def _evening_loop() -> None:
    """17:50 に記憶を同期し直し、18:05 以降は定期実行の便りを取りに行く(取り込んだら翌日まで何もしない)。"""
    synced_day = fetched_day = None
    while not stop_evt.wait(120):
        if not managed_enabled():
            continue
        now = datetime.now(JST)
        day = now.strftime("%Y-%m-%d")
        try:
            if (now.hour, now.minute) >= (17, 50) and synced_day != day:
                _sync_memory()
                synced_day = day
            if (now.hour, now.minute) >= (18, 5) and fetched_day != day:
                from .brain import managed
                got = managed.fetch_scheduled_letter(store, emit=hub.emit, day=day)
                if got:
                    body, meta = got
                    calls = [c["call_id"] for c in store.calls(50) if c.get("karte") and (c["started"] or "").startswith(day)]
                    lid = store.add_letter("evening", body, "managed-agents", calls)
                    hub.emit({"type": "letter", "id": lid, "letter": body, "via": "managed-agents", "meta": meta})
                    fetched_day = day
        except Exception as e:
            hub.emit({"type": "error", "where": "evening", "message": f"{type(e).__name__}: {e}"})
room = VirtualRoom(audible=AUDIBLE)
stop_evt = threading.Event()
demo = {"answers": [], "scenario": None}
llm.on_call(lambda rec: hub.emit({"type": "claude", **rec}))


def _ear_loop():
    if INPUT == "mic":
        ear.run_mic(stop_evt)
    else:
        room.run(ear.feed, stop_evt)


@app.on_event("startup")
async def _startup():
    hub.loop = asyncio.get_running_loop()
    for cid in store.pending_transcripts():     # 前に止めたとき残っていた文字起こしを片づける
        fz._purge(cid)
    threading.Thread(target=_ear_loop, daemon=True).start()
    threading.Thread(target=_evening_loop, daemon=True).start()


# ---------- 画面 ----------
@app.get("/")
def index():
    return FileResponse(WEB / "index.html")


@app.get("/{page}.html")
def page(page: str):
    return FileResponse(WEB / f"{page}.html")


@app.websocket("/ws")
async def ws(websocket: WebSocket):
    if not _local_origin(websocket.headers.get("origin"), websocket.headers.get("host")):
        await websocket.close(code=1008)          # この Mac の画面以外には、文字起こしを流さない
        return
    await websocket.accept()
    hub.clients.add(websocket)
    try:
        await websocket.send_text(json.dumps({"type": "hello", "recent": hub.recent[-150:]}, ensure_ascii=False, default=str))
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        hub.clients.discard(websocket)


# ---------- 状態 ----------
@app.get("/api/state")
def state():
    base = Baseline.load(baseline_path())
    calls = store.calls(30)
    for c in calls:
        c.pop("lines", None) if c.get("transcript_purged") else None
    return JSONResponse({
        "calls": calls, "memos": store.memos(), "letters": store.letters(), "context": store.context(),
        "baseline": base.__dict__, "spent_usd": round(llm.spent_usd(), 4), "budget_usd": config.BUDGET_USD,
        "ear_state": ear.state, "models": {"listener": config.MODEL_LISTENER, "rebuttal": config.MODEL_REBUTTAL,
                                           "family": config.MODEL_FAMILY, "letter": config.MODEL_LETTER},
        "scenarios": [{"id": s["id"], "title": s["title"], "kind": s["kind"]} for s in SCEN.values()],
    })


@app.get("/api/cards")
def cards():
    from .brain import knowledge
    return knowledge.cards()


@app.get("/api/privacy")
def privacy(n: int = 20):
    p = config.RUNS / "privacy_ledger.jsonl"
    rows = [json.loads(x) for x in p.read_text().splitlines()[-n:]] if p.exists() else []
    total_chars = sum(r["chars"] for r in rows)
    return {"rows": rows[::-1], "audio_bytes": 0, "chars": total_chars}


# ---------- デモ操作 ----------
class Play(BaseModel):
    id: str
    clock: str | None = None      # 台本の時刻に合わせる(例 "14:02:50")
    auto_answer: bool = True


@app.post("/api/play")
def play(p: Play):
    if INPUT == "mic":
        return JSONResponse({"error": "マイク入力のときは、デモの音声を流せない(FUSUMA_INPUT=virtual で起動する)"}, status_code=409)
    sc = SCEN[p.id]
    h, m = map(int, (p.clock or sc["time"]).split(":")[:2])
    ear.set_clock(datetime.now().replace(hour=h, minute=m, second=0, microsecond=0) - timedelta(seconds=10))
    fz.scenario_tag = p.id
    demo["scenario"] = p.id
    answers = [s for s in SCEN.values() if s.get("answers_for") == p.id]
    demo["answers"] = []
    if p.auto_answer and answers:
        aid = answers[0]["id"]
        demo["answers"] = [config.SCENARIO_AUDIO / f"{aid}_a{k}" for k in range(1, len(answers[0]["script"]) + 1)]
    dur = room.inject(config.SCENARIO_AUDIO / f"{p.id}_16k.wav", play=config.SCENARIO_AUDIO / f"{p.id}.wav")
    hub.emit({"type": "demo", "scenario": p.id, "title": sc["title"], "duration": dur,
              "file": f"{p.id}.wav", "wall": time.time()})   # 動画編集で音を重ねるための時刻
    return {"ok": True, "duration": dur, "answers": len(demo["answers"])}


def _auto_answer(_text: str) -> None:
    """デモ: ふすまごしが話し終えたら、少し間をおいて祖母の答え(録音)を部屋に流す。"""
    if fz.dialog is None or not demo["answers"]:
        return
    nxt = demo["answers"].pop(0)

    def go():
        time.sleep(1.2)
        room.inject(Path(f"{nxt}_16k.wav"), play=Path(f"{nxt}.wav"))
        hub.emit({"type": "inject", "file": Path(f"{nxt}.wav").name, "wall": time.time()})
    threading.Thread(target=go, daemon=True).start()


fz.on_spoken = _auto_answer


class Mute(BaseModel):
    seconds: float


@app.post("/api/ear/mute")
def ear_mute(m: Mute):
    """デモの電話(phone_sim)用: 受話器から出る相手の声のあいだだけ、部屋の耳を止める。
    本物では受話器は耳に当たっていて部屋のマイクにはほとんど届かない。それをスピーカーで再生するデモで再現する。"""
    ear.mute_for(max(0.0, min(30.0, m.seconds)))
    hub.emit({"type": "line_muted", "seconds": round(m.seconds, 2), "wall": time.time()})
    return {"ok": True}


class Hook(BaseModel):
    event: str


@app.post("/api/ear/hook")
def ear_hook(h: Hook):
    """デモの電話(phone_sim)用の予備: 発信音・受話器の音をマイクが聞き逃したときだけ、フックの合図として渡す。"""
    if h.event not in ("dial", "ring", "handset"):
        return JSONResponse({"error": "unknown"}, status_code=400)
    ear._on_sound(h.event, ear.t, {"hook": True})
    hub.emit({"type": "hook", "event": h.event, "wall": time.time()})
    return {"ok": True, "state": ear.state}


class Say(BaseModel):
    text: str


@app.post("/api/say")
def say(s: Say):
    def go():
        try:
            fz.say(s.text)
        except SilenceViolation as e:
            hub.emit({"type": "error", "where": "say", "message": str(e)})
    threading.Thread(target=go, daemon=True).start()
    return {"ok": True}


@app.post("/api/dialog/{call_id}")
def dialog_now(call_id: str):
    threading.Thread(target=fz.start_dialog, args=(call_id,), daemon=True).start()
    return {"ok": True}


class Letter(BaseModel):
    urgency: str = "evening"
    via: str = "messages"          # messages | managed
    reset_day: bool = False         # デモをやり直すとき、その日の古い便りを記憶ストアから消す


@app.post("/api/letter")
def letter(l: Letter):
    if l.via == "managed" and not managed_enabled():
        return JSONResponse({"error": "Managed Agents が未作成です。先に cd app/managed && ant apply ... を実行してください"}, status_code=409)

    def run():
        try:
            _letter(l)
        except Exception as e:
            hub.emit({"type": "error", "where": "letter", "message": f"{type(e).__name__}: {e}"})
    threading.Thread(target=run, daemon=True).start()
    return {"ok": True}


def _letter(l: Letter) -> None:
    """便りを書く。via=managed は Managed Agents の定期実行を手動で起こす(採点に合格した便りだけ届く)。"""
    hub.emit({"type": "thinking", "who": "letter", "via": l.via})
    today = datetime.now(JST).strftime("%Y-%m-%d")      # 端末の時計は日本時間を前提(定期実行と同じ日付)
    calls = [c for c in store.calls(50) if c.get("karte") and (c["started"] or "").startswith(today)]
    if l.via == "managed":
        from .brain import managed
        body, meta = managed.evening_letter(store, emit=hub.emit, reset_day=l.reset_day)   # 採点に合格した便りだけ(gate)
        lid = store.add_letter(l.urgency, body, "managed-agents", [c["call_id"] for c in calls])
        hub.emit({"type": "letter", "id": lid, "letter": body, "via": "managed-agents", "meta": meta})
    else:
        body = letters.write(l.urgency, calls, store)
        lid = store.add_letter(l.urgency, body, "messages-api", [c["call_id"] for c in calls])
        hub.emit({"type": "letter", "id": lid, "letter": body, "via": "messages-api"})


@app.post("/api/reset")
def reset():
    for cid in store.pending_transcripts():     # 消す前に、残っている文字起こしを台帳・ログからも伏せる
        fz._purge(cid)
    store.reset()
    hub.recent.clear()
    hub.emit({"type": "reset"})
    return {"ok": True}
