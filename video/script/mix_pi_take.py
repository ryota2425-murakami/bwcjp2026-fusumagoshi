"""Pi の実機録画(pi_live.mp4)に、通話の音・ふすまごしの声・電話のあとの祖母の答えを、イベントの時刻どおりに重ねる(確認用)。
  lab/.venv/bin/python video/script/mix_pi_take.py video/assets/rec/call_P01_v1
"""
import json, subprocess, sys
from datetime import datetime
from pathlib import Path
import numpy as np, soundfile as sf
from scipy.signal import resample_poly

ROOT = Path(__file__).resolve().parents[2]
D = Path(sys.argv[1]).resolve()
m = json.loads((D / "timing.json").read_text()); pi = json.loads((D / "pi_live.json").read_text())
to_v = lambda ts: ts + pi["clock_offset_pi_minus_mac"] - pi["pi_rec_t0_pi_clock"]
dur = float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(D / "pi_live.mp4")],
                           capture_output=True, text=True).stdout)
SR = 48000
mix = np.zeros(int(dur * SR) + SR, dtype=np.float32)
def place(path: Path, at: float, gain: float = 1.0):
    a, sr = sf.read(path, dtype="float32")
    if a.ndim > 1: a = a.mean(axis=1)
    if sr != SR: a = resample_poly(a, SR, sr).astype(np.float32)
    i = int(at * SR)
    if i < 0: a, i = a[-i:], 0
    n = min(len(a), len(mix) - i); mix[i:i + n] += a[:n] * gain
SC = ROOT / "lab" / "data" / "scenarios"; SP = ROOT / "lab" / "runs" / "speech"
for e in m["events"]:
    if e["type"] == "demo":
        place(SC / e["file"], to_v(e["_ts"]))
    elif e["type"] == "inject":
        place(SC / e["file"], to_v(e["_ts"]))
    elif e["type"] == "speak":
        f = SP / (datetime.fromisoformat(e["ts"]).strftime("%Y%m%d-%H%M%S") + "_fusuma.wav")
        if f.exists(): place(f, to_v(e["_ts"]) + 0.1, 0.9)
mix = mix / max(1.0, float(np.abs(mix).max()) / 0.9)
sf.write(D / "pi_live_mix.wav", mix, SR)
subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(D / "pi_live.mp4"), "-i", str(D / "pi_live_mix.wav"), "-map", "0:v", "-map", "1:a",
                "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-shortest", str(D / "pi_live_preview.mp4")], check=True)
print("wrote", D / "pi_live_preview.mp4")
