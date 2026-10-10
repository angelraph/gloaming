"""Renders the motion-graphics scenes in mg.html frame by frame (deterministic, 30 fps) and
encodes each to clips/<name>.mp4. Usage: python render_mg.py [still]  (still = test frames only)"""
import json
import subprocess
import sys
from pathlib import Path

import imageio_ffmpeg
from playwright.sync_api import sync_playwright

HERE = Path(__file__).parent
FPS = 30
FF = imageio_ffmpeg.get_ffmpeg_exe()
VO = json.loads((HERE / "vo" / "durations.json").read_text())

# (clip name, scene, duration seconds, params)
CLIPS = [
    ("01_intro", "intro", 7.2, {}),
    ("02_problem", "problem", VO["problem"] + 1.4, {}),
    ("03_idea", "idea", VO["idea"] + 1.4, {}),
    ("04_ch_desk", "chapter", 2.4, {"num": "01", "title": "The live desk", "sub": "gloamingdesk.vercel.app", "seed": 3}),
    ("06_ch_console", "chapter", 2.4, {"num": "02", "title": "The night console", "sub": "New since submission", "seed": 9}),
    ("11_ch_proof", "chapter", 2.4, {"num": "03", "title": "Proof, not promises", "sub": "Real fills, real reasoning", "seed": 15}),
    ("15_ch_record", "chapter", 2.4, {"num": "04", "title": "The full record", "sub": "Every decision, open to inspect", "seed": 21}),
    ("18_outro", "outro", VO["outro"] + 3.0, {}),
]


def main(still=False):
    (HERE / "clips").mkdir(exist_ok=True)
    (HERE / "stills").mkdir(exist_ok=True)
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": 1920, "height": 1080})
        page.goto((HERE / "mg.html").as_uri())
        page.wait_for_function("window.ready !== undefined")
        page.evaluate("window.ready()")
        page.wait_for_timeout(800)
        for name, scene, dur, params in CLIPS:
            if still:
                for frac in (0.15, 0.5, 0.85):
                    page.evaluate("([s,t,d,p]) => window.render(s,t,d,p)", [scene, dur * frac, dur, params])
                    page.screenshot(path=str(HERE / "stills" / f"{name}_{int(frac*100)}.png"))
                continue
            n = int(round(dur * FPS))
            enc = subprocess.Popen(
                [FF, "-y", "-loglevel", "error", "-f", "image2pipe", "-framerate", str(FPS), "-i", "-",
                 "-c:v", "libx264", "-preset", "medium", "-crf", "13", "-pix_fmt", "yuv420p", str(HERE / "clips" / f"{name}.mp4")],
                stdin=subprocess.PIPE,
            )
            for i in range(n):
                page.evaluate("([s,t,d,p]) => window.render(s,t,d,p)", [scene, i / FPS, dur, params])
                enc.stdin.write(page.screenshot(type="png"))
            enc.stdin.close()
            enc.wait()
            print(name, n, "frames")
        browser.close()


if __name__ == "__main__":
    main(still="still" in sys.argv)
