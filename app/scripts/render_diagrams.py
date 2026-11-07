"""README の図(web/img/*.svg)を、Web フォント(見出し Shippori Mincho B1・注記 Klee One)で PNG に描き、
SVG も同じ場所(docs/images/)に写す。README では PNG を使う。

python app/scripts/render_diagrams.py                       # 全部 → docs/images/(lab から動かすと ../fusumagoshi/docs/images/)
python app/scripts/render_diagrams.py architecture eval      # 一部だけ
"""
from __future__ import annotations

import shutil
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

APP = Path(__file__).resolve().parents[1]
SRC = APP / "web" / "img"
OUT = APP.parent / "docs" / "images" if (APP.parent / "docs").exists() else APP.parents[1] / "fusumagoshi" / "docs" / "images"
NAMES = ["architecture", "eval", "ma"]       # README の図。flow は画面とキャラの実物から組む web/img/flow.html(Chrome で書き出す)
FONT = ("https://fonts.googleapis.com/css2?family=Shippori+Mincho+B1:wght@500;600;700;800"
        "&family=Klee+One:wght@400;600&display=block")
PAPER = "#f3ead8"     # 和紙の生成り(図の地と同じ色)
SCALE = 1.5           # 1600 幅の図 → 2400 幅

# 日本語の Web フォントは文字の範囲ごとに分かれて届く。図の中の文字を、使っている書体と太さで先に読み込ませ、
# 読み込めなかった文字があれば止める(代わりの書体で描いた PNG を残さない)。
# 書体の CSS そのものが届かないと document.fonts.check() は true を返すので、最初に指定した書体が 1 つも
# 読み込まれていない文字も「読み込めなかった」に数える。
LOAD_FONTS = """async () => {
  const want = [];
  for (const el of document.querySelectorAll('svg text')) {
    const cs = getComputedStyle(el);
    const first = cs.fontFamily.split(',')[0].trim().replace(/^["']|["']$/g, '');
    want.push([`${cs.fontWeight} 32px ${cs.fontFamily}`, el.textContent, first]);
  }
  await Promise.all(want.map(([f, t]) => document.fonts.load(f, t)));
  await document.fonts.ready;
  const loaded = new Set([...document.fonts].filter(f => f.status === 'loaded').map(f => f.family.replace(/["']/g, '')));
  return want.filter(([f, t, first]) => !loaded.has(first) || !document.fonts.check(f, t)).map(([f, t]) => f + ' ' + t);
}"""


def render(names: list[str], src: Path = SRC, out: Path = OUT) -> None:
    out.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        page = browser.new_page(device_scale_factor=SCALE, viewport={"width": 1700, "height": 1100})
        for name in names:
            svg = (src / f"{name}.svg").read_text()
            page.set_content(f'<!doctype html><html><head><meta charset="utf-8"><link rel="stylesheet" href="{FONT}">'
                             f'<style>html,body{{margin:0;background:{PAPER}}} svg{{display:block}}</style></head>'
                             f'<body>{svg}</body></html>', wait_until="networkidle")
            missing = page.evaluate(LOAD_FONTS)
            if missing:
                raise SystemExit(f"{name}: Web フォントを読み込めない文字があります: {missing[:3]}")
            box = page.evaluate("(() => { const v = document.querySelector('svg').viewBox.baseVal; return [v.width, v.height]; })()")
            page.set_viewport_size({"width": int(box[0]), "height": int(box[1])})
            page.evaluate("(([w, h]) => { const s = document.querySelector('svg'); s.setAttribute('width', w); s.setAttribute('height', h); })",
                          box)
            page.locator("svg").first.screenshot(path=str(out / f"{name}.png"))
            shutil.copyfile(src / f"{name}.svg", out / f"{name}.svg")
            print(f"{name}.png  {int(box[0] * SCALE)}x{int(box[1] * SCALE)}  (+ {name}.svg)")
        browser.close()


if __name__ == "__main__":
    render(sys.argv[1:] or NAMES)
