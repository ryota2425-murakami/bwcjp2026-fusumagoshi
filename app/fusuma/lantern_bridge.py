"""ふすまの中の Claude(Raspberry Pi)へ、表情の合図だけを渡す中継。

  ../.venv/bin/python -m fusuma.lantern_bridge --allow <Pi の IP>        (app/ で実行)

- 端末サーバー(127.0.0.1:8780)はこれまでどおり Mac の中だけで動かす。この中継がその /ws を
  Mac の中から購読し、「いま静かにする」「いま話している(長さ)」「答えが来た」などの合図に
  置き換えて、許可した Pi にだけ流す(--allow。既定は Mac 自身だけ)。
- 文字起こし・話した文・電話の相手・便りの本文は、一文字も Pi へ送らない。送るのは気分の名前と
  秒数と口の開き(0〜1 の数列)だけ。口の動きは、話す文のモーラ数から Mac 側で作る。
- Pi からは「さわられた」だけを受け取る(ログに残すだけで、ほかへは渡さない)。
"""
from __future__ import annotations

import argparse
import asyncio
import json
import re
import time
from pathlib import Path

import uvicorn
import websockets
from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

LANTERN_WEB = Path(__file__).resolve().parents[1] / "web" / "lantern"
UPSTREAM = "ws://127.0.0.1:8780/ws"
ENV_HZ = 20                                   # 口の開きの数列のサンプル数/秒
LOOPBACK = {"127.0.0.1", "::1", "localhost"}

_KANA = re.compile(r"[ぁ-ゖァ-ヺー]")
_SMALL = re.compile(r"[ゃゅょぁぃぅぇぉゎャュョァィゥェォヮ]")
_KANJI = re.compile(r"[一-龯々〆ヵヶ]")
_ALNUM = re.compile(r"[A-Za-z0-9０-９Ａ-Ｚａ-ｚ]")
_PAUSE = {"、": 0.18, "，": 0.18, ",": 0.18, "。": 0.32, "．": 0.32, "？": 0.3, "?": 0.3, "！": 0.3, "!": 0.3, "…": 0.3}


def mouth_envelope(text: str, dur: float, hz: int = ENV_HZ) -> list[float]:
    """話す文から、口の開き(0〜1)の数列を作る。文そのものは返さない。

    かなは 1 モーラ、漢字は 1.6 モーラ、英数字は 1 モーラとして、句読点に間を置き、全体を dur 秒に割り付ける。
    各モーラは「開いて閉じる」山にし、長音や母音の続きは山を少し低くつなげる。"""
    units: list[tuple[str, float]] = []        # ("m", 重さ) モーラ / ("p", 秒) 間
    for ch in text:
        if ch in _PAUSE:
            units.append(("p", _PAUSE[ch]))
        elif _SMALL.match(ch):
            continue                            # 拗音の小さい字は前のモーラに含める
        elif _KANA.match(ch):
            units.append(("m", 0.75 if ch == "ー" else 1.0))
        elif _KANJI.match(ch):
            units.append(("m", 1.6))
        elif _ALNUM.match(ch):
            units.append(("m", 1.0))
    n = max(1, int(round(dur * hz)))
    if not units or dur <= 0:
        return [0.0] * n
    pause_total = sum(v for k, v in units if k == "p")
    pause_total = min(pause_total, dur * 0.35)
    scale_p = pause_total / max(1e-6, sum(v for k, v in units if k == "p")) if pause_total else 0
    mora_total = sum(v for k, v in units if k == "m")
    per_mora = (dur - pause_total) / max(1e-6, mora_total)
    env = [0.0] * n
    t = 0.04
    k = 0
    for kind, v in units:
        if kind == "p":
            t += v * scale_p
            continue
        span = v * per_mora
        peak = 0.55 + 0.45 * ((k * 7919) % 11) / 10          # 山の高さに少し変化(決定的)
        k += 1
        i0, i1 = int(t * hz), max(int(t * hz) + 1, int((t + span) * hz))
        for i in range(i0, min(i1, n)):
            x = (i - i0 + 0.5) / max(1, i1 - i0)
            env[i] = max(env[i], round(peak * (1 - abs(2 * x - 1)) ** 0.7, 2))
        t += span
    return env


