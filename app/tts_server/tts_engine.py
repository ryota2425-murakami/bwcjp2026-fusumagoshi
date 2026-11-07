"""ふすまごし TTS エンジン(Qwen3-TTS / MLX, ローカル実行)

- 声は誰かの録音から複製しない。VoiceDesign で「文章の説明」から合成の声見本(ref)を作り、
  Base モデルでその合成の声見本を参照して全セリフを一貫した声で読む。
- 実行は .venv-tts(mlx-audio)で。メイン側からは HTTP(serve)か CLI で呼ぶ。

使い方:
  python tts_engine.py design            # 全ペルソナの声見本を作る(初回のみ)
  python tts_engine.py say grandma "はい、もしもし" out.wav
  python tts_engine.py serve --port 8766  # POST /tts {"persona":..., "text":...} -> audio/wav
"""
from __future__ import annotations

import io
import json
import os
import sys
import threading
import time
from pathlib import Path

import numpy as np
import soundfile as sf

HERE = Path(__file__).resolve().parent
VOICE_DIR = HERE / "voices"
DESIGN_MODEL = "mlx-community/Qwen3-TTS-12Hz-1.7B-VoiceDesign-8bit"
BASE_MODEL = "mlx-community/Qwen3-TTS-12Hz-1.7B-Base-8bit"

# ペルソナ: 声の説明(VoiceDesign 用)と、声見本として読ませる文
PERSONAS: dict[str, dict] = {
    "grandma": {
        "instruct": "85歳くらいの日本人のおばあさんの声。声は細く、かすれていて、少し震える。ゆっくり、やさしく、のんびりと話す。田舎で一人暮らしをしている、年を重ねた祖母。",   # seed 4102(--exact-seed 4102 で作り直せる)
        "ref_text": "はい、もしもし。ええ、元気にしてますよ。今日はね、畑の大根がよく採れたの。",
    },
    "fusuma": {
        "instruct": "落ち着いた40代の日本人女性の声。やわらかく、ゆっくり、家族に話しかけるような温かい口調。押しつけがましくない。",
        "ref_text": "おかえりなさい。今日はいいお天気だったね。お茶でも淹れようか。",
    },
    "narrator": {
        "instruct": "50代の日本人男性の声。低めで、あたたかく、落ち着いた語り口。ドキュメンタリーのナレーターのように、誠実に、ゆっくり丁寧に話す。",   # seed 3104
        "ref_text": "子どものころ、ふすまの向こうから、祖母の声が聞こえていました。",
    },
    "kenta": {
        "instruct": "30代の日本人男性の声。明るく優しい孫の声。少し照れくさそうに、祖母に話しかける。",
        "ref_text": "もしもし、ばあちゃん？元気？膝の具合はどう？",
    },
}

_lock = threading.Lock()
_models: dict[str, object] = {}


def _load(name: str):
    from mlx_audio.tts.utils import load_model

    if name not in _models:
        t0 = time.time()
        _models[name] = load_model(name)
        print(f"[tts] loaded {name} in {time.time()-t0:.1f}s", file=sys.stderr)
    return _models[name]


def _to_np(results) -> np.ndarray:
    return np.concatenate([np.array(r.audio, dtype=np.float32) for r in results])


def _expected_seconds(text: str) -> float:
    # ざっくり 1 文字 0.17 秒 + 句読点の間(崩れ検出用の目安)
    n = len([c for c in text if c not in "、。！？!?… 「」"])
    return 0.17 * n + 0.35 * sum(text.count(c) for c in "、。！？…")


def design_all(force: bool = False, only: str | None = None, seed_base: int = 1000, exact_seed: int | None = None) -> None:
    """文章の説明(VoiceDesign)から声見本を作る。使った seed は voices/<name>_ref.json に残る。
    いまの声見本を作り直すときは、その seed を exact_seed で渡す(例: --only narrator --exact-seed 1002 --force)。"""
    VOICE_DIR.mkdir(parents=True, exist_ok=True)
    model = _load(DESIGN_MODEL)
    import mlx.core as mx

    for i, (name, p) in enumerate(PERSONAS.items()):
        if only and name != only:
            continue
        out = VOICE_DIR / f"{name}_ref.wav"
        if out.exists() and not force:
            continue
        exp = _expected_seconds(p["ref_text"])
        for attempt in range(1 if exact_seed is not None else 6):
            seed = exact_seed if exact_seed is not None else seed_base + i * 10 + attempt
            mx.random.seed(seed)
            audio = _to_np(model.generate_voice_design(text=p["ref_text"], language="Japanese", instruct=p["instruct"]))
            dur = len(audio) / model.sample_rate
            ok = 0.6 * exp <= dur <= 1.7 * exp
            print(f"[tts] design {name} seed={seed}: {dur:.1f}s (expected ~{exp:.1f}s) {'OK' if ok else 'retry'}", file=sys.stderr)
            if ok:
                break
        sf.write(out, audio, model.sample_rate)
        (VOICE_DIR / f"{name}_ref.json").write_text(
            json.dumps({"persona": name, **p, "model": DESIGN_MODEL, "seed": seed}, ensure_ascii=False, indent=2)
        )


