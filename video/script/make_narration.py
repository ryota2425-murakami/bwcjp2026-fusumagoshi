"""ナレーションと会話の音声を作る(ローカルの TTS サーバー経由)。

python video/script/make_narration.py            # 足りないものだけ作る
python video/script/make_narration.py --force n03 # 指定した id を作り直す
各行は whisper で文字に戻して台本と照合し、崩れていれば seed を変えて作り直す。
"""
from __future__ import annotations

import argparse
import io
import json
import sys
import zlib
from pathlib import Path

import httpx
import numpy as np
import soundfile as sf

HERE = Path(__file__).resolve().parent
OUT = HERE.parent / "project" / "public" / "narration"
_LAB = HERE.parents[1] / "lab" if (HERE.parents[1] / "lab" / "app").exists() else HERE.parents[1]   # 検証用(lab/)でもリポジトリの中でも
sys.path.insert(0, str(_LAB / "app" / "scripts"))
import synth_scenarios as S  # noqa: E402  (ASR 照合と無音トリムを再利用)


READING = {"便り係": "たよりがかり", "便りを": "たよりを", "便りは": "たよりは", "便りが": "たよりが", "反証役": "はんしょうやく",
           "三つのクロード": "みっつのクロード", "信用金庫": "しんようきんこ", "八十件": "はちじゅっけん", "二秒": "にびょう",
           "九秒": "きゅうびょう", "三割": "さんわり", "聞き役": "ききやく", "まとめ役": "まとめやく", "採点役": "さいてんやく",
           "出典": "しゅってん", "黙りこむ": "だまりこむ", "一枚": "いちまい"}
# 声の聞こえ方(合成したあとにかける): ふすま越しにこもる声 / 電話のスピーカーの声
FX = {"fusuma": "lowpass=f=1400,aecho=0.7:0.5:28|55:0.22|0.12,volume=-3dB",
      "phone": "highpass=f=330,lowpass=f=3300,acompressor=threshold=0.1:ratio=3,volume=-1dB"}


def ffx(a: np.ndarray, af: str) -> np.ndarray:
    """ffmpeg のフィルタを通す(速さを変える rubberband・声の聞こえ方)。"""
    import subprocess
    import tempfile
    with tempfile.TemporaryDirectory() as td:
        src, dst = Path(td) / "in.wav", Path(td) / "out.wav"
        sf.write(src, a, S.SR)
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(src), "-af", af, "-ar", str(S.SR), str(dst)], check=True)
        out, _ = sf.read(dst, dtype="float32")
    return out


def speed_up(a: np.ndarray, speed: float) -> np.ndarray:
    """早口: 音程はそのまま、速さだけ変える(物語は素の速さ、技術の説明は 1.4〜1.5 倍)。"""
    if abs(speed - 1.0) < 0.01:
        return a
    af = f"rubberband=tempo={speed}:formant=preserved" if S._has_rubberband() else f"atempo={speed}"
    return ffx(a, af)


def tts(persona: str, text: str, seed: int) -> np.ndarray:
    for k, v in READING.items():   # 読み違えやすい語は、合成するときだけかなで渡す
        text = text.replace(k, v)
    r = httpx.post(S.TTS_URL, json={"persona": persona, "text": text, "seed": seed}, timeout=300)
    r.raise_for_status()
    a, sr = sf.read(io.BytesIO(r.content), dtype="float32")
    return a


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--force", nargs="*", default=[])
    args = ap.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    data = json.loads((HERE / "narration.json").read_text())
    items = [("narrator", x) for x in data["lines"]] + [(x["persona"], x) for x in data["dialog"]]
    old = json.loads((OUT / "narration_meta.json").read_text()) if (OUT / "narration_meta.json").exists() else {}
    meta = {}
    for persona, x in items:
        p = OUT / f"{x['id']}.wav"
        same = old.get(x["id"], {}).get("text") == x["text"]      # 台本が変わった行は自動で作り直す
        if p.exists() and same and x["id"] not in args.force and "all" not in args.force:
            a, sr = sf.read(p)
            meta[x["id"]] = {**old.get(x["id"], {}), "text": x["text"], "dur": round(len(a) / sr, 2)}
            continue
        best = None
        for attempt in range(5):
            seed = x["seed"] if attempt == 0 and "seed" in x else 300 + attempt * 17 + zlib.crc32(x["id"].encode()) % 50
            a = speed_up(S.trim_silence(tts(persona, x["text"], seed)), x.get("speed", 1.0))
            heard = S.asr(a)
            sim = S.similarity(x["text"], heard)
            exp = (0.16 * len(S.kana(x["text"])) + 0.3) / x.get("speed", 1.0)
            ok = sim >= 0.8 and 0.5 * exp <= len(a) / S.SR <= 2.0 * exp
            if best is None or sim > best[0]:
                best = (sim, a, heard, seed)
            if ok:
                break
        sim, a, heard, seed = best
        if x.get("fx"):
            a = ffx(a, FX[x["fx"]])
        a = np.concatenate([np.zeros(int(0.12 * S.SR), dtype=np.float32), a, np.zeros(int(0.2 * S.SR), dtype=np.float32)])
        sf.write(p, a, S.SR)
        meta[x["id"]] = {"text": x["text"], "dur": round(len(a) / S.SR, 2), "sim": round(sim, 3), "seed": seed,
                         "speed": x.get("speed", 1.0), "fx": x.get("fx")}
        print(f"{x['id']} [{persona}] {len(a)/S.SR:.1f}s sim={sim:.2f} {'' if sim >= 0.8 else '⚠'} 「{heard}」", flush=True)
    (OUT / "narration_meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=1))
    print(f"total narration {sum(v['dur'] for k, v in meta.items() if k[0] in 'nabcde'):.1f}s")


if __name__ == "__main__":
    main()