class Lantern:
    """端末のイベントから、行灯の気分を決める(状態は Mac 側に一つだけ持つ)。"""

    def __init__(self):
        self.mood = "watch"
        self.since = time.time()
        self.dialog = False
        self.in_call = False
        self.sus = 0.0                              # 通話中のあやしさ(0..1)。聞き役の risk から
        self.ask = 0.0                              # 聞きたさ(0..1)。聞き役の to_ask の数から
        self.upstream_ok = False
        self.peers: dict[WebSocket, str] = {}      # 接続 → 役割(kitchen: 台所の端末の顔 / family: 家族の机の上)

    def snapshot(self) -> dict:
        return {"type": "mood", "mood": self.mood, "since": self.since, "server_time": time.time(),
                "upstream": self.upstream_ok}

    def _set(self, mood: str) -> dict | None:
        if mood == self.mood:
            return None
        self.mood, self.since = mood, time.time()
        return self.snapshot()

    def _uneasy(self, sus: float, ask: float) -> dict | None:
        sus, ask = round(max(0.0, min(1.0, sus)), 2), round(max(0.0, min(1.0, ask)), 2)
        if (sus, ask) == (self.sus, self.ask):
            return None
        self.sus, self.ask = sus, ask
        return {"type": "uneasy", "sus": sus, "ask": ask, "server_time": time.time()}   # 数値だけ。理由や文は送らない

    def on_event(self, ev: dict) -> list[dict]:
        """端末のイベント 1 つを、Pi へ送る合図(0 個以上)に変える。文字は含めない。"""
        t = ev.get("type")
        out: list[dict | None] = []
        if t == "hello":
            for past in ev.get("recent", [])[-60:]:     # 途中から繋いだとき、いまの様子だけ組み立て直す
                self.on_event(past)
            return [self.snapshot()]
        if t == "state":
            st = ev.get("state")
            if st in ("ringing", "dialing", "in_call"):
                self.dialog = False
                if not self.in_call:
                    out.append(self._uneasy(0, 0))
                self.in_call = True
                out.append(self._set("call"))
            elif st in ("ended", "idle"):
                if self.in_call:
                    out.append(self._uneasy(0, self.ask))   # 電話が終わったら、あやしさは引き、聞きたさは残す
                self.in_call = False
                out.append(self._set("watch"))
        elif t == "listener" and self.in_call and not ev.get("final"):
            o = ev.get("out") or {}
            sus = {"low": 0.15, "medium": 0.6, "high": 1.0}.get(o.get("risk"), 0.0)
            sus = max(sus, min(1.0, float(o.get("score") or 0)))
            ask = min(1.0, len(o.get("to_ask") or []) / 2) * (0.4 if o.get("risk") == "low" else 1.0)
            out.append(self._uneasy(sus, ask))
        elif t == "thinking" and not self.in_call and not self.dialog:
            out.append(self._set("think"))
        elif t == "decision" and not self.in_call:
            act = (ev.get("decision") or {}).get("action")
            out.append(self._set("watch"))
            out.append(self._uneasy(0, 0 if act in (None, "silent") else 1.0))
        elif t == "speak":
            dur = float(ev.get("dur") or 0)
            out.append(self._uneasy(0, 0))
            out.append(self._set("after"))
            out.append({"type": "speak", "dur": round(dur, 2), "hz": ENV_HZ,
                        "env": mouth_envelope(str(ev.get("text") or ""), dur),
                        "then": "listen" if self.dialog else "watch", "server_time": time.time()})
        elif t == "speak_stopped":
            out.append({"type": "speak_stop", "server_time": time.time()})
            out.append(self._set("call"))
        elif t == "dialog":
            self.dialog = True
            out.append({"type": "await_answer", "server_time": time.time()})
        elif t == "room_utt" and self.dialog:
            out.append({"type": "nod", "server_time": time.time()})
        elif t in ("dialog_done", "dialog_closed", "dialog_skipped", "reset"):
            self.dialog = False
            out.append(self._uneasy(0, 0))
            out.append(self._set("watch"))
        elif t == "letter":
            out.append(self._set("letter"))
            out.append({"type": "letter", "server_time": time.time()})
        elif t == "sound" and ev.get("event") == "doorbell":
            out.append({"type": "glance", "gaze": -0.85, "server_time": time.time()})
        return [o for o in out if o]

    async def broadcast(self, msgs: list[dict]) -> None:
        for m in msgs:
            for ws, role in list(self.peers.items()):
                out = for_role(m, role)
                if out is None:
                    continue
                try:
                    await ws.send_text(json.dumps(out, ensure_ascii=False))
                except Exception:
                    self.peers.pop(ws, None)


