"""デモの電話をかける(祖母役が台本を読む)。Mac のスピーカーで、発信音 → 相手の声 → 切る音 を流す。

  lab/.venv/bin/python lab/scripts/phone_sim.py [--line video/assets/police/scam_line.wav] [--line-device <番号|名前>]

- 発信音(dial)と切る音(hangup)は部屋のスピーカーから流す。ふすまごしの耳は、これで電話の始まりと終わりを知る。
- 相手(犯人)の声は --line-device(イヤホンなど)へ。指定がなければ部屋のスピーカーから流し、そのあいだだけ
  端末の耳を止める(/api/ear/mute)。本物では受話器を耳に当てていて、部屋のマイクには祖母の声しか届かない。その再現。
- 流した時刻を lab/runs/phone_sim/<時刻>.json に残す(動画で相手の声を重ねるため)。
"""
import argparse
import json
import threading
import time
from datetime import datetime
from pathlib import Path

import httpx
import numpy as np
import sounddevice as sd
import soundfile as sf

LAB = Path(__file__).resolve().parents[1]
ROOT = LAB.parent
SFX = LAB / "data" / "sfx"
API = "http://127.0.0.1:8780"


def play(path: Path, device=None, gain: float = 1.0) -> float:
    x, sr = sf.read(path, dtype="float32")
    sd.play(x * gain, sr, device=device)
    sd.wait()
    return len(x) / sr


def ear_state(http) -> str:
    try:
        return http.get(f"{API}/api/state").json().get("ear_state", "?")
    except Exception:
        return "?"


def ensure(http, want: tuple, event: str, wait: float = 2.0) -> None:
    """マイクが音を聞き分けたかを見て、聞き逃していたらフックの合図を送る(予備)。"""
    t = time.time() + wait
    while time.time() < t:
        if ear_state(http) in want:
            print(f"  (耳: {want[0]} を聞き分けた)", flush=True)
            return
        time.sleep(0.25)
    http.post(f"{API}/api/ear/hook", json={"event": event})
    print(f"  (耳が聞き逃したので、フックの合図 {event} を送った → {ear_state(http)})", flush=True)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--line", default=str(ROOT / "video/assets/police/scam_line.wav"))
    ap.add_argument("--line-device", default=None, help="相手の声を出す機器(イヤホン)。なければ部屋のスピーカー + 耳を止める")
    ap.add_argument("--line-gain", type=float, default=0.8)
    ap.add_argument("--countdown", type=float, default=3.0)
    ap.add_argument("--guide", nargs="?", const=str(ROOT / "video/assets/police/afureko_guide_silent.mp4"), default=None,
                    help="アフレコガイドの動画(音なし)を QuickTime で全画面に出し、相手の声と同時に再生する")
    ap.add_argument("--stand-in", action="store_true", help="祖母の台詞を Mac の声(Kyoko)で代わりに読む(リハーサル用)")
    a = ap.parse_args()
    dev = int(a.line_device) if a.line_device and a.line_device.isdigit() else a.line_device
    line = Path(a.line)
    meta = json.loads(line.with_suffix(".json").read_text())
    spans, turns = meta["caller_spans"], meta.get("victim_turns", [])
    http = httpx.Client(timeout=3)
    log = {"line": str(line), "events": []}

    def mark(kind, **kw):
        log["events"].append({"kind": kind, "wall": time.time(), **kw})

    def qt(script: str) -> None:
        import subprocess
        subprocess.run(["osascript", "-e", f'tell application "QuickTime Player" to {script}'], check=False)

    import subprocess as _sp
    vol = _sp.run(["osascript", "-e", "get volume settings"], capture_output=True, text=True).stdout
    if "output muted:true" in vol or "output volume:0," in vol:
        print("⚠️  Mac のスピーカーが消音です。発信音と相手の声が鳴らないので、音を出せるようにしてから、もう一度。", flush=True)
        raise SystemExit(1)
    if a.guide:                                       # 先に開いて、頭で止めておく(再生の合図だけを相手の声と同時に)
        qt(f'open POSIX file "{Path(a.guide).resolve()}"')
        time.sleep(1.5)
        qt("tell document 1 to set presenting to true")
        time.sleep(1.0)
        qt("tell document 1 to pause")
        qt("tell document 1 to set current time to 0")
    for i in range(int(a.countdown), 0, -1):
        print(f"  {i}…", flush=True); time.sleep(1)
    print("📞 発信", flush=True)
    mark("dial")
    play(SFX / "dial.wav")
    ensure(http, ("dialing", "in_call"), "dial", wait=1.5)
    time.sleep(0.3)

    x, sr = sf.read(line, dtype="float32")
    if a.guide:
        qt("tell document 1 to play")                 # ガイドの 0 秒と相手の声の 0 秒をそろえる
    t0 = time.time()
    mark("line_start", t0=t0)
    if dev is None:                                   # 部屋のスピーカーから流すときは、相手の声のあいだ耳を止める
        def muter():
            for sp in spans:
                wait = t0 + sp["start"] - 0.15 - time.time()
                if wait > 0:
                    time.sleep(wait)
                try:
                    http.post(f"{API}/api/ear/mute", json={"seconds": sp["end"] - sp["start"] + 0.45})
                except Exception as e:
                    print("mute failed:", e, flush=True)
        threading.Thread(target=muter, daemon=True).start()

    import subprocess
    sd.play(x * a.line_gain, sr, device=dev)
    k = 0
    if turns:
        print(f"\n  つぎのあなた: 「{turns[0]['text']}」", flush=True)
    while sd.get_stream().active:
        el = time.time() - t0
        while k < len(turns) and el >= turns[k]["start"] - 0.1:
            tx = turns[k]["text"]
            print(f"\n  ▶▶ {el:5.1f}s  いま言う: 「{tx}」(約{turns[k]['gap']:.0f}秒)", flush=True)
            mark("victim_turn", text=tx, start=turns[k]["start"])
            if a.stand_in:
                subprocess.Popen(["say", "-v", "Kyoko", "-r", "175", tx.replace("〇〇", "まるまる")])
            if k + 1 < len(turns):
                print(f"     (このあと相手 → つぎ: 「{turns[k + 1]['text']}」)", flush=True)
            k += 1
        time.sleep(0.05)
    mark("line_end")
    time.sleep(0.4)
    print("📴 切る", flush=True)
    mark("hangup")
    play(SFX / "hangup.wav")
    ensure(http, ("ended", "idle"), "handset", wait=3.0)
    out = LAB / "runs" / "phone_sim"
    out.mkdir(parents=True, exist_ok=True)
    p = out / (datetime.now().strftime("%Y%m%d_%H%M%S") + ".json")
    p.write_text(json.dumps(log, ensure_ascii=False, indent=1))
    print(f"saved {p}", flush=True)


if __name__ == "__main__":
    main()
