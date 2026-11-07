"""耳のパイプライン: マイク(またはファイル) → 音イベント → 通話状態 → 祖母の発話 → 音声スコア。

- ASR が動くのは「通話中」と「ふすまごしが話しかけた直後」だけ。それ以外の独り言や生活音は文字にしない。
- 端末自身が話している間は聞かない(半二重)。
- 出すのはイベント(dict)だけ。判断はしない。
"""
from __future__ import annotations

import queue
import threading
import time
import uuid
from collections import deque
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta
from pathlib import Path
from typing import Callable

import numpy as np
import soundfile as sf

from .. import config
from . import asr, prosody
from .ma import MaTracker, summary_line
from .score import event_line, utt_line
from .sed import HOP, WIN, SoundEvents
from .vad import CHUNK, StreamSegmenter

BASELINE_PATH = config.RUNS / "baseline_grandma.json"
SHIPPED_BASELINE = config.ROOT / "eval" / "baseline_grandma.json"   # リポジトリに同梱した「いつもの声」(合成音声の祖母)


def baseline_path() -> Path:
    """calibrate_baseline.py で作った「いつもの声」。まだ作っていなければ、リポジトリに同梱したものを使う。"""
    return BASELINE_PATH if BASELINE_PATH.exists() else SHIPPED_BASELINE