def for_role(m: dict, role: str) -> dict | None:
    """家族の机の上の Pi には、便りが届いたことと生存確認だけを渡す。
    電話中かどうか・話しているかどうかは送らない(見張るのでも、のぞくのでもなく)。"""
    if role == "kitchen":
        return m
    if m.get("type") in ("letter", "beat"):
        return m
    if m.get("type") == "mood":
        return {**m, "mood": "letter" if m.get("mood") == "letter" else "watch", "since": 0}
    return None


lantern = Lantern()
app = FastAPI(title="fusumagoshi lantern bridge")
ALLOW: set[str] = set(LOOPBACK)          # 台所の端末(全部の合図)
FAMILY: set[str] = set()                 # 家族の机の上(便りだけ)
REPLAY: dict = {}
TALK: dict = {}                          # 会話デモ(fusuma.talk_demo)。端末につながず、/cue の合図だけを流す


async def upstream_loop() -> None:
    """端末サーバーの /ws を購読し続ける(落ちても待って繋ぎ直す)。Origin は付けない(Mac の中からの接続)。"""
    backoff = 1.0
    while True:
        try:
            async with websockets.connect(UPSTREAM, max_size=2 ** 22, open_timeout=5) as ws:
                lantern.upstream_ok, backoff = True, 1.0
                await lantern.broadcast([lantern.snapshot()])
                async for raw in ws:
                    try:
                        ev = json.loads(raw)
                    except json.JSONDecodeError:
                        continue
                    if ev.get("type") == "level":
                        continue
                    await lantern.broadcast(lantern.on_event(ev))
        except Exception:
            pass
        if lantern.upstream_ok:
            lantern.upstream_ok = False
            await lantern.broadcast([lantern.snapshot()])
        await asyncio.sleep(backoff)
        backoff = min(backoff * 1.6, 15.0)


async def heartbeat_loop() -> None:
    while True:
        await asyncio.sleep(5)
        await lantern.broadcast([{"type": "beat", "server_time": time.time(), "upstream": lantern.upstream_ok}])


async def replay_loop(path: Path, start: float, speed: float) -> None:
    """録画のときのイベント(record_demo の timing.json)を、同じ間隔で流し直す(動画や確認用。Claude は呼ばない)。"""
    m = json.loads(path.read_text())
    evs = sorted((e for e in m["events"] if e.get("type") != "level"), key=lambda e: e["_ts"])
    t0 = m.get("t_page", evs[0]["_ts"]) + start
    lantern.upstream_ok = True
    await asyncio.sleep(REPLAY.get("lead", 3.0))
    wall0 = time.time()
    for e in evs:
        if e["_ts"] < t0:
            lantern.on_event(e)                 # 始める前のぶんは、状態だけ進める
            continue
        wait = (e["_ts"] - t0) / speed - (time.time() - wall0)
        if wait > 0:
            await asyncio.sleep(wait)
        await lantern.broadcast(lantern.on_event(e))
    print("[lantern] replay finished", flush=True)


