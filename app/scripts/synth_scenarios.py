"""シナリオ台本(祖母の発話のみ) → 通話音声 wav を合成する。

1. 各セリフを TTS サーバー(Qwen3-TTS, 合成の声見本を参照)で読み上げ
2. whisper-server で文字に戻し、台本との一致(かな読みの類似度)と長さを検査。崩れていれば seed を変えて再生成
3. 話し方(ためらい・押されて小声など)に応じて 音量・速さ・高さ を加工(ffmpeg rubberband)
4. 呼出音・受話器の音・沈黙(=相手が話している時間)・部屋の環境音と合わせて 1 本の wav に

出力: <ルート>/data/scenarios/<ID>.wav (24kHz, 動画用) / <ID>_16k.wav (耳の入力用) / <ID>.truth.json (正解タイミング)
"""
from __future__ import annotations

import argparse
import functools
import difflib
import hashlib
import io
import json
import subprocess
import sys
import tempfile
from pathlib import Path

import httpx
import numpy as np
import pykakasi
import soundfile as sf
from scipy.signal import butter, lfilter, resample_poly

APP = Path(__file__).resolve().parents[1]
LAB = APP.parent
OUT_DIR = LAB / "data" / "scenarios"
CACHE = LAB / "data" / "tts_cache"
# ダイヤル音(DTMF)を作るための番号。先頭を 0000 にして、実在の番号と重ならないようにしている(架空のデータだけ)
FAKE_DIAL = "0000271828"       # S08 で祖母がかける番号
FAKE_ENROLL = "0000314159"     # 耳に登録するダイヤル音(シナリオとは別の番号で、登録と試験を分ける)
SFX_DIR = LAB / "data" / "sfx"
TTS_URL = "http://127.0.0.1:8766/tts"
ASR_URL = "http://127.0.0.1:8765/inference"
ASR_PROMPT = "電話での会話。今日中、半額、定期購入、解約、還付金、暗証番号、キャッシュカード、口座、銀行協会、信用金庫、整形外科。"
SR = 24000

# 話し方 → (音量 dB, 速さ倍率, 高さ 半音)
STYLE = {
    "n": (0.0, 1.00, 0.0),
    "p": (0.0, 0.98, 0.0),
    "c": (1.5, 1.04, 0.6),
    "l": (1.5, 1.03, 0.6),
    "w": (-2.0, 1.00, 0.2),
    "h": (-3.5, 0.94, -0.4),
    "u": (-7.5, 0.88, -1.2),
    "b": (-4.5, 1.00, -0.3),
    "f": (1.0, 1.00, 0.0),
}
# TTS が読み違えやすい語の読み(合成入力のみ。台本と正解テキストは漢字のまま)
READING = {"今日中": "きょうじゅう", "二の五": "にのご", "三の、一の、二番": "さんの、いちの、にばん", "解約": "かいやく"}

_kks = pykakasi.kakasi()
_NUM = set("0123456789０１２３４５６７８９一二三四五六七八九十百千万円,-ー－")


def kana(s: str) -> str:
    s = "".join(ch for ch in s if ch not in "、。！？!?…「」・ 　\n\"")
    return "".join(item["hira"] for item in _kks.convert(s))


def similarity(a: str, b: str) -> float:
    # 数字は「四千九百八十円」と「4980円」のように表記が揺れるので、比べる前に除く
    a2 = "".join(ch for ch in a if ch not in _NUM)
    b2 = "".join(ch for ch in b if ch not in _NUM)
    return difflib.SequenceMatcher(None, kana(a2), kana(b2)).ratio()


@functools.lru_cache
def _ref_hash(persona: str) -> str:
    ref = APP / "tts_server" / "voices" / f"{persona}_ref.wav"
    return hashlib.sha1(ref.read_bytes()).hexdigest()[:8] if ref.exists() else "-"


