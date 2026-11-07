"""wav ファイルを耳に通して、音声スコア(JSONL)と Claude に渡すテキストを出す(オフライン)。

python app/scripts/ear_file.py data/scenarios/S05_16k.wav [--start 14:02:50]
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from fusuma.ear.pipeline import Ear  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("wav")
    ap.add_argument("--start", default=None, help="録音開始の時刻 HH:MM:SS")
    ap.add_argument("--out", default=None)
    args = ap.parse_args()
    start = datetime.now()
    if args.start:
        h, m, s = (args.start.split(":") + ["0"])[:3]
        start = start.replace(hour=int(h), minute=int(m), second=int(s), microsecond=0)
    events = []

    def on(ev):
        if ev["type"] == "level":
            return
        events.append(ev)
        if ev["type"] == "state":
            print(f"[state] {ev['clock']} → {ev['state']} {ev.get('sound') or ev.get('reason') or ''}")
            if ev["state"] == "ended":
                print("  " + ev["ma_line"])
        elif ev["type"] in ("utt", "room_utt"):
            print("  " + (ev.get("line") or f"{ev['clock']} 「{ev['text']}」"))

    t0 = time.time()
    ear = Ear(on, start_wall=start)
    ear.run_file(Path(args.wav))
    print(f"processed in {time.time()-t0:.1f}s")
    if args.out:
        Path(args.out).write_text("\n".join(json.dumps(e, ensure_ascii=False, default=str) for e in events))


if __name__ == "__main__":
    main()
