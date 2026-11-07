"""ふすまの中の Claude と話す(会話デモ)。

Mac のマイクで聞き(Silero VAD → whisper.cpp)、Mac で考え(Claude)、Mac のスピーカーで話す(AivisSpeech「まお」)。
Pi の画面へは、中継(lantern_bridge --talk)を通して表情の合図だけを送る。文字は Pi へ送らない。

  ../.venv/bin/python -m fusuma.talk_demo [--idle 40] [--save]                      (app/ で実行)

前提: whisper(:8765)、AivisSpeech(:10101)、中継 `python -m fusuma.lantern_bridge --talk --allow <Pi の IP>`(:8781)。

- 話しかけられると「聞く」顔になり、話の切れ目でうなずく。
- 話し終えると「考え中」(頭をぽりぽり、点々)になり、Claude の返事ができたら、口を動かして話す。
- しばらく(--idle 秒)だれも話さないと、自分から短い質問をする。
- --save で、マイクの音・返事の声・合図の時刻を lab/runs/talk/<時刻>/ に残す(動画の素材用。Mac の中だけ)。
"""
from __future__ import annotations

import argparse
import io
import json
import queue
import threading
import time
from datetime import datetime
from pathlib import Path

import httpx
import numpy as np
import sounddevice as sd
import soundfile as sf

from . import config
from .brain import llm
from .ear import asr
from .ear.vad import CHUNK, StreamSegmenter

BRIDGE = "http://127.0.0.1:8781/cue"
ENGINE = "http://127.0.0.1:10101"
STYLE = 888753763                       # AivisSpeech「まお」おちつき
RUNS = Path(__file__).resolve().parents[2] / "runs" / "talk"

SYSTEM = """あなたは「ふすまの中の Claude」。手作りの小さなふすまの中の画面に住んでいる、コーラル色の小さな生きものです。
台所の机の上から、家族(小さな子どもも)と話します。

話し方:
- 返事は話し言葉で 1〜2 文、全部で 50 文字くらいまで。やさしく、明るく、少しおちゃめに。
- 声で読み上げるので、記号・絵文字・かっこ・箇条書き・英字・数字の羅列は使わない。
- 子どもにも分かる言葉で。分からないことは正直に「わからないなあ」と言う。
- ときどき(毎回ではなく)相手に短い質問を返して、話を続ける。
- 聞き取りがおかしい文が来たら、ききかえす。
- 危ないこと・こわいことはすすめない。"""

ASR_PROMPT = "子どもと、おうちで話しています。きょう、ようちえん、がっこう、こうえん、ブランコ、すべりだい、おやつ、どうぶつ、ねこ、いぬ、パパ、ママ。"

IDLE_ASK = "(しばらく、だれも話していません。話しかけるきっかけになる、短くて楽しい質問を一つだけしてください。前の話があれば、それにつなげて)"


