#!/bin/zsh
# HyperFrames CLI を呼ぶ(プロジェクトのフォルダで実行する)。
# Claude Code の HyperFrames プラグインがあればその版を、なければ npm の同じ版を使う。
L="$HOME/.claude/plugins/cache/hyperframes/hyperframes/0.9.19/skills/hyperframes/scripts/plugin-cli.mjs"
if [ -f "$L" ]; then exec node "$L" "$@"; else exec npx -y hyperframes@0.9.19 "$@"; fi