def tts(text: str, seed: int, persona: str = "grandma") -> np.ndarray:
    tts_text = text
    for k, v in READING.items():
        tts_text = tts_text.replace(k, v)
    key = hashlib.sha1(f"{persona}|{_ref_hash(persona)}|{tts_text}|{seed}".encode()).hexdigest()[:16]   # 声見本が変われば作り直す
    path = CACHE / f"{key}.wav"
    if not path.exists():
        r = httpx.post(TTS_URL, json={"persona": persona, "text": tts_text, "seed": seed}, timeout=300)
        r.raise_for_status()
        path.write_bytes(r.content)
    audio, sr = sf.read(path, dtype="float32")
    assert sr == SR, sr
    return audio


def asr(audio: np.ndarray, sr: int = SR) -> str:
    a16 = resample_poly(audio, 2, 3).astype(np.float32) if sr == 24000 else audio
    buf = io.BytesIO()
    sf.write(buf, a16, 16000, format="WAV", subtype="PCM_16")
    r = httpx.post(ASR_URL, files={"file": ("u.wav", buf.getvalue(), "audio/wav")},
                   data={"response_format": "json", "language": "ja", "no_timestamps": "true", "no_context": "true", "temperature": "0.0", "prompt": ASR_PROMPT}, timeout=120)
    r.raise_for_status()
    return r.json().get("text", "").strip()


def trim_silence(a: np.ndarray, thr_db: float = -42.0) -> np.ndarray:
    frame = int(0.01 * SR)
    env = np.array([np.sqrt(np.mean(a[i:i + frame] ** 2) + 1e-12) for i in range(0, len(a), frame)])
    db = 20 * np.log10(env + 1e-12)
    idx = np.where(db > thr_db)[0]
    if len(idx) == 0:
        return a
    s = max(0, idx[0] * frame - int(0.03 * SR))
    e = min(len(a), (idx[-1] + 1) * frame + int(0.06 * SR))
    return a[s:e]


@functools.lru_cache
def _has_rubberband() -> bool:
    out = subprocess.run(["ffmpeg", "-hide_banner", "-filters"], capture_output=True, text=True).stdout
    return " rubberband " in out


def style_fx(a: np.ndarray, style: str) -> np.ndarray:
    gain, tempo, semis = STYLE[style]
    if tempo == 1.0 and semis == 0.0:
        return a * (10 ** (gain / 20))
    with tempfile.TemporaryDirectory() as td:
        src, dst = Path(td) / "in.wav", Path(td) / "out.wav"
        sf.write(src, a, SR)
        ratio = 2 ** (semis / 12)
        if _has_rubberband():
            af = f"rubberband=tempo={tempo}:pitch={ratio:.5f}:formant=preserved,volume={gain}dB"
        else:   # rubberband の入っていない ffmpeg でも動くように: 高さは標本化率で、速さは atempo で(声の質は少し変わる)
            af = f"asetrate={SR * ratio:.0f},aresample={SR},atempo={tempo / ratio:.5f},volume={gain}dB"
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(src), "-af", af, "-ar", str(SR), str(dst)], check=True)
        out, _ = sf.read(dst, dtype="float32")
    return out


def synth_line(text: str, style: str, base_seed: int) -> tuple[np.ndarray, dict]:
    expected = 0.16 * len(kana(text)) + 0.25
    best = None
    for attempt in range(5):
        seed = base_seed + attempt
        raw = trim_silence(tts(text, seed))
        dur = len(raw) / SR
        heard = asr(raw)
        sim = similarity(text, heard)
        ok = sim >= 0.72 and 0.45 * expected <= dur <= 2.2 * expected
        cand = (sim - (0 if ok else 1), raw, {"seed": seed, "asr": heard, "sim": round(sim, 3), "dur": round(dur, 2)})
        if best is None or cand[0] > best[0]:
            best = cand
        if ok:
            break
    _, raw, info = best
    info["ok"] = info["sim"] >= 0.72
    return style_fx(raw, style), info