class Talk:
    def __init__(self, a: argparse.Namespace):
        self.a = a
        self.http = httpx.Client(timeout=30)
        self.seg = StreamSegmenter(min_silence_ms=a.silence_ms)
        self.q: queue.Queue[np.ndarray] = queue.Queue()
        self.busy = threading.Event()          # 考えている / 話しているあいだは聞かない(半二重)
        self.history: list[dict] = []
        self.mood = "watch"
        self.last_activity = time.time()
        self.listen_until = 0.0
        self.speech_started = 0.0
        self.last_nod = 0.0
        self.unanswered = 0                    # 返事のなかった自分からの質問(2 回で、話しかけられるまでやめる)
        self.out: Path | None = None
        self.mic_file: sf.SoundFile | None = None
        self.t0 = time.time()
        if a.save:
            self.out = RUNS / datetime.now().strftime("%Y%m%d_%H%M%S")
            self.out.mkdir(parents=True, exist_ok=True)
            self.mic_file = sf.SoundFile(self.out / "mic.wav", "w", samplerate=config.SR, channels=1, subtype="PCM_16")
            print(f"[talk] saving to {self.out}", flush=True)

    # ---------- 記録 ----------
    def log(self, kind: str, **kw) -> None:
        rec = {"t": round(time.time() - self.t0, 3), "wall": time.time(), "kind": kind, **kw}
        if self.out:
            with open(self.out / "events.jsonl", "a") as f:
                f.write(json.dumps(rec, ensure_ascii=False) + "\n")

    # ---------- Pi への合図 ----------
    def cue(self, kind: str, **kw) -> None:
        if kind in ("watch", "listen", "think", "speak"):
            self.mood = "listen" if (kind == "speak" and kw.get("then") == "listen") else ("after" if kind == "speak" else kind)
        try:
            self.http.post(BRIDGE, json={"kind": kind, **kw}, timeout=2)
        except Exception as e:
            print(f"[talk] bridge: {e}", flush=True)
        self.log("cue", cue=kind, **{k: v for k, v in kw.items() if k != "text"})

    # ---------- 声 ----------
    def tts(self, text: str) -> tuple[np.ndarray, int]:
        q = self.http.post(f"{ENGINE}/audio_query", params={"text": text, "speaker": STYLE}).json()
        q["speedScale"] = self.a.speed
        q["prePhonemeLength"], q["postPhonemeLength"] = 0.05, 0.15
        r = self.http.post(f"{ENGINE}/synthesis", params={"speaker": STYLE}, json=q, timeout=60)
        r.raise_for_status()
        data, sr = sf.read(io.BytesIO(r.content), dtype="float32")
        return data, sr

    def say(self, text: str, then: str = "listen") -> None:
        audio, sr = self.tts(text)
        dur = len(audio) / sr
        print(f"  🟠 {text}  ({dur:.1f}s)", flush=True)
        n = sum(1 for _ in self.out.glob("say_*.wav")) if self.out else 0
        if self.out:
            sf.write(self.out / f"say_{n:03d}.wav", audio, sr)
        self.log("say", text=text, dur=round(dur, 3), wav=f"say_{n:03d}.wav" if self.out else None)
        self.cue("speak", text=text, dur=dur, then=then)
        sd.play(audio * self.a.volume, sr)
        sd.wait()
        time.sleep(0.25)                                  # 部屋の残響が消えるまで
        self.listen_until = time.time() + self.a.listen_after
        self.last_activity = time.time()

    # ---------- 考える ----------
    def think(self, user_text: str, idle: bool = False) -> str:
        self.history.append({"role": "user", "content": user_text})
        self.history = self.history[-16:]
        if self.history[0]["role"] != "user":
            self.history = self.history[1:]
        text = ""
        for _ in range(2):                         # 考えすぎて文が空になったら、もう一度だけ
            text, _r = llm.call("talk_idle" if idle else "talk", self.a.model, SYSTEM, self.history,
                                max_tokens=1500, effort="low")
            text = str(text).strip().replace("\n", "")
            if text:
                break
        if not text:
            text = "うーん、ちょっとかんがえちゃった。もういっかい、おはなしして?"
        self.history.append({"role": "assistant", "content": text})
        return text

    def respond(self, seg_audio: np.ndarray) -> None:
        try:
            t_asr = time.time()
            text = asr.transcribe(seg_audio, prompt=ASR_PROMPT)
            if not text:
                self.cue("watch")
                return
            print(f"\n👂 {text}   (asr {time.time() - t_asr:.1f}s)", flush=True)
            self.log("heard", text=text)
            self.unanswered = 0
            self.cue("think")
            t_llm = time.time()
            reply = self.think(text)
            self.log("reply", text=reply, sec=round(time.time() - t_llm, 2))
            self.say(reply)
        except Exception as e:
            print(f"[talk] error: {e}", flush=True)
            self.cue("watch")
        finally:
            self.seg.reset()
            self.busy.clear()

    def ask(self) -> None:
        try:
            self.cue("think")
            q = self.think(IDLE_ASK, idle=True)
            self.log("ask", text=q)
            self.unanswered += 1
            print("\n💭 (しばらく静かだったので)", flush=True)
            self.say(q)
        except Exception as e:
            print(f"[talk] error: {e}", flush=True)
            self.cue("watch")
        finally:
            self.seg.reset()
            self.busy.clear()

    # ---------- 聞く ----------
    def run(self) -> None:
        def cb(indata, frames, t, status):
            self.q.put(indata[:, 0].copy())

        self.cue("watch")
        if self.a.greet:
            self.busy.set()
            threading.Thread(target=self._greet, daemon=True).start()
        print("[talk] listening (Ctrl+C で終わり)", flush=True)
        with sd.InputStream(samplerate=config.SR, channels=1, dtype="float32", blocksize=CHUNK, callback=cb,
                            device=self.a.mic):
            while True:
                try:
                    chunk = self.q.get(timeout=0.5)
                except queue.Empty:
                    chunk = None
                now = time.time()
                if chunk is not None and self.mic_file:
                    self.mic_file.write(chunk)
                if self.busy.is_set():
                    continue
                if chunk is not None and len(chunk) == CHUNK:
                    was = self.seg.in_speech
                    segs = self.seg.feed(chunk * self.a.gain)
                    if self.seg.in_speech and not was:
                        self.speech_started = now
                        self.last_activity = now
                        if self.mood != "listen":
                            self.cue("listen")
                    # 話の途中の小さな切れ目で、うなずく
                    if self.seg.in_speech and self.seg.silence_run == 6 and now - self.speech_started > 1.2 and now - self.last_nod > 1.8:
                        self.last_nod = now
                        self.cue("nod")
                    for s in segs:
                        if s.dur < 0.35:
                            continue
                        self.busy.set()
                        self.last_activity = now
                        threading.Thread(target=self.respond, args=(s.audio,), daemon=True).start()
                        break
                if self.busy.is_set() or self.seg.in_speech:
                    continue
                if self.mood == "listen" and now > self.listen_until and now - self.speech_started > 3:
                    self.cue("watch")
                if self.a.idle > 0 and self.unanswered < self.a.max_asks and self.mood == "watch" and now - self.last_activity > self.a.idle:
                    self.busy.set()
                    self.last_activity = now
                    threading.Thread(target=self.ask, daemon=True).start()

    def _greet(self) -> None:
        try:
            self.say(self.a.greet)
            self.history = [{"role": "user", "content": "(あなたが画面にあらわれました)"}, {"role": "assistant", "content": self.a.greet}]
        finally:
            self.seg.reset()
            self.busy.clear()