@app.on_event("startup")
async def _startup() -> None:
    if TALK.get("on"):
        lantern.upstream_ok = True                  # 会話デモのあいだは「つながっている」扱い
    elif REPLAY.get("path"):
        lantern.upstream_ok = True                  # 流し直しのあいだは「つながっている」扱い(うとうとさせない)
        if not REPLAY.get("manual"):
            asyncio.create_task(replay_loop(Path(REPLAY["path"]), REPLAY.get("start", 0.0), REPLAY.get("speed", 1.0)))
    else:
        asyncio.create_task(upstream_loop())
    asyncio.create_task(heartbeat_loop())


@app.post("/replay/start")
async def replay_start(request: Request):
    """Mac の中からだけ: 流し直しを今から始める(Pi の画面の録画と時刻を合わせるため、始めた時刻を返す)。"""
    if (request.client.host if request.client else "") not in LOOPBACK or not REPLAY.get("path"):
        return JSONResponse({"error": "forbidden"}, status_code=403)
    REPLAY["lead"] = 0.0
    t = time.time()
    asyncio.create_task(replay_loop(Path(REPLAY["path"]), REPLAY.get("start", 0.0), REPLAY.get("speed", 1.0)))
    return {"ok": True, "started_at": t}


def _allowed(host: str | None) -> bool:
    return (host or "") in ALLOW or (host or "") in FAMILY


def _role(host: str | None, asked: str | None) -> str:
    """役割は Mac 側で決める(Pi が kitchen を名乗っても、--family に入っていれば family)。"""
    if (host or "") in FAMILY:
        return "family"
    return "family" if asked == "family" else "kitchen"


@app.middleware("http")
async def _only_allowed(request, call_next):
    if not _allowed(request.client.host if request.client else None):
        return JSONResponse({"error": "forbidden"}, status_code=403)
    return await call_next(request)


@app.websocket("/lantern")
async def lantern_ws(websocket: WebSocket):
    if not _allowed(websocket.client.host if websocket.client else None):
        await websocket.close(code=1008)
        return
    await websocket.accept()
    host = websocket.client.host if websocket.client else None
    lantern.peers[websocket] = _role(host, None) if host in FAMILY else "family"     # 名乗るまでは、いちばん狭く
    try:
        while True:
            msg = await websocket.receive_text()
            try:
                m = json.loads(msg)
            except json.JSONDecodeError:
                continue
            if m.get("type") == "touch":
                print(f"[lantern] touched ({host or '?'})", flush=True)
            elif m.get("type") == "hello":
                role = _role(host, m.get("role"))
                lantern.peers[websocket] = role
                print(f"[lantern] peer {m.get('who', '?')} {host or '?'} role={role}", flush=True)
                snap = for_role(lantern.snapshot(), role)
                if snap:
                    await websocket.send_text(json.dumps(snap))
    except WebSocketDisconnect:
        pass
    finally:
        lantern.peers.pop(websocket, None)


@app.post("/test/{kind}")
async def test_signal(kind: str, request: Request):
    """Mac の中からだけ: 合図を手で送る(配線の確認用)。kind = call | watch | after | listen | letter | nod | touch"""
    if (request.client.host if request.client else "") not in LOOPBACK:
        return JSONResponse({"error": "forbidden"}, status_code=403)
    if kind in ("call", "watch", "letter"):
        msgs = [m for m in [lantern._set(kind)] if m]
        if kind == "letter":
            msgs.append({"type": "letter", "server_time": time.time()})
    elif kind == "after":
        msgs = [m for m in [lantern._set("after")] if m]
        msgs.append({"type": "speak", "dur": 3.0, "hz": ENV_HZ, "env": mouth_envelope("こんにちは、きょうもいいひだね。", 3.0),
                     "then": "listen", "server_time": time.time()})
    elif kind == "listen":
        msgs = [{"type": "await_answer", "server_time": time.time()}]
    elif kind in ("nod", "touch"):
        msgs = [{"type": kind, "server_time": time.time()}]
    else:
        return JSONResponse({"error": "unknown"}, status_code=404)
    await lantern.broadcast(msgs)
    return {"ok": True, "sent": [m["type"] for m in msgs], "peers": len(lantern.peers)}


