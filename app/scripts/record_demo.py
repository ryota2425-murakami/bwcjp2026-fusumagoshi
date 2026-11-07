"""デモ画面を録画する(動画用)。サーバー(:8780)が動いている前提。

python app/scripts/record_demo.py call   --scenario S05 --out video/assets/rec/call_S05      # リポジトリ直下から
python app/scripts/record_demo.py letter --out video/assets/rec/letter
(作業用の配置 lab/ からなら --out ../video/assets/rec/...)
- 画面は Playwright(ヘッドレス Chromium, 1920x1080)で録る。音は、イベントの時刻(wall/_ts)を使って編集時に重ねる。
- ふすまごしの声を動画で使うので、サーバーは FUSUMA_SAVE_SPEECH=1 で起動しておく(runs/speech に声が残る。ふだんは残さない)。
"""
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import time
from pathlib import Path

import httpx
from playwright.sync_api import sync_playwright

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from fusuma import config  # noqa: E402

BASE = "http://127.0.0.1:8780"
EVENTS = config.RUNS / "events.jsonl"


def events_since(t0: float) -> list[dict]:
    out = []
    if EVENTS.exists():
        for line in EVENTS.read_text().splitlines()[-3000:]:
            try:
                e = json.loads(line)
            except Exception:
                continue
            if e.get("_ts", 0) >= t0:
                out.append(e)
    return out


def wait_for(t0: float, kind: str, timeout: float) -> list[dict]:
    end = time.time() + timeout
    while time.time() < end:
        evs = events_since(t0)
        if any(e["type"] == kind for e in evs):
            return evs
        time.sleep(1.0)
    raise TimeoutError(kind)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("what", choices=["call", "letter", "idle"])
    ap.add_argument("--scenario", default="S05")
    ap.add_argument("--clock", default=None)
    ap.add_argument("--page", default=None)
    ap.add_argument("--out", required=True)
    ap.add_argument("--tail", type=float, default=4.0)
    ap.add_argument("--timeout", type=float, default=600)
    args = ap.parse_args()
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    page_url = BASE + (args.page or ("/family.html" if args.what == "letter" else "/"))
    with sync_playwright() as p:
        browser = p.chromium.launch()
        ctx = browser.new_context(viewport={"width": 1920, "height": 1080}, device_scale_factor=1,
                                  record_video_dir=str(out), record_video_size={"width": 1920, "height": 1080})
        page = ctx.new_page()
        t_page = time.time()
        page.goto(page_url, wait_until="networkidle")
        page.wait_for_timeout(2500)
        t_trigger = time.time()
        if args.what == "call":
            r = httpx.post(BASE + "/api/play", json={"id": args.scenario, "clock": args.clock}, timeout=30).json()
            print("play:", r, flush=True)
            evs = wait_for(t_trigger, "dialog_done", args.timeout) if r.get("answers") else wait_for(t_trigger, "decision", args.timeout)
        elif args.what == "letter":
            httpx.post(BASE + "/api/letter", json={"urgency": "evening", "via": "managed", "reset_day": True}, timeout=30)
            evs = wait_for(t_trigger, "letter", args.timeout)
        else:
            page.wait_for_timeout(args.tail * 1000)
            evs = []
        page.wait_for_timeout(args.tail * 1000)
        t_end = time.time()
        video_path = page.video.path()
        ctx.close()
        browser.close()
    webm = out / "screen.webm"
    shutil.move(video_path, webm)
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(webm), "-c:v", "libx264", "-preset", "medium", "-crf", "18",
                    "-pix_fmt", "yuv420p", "-r", "30", str(out / "screen.mp4")], check=True)
    meta = {"t_page": t_page, "t_trigger": t_trigger, "t_end": t_end, "url": page_url, "what": args.what, "scenario": args.scenario,
            "events": [e for e in events_since(t_page) if e.get("type") not in ("level",)]}
    (out / "timing.json").write_text(json.dumps(meta, ensure_ascii=False, indent=1, default=str))
    print(f"saved {out}/screen.mp4 ({t_end - t_page:.0f}s)")


if __name__ == "__main__":
    main()
