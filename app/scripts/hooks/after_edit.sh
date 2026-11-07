#!/usr/bin/env bash
# Claude Code PostToolUse フック: 判定に効くファイル(プロンプト・知識カード・スキーマ)を変えたら、小さな評価を自動で回す。
# 耳の出力はキャッシュ済みなので、脳(Claude)だけを 4 シナリオ流す(約 1 分・約 $0.15)。FUSUMA_AUTO_EVAL=1 のときだけ回す。
# 結果は additionalContext として Claude に返り、次の手を決める材料になる。
set -u
INPUT="$(cat)"
FILE="$(printf '%s' "$INPUT" | python3 -c 'import sys,json; print(json.load(sys.stdin).get("tool_input",{}).get("file_path",""))')"
case "$FILE" in
  */fusuma/brain/prompts/*.md|*/knowledge/cards.json|*/fusuma/brain/schemas.py) ;;
  *) exit 0 ;;
esac
if [ "${FUSUMA_AUTO_EVAL:-0}" != "1" ]; then
  # 評価は Claude API を使う(約 $0.15)。クローンした人のクレジットを黙って使わないよう、既定では回さずに知らせるだけ
  python3 -c 'import json,sys; print(json.dumps({"hookSpecificOutput": {"hookEventName": "PostToolUse", "additionalContext": sys.argv[1] + " は判定に効くファイルです。小さな評価(約 $0.15)を回すなら FUSUMA_AUTO_EVAL=1 を設定するか、app/scripts/run_eval.py --tag quick --ids S05 S13 S03 S11 を実行してください。"}}, ensure_ascii=False))' "$FILE"
  exit 0
fi
APP="$(cd "$(dirname "$0")/../.." && pwd)"
PY="${FUSUMA_PYTHON:-$APP/../.venv/bin/python}"
OUT="$("$PY" "$APP/scripts/run_eval.py" --tag "hook-$(date +%H%M%S)" --ids S05 S13 S03 S11 --workers 4 2>/dev/null)"
SUMMARY="$(printf '%s' "$OUT" | grep -E '^(S0|S1)[0-9] ' ; printf '%s' "$OUT" | grep -E '"(false_alarm|missed|usd)"' | tr -d ' ,' | tr '\n' ' ')"
python3 - "$FILE" "$SUMMARY" <<'EOF'
import json, sys
f, s = sys.argv[1], sys.argv[2]
print(json.dumps({"hookSpecificOutput": {"hookEventName": "PostToolUse",
  "additionalContext": f"{f} を変えたので小さな評価(S05 勧誘・S13 本物の警察・S03 カード詐欺・S11 友人)を回しました:\n{s}\n本物の電話(S13, S11)で silent 以外になっていたら誤警報です。"}}, ensure_ascii=False))
EOF
