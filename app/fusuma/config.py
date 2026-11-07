"""ふすまごし 設定(パス・モデル・しきい値・予算)。環境変数で上書きできる。"""
from __future__ import annotations

import os
from pathlib import Path

APP = Path(__file__).resolve().parents[1]          # .../app
ROOT = APP.parent                                   # .../lab (開発) / リポジトリ直下(公開版)
DATA = Path(os.getenv("FUSUMA_DATA", ROOT / "data"))
RUNS = Path(os.getenv("FUSUMA_RUNS", ROOT / "runs"))
MODELS = Path(os.getenv("FUSUMA_MODELS", ROOT / "models"))
DB_PATH = Path(os.getenv("FUSUMA_DB", RUNS / "fusuma.sqlite3"))
KNOWLEDGE = APP / "knowledge" / "cards.json"
PROMPTS = APP / "fusuma" / "brain" / "prompts"
SCENARIOS = APP / "scenarios" / "scenarios.json"
SCENARIO_AUDIO = DATA / "scenarios"
ENROLL_DIR = DATA / "sfx"

# 端末(耳)のローカルサービス
ASR_URL = os.getenv("FUSUMA_ASR_URL", "http://127.0.0.1:8765/inference")
TTS_URL = os.getenv("FUSUMA_TTS_URL", "http://127.0.0.1:8766/tts")
YAMNET_ONNX = MODELS / "yamnet" / "yamnet.onnx"
YAMNET_CLASSES = MODELS / "yamnet" / "yamnet_class_map.csv"
ASR_PROMPT = "電話での会話。今日中、半額、定期購入、解約、還付金、暗証番号、キャッシュカード、口座、銀行協会、信用金庫、整形外科、みどり町。"

SR = 16000
VAD_THRESHOLD = 0.5
VAD_MIN_SILENCE_MS = 600
VAD_MIN_SPEECH_MS = 160
VAD_PAD_MS = 80
BACKCHANNEL_MAX_SEC = 0.6          # 0.6 秒未満の「はい/ええ/うん/そう」はあいづち(同意と数えない)
BACKCHANNEL_WORDS = ("はい", "ええ", "うん", "そう", "はあ", "ああ", "へえ", "ほう")
LISTENER_EVERY_UTTS = 10           # 聞き役(listener)を呼ぶ間隔: 10 発話 or 60 秒、および通話終了時
LISTENER_EVERY_SEC = 60
POST_CALL_DELAY_SEC = float(os.getenv("FUSUMA_POST_CALL_DELAY", "20"))  # 電話のあと、少し間をおいてから話しかける
LONG_SILENCE_END_SEC = 25          # 受話器置きの音がなくても、長い無音で通話終了とみなす
DIALOG_IDLE_SEC = 25.0           # 電話のあとに話しかけて、これだけ答えがなければ会話を閉じる(文字起こしも消す)
QUIET_BEFORE_OPENER_SEC = 8.0    # 部屋がこれだけ静かなら話しかける(耳が気づかなかった電話の、聞いている側の沈黙を考えて)
# 電話のあとの最初の一言は固定。聞き取った中身を先に言わず、本人に話してもらう(尊厳と「覗かない」距離感のため)
POSTCALL_OPENER = os.getenv("FUSUMA_POSTCALL_OPENER", "そういえば、さっきの電話、なんだったの？")

# Claude(脳)のモデル。用途ごとに選ぶ(README「Claude の使い分け」)
MODEL_LISTENER = os.getenv("FUSUMA_MODEL_LISTENER", "claude-haiku-5-5")   # 通話中に何度も呼ぶ。速く安く、構造化出力
MODEL_REBUTTAL = os.getenv("FUSUMA_MODEL_REBUTTAL", "claude-sonnet-5-5")  # 独立文脈で「本物の可能性」。出典つき
MODEL_FAMILY = os.getenv("FUSUMA_MODEL_FAMILY", "claude-sonnet-5-5")      # 判断の統合・カルテ・電話のあとの会話
MODEL_LETTER = os.getenv("FUSUMA_MODEL_LETTER", "claude-opus-5-5")        # 今すぐの便り(Messages API)。夕方の便りは Managed Agents の Sonnet 5.5

# API 予算(無料クレジットの範囲内で使う。超えたら呼び出しを止める)
BUDGET_USD = float(os.getenv("FUSUMA_BUDGET_USD", "80"))
PRICES = {  # USD per 1M tokens (input, output, cache_read)
    "claude-haiku-5-5": (0.10, 0.50, 0.01),
    "claude-sonnet-5-5": (2.00, 10.00, 0.20),
    "claude-opus-5-5": (4.00, 20.00, 0.20),
    "claude-fable-5-1": (10.00, 50.00, 0.25),
}

PERSON = {"name": "和子", "role": "祖母", "family": "息子の誠、孫の健太(どちらも関東在住)"}
