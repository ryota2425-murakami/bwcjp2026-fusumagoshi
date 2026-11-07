"""ASR: whisper.cpp サーバー(whisper large-v3-turbo, Metal)へ発話区間を送る。ローカル完結。"""
from __future__ import annotations

import io
import re

import httpx
import numpy as np
import soundfile as sf

from .. import config

# 無音や雑音で whisper が出しがちな定型の幻聴
HALLUCINATIONS = ("ご視聴ありがとうございました", "チャンネル登録", "お疲れ様でした", "字幕", "ありがとうございました。ありがとうございました")
_client = httpx.Client(timeout=60)


def transcribe(audio16: np.ndarray, prompt: str | None = None) -> str:
    pad = np.zeros(int(0.15 * config.SR), dtype=np.float32)
    buf = io.BytesIO()
    sf.write(buf, np.concatenate([pad, audio16.astype(np.float32), pad]), config.SR, format="WAV", subtype="PCM_16")
    r = _client.post(config.ASR_URL, files={"file": ("seg.wav", buf.getvalue(), "audio/wav")},
                     data={"response_format": "json", "language": "ja", "no_timestamps": "true", "no_context": "true", "temperature": "0.0", "prompt": config.ASR_PROMPT if prompt is None else prompt})
    r.raise_for_status()
    text = r.json().get("text", "")
    return clean(text)


def clean(text: str) -> str:
    text = text.replace("\n", "").strip()
    text = re.sub(r"\s+", "", text)
    if not re.search(r"[ぁ-んァ-ン一-龥a-zA-Z0-9]", text):
        return ""
    for h in HALLUCINATIONS:
        if h in text:
            return ""
    # 同じ語の連続(幻聴によくある)を 2 回までに
    text = re.sub(r"(.{2,8}?)\1{2,}", r"\1\1", text)
    return text