# ---------- 効果音(合成。実際の家では実機の音を数秒登録して使う) ----------
def sfx_ring(n: int) -> np.ndarray:
    t = np.arange(int(1.0 * SR)) / SR
    sq = (np.sign(np.sin(2 * np.pi * 16 * t)) + 1) / 2  # 16Hz で 2 音を切り替える電子音
    tone = sq * np.sin(2 * np.pi * 1300 * t) + (1 - sq) * np.sin(2 * np.pi * 1630 * t)
    tone += 0.25 * np.sin(2 * np.pi * 2600 * t) * sq
    env = np.minimum(1, np.minimum(t / 0.01, (1.0 - t) / 0.02))
    burst = 0.22 * tone * env
    gap = np.zeros(int(2.0 * SR))
    return np.concatenate([np.concatenate([burst, gap]) for _ in range(n)])[: -int(1.4 * SR)].astype(np.float32)


def _click(strength: float, seed: int) -> np.ndarray:
    rng = np.random.default_rng(seed)
    n = int(0.12 * SR)
    t = np.arange(n) / SR
    noise = rng.normal(0, 1, n) * np.exp(-t / 0.006)
    b, a = butter(2, [1500 / (SR / 2), 5000 / (SR / 2)], btype="band")
    click = lfilter(b, a, noise)
    thump = np.sin(2 * np.pi * 90 * t) * np.exp(-t / 0.035)
    return (strength * (0.6 * click / (np.abs(click).max() + 1e-9) + 0.5 * thump)).astype(np.float32)


def sfx_pickup() -> np.ndarray:
    return np.concatenate([_click(0.35, 1), np.zeros(int(0.05 * SR)), _click(0.18, 2)]).astype(np.float32)


def sfx_hangup() -> np.ndarray:
    return np.concatenate([_click(0.45, 3), np.zeros(int(0.03 * SR)), _click(0.3, 4)]).astype(np.float32)


DTMF = {"0": (941, 1336), "1": (697, 1209), "2": (697, 1336), "3": (697, 1477), "4": (770, 1209), "5": (770, 1336),
        "6": (770, 1477), "7": (852, 1209), "8": (852, 1336), "9": (852, 1477)}


def sfx_dial(digits: str) -> np.ndarray:
    parts = []
    t = np.arange(int(0.1 * SR)) / SR
    for d in digits:
        lo, hi = DTMF[d]
        parts += [0.15 * (np.sin(2 * np.pi * lo * t) + np.sin(2 * np.pi * hi * t)), np.zeros(int(0.08 * SR))]
    return np.concatenate(parts).astype(np.float32)


def room_tone(n: int, seed: int) -> np.ndarray:
    rng = np.random.default_rng(seed)
    white = rng.normal(0, 1, n)
    b, a = butter(1, 400 / (SR / 2))
    return (0.0025 * lfilter(b, a, white) / 0.05 + 0.0006 * white).astype(np.float32)


