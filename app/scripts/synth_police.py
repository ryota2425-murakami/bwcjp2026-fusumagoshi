"""P01: 架空料金請求の電話(相手は警視庁の再現ドラマの犯人役の声、祖母は合成の声)を作る。

  ../.venv/bin/python scripts/synth_police.py [--force]          (app/ で実行。TTS :8766 と whisper :8765 が要る)

- 相手の声: video/assets/police/scam_line.json の区間(警視庁 YouTube yL9rZI2qmFc「架空料金請求詐欺編」再現ドラマより。
  video/script/make_scam_line.py が切り出したもの)。
- 祖母の声: synth_scenarios.py と同じ合成(Qwen3-TTS の祖母の声見本・読み戻し検査・話し方の加工)。
  ドラマの被害者の台詞を、祖母の話し方(ゆっくり、戸惑い、言いよどみ)に直したもの。
- 出力(data/scenarios):
    P01.wav      … 動画・スピーカー用。祖母の声 + 受話器から漏れる相手の声(電話の帯域、小さめ)+ ダイヤル音・切る音
    P01_16k.wav  … 耳の入力用。祖母の声 + ダイヤル音・切る音 だけ(部屋のマイクに届くのは祖母の声だけ、という前提どおり)
    P01.truth.json
  電話のあとの答え(P02_a1..)は synth_scenarios.py P02 で作る(scenarios.json の P02)。
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

import numpy as np
import soundfile as sf
from scipy.signal import butter, lfilter, resample_poly

sys.path.insert(0, str(Path(__file__).resolve().parent))
import synth_scenarios as ss  # noqa: E402

ROOT = ss.LAB.parent
POLICE = ROOT / "video" / "assets" / "police"
SID = "P01"

# 祖母の台詞(相手の n 番目の台詞のあとに言う)。(話し方, 文, 相手の声が終わってから話し始めるまでの間 秒)
GRANDMA = [
    ("h", "あのう……もしもし。携帯にね、ご利用料金の確認が、取れておりません、って……メッセージが、来たんですけど……", 0.9),
    ("n", "はい……そう、です。", 0.8),
    ("h", "えっと……名前は、主人の名前で、東京たけし、です。住所は……東京都、東京町、百十番地、です。", 1.2),
    ("u", "有料サイト、ですか……? わたし、そんなの、見た覚えが、ないんですけどねえ……", 1.0),
    ("h", "えっ……よんまんえんも、するんですか。", 0.7),
    ("u", "そんな……。わかりました……。それで、どうやって、払えば、いいんでしょうか。クレジットカード、とか……?", 1.3),
    ("h", "電子マネー、カード……? それは、どういう……", 0.8),
    ("u", "コンビニなら……すぐそこに、ありますけど……。コンビニで、買えるんですね……", 1.0),
    ("u", "……わかりました。急いで……行ってきます。", 1.1),
]
ss.READING.update({"百十番地": "ひゃくとおばんち", "東京町": "とうきょうちょう", "東京たけし": "とうきょう たけし"})


def phone_band(x: np.ndarray, sr: int) -> np.ndarray:
    """受話器から漏れる声: 電話の帯域(300〜3400Hz)にして、少し小さく。"""
    b, a = butter(4, [300 / (sr / 2), 3400 / (sr / 2)], btype="band")
    return (lfilter(b, a, x) * 0.42).astype(np.float32)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--force", action="store_true")
    a = ap.parse_args()
    out24, out16, truth_p = ss.OUT_DIR / f"{SID}.wav", ss.OUT_DIR / f"{SID}_16k.wav", ss.OUT_DIR / f"{SID}.truth.json"
    if out24.exists() and not a.force:
        print("exists (use --force)"); return
    SR = ss.SR
    meta = json.loads((POLICE / "scam_line.json").read_text())
    line, lsr = sf.read(POLICE / "scam_line.wav", dtype="float32")
    if line.ndim > 1:
        line = line.mean(axis=1)
    line = resample_poly(line, SR, lsr).astype(np.float32) if lsr != SR else line
    spans = meta["caller_spans"]
    assert len(spans) == len(GRANDMA), (len(spans), len(GRANDMA))

    room, caller = [], []          # 部屋に届く音(祖母・効果音) / 受話器の相手の声
    truth = {"id": SID, "title": "架空料金請求(携帯料金サポートを名乗る・警視庁 再現ドラマの声)", "kind": "call",
             "events": [], "utterances": [], "caller": []}
    cursor = 0.0

    def push(r: np.ndarray, c: np.ndarray | None = None) -> None:
        nonlocal cursor
        room.append(r); caller.append(c if c is not None else np.zeros_like(r)); cursor += len(r) / SR

    def silence(sec: float) -> np.ndarray:
        return np.zeros(int(sec * SR), dtype=np.float32)

    push(silence(0.8))
    truth["events"].append({"t": round(cursor, 2), "type": "dial"})
    push(ss.sfx_dial(ss.FAKE_DIAL)); push(silence(2.2))
    for i, (sp, (style, text, gap)) in enumerate(zip(spans, GRANDMA)):
        seg = line[int(sp["start"] * SR):int(sp["end"] * SR)]
        truth["caller"].append({"start": round(cursor, 2), "end": round(cursor + len(seg) / SR, 2), "text": sp["text"]})
        push(np.zeros(len(seg), dtype=np.float32), phone_band(seg, SR))
        push(silence(gap))
        seed = int(hashlib.sha1(f"{SID}-{i}".encode()).hexdigest()[:6], 16) % 100000
        audio, info = ss.synth_line(text, style, seed)
        start = cursor
        push(audio)
        truth["utterances"].append({"start": round(start, 2), "end": round(cursor, 2), "pause": gap, "text": text,
                                    "style": style, **info})
        flag = "" if info["ok"] else "  ⚠"
        print(f"  {SID} {start:6.1f}s [{style}] {text}  ← ASR「{info['asr']}」 sim={info['sim']}{flag}", file=sys.stderr)
        push(silence(0.7))
    push(silence(1.0))
    truth["events"].append({"t": round(cursor, 2), "type": "hangup"})
    push(ss.sfx_hangup()); push(silence(2.0))
    r = np.concatenate(room); c = np.concatenate(caller)
    tone = ss.room_tone(len(r), seed=7)
    ear = np.clip(r + tone, -0.98, 0.98).astype(np.float32)
    play = np.clip(r + c + tone, -0.98, 0.98).astype(np.float32)
    sf.write(out24, play, SR)
    sf.write(out16, resample_poly(ear, 2, 3).astype(np.float32), 16000, subtype="PCM_16")
    truth["duration"] = round(len(r) / SR, 2)
    truth_p.write_text(json.dumps(truth, ensure_ascii=False, indent=2))
    bad = [u for u in truth["utterances"] if not u["ok"]]
    print(f"{SID}: {truth['duration']}s, {len(truth['utterances'])} lines, bad {len(bad)}")


if __name__ == "__main__":
    main()
