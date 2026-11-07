"""端末の入出力: 仮想の部屋(デモ用の音の通り道)とスピーカー(TTS)。マイク入力は ear/pipeline.py の Ear.run_mic(FUSUMA_INPUT=mic。未検証)。"""
from __future__ import annotations

import io
import json
import queue
import threading
import time
from datetime import datetime
from pathlib import Path

import httpx
import numpy as np
import soundfile as sf

from . import config
from .ear.vad import CHUNK


class VirtualRoom:
    """部屋の音を 32ms ずつ実時間で流す。何も鳴っていないときは小さな環境音。
    デモでは、ここに通話の音声や、祖母の答えの音声を流し込む(同時にスピーカーからも鳴らす)。"""

    def __init__(self, audible: bool = True):
        self.audible = audible
        self.q: "queue.Queue[tuple[np.ndarray, Path | None, callable]]" = queue.Queue()
        self.cur: np.ndarray | None = None
        self.pos = 0
        self.done_cb = None
        self.rng = np.random.default_rng(0)
        self.busy = False

    def inject(self, wav16: Path, play: Path | None = None, on_done=None) -> float:
        a, sr = sf.read(wav16, dtype="float32")
        assert sr == config.SR
        self.q.put((a, play, on_done))
        return len(a) / sr

    def _next_chunk(self) -> np.ndarray:
        if self.cur is None and not self.q.empty():
            self.cur, play, self.done_cb = self.q.get()
            self.pos = 0
            self.busy = True
            if play is not None and self.audible:
                import sounddevice as sd
                pa, psr = sf.read(play, dtype="float32")
                threading.Thread(target=lambda: sd.play(pa, psr), daemon=True).start()
        if self.cur is not None:
            chunk = self.cur[self.pos:self.pos + CHUNK]
            self.pos += CHUNK
            if len(chunk) < CHUNK:
                chunk = np.pad(chunk, (0, CHUNK - len(chunk)))
                cb = self.done_cb
                self.cur, self.done_cb, self.busy = None, None, False
                if cb:
                    threading.Thread(target=cb, daemon=True).start()
            return chunk.astype(np.float32)
        return (self.rng.normal(0, 0.0006, CHUNK)).astype(np.float32)

    def run(self, feed, stop: threading.Event) -> None:
        t0 = time.monotonic()
        n = 0
        while not stop.is_set():
            feed(self._next_chunk())
            n += 1
            lag = n * CHUNK / config.SR - (time.monotonic() - t0)
            if lag > 0:
                time.sleep(lag)


class Speaker:
    """ふすまごしの声(Qwen3-TTS, ローカル)。
    再生の直前と再生中に may_speak() を確かめ、電話が鳴ったら再生をやめる(合成に数秒かかるあいだの着信にも備える)。
    save=True のときだけ、話した音声を runs/speech に残す(デモ動画の編集用。ふだんは残さない)。"""

    def __init__(self, audible: bool = True, out_dir: Path = config.RUNS / "speech", save: bool = False):
        self.audible = audible
        self.save = save
        self.out_dir = out_dir
        self.client = httpx.Client(timeout=120)
        self.log = out_dir / "speech_log.jsonl"
        self.speaking_until = 0.0

    def synth(self, text: str, persona: str = "fusuma") -> tuple[np.ndarray, int]:
        r = self.client.post(config.TTS_URL, json={"persona": persona, "text": text, "seed": 7})
        r.raise_for_status()
        a, sr = sf.read(io.BytesIO(r.content), dtype="float32")
        return a, sr

    def say(self, text: str, before_play=None, may_speak=None) -> float | None:
        """話す。途中で話せなくなったら(電話が鳴ったら)None を返す。"""
        ok = may_speak or (lambda: True)
        a, sr = self.synth(text)
        dur = len(a) / sr
        if not ok():                       # 合成しているあいだに電話が鳴った
            return None
        if before_play:
            before_play(dur)
        if self.save:
            ts = datetime.now()
            self.out_dir.mkdir(parents=True, exist_ok=True)
            path = self.out_dir / f"{ts.strftime('%Y%m%d-%H%M%S')}_fusuma.wav"
            sf.write(path, a, sr)
            with self.log.open("a") as f:
                f.write(json.dumps({"ts": ts.isoformat(timespec="milliseconds"), "text": text, "file": path.name, "dur": round(dur, 2)},
                                   ensure_ascii=False) + "\n")
        self.speaking_until = time.time() + dur
        block = int(0.1 * sr)
        if self.audible:
            # 自分専用の出力ストリームに 0.1 秒ずつ書く。途中でやめても、部屋の音(VirtualRoom の再生)は止めない
            import sounddevice as sd
            with sd.OutputStream(samplerate=sr, channels=1, dtype="float32") as out:
                for i in range(0, len(a), block):
                    if not ok():
                        out.abort()
                        self.speaking_until = time.time()
                        return None
                    out.write(a[i:i + block].reshape(-1, 1))
            return dur
        t_end = time.monotonic() + dur
        while time.monotonic() < t_end:    # 音を出さない設定でも、同じ間隔で確かめる
            if not ok():
                self.speaking_until = time.time()
                return None
            time.sleep(0.1)
        return dur
