#!/usr/bin/env bash
# ふすまごし セットアップ(macOS / Apple Silicon)。リポジトリ直下で: bash scripts/setup.sh
# 1) Python 環境 2) whisper.cpp(Metal) 3) モデル(whisper large-v3-turbo / YAMNet / Silero は pip) 4) TTS(MLX)
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
need() { command -v "$1" >/dev/null || { echo "missing: $1 ($2)"; exit 1; }; }
need brew "https://brew.sh"; need uv "brew install uv"; need ffmpeg "brew install ffmpeg"; need cmake "brew install cmake"
command -v rubberband >/dev/null || brew install rubberband   # ffmpeg に rubberband が無くても、合成は atempo で代わりに動く
command -v ant >/dev/null || echo "note: Claude Platform の CLI(ant)が無い。夕方の便り(Managed Agents)を使うなら: brew install --cask anthropics/tap/ant"

echo "== Python(耳・脳・画面)"
uv venv --python 3.12 .venv
uv pip install --python .venv/bin/python -r app/requirements.txt

echo "== Python(TTS / MLX)"
uv venv --python 3.12 .venv-tts
uv pip install --python .venv-tts/bin/python "mlx-audio[tts]" fastapi "uvicorn[standard]" soundfile

echo "== whisper.cpp v1.7.6(Metal)"
mkdir -p vendor models/whisper models/yamnet logs runs data
if [ ! -x vendor/whisper.cpp-1.7.6/build/bin/whisper-server ]; then
  git clone --depth 1 --branch v1.7.6 https://github.com/ggml-org/whisper.cpp.git vendor/whisper.cpp-1.7.6
  cmake -S vendor/whisper.cpp-1.7.6 -B vendor/whisper.cpp-1.7.6/build -DCMAKE_BUILD_TYPE=Release -DGGML_METAL=ON -DWHISPER_BUILD_SERVER=ON
  cmake --build vendor/whisper.cpp-1.7.6/build -j 8 --config Release
fi

echo "== モデル"
[ -f models/whisper/ggml-large-v3-turbo-q8_0.bin ] || curl -L --fail -o models/whisper/ggml-large-v3-turbo-q8_0.bin \
  https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-large-v3-turbo-q8_0.bin
[ -f models/yamnet/yamnet.onnx ] || curl -L --fail -o models/yamnet/yamnet.onnx https://huggingface.co/audiomagic/yamnet-onnx/resolve/main/yamnet.onnx
[ -f models/yamnet/yamnet_class_map.csv ] || curl -L --fail -o models/yamnet/yamnet_class_map.csv https://huggingface.co/audiomagic/yamnet-onnx/resolve/main/yamnet_class_map.csv

echo "== TTS のモデル(約 2GB。先に取っておくと、初回の起動がすぐ終わる)"
(cd app/tts_server && ../../.venv-tts/bin/python -c "import tts_engine as t; t._load(t.BASE_MODEL)")

echo "== 声見本(合成音声。実在の人の声は使わない)"
[ -f app/tts_server/voices/fusuma_ref.wav ] || (cd app/tts_server && ../../.venv-tts/bin/python tts_engine.py design)

cat <<'EOF'

セットアップ完了。次に(README の「動かし方」と同じ):
  1. Claude の認証:   ant auth login   (または ANTHROPIC_API_KEY を設定)
  2. サービス起動:     bash scripts/services.sh start      (聞けるようになるまで待つ)
  3. デモ音声の合成:   .venv/bin/python app/scripts/synth_scenarios.py    (初回のみ・約 20 分)
  4. 原則のテスト:     cd app && ../.venv/bin/python tests/test_principles.py && cd ..   (API を使わない)
  5. 画面を起動:       cd app && ../.venv/bin/uvicorn fusuma.server:app --port 8780   → http://localhost:8780
  6. 記憶の下準備:     .venv/bin/python app/scripts/run_call.py --reset S00 R01
  7. デモ:             curl -X POST localhost:8780/api/play -H 'content-type: application/json' -d '{"id":"S05","clock":"14:01:50"}'
  夕方の便り(Managed Agents)を使うなら、先に: cd app/managed && ant apply agents/fusuma-family/deployment-evening.yaml
  (毎日 18:00 に動く。止めるとき: .venv/bin/python app/scripts/managed_schedule.py pause)
EOF