def build(sc: dict, force: bool = False) -> dict:
    sid = sc["id"]
    out24, out16, truth_p = OUT_DIR / f"{sid}.wav", OUT_DIR / f"{sid}_16k.wav", OUT_DIR / f"{sid}.truth.json"
    if out24.exists() and truth_p.exists() and not force:
        return json.loads(truth_p.read_text())
    pieces: list[np.ndarray] = []
    truth = {"id": sid, "title": sc["title"], "kind": sc["kind"], "events": [], "utterances": []}
    cursor = 0.0

    def add(a: np.ndarray):
        nonlocal cursor
        pieces.append(a)
        cursor += len(a) / SR

    add(np.zeros(int(0.8 * SR), dtype=np.float32))
    answer_mode = sc.get("answers_for") is not None
    for i, item in enumerate(sc["script"]):
        if item[0] == "ring":
            truth["events"].append({"t": round(cursor, 2), "type": "ring"})
            add(sfx_ring(item[1]))
            add(np.zeros(int(0.9 * SR), dtype=np.float32))
        elif item[0] == "dial":
            truth["events"].append({"t": round(cursor, 2), "type": "dial"})
            add(sfx_dial(FAKE_DIAL))
            add(np.zeros(int(2.5 * SR), dtype=np.float32))
        elif item[0] == "pickup":
            truth["events"].append({"t": round(cursor, 2), "type": "pickup"})
            add(sfx_pickup())
        elif item[0] == "hangup":
            add(np.zeros(int(item[1] * SR), dtype=np.float32))
            truth["events"].append({"t": round(cursor, 2), "type": "hangup"})
            add(sfx_hangup())
        else:
            pause, style, text = item
            seed = int(hashlib.sha1(f"{sid}-{i}".encode()).hexdigest()[:6], 16) % 100000
            audio, info = synth_line(text, style, seed)
            if answer_mode:
                # 電話のあとの答えは 1 行ずつ別ファイル(デモで問いかけに合わせて再生)
                k = sum(1 for u in truth["utterances"]) + 1
                p = OUT_DIR / f"{sid}_a{k}.wav"
                sf.write(p, np.concatenate([audio, np.zeros(int(0.3 * SR), dtype=np.float32)]), SR)
                sf.write(OUT_DIR / f"{sid}_a{k}_16k.wav", resample_poly(audio, 2, 3).astype(np.float32), 16000)
                truth["utterances"].append({"k": k, "text": text, "style": style, **info, "file": p.name})
                print(f"  {sid}_a{k} [{style}] {text}  ← ASR「{info['asr']}」 sim={info['sim']}", file=sys.stderr)
                continue
            add(np.zeros(int(pause * SR), dtype=np.float32))
            start = cursor
            add(audio)
            truth["utterances"].append({"start": round(start, 2), "end": round(cursor, 2), "pause": pause,
                                        "text": text, "style": style, **info})
            flag = "" if info["ok"] else "  ⚠"
            print(f"  {sid} {start:6.1f}s [{style}] {text}  ← ASR「{info['asr']}」 sim={info['sim']}{flag}", file=sys.stderr)
    if answer_mode:
        truth_p.write_text(json.dumps(truth, ensure_ascii=False, indent=2))
        return truth
    add(np.zeros(int(1.5 * SR), dtype=np.float32))
    audio = np.concatenate(pieces)
    audio = audio + room_tone(len(audio), seed=len(sid))
    audio = np.clip(audio, -0.98, 0.98).astype(np.float32)
    sf.write(out24, audio, SR)
    sf.write(out16, resample_poly(audio, 2, 3).astype(np.float32), 16000, subtype="PCM_16")
    truth["duration"] = round(len(audio) / SR, 2)
    truth_p.write_text(json.dumps(truth, ensure_ascii=False, indent=2))
    return truth


def write_enrollment_sfx() -> None:
    """登録音(実機の呼出音・受話器の音の代わり)を保存。耳の音イベント検出が埋め込みを平均して使う。"""
    SFX_DIR.mkdir(parents=True, exist_ok=True)
    for name, a in {"ring": sfx_ring(3), "pickup": sfx_pickup(), "hangup": sfx_hangup(), "dial": sfx_dial(FAKE_ENROLL)}.items():
        pad = np.zeros(int(0.3 * SR), dtype=np.float32)
        a = np.concatenate([pad, a, pad])
        sf.write(SFX_DIR / f"{name}.wav", a, SR)
        sf.write(SFX_DIR / f"{name}_16k.wav", resample_poly(a, 2, 3).astype(np.float32), 16000)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("ids", nargs="*", help="作るシナリオ ID(省略で全部)")
    ap.add_argument("--force", action="store_true")
    args = ap.parse_args()
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    CACHE.mkdir(parents=True, exist_ok=True)
    write_enrollment_sfx()
    data = json.loads((APP / "scenarios" / "scenarios.json").read_text())
    report = []
    for sc in data["scenarios"]:
        if args.ids and sc["id"] not in args.ids:
            continue
        if sc.get("builder"):            # 別の作り方のシナリオ(P01 は synth_police.py)
            print(f"== {sc['id']} skip (scripts/{sc['builder']}.py で作る)", file=sys.stderr)
            continue
        print(f"== {sc['id']} {sc['title']}", file=sys.stderr)
        t = build(sc, force=args.force)
        bad = [u for u in t["utterances"] if not u.get("ok", True)]
        report.append((sc["id"], len(t["utterances"]), len(bad), t.get("duration")))
    print("\nID    lines  bad  duration")
    for r in report:
        print(f"{r[0]:5} {r[1]:5} {r[2]:4}  {r[3]}")


if __name__ == "__main__":
    main()