# 合成のときだけ、読み違えやすい語をかなで渡す(画面や記録の文字はそのまま)。
# 例: 「大根」を「ワイモッコ」のように読んだことがある(2026-11-06 の収録)
READING = {"大根": "だいこん", "煮物": "にもの", "膝": "ひざ", "整形外科": "せいけいげか", "春風健康": "はるかぜけんこう"}


def _reading(text: str) -> str:
    for k, v in READING.items():
        text = text.replace(k, v)
    return text


# 行灯(キャラ)の声は、VOICEVOX 互換のローカルエンジン(AivisSpeech / VOICEVOX)で読む。
# エンジンに届かないときは、これまでの Qwen3-TTS の声(fusuma の声見本)に戻る。FUSUMA_LAMP_ENGINE= (空) で常に Qwen3-TTS。
LAMP_ENGINE = os.getenv("FUSUMA_LAMP_ENGINE", "http://127.0.0.1:10101")    # AivisSpeech Engine(VOICEVOX なら :50021)
LAMP_STYLE = int(os.getenv("FUSUMA_LAMP_STYLE", "888753763"))             # AivisSpeech「まお」おちつき(ACML 1.0)
LAMP_SPEED = float(os.getenv("FUSUMA_LAMP_SPEED", "1.0"))
ENGINE_PERSONAS = {"fusuma"}


def _engine_synth(text: str) -> tuple[np.ndarray, int]:
    import urllib.parse
    import urllib.request

    def post(url: str, body: bytes | None = None) -> bytes:
        req = urllib.request.Request(url, data=body, method="POST", headers={"Content-Type": "application/json"})
        return urllib.request.urlopen(req, timeout=60).read()

    q = json.loads(post(f"{LAMP_ENGINE}/audio_query?" + urllib.parse.urlencode({"text": text, "speaker": LAMP_STYLE})))
    q["speedScale"] = LAMP_SPEED
    wav = post(f"{LAMP_ENGINE}/synthesis?speaker={LAMP_STYLE}", json.dumps(q).encode())
    audio, sr = sf.read(io.BytesIO(wav), dtype="float32")
    if audio.ndim > 1:
        audio = audio.mean(axis=1)
    return audio, sr


def synth(persona: str, text: str, seed: int | None = None) -> tuple[np.ndarray, int]:
    """ペルソナの合成声見本を参照して text を読む(行灯の声だけは、ローカルの音声合成エンジンで)。"""
    text = _reading(text)
    if persona in ENGINE_PERSONAS and LAMP_ENGINE:
        try:
            return _engine_synth(text)
        except Exception as e:      # エンジンが止まっていても、行灯は黙らない(いつもの声で話す)
            print(f"[tts] lamp engine unavailable ({type(e).__name__}); falling back to Qwen3-TTS", file=sys.stderr)
    ref = VOICE_DIR / f"{persona}_ref.wav"
    if not ref.exists():
        raise FileNotFoundError(f"voice ref missing: {ref} (run: python tts_engine.py design)")
    with _lock:
        model = _load(BASE_MODEL)
        if seed is not None:
            import mlx.core as mx

            mx.random.seed(seed)
        audio = _to_np(model.generate(text=text, ref_audio=str(ref), ref_text=PERSONAS[persona]["ref_text"]))
        return audio, model.sample_rate


try:
    from pydantic import BaseModel

    class TTSRequest(BaseModel):
        persona: str = "fusuma"
        text: str
        seed: int | None = None
except ImportError:  # design/say だけなら pydantic 不要
    TTSRequest = None  # type: ignore


def serve(port: int = 8766) -> None:
    from fastapi import FastAPI
    from fastapi.responses import Response
    import uvicorn

    app = FastAPI(title="fusuma-tts")

    @app.get("/health")
    def health():
        return {"ok": True, "personas": list(PERSONAS)}

    @app.post("/tts")
    def tts(req: TTSRequest):
        t0 = time.time()
        audio, sr = synth(req.persona, req.text, req.seed)
        buf = io.BytesIO()
        sf.write(buf, audio, sr, format="WAV")
        return Response(
            buf.getvalue(),
            media_type="audio/wav",
            headers={"X-Synth-Seconds": f"{time.time()-t0:.2f}", "X-Audio-Seconds": f"{len(audio)/sr:.2f}"},
        )

    _load(BASE_MODEL)  # warm up
    uvicorn.run(app, host="127.0.0.1", port=port, log_level="warning")


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "help"
    if cmd == "design":
        only = sys.argv[sys.argv.index("--only") + 1] if "--only" in sys.argv else None
        seed_base = int(sys.argv[sys.argv.index("--seed") + 1]) if "--seed" in sys.argv else 1000
        exact = int(sys.argv[sys.argv.index("--exact-seed") + 1]) if "--exact-seed" in sys.argv else None
        design_all(force="--force" in sys.argv, only=only, seed_base=seed_base, exact_seed=exact)
    elif cmd == "say":
        persona, text, out = sys.argv[2], sys.argv[3], sys.argv[4]
        audio, sr = synth(persona, text)
        sf.write(out, audio, sr)
        print(f"{out}: {len(audio)/sr:.2f}s")
    elif cmd == "serve":
        port = int(sys.argv[sys.argv.index("--port") + 1]) if "--port" in sys.argv else 8766
        serve(port)
    else:
        print(__doc__)
