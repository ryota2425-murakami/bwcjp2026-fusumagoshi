"""「いつもの声」(韻律のベースライン)を、普段の会話から作る。

普段の会話 = 友人との電話・病院や宅配の電話・夕方のおしゃべり(安心な場面)。
中央値をとるので、多少の認識誤りや外れ値には強い。
注意: ここで使う本物の電話 3 件(S10・S11・S12)は評価にも入っている(基準と同じ録音なので、厳密には独立していない)。
実機では、台所での普段の話し声から作る想定。
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import soundfile as sf

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from fusuma import config  # noqa: E402
from fusuma.ear import asr, prosody  # noqa: E402
from fusuma.ear.pipeline import BASELINE_PATH  # noqa: E402
from fusuma.ear.vad import CHUNK, StreamSegmenter  # noqa: E402

NORMAL = ["S11", "S10", "S12", "R01"]


def main():
    f0s, dbs, rates = [], [], []
    for sid in NORMAL:
        a, _ = sf.read(config.SCENARIO_AUDIO / f"{sid}_16k.wav", dtype="float32")
        v = StreamSegmenter()
        segs = []
        for i in range(0, len(a) - CHUNK, CHUNK):
            segs += v.feed(a[i:i + CHUNK])
        segs += v.flush()
        for s in segs:
            if s.dur < 0.8:
                continue
            text = asr.transcribe(s.audio)
            feat = prosody.measure(s.audio)
            m = prosody.morae(text)
            if feat["f0"]:
                f0s.append(feat["f0"])
            if feat["db"] is not None:
                dbs.append(feat["db"])
            if m >= 4 and s.dur > 0.8:
                rates.append(m / s.dur)
            print(f"{sid} {s.start:6.1f}s {s.dur:.1f}s f0={feat['f0']} db={feat['db']} 「{text}」")
    base = prosody.Baseline(f0=float(np.median(f0s)), db=float(np.median(dbs)), rate=float(np.median(rates)), n=len(f0s))
    base.save(BASELINE_PATH)
    print(f"\nいつもの声: F0 {base.f0:.0f}Hz / 声量 {base.db:.1f}dBFS / 話速 {base.rate:.1f}モーラ毎秒 (n={base.n}) → {BASELINE_PATH}")


if __name__ == "__main__":
    main()