class Ear:
    def __init__(self, on_event: Callable[[dict], None], start_wall: datetime | None = None,
                 sed: SoundEvents | None = None, realtime: bool = False):
        self.emit = on_event
        self.sed = sed or SoundEvents()
        self.vad = StreamSegmenter()
        self.base = prosody.Baseline.load(baseline_path())
        self.start_wall = start_wall or datetime.now()
        self.realtime = realtime
        self.pool = ThreadPoolExecutor(max_workers=1) if realtime else None
        self._pending = 0                       # 文字にしている途中の発話区間の数
        self._plock = threading.Lock()
        self.reset_audio()

    # ---------- 状態 ----------
    def reset_audio(self) -> None:
        self.t = 0.0
        self.ring = deque(maxlen=int(WIN * config.SR) + CHUNK)
        self.next_sed = WIN
        self.next_level = 0.1
        self.state = "idle"
        self.call: dict | None = None
        self.ma: MaTracker | None = None
        self.sound_marks: list[tuple[float, float, str]] = []   # (start, end, event)
        self.last_speech_end = 0.0
        self.last_voice_end = -1e9               # 部屋で最後に声がした時刻(文字にしたかどうかに関係なく)
        self.room_until = -1.0
        self.room_tag = None
        self.vad.reset()

    def set_clock(self, wall_now: datetime) -> None:
        """今この瞬間を wall_now として時刻を振り直す(デモで台本の時刻に合わせる)。"""
        self.start_wall = wall_now - timedelta(seconds=self.t)

    def clock(self, t: float) -> str:
        return (self.start_wall + timedelta(seconds=t)).strftime("%H:%M:%S")

    def wall(self, t: float) -> datetime:
        return self.start_wall + timedelta(seconds=t)

    # ---------- 外部から ----------
    def open_room_listen(self, seconds: float, tag: str = "postcall") -> None:
        """ふすまごしが話しかけた直後だけ、部屋の声を聞く。"""
        self.room_until = self.t + seconds
        self.room_tag = tag

    def mute_for(self, seconds: float) -> None:
        self.vad.mute_until(self.t + seconds)

    def quiet_for(self, seconds: float) -> bool:
        """部屋がこれだけの時間、静かだったか(誰かが話していたら、話しかけない)。"""
        return not self.vad.in_speech and self.t - self.last_voice_end >= seconds

    # ---------- 1 チャンク(32ms) ----------
    def feed(self, chunk: np.ndarray) -> None:
        self.ring.extend(chunk)
        self.t += CHUNK / config.SR
        if self.t >= self.next_level:
            self.next_level += 0.1
            rms = float(np.sqrt(np.mean(chunk ** 2) + 1e-12))
            self.emit({"type": "level", "t": round(self.t, 2), "db": round(20 * np.log10(rms + 1e-12), 1),
                       "state": self.state})
        if self.t >= self.next_sed:
            self.next_sed += HOP
            self._sed(np.array(self.ring, dtype=np.float32)[-int(WIN * config.SR):], self.t - WIN)
        for seg in self.vad.feed(chunk):
            self._segment(seg)
        self._timeouts()

    def _sed(self, window: np.ndarray, t0: float) -> None:
        frames = self.sed.run(window, t0)
        if not frames:
            return
        c = self.sed.classify(frames[0])
        ev = c["event"]
        if ev:
            self.sound_marks.append((t0, t0 + WIN, ev))
        self._on_sound(ev, t0, c)

    def _on_sound(self, ev: str | None, t0: float, info: dict) -> None:
        if ev is None:
            return
        if ev == "ring" and self.state in ("idle", "ended"):
            self._new_call("incoming", t0)
            self._set_state("ringing", t0, info)
        elif ev == "dial" and self.state in ("idle", "ended"):
            self._new_call("outgoing", t0)
            self._set_state("dialing", t0, info)
        elif ev == "handset":
            if self.state in ("ringing", "dialing"):
                self._set_state("in_call", t0 + 0.4, info, sound="pickup")
            elif self.state == "in_call" and self.call and t0 - self.call["start_t"] > 3.0 and t0 > self.last_speech_end:
                self._end_call(t0 + 0.4, reason="hangup")
        elif ev == "doorbell":
            self.emit({"type": "sound", "event": "doorbell", "t": round(t0, 2), "clock": self.clock(t0)})

    def _new_call(self, direction: str, t0: float) -> None:
        cid = self.wall(t0).strftime("%Y%m%d-%H%M") + "-" + uuid.uuid4().hex[:4]
        self.call = {"call_id": cid, "direction": direction, "ring_t": t0, "start_t": None, "lines": []}

    def _set_state(self, state: str, t: float, info: dict | None = None, sound: str | None = None) -> None:
        if state == self.state:
            return
        self.state = state
        if state == "in_call" and self.call is not None:
            self.call["start_t"] = t
            self.ma = MaTracker(call_start=t)
            self.last_speech_end = t
            self.call["lines"].append(event_line(self.clock(t), "pickup" if self.call["direction"] == "incoming" else "dial"))
        ev = {"type": "state", "state": state, "t": round(t, 2), "clock": self.clock(t),
              "call_id": self.call["call_id"] if self.call else None,
              "direction": self.call["direction"] if self.call else None}
        if sound:
            ev["sound"] = sound
        if info:
            ev["sed"] = {k: info[k] for k in ("phone", "sims", "top") if k in info}
        self.emit(ev)

    def _end_call(self, t: float, reason: str) -> None:
        if not self.call:
            return
        call, ma = self.call, self.ma
        self.state = "ended"
        self.call = None
        self.ma = None

        def emit_end() -> None:
            call["lines"].append(event_line(self.clock(t), "hangup"))
            summary = ma.summary(t) if ma else {}
            self.emit({"type": "state", "state": "ended", "t": round(t, 2), "clock": self.clock(t), "reason": reason,
                       "call_id": call["call_id"], "direction": call["direction"], "ma": summary,
                       "ma_line": summary_line(self.clock(t), summary), "lines": list(call["lines"]),
                       "started": self.wall(call["start_t"] or t).isoformat(timespec="seconds"),
                       "duration": round(t - (call["start_t"] or t), 1)})

        if self.pool:      # 受話器を置く直前の発話を文字にし終えてから(ASR のプールは 1 本なので、先に入った区間が先に終わる)
            with self._plock:
                self._pending += 1
            self.pool.submit(self._process_counted_fn, emit_end)
        else:
            emit_end()

    def _timeouts(self) -> None:
        if self.state == "in_call" and self.call and not self.vad.in_speech:
            if self.t - self.last_speech_end > config.LONG_SILENCE_END_SEC:
                self._end_call(self.t, reason="silence")
        if self.state in ("ringing", "dialing") and self.call and self.t - self.call["ring_t"] > 40:
            self.emit({"type": "state", "state": "idle", "t": round(self.t, 2), "clock": self.clock(self.t), "reason": "no_answer"})
            self.state, self.call = "idle", None

    # ---------- 発話区間 ----------
    def _overlaps_sound(self, s: float, e: float) -> bool:
        for a, b, ev in self.sound_marks[-12:]:
            if ev in ("ring", "dial", "handset", "doorbell"):
                ov = min(e, b) - max(s, a)
                if ov > 0.45 * (e - s) and (e - s) < 2.5:
                    return True
        return False

    def _segment(self, seg) -> None:
        self.last_voice_end = max(self.last_voice_end, seg.end)
        in_room = seg.start <= self.room_until and self.state in ("idle", "ended")   # 窓の中で話し始めた答えは、終わりが窓の外でも聞く
        if self.state == "ringing" and not self._overlaps_sound(seg.start, seg.end):
            self._set_state("in_call", seg.start - 0.3)     # 受話器の音を聞き逃しても、話し始めたら通話中
        if self.state == "dialing" and not self._overlaps_sound(seg.start, seg.end):
            self._set_state("in_call", seg.start - 0.3)
        if self.state != "in_call" and not in_room:
            return                                           # 通話外の独り言は文字にしない
        if self._overlaps_sound(seg.start, seg.end):
            return
        kind = "utt" if self.state == "in_call" else "room_utt"
        pre_pause = max(0.0, seg.start - self.last_speech_end) if kind == "utt" else 0.0
        if kind == "utt":
            self.last_speech_end = seg.end
        job = (seg, kind, pre_pause, self.call if kind == "utt" else None, self.ma if kind == "utt" else None, self.room_tag)
        if self.pool:
            with self._plock:
                self._pending += 1
            self.pool.submit(self._process_counted, *job)
        else:
            self._process(*job)

    def _process_counted(self, *job) -> None:
        self._process_counted_fn(self._process, *job)

    def _process_counted_fn(self, fn, *args) -> None:
        try:
            fn(*args)
        finally:
            with self._plock:
                self._pending -= 1

    def hearing(self) -> bool:
        """いま話し声を聞いている途中か、文字にしている途中か(電話のあとの答えがまだ続くかの判断に使う)。"""
        return self.vad.in_speech or self._pending > 0

    def _process(self, seg, kind: str, pre_pause: float, call: dict | None, ma: MaTracker | None, tag: str | None) -> None:
        """1 区間を文字にする。区間を切った時点の通話(call)に結びつける(文字にしているあいだに電話が終わっても、次の電話に混ざらない)。"""
        call_id = call["call_id"] if call else None
        try:
            text = asr.transcribe(seg.audio)
        except Exception as e:  # ASR が落ちても通話の追跡は止めない
            self.emit({"type": "error", "where": "asr", "message": str(e)})
            return
        if not text:
            return
        feat = prosody.measure(seg.audio)
        rel = prosody.relative(feat, text, self.base)
        u = {"type": kind, "call_id": call_id, "tag": tag, "clock": self.clock(seg.start), "t": round(seg.start, 2),
             "end": round(seg.end, 2), "text": text, "pre_pause": round(pre_pause, 1), "dur": feat["dur"],
             "f0": feat["f0"], "db": feat["db"], "backchannel": prosody.is_backchannel(text, feat["dur"]),
             "tv": False, **rel}
        if kind == "utt" and ma is not None:
            ma.add(u)
            u["ma"] = ma.summary(seg.end)
            line = utt_line(u)
            u["line"] = line
            if call is not None:
                call["lines"].append(line)
        self.emit(u)

    def drain(self) -> None:
        if self.pool:
            self.pool.shutdown(wait=True)
            self.pool = ThreadPoolExecutor(max_workers=1)

    # ---------- 入力源 ----------
    def run_file(self, path: Path, realtime: bool = False, play_path: Path | None = None,
                 stop: threading.Event | None = None) -> None:
        audio, sr = sf.read(path, dtype="float32")
        assert sr == config.SR, f"{path} must be 16kHz"
        player = None
        if play_path is not None:
            import sounddevice as sd
            pa, psr = sf.read(play_path, dtype="float32")
            sd.play(pa, psr)
            player = sd
        t_start = time.monotonic()
        for i in range(0, len(audio) - CHUNK, CHUNK):
            if stop is not None and stop.is_set():
                break
            self.feed(audio[i:i + CHUNK])
            if realtime:
                lag = (i + CHUNK) / config.SR - (time.monotonic() - t_start)
                if lag > 0:
                    time.sleep(lag)
        for seg in self.vad.flush():
            self._segment(seg)
        if self.state == "in_call":
            self._end_call(self.t, reason="eof")
        self.drain()
        if player is not None:
            player.stop()

    def run_mic(self, stop: threading.Event) -> None:
        import sounddevice as sd
        q: "queue.Queue[np.ndarray]" = queue.Queue()

        def cb(indata, frames, t, status):
            q.put(indata[:, 0].copy())

        with sd.InputStream(samplerate=config.SR, channels=1, blocksize=CHUNK, dtype="float32", callback=cb):
            while not stop.is_set():
                try:
                    self.feed(q.get(timeout=0.5))
                except queue.Empty:
                    continue