def main() -> None:
    ap = argparse.ArgumentParser(description="ふすまの中の Claude と話す")
    ap.add_argument("--model", default="claude-sonnet-5-5")
    ap.add_argument("--idle", type=float, default=40.0, help="この秒数だれも話さなければ、自分から質問する(0 で止める)")
    ap.add_argument("--max-asks", type=int, default=2, help="返事がないまま自分から質問するのは、この回数まで")
    ap.add_argument("--listen-after", type=float, default=8.0, help="話し終えてから、聞く顔で待つ秒数")
    ap.add_argument("--silence-ms", type=int, default=800, help="この長さ黙ったら、話し終えたとみなす")
    ap.add_argument("--speed", type=float, default=1.05)
    ap.add_argument("--volume", type=float, default=0.9)
    ap.add_argument("--gain", type=float, default=1.0, help="マイクの音を何倍にして聞くか")
    ap.add_argument("--mic", default=None, help="入力デバイス(番号か名前)。既定は Mac の既定")
    ap.add_argument("--greet", default="", help="始めに話す一言(空なら話さない)")
    ap.add_argument("--save", action="store_true", help="マイクの音・返事の声・合図の時刻を runs/talk に残す")
    a = ap.parse_args()
    if a.mic and a.mic.isdigit():
        a.mic = int(a.mic)
    t = Talk(a)
    try:
        t.run()
    except KeyboardInterrupt:
        pass
    finally:
        if t.mic_file:
            t.mic_file.close()
        t.cue("watch")
        print(f"\n[talk] bye. spent ${llm.spent_usd():.2f} total", flush=True)


if __name__ == "__main__":
    main()