@app.post("/cue")
async def cue(request: Request):
    """Mac の中からだけ: 会話デモ(talk_demo)の合図。kind = watch | listen | think | speak | nod | letter。
    speak の text は口の開きを作るのに使うだけで、Pi へは送らない。"""
    if (request.client.host if request.client else "") not in LOOPBACK:
        return JSONResponse({"error": "forbidden"}, status_code=403)
    b = await request.json()
    kind, now = b.get("kind"), time.time()
    msgs: list[dict | None] = []
    if kind in ("watch", "think", "letter", "call"):
        msgs.append(lantern._set(kind))
        if kind == "letter":
            msgs.append({"type": "letter", "server_time": now})
    elif kind == "listen":
        msgs.append(lantern._set("listen"))
        msgs.append({"type": "await_answer", "server_time": now})
    elif kind == "speak":
        dur = float(b.get("dur") or 0)
        msgs.append(lantern._set("after"))
        msgs.append({"type": "speak", "dur": round(dur, 2), "hz": ENV_HZ, "env": mouth_envelope(str(b.get("text") or ""), dur),
                     "then": "listen" if b.get("then") == "listen" else "watch", "server_time": now})
        if b.get("then") == "listen":
            lantern.mood = "listen"                 # 話し終えたら Pi 側で「聞く」に移る。中継の状態も合わせる
    elif kind in ("nod", "touch"):
        msgs.append({"type": kind, "server_time": now})
    elif kind == "uneasy":
        msgs.append(lantern._uneasy(float(b.get("sus") or 0), float(b.get("ask") or 0)))
    elif kind == "glance":
        msgs.append({"type": "glance", "gaze": float(b.get("gaze") or -0.8), "server_time": now})
    else:
        return JSONResponse({"error": "unknown"}, status_code=404)
    out = [m for m in msgs if m]
    await lantern.broadcast(out)
    return {"ok": True, "sent": [m["type"] for m in out], "peers": len(lantern.peers)}


@app.get("/status")
def status():
    return {"mood": lantern.mood, "upstream": lantern.upstream_ok, "peers": len(lantern.peers)}


if LANTERN_WEB.exists():
    app.mount("/", StaticFiles(directory=LANTERN_WEB, html=True), name="lantern")


def main() -> None:
    ap = argparse.ArgumentParser(description="ふすまの中の Claude への中継")
    ap.add_argument("--host", default="0.0.0.0")
    ap.add_argument("--port", type=int, default=8781)
    ap.add_argument("--allow", nargs="*", default=[], help="台所の端末として全部の合図を受け取ってよい Pi の IP")
    ap.add_argument("--family", nargs="*", default=[], help="家族の机の上の Pi の IP(便りが届いたことだけ)")
    ap.add_argument("--replay", help="端末につながず、録画の timing.json を流し直す")
    ap.add_argument("--replay-from", type=float, default=0.0, help="録画の何秒目から流すか")
    ap.add_argument("--replay-speed", type=float, default=1.0)
    ap.add_argument("--replay-lead", type=float, default=3.0, help="起動してから流し始めるまでの秒数")
    ap.add_argument("--talk", action="store_true", help="会話デモ用: 端末につながず、/cue の合図だけを流す")
    ap.add_argument("--replay-manual", action="store_true", help="POST /replay/start で始める(録画と時刻を合わせるとき)")
    a = ap.parse_args()
    ALLOW.update(a.allow)
    FAMILY.update(a.family)
    TALK["on"] = a.talk
    if a.replay:
        REPLAY.update(path=a.replay, start=a.replay_from, speed=a.replay_speed, lead=a.replay_lead, manual=a.replay_manual)
    print(f"[lantern] bridge on {a.host}:{a.port}, kitchen={sorted(ALLOW)}, family={sorted(FAMILY)}"
          + (f", replay={a.replay}@{a.replay_from}s" if a.replay else ""), flush=True)
    uvicorn.run(app, host=a.host, port=a.port, log_level="warning")


if __name__ == "__main__":
    main()
