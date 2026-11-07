#!/usr/bin/env python3
"""Claude Code PreToolUse フック: ふすまごしの原則に反するコードを書き込む前に止める。

止めるもの(書き込もうとしている文字列の、代表的な書き方の印で判定する簡易な番人。意味までは読まないので、すり抜ける書き方はある):
  1. 脳(fusuma/brain)が音声を Claude に送ろうとしている(input_audio, audio/wav, 音声ファイルを開く 等)
  2. 端末が声を出す経路を Fusuma.say() の外に足す(fusuma/ の中で sounddevice・TTS・speaker.say・synth を直接使う)。
     ただし devices.py(Speaker と、デモの部屋の音)と ear/pipeline.py(ファイル入力の部屋の音)は除く
  3. 実在しうる電話番号(0 から始まる 10〜11 桁。ハイフン・空白・全角・かっこ・点・+81 の書き方も見る)。どのファイルでも止める。
     架空の印として先頭を 0000 にした番号だけは通す
  4. 本人が「内緒」と言ったメモを取り出す(include_secret=True / memos(True))
名前・会社・住所が実在のものと重なっていないかは、ここでは判定できない(auditor サブエージェントが確かめる)。
終了コード 2 で止め、理由を Claude に返す。
"""
import json
import re
import sys
import unicodedata

data = json.load(sys.stdin)
ti = data.get("tool_input", {})
path = ti.get("file_path", "") or ""
text = unicodedata.normalize("NFKC", "\n".join(str(ti.get(k, "")) for k in ("content", "new_string")))
# 電話番号の書き方をそろえて見る: (03)1234-5678 / 03(1234)5678 / 03.1234.5678 / +81-3-1234-5678 など
SEP = "-‐‑–—−ー "
phone_text = re.sub(r"\+81[" + SEP + r".()]*", "0", text)
phone_text = re.sub(r"\((?=0\d)", "", phone_text)
phone_text = re.sub(r"(?<=\d)[()](?=\d)|(?<=\d)\)(?=[" + SEP + r"]?\d)", "-", phone_text)
phone_text = re.sub(r"(?<![\d.])(0\d{1,4})\.(\d{1,4})\.(\d{3,4})(?![\d.])", r"\1-\2-\3", phone_text)   # 03.1234.5678(小数は見ない)
problems = []
if path.endswith(("/tests/test_principles.py", "/hooks/guard_principles.py")):
    sys.exit(0)        # このフック自身と、そのテスト(わざと止めるべき文字列を持つ)

if "/fusuma/brain/" in path:
    if re.search(r"input_audio|audio/wav|audio/mpeg|\"type\":\s*\"audio\"|media_type=.audio", text):
        problems.append("脳(Claude 側)に音声を送る記述があります。Claude に渡すのはテキストの音声スコアだけ(原則: 音声は端末の外に出さない)。")
    if re.search(r"(open|read)\([^)]*\.(wav|mp3|m4a)", text):
        problems.append("brain/ で音声ファイルを読んでいます。音声は ear/ だけが扱います。")

if "/fusuma/" in path and path.endswith(".py") and not path.endswith(("/fusuma/devices.py", "/fusuma/ear/pipeline.py", "/fusuma/config.py")):
    for m in re.finditer(r"(speaker\.say\(|sd\.play|sounddevice|TTS_URL|OutputStream|\.synth\(|afplay|os\.system\(|simpleaudio|playsound|pyaudio)", text):
        problems.append(f"{path.rsplit('/', 1)[-1]} で {m.group(1)} を直接使っています。"
                        "話す経路は Fusuma.say()(通話中は SilenceViolation、再生中の着信でも止まる)だけにしてください。")

for m in re.finditer(r"(?<![\d.])0\d{0,4}[" + SEP + r"]*\d{1,4}[" + SEP + r"]*\d{3,4}(?![\d.])", phone_text):
    digits = re.sub(r"\D", "", m.group())
    if len(digits) in (10, 11) and not digits.startswith("0000"):
        problems.append(f"電話番号らしき数字「{m.group()}」があります。実在の番号を使わない(架空にするなら先頭を 0000 に)。")
        break

if path.endswith(".py") and re.search(r"include_secret[\"']?\s*[:=]\s*(bool\s*=\s*)?True|\.memos\(\s*True", text):
    problems.append("内緒のメモ(secret)を含めて取り出しています。内緒と判定したメモは、記憶ストア・便り・以後のプロンプトに出しません。")

if problems:
    print("ふすまごしの原則チェックで止めました:\n- " + "\n- ".join(problems), file=sys.stderr)
    sys.exit(2)
sys.exit(0)
