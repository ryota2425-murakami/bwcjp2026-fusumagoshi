"""効果音と、技術の場面の軽いリズム(拍子木と木琴)を、数式から作る(素材のライセンスが要らない)。

python video/script/make_sfx.py   → project/public/sfx/*.wav, project/public/music/wood_rhythm.wav
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import soundfile as sf
from scipy.signal import butter, lfilter

SR = 44100
V = Path(__file__).resolve().parents[1]
SFX = V / "project" / "public" / "sfx"
MUSIC = V / "project" / "public" / "music"
rng = np.random.default_rng(7)


def t(sec: float) -> np.ndarray:
    return np.arange(int(sec * SR)) / SR


def bp(x: np.ndarray, lo: float, hi: float, order: int = 2) -> np.ndarray:
    b, a = butter(order, [lo / (SR / 2), hi / (SR / 2)], btype="band")
    return lfilter(b, a, x)


def lp(x: np.ndarray, f: float, order: int = 2) -> np.ndarray:
    b, a = butter(order, f / (SR / 2))
    return lfilter(b, a, x)


def env(n: int, attack: float, decay: float) -> np.ndarray:
    tt = np.arange(n) / SR
    e = np.exp(-tt / decay)
    a = np.clip(tt / max(attack, 1e-4), 0, 1)
    return a * e


def norm(x: np.ndarray, peak: float = 0.8) -> np.ndarray:
    return (x / (np.max(np.abs(x)) + 1e-9) * peak).astype(np.float32)


def wood(freq: float, dur: float = 0.25, decay: float = 0.045, noise: float = 0.5) -> np.ndarray:
    """木を打つ音(拍子木・判子・ふすまの木枠)。"""
    n = int(dur * SR)
    tt = np.arange(n) / SR
    body = np.sin(2 * np.pi * freq * tt) + 0.45 * np.sin(2 * np.pi * freq * 2.76 * tt)
    hit = bp(rng.normal(0, 1, n), freq * 0.8, min(freq * 6, SR / 2 - 100)) * np.exp(-tt / 0.006)
    return env(n, 0.0008, decay) * body + noise * hit


def marimba(freq: float, dur: float = 0.5) -> np.ndarray:
    n = int(dur * SR)
    tt = np.arange(n) / SR
    x = np.sin(2 * np.pi * freq * tt) + 0.3 * np.sin(2 * np.pi * freq * 4 * tt) * np.exp(-tt / 0.03)
    return env(n, 0.002, 0.22) * x


def main() -> None:
    SFX.mkdir(parents=True, exist_ok=True)
    MUSIC.mkdir(parents=True, exist_ok=True)
    out = {}
    # 柱時計の刻み(コチ・コチ)。1 秒に 1 回ずつ高さを変えて 12 秒
    tick = []
    for i in range(12):
        a = wood(2600 if i % 2 == 0 else 2200, 0.06, 0.006, 0.9) * 0.6
        pad = np.zeros(SR - len(a))
        tick.append(np.concatenate([a, pad]))
    out["clock_tick"] = norm(np.concatenate(tick), 0.35)
    # ふすまを閉める「トン」: 低い木の音と、敷居に当たる響き
    n = int(0.6 * SR)
    th = wood(140, 0.6, 0.09, 0.8) + 0.5 * wood(420, 0.6, 0.03, 0.4)
    out["fusuma_ton"] = norm(lp(th, 1800), 0.85)
    # ふすまを滑らせる「すーっ」(帯域をしぼった雑音)
    n = int(1.2 * SR)
    tt = np.arange(n) / SR
    sl = bp(rng.normal(0, 1, n), 300, 2600) * np.sin(np.pi * np.clip(tt / 1.2, 0, 1)) ** 1.5
    out["fusuma_slide"] = norm(sl, 0.4)
    # 判子「コン」
    out["stamp_kon"] = norm(wood(820, 0.25, 0.035, 0.6), 0.7)
    # 「カタン」(木の札が落ちる)
    k = np.zeros(int(0.35 * SR))
    a = wood(1100, 0.15, 0.02, 0.7)
    b = wood(700, 0.2, 0.03, 0.6)
    k[:len(a)] += a
    k[int(0.09 * SR):int(0.09 * SR) + len(b)] += b
    out["katan"] = norm(k, 0.6)
    # 郵便受け「コトン」
    k = np.zeros(int(0.6 * SR))
    a = wood(520, 0.3, 0.05, 0.7)
    b = wood(260, 0.4, 0.08, 0.5)
    k[:len(a)] += a
    k[int(0.12 * SR):int(0.12 * SR) + len(b)] += b * 0.8
    out["mailbox_koton"] = norm(k, 0.7)
    # 合格の鈴
    n = int(2.2 * SR)
    tt = np.arange(n) / SR
    bell = (np.sin(2 * np.pi * 1318.5 * tt) + 0.6 * np.sin(2 * np.pi * 1975.5 * tt) + 0.3 * np.sin(2 * np.pi * 3520 * tt)) * np.exp(-tt / 0.6)
    out["bell"] = norm(bell * env(n, 0.002, 10), 0.45)
    # キーボードを打つ音(Claude Code の画面)
    n = int(3.0 * SR)
    ty = np.zeros(n)
    pos = 0.0
    while pos < 2.9:
        c = wood(rng.uniform(1800, 3200), 0.04, 0.004, 1.0) * rng.uniform(0.4, 1.0)
        i = int(pos * SR)
        ty[i:i + len(c)] += c[: n - i]
        pos += rng.uniform(0.06, 0.16)
    out["typing"] = norm(ty, 0.35)
    # 行灯が灯る小さな音(やわらかい鈴)
    n = int(1.4 * SR)
    tt = np.arange(n) / SR
    out["lamp_on"] = norm((np.sin(2 * np.pi * 880 * tt) + 0.4 * np.sin(2 * np.pi * 1320 * tt)) * np.exp(-tt / 0.35) * env(n, 0.01, 10), 0.3)
    # 部屋の静けさ(冷蔵庫の低い音と空気)
    n = int(20 * SR)
    room = lp(rng.normal(0, 1, n), 400) * 0.6 + 0.15 * np.sin(2 * np.pi * 50 * np.arange(n) / SR)
    out["room_tone"] = norm(room, 0.06)
    for k, v in out.items():
        sf.write(SFX / f"{k}.wav", v, SR)

    # 技術の場面の軽いリズム(拍子木と木琴、陽音階、120 BPM、32 小節 ≒ 64 秒)
    bpm = 120
    beat = 60 / bpm
    bars = 32
    total = int(bars * 4 * beat * SR) + SR
    mus = np.zeros(total)
    scale = [293.66, 329.63, 392.0, 440.0, 493.88, 587.33, 659.25]      # D E G A B D E(陽音階)
    pattern = [0, 2, 4, 2, 5, 4, 2, 3, 0, 2, 4, 5, 6, 5, 4, 2]
    for bar in range(bars):
        for step in range(8):                                   # 8 分音符
            st = (bar * 4 + step / 2) * beat
            i = int(st * SR)
            if step % 2 == 0:                                   # 拍子木(表拍)
                w = wood(1500 if step == 0 else 1250, 0.12, 0.02, 0.8) * (0.55 if step == 0 else 0.35)
                mus[i:i + len(w)] += w
            note = scale[pattern[(bar * 8 + step) % len(pattern)]]
            m = marimba(note, 0.45) * (0.42 if step % 2 == 0 else 0.3)
            mus[i:i + len(m)] += m
        bass = marimba(scale[0] / 2 if bar % 4 != 3 else scale[3] / 2, 1.2) * 0.5
        i = int(bar * 4 * beat * SR)
        mus[i:i + len(bass)] += bass
    mus = lp(mus, 6000)
    sf.write(MUSIC / "wood_rhythm.wav", norm(mus, 0.6), SR)
    print("sfx:", ", ".join(sorted(out)), "| music: wood_rhythm.wav", round(total / SR, 1), "s")


if __name__ == "__main__":
    main()
