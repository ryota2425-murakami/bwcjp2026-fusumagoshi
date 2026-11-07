"""行灯(キャラ)の台詞を、いまの行灯の声(AivisSpeech「まお」おちつき)で読み直す。

録画(call_S05_v4)の画面とずらさないように、文ごとに「録画のときの長さ」へ合わせて書き出す。
台詞の文字は v4 の収録のときに Claude が書いたものをそのまま使う(speech_log.jsonl)。

  ../../lab/.venv/bin/python make_lamp_v3.py            (video/script で実行。AivisSpeech Engine :10101 が動いていること)

出力: lab/runs/speech_v3/<元の wav 名>_s<k>.wav と index.json
"""
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import urllib.parse
import urllib.request
from pathlib import Path

import numpy as np
import soundfile as sf

sys.path.insert(0, str(Path(__file__).resolve().parent))
from spans import sentence_spans  # noqa: E402

LAB = Path(__file__).resolve().parents[2] / "lab"
SRC = LAB / "runs" / "speech"
OUT = LAB / "runs" / "speech_v3"
ENGINE = "http://127.0.0.1:10101"
STYLE = 888753763          # AivisSpeech「まお」おちつき
FILES = ["20261106-144650_fusuma.wav", "20261106-144715_fusuma.wav", "20261106-144741_fusuma.wav", "20261106-144806_fusuma.wav"]
READING = {"大根": "だいこん", "煮物": "にもの", "膝": "ひざ"}


def post(url: str, body: bytes | None = None) -> bytes:
    req = urllib.request.Request(url, data=body, method="POST", headers={"Content-Type": "application/json"})
    return urllib.request.urlopen(req, timeout=120).read()


def synth(text: str, speed: float = 1.0) -> tuple[np.ndarray, int]:
    for k, v in READING.items():
        text = text.replace(k, v)
    q = json.loads(post(f"{ENGINE}/audio_query?" + urllib.parse.urlencode({"text": text, "speaker": STYLE})))
    q["speedScale"] = speed
    for ph in q["accent_phrases"]:              # 速めに読むと「ひざ」が「きざ」に聞こえたので、ヒの子音を少し長く
        for m in ph["moras"]:
            if m["text"] == "ヒ" and m.get("consonant_length"):
                m["consonant_length"] *= 1.5
    q["prePhonemeLength"] = 0.02
    q["postPhonemeLength"] = 0.02
    wav = post(f"{ENGINE}/synthesis?speaker={STYLE}", json.dumps(q).encode())
    a, sr = sf.read(__import__("io").BytesIO(wav), dtype="float32")
    return (a.mean(axis=1) if a.ndim > 1 else a), sr


def trim(a: np.ndarray, sr: int, top_db: float = 40) -> np.ndarray:
    hop = int(0.005 * sr)
    rms = np.array([np.sqrt(np.mean(a[i:i + hop] ** 2) + 1e-12) for i in range(0, len(a) - hop, hop)])
    db = 20 * np.log10(rms + 1e-9)
    idx = np.where(db > db.max() - top_db)[0]
    return a[max(0, idx[0] * hop - hop):min(len(a), (idx[-1] + 2) * hop)]


def stretch_to(a: np.ndarray, sr: int, dur: float) -> np.ndarray:
    with tempfile.TemporaryDirectory() as td:
        i, o = Path(td) / "i.wav", Path(td) / "o.wav"
        sf.write(i, a, sr)
        subprocess.run(["rubberband", "-3", "-q", "-D", f"{dur:.4f}", "--formant", str(i), str(o)], check=True)
        b, _ = sf.read(o, dtype="float32")
    return b.mean(axis=1) if b.ndim > 1 else b


def rms_db(a: np.ndarray) -> float:
    loud = a[np.abs(a) > 0.003]
    return 20 * np.log10(np.sqrt(np.mean((loud if len(loud) else a) ** 2)) + 1e-9)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    log = {json.loads(x)["file"]: json.loads(x) for x in (SRC / "speech_log.jsonl").read_text().splitlines() if x.strip()}
    index: dict[str, list[dict]] = {}
    for f in FILES:
        text = log[f]["text"]
        orig, osr = sf.read(SRC / f, dtype="float32")
        orig = orig.mean(axis=1) if orig.ndim > 1 else orig
        spans = sentence_spans(SRC / f, text)
        rows = []
        for k, (s0, s1, sent) in enumerate(spans):
            target = s1 - s0
            raw, sr = synth(sent.strip())
            raw = trim(raw, sr)
            speed = max(0.85, min(1.2, (len(raw) / sr) / max(0.3, target - 0.06)))
            if abs(speed - 1) > 0.03:                     # 速さは、まず合成のときに近づける(声が自然なまま)
                raw, sr = synth(sent.strip(), speed)
                raw = trim(raw, sr)
            body = stretch_to(raw, sr, max(0.3, target - 0.06))   # 残りの差だけ伸び縮み
            pad = np.zeros(int(0.03 * sr), dtype=np.float32)
            out = np.concatenate([pad, body, pad])
            seg = orig[int(s0 * osr):int(s1 * osr)]
            out *= 10 ** ((rms_db(seg) - rms_db(out)) / 20)       # 元の文と同じ大きさに
            out = np.clip(out, -0.98, 0.98)
            name = f"{Path(f).stem}_s{k}.wav"
            sf.write(OUT / name, out, sr)
            rows.append({"k": k, "text": sent.strip(), "wav": name, "dur": round(len(out) / sr, 3), "target": round(target, 3),
                         "speed": round(speed, 3)})
            print(f"{name}: {len(out) / sr:.2f}s (target {target:.2f}s, speed {speed:.2f})  {sent.strip()}")
        index[f] = rows
    (OUT / "index.json").write_text(json.dumps({"engine": "AivisSpeech 1.2.0", "voice": "まお / おちつき", "style": STYLE,
                                                "license": "ACML 1.0", "files": index}, ensure_ascii=False, indent=1))
    print("wrote", OUT / "index.json")


if __name__ == "__main__":
    main()
