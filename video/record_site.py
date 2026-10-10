"""Records the narrated walkthrough of the live desk at 1920x1080.

Every page is loaded (data included) before recording starts, and every cursor move, hover,
scroll and click runs inside the page at its own frame rate, so each scene lasts exactly as
long as its voice clip plus a short pad. Frames come from Chrome's screencast with their real
timestamps; scene start times are logged for the editor.
Output: rec/frames/*.jpg, rec/frames.json, rec/scenes.json"""
import base64
import json
import shutil
import sys
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

HERE = Path(__file__).parent
SITE = "https://gloamingdesk.vercel.app"
VO = json.loads((HERE / "vo" / "durations.json").read_text())
PAD = {"hero": 1.2, "book": 1.0, "market": 1.0, "spread": 1.0, "risk": 1.0, "tape": 1.0, "reasons": 1.4,
       "loop": 1.0, "agent": 2.2, "performance": 2.4}
CURSOR_JS = (HERE / "cursor.js").read_text(encoding="utf-8")
SLOW = 3.0  # recorded at a third of real speed, played back at triple speed (see slowmo.js)
SLOWMO_JS = (HERE / "slowmo.js").read_text(encoding="utf-8")
# no blur while recording: views change with a clean fade, so every frame stays legible
NO_BLUR = ("document.addEventListener('DOMContentLoaded', () => { const s = document.createElement('style');"
           " s.textContent = '.console-panel,.reason-slide,.title-reveal *,.reveal{filter:none !important}';"
           " document.head.appendChild(s); });")
ZOOM = "document.addEventListener('DOMContentLoaded', () => { document.documentElement.style.zoom = '1.6'; });"


class Rec:
    def __init__(self, page):
        self.frames, self.scenes, self.cdps = [], [], {}
        self.dir = HERE / "rec" / "frames"
        if self.dir.parent.exists():
            shutil.rmtree(self.dir.parent)
        self.dir.mkdir(parents=True)
        self.page = self.cdp = None
        self.t0 = time.time()
        self.use(page, start=False)

    def use(self, page, start=True):
        if self.cdp is not None and start:
            self.cdp.send("Page.stopScreencast")
        if page not in self.cdps:
            cdp = page.context.new_cdp_session(page)
            cdp.on("Page.screencastFrame", lambda f, c=cdp: self.on_frame(f, c))
            self.cdps[page] = cdp
        self.page, self.cdp = page, self.cdps[page]
        page.bring_to_front()
        if start:
            self.start()

    def on_frame(self, f, cdp):
        p = self.dir / f"{len(self.frames):06d}.jpg"
        p.write_bytes(base64.b64decode(f["data"]))
        self.frames.append({"file": p.name, "t": f["metadata"]["timestamp"]})
        try:
            cdp.send("Page.screencastFrameAck", {"sessionId": f["sessionId"]})
        except Exception:
            pass

    def slow(self):
        """CSS animations and transitions run at half speed too (re-applied after each load)."""
        self.cdp.send("Animation.enable")
        self.cdp.send("Animation.setPlaybackRate", {"playbackRate": 1 / SLOW})

    def start(self):
        self.slow()
        self.cdp.send("Page.startScreencast", {"format": "jpeg", "quality": 92, "maxWidth": 1920, "maxHeight": 1080, "everyNthFrame": 1})

    def stop(self):
        self.cdp.send("Page.stopScreencast")
        (HERE / "rec" / "frames.json").write_text(json.dumps(self.frames))
        (HERE / "rec" / "scenes.json").write_text(json.dumps(self.scenes, indent=1))

    # in-page actions: one round trip each, the motion itself runs in the browser
    def js(self, code, *args):
        return self.page.evaluate(code, list(args))

    def move(self, x, y, ms=700):
        self.js("([x,y,ms]) => window.__cur.move(x,y,ms)", x, y, ms)

    def move_to(self, sel, ms=800, fx=0.5, fy=0.5):
        self.js("([s,ms,fx,fy]) => window.__cur.moveTo(s,ms,fx,fy)", sel, ms, fx, fy)

    def sweep(self, sel, fx0, fx1, fy, ms):
        self.js("([s,a,b,y,ms]) => window.__cur.sweep(s,a,b,y,ms)", sel, fx0, fx1, fy, ms)

    def click(self, sel, ms=700):
        self.js("([s,ms]) => window.__cur.click(s,ms)", sel, ms)

    def scroll_to(self, sel, ms=1400, offset=90):
        self.js("([s,o,ms]) => window.__scroll(s,o,ms)", sel, offset, ms)

    def cam(self, sel, max_scale, ms, up=0):
        res = self.js("([s,m,ms,up]) => window.__cam(s,m,ms,up)", sel, max_scale, ms, up)
        if isinstance(res, str):
            print("    camera:", res, flush=True)

    def cam_reset(self, ms):
        self.js("([ms]) => window.__camReset(ms)", ms)

    def scroll_in(self, sel, dy, ms):
        self.js("([s,dy,ms]) => window.__scrollBy(s,dy,ms)", sel, dy, ms)

    def wait(self, s):
        """s is screen time; the page runs at half speed, so the real wait is s * SLOW.
        Playwright's own wait keeps acknowledging screencast frames; time.sleep would stall them."""
        self.real_wait(s * SLOW)

    def real_wait(self, s):
        if s > 0:
            self.page.wait_for_timeout(int(s * 1000))

    def log(self, what):
        print(f"    {time.time() - self.t0:5.1f}s {what}", flush=True)

    def scene(self, sid):
        rec = self

        class _S:
            def __enter__(s):
                s.t0 = rec.t0 = time.time()
                rec.scenes.append({"id": sid, "start": s.t0, "dur": (VO[sid] + PAD[sid]) * SLOW, "slow": SLOW})
                print("scene", sid, round(VO[sid] + PAD[sid], 2), flush=True)

            def __exit__(s, *a):
                left = s.t0 + (VO[sid] + PAD[sid]) * SLOW - time.time()
                if left > 0:
                    rec.real_wait(left)
                else:
                    print("  OVER by", round(-left, 2), "s", flush=True)
                    rec.scenes[-1]["dur"] = time.time() - s.t0
        return _S()



def preload(ctx):
    home = ctx.new_page()
    for path, ready in (("/agent", "#feed li button"), ("/performance", '[aria-label="Checked against Bitget"] table')):
        home.goto(SITE + path, wait_until="networkidle", timeout=180_000)  # warms the caches
        home.wait_for_selector(ready, timeout=180_000)
    home.goto(SITE + "/", wait_until="networkidle", timeout=180_000)
    home.wait_for_selector("#console-panel-book .recharts-area", timeout=180_000)
    home.locator("#console-tab-market").click()
    home.wait_for_selector("#console-panel-market .candle", timeout=180_000)
    home.wait_for_function("document.querySelectorAll('#console-panel-spread .heat-cell').length > 0", timeout=180_000)
    home.locator("#console-tab-book").click()
    home.wait_for_selector('[aria-label="Choose a trade"] button', timeout=180_000)
    home.evaluate("window.scrollTo(0,0)")
    home.evaluate(CURSOR_JS)
    home.evaluate("window.__cur.move(1300, 420, 1)")
    home.wait_for_timeout(2500)
    return home


def main():
    with sync_playwright() as p:
        browser = p.chromium.launch()
        ctx = browser.new_context(viewport={"width": 1920, "height": 1080}, locale="en-US")
        ctx.add_init_script(ZOOM)
        ctx.add_init_script(NO_BLUR)
        ctx.add_init_script(SLOWMO_JS)
        home = preload(ctx)
        print("preloaded; cursor zoom factor", home.evaluate("window.__cur.Z"), flush=True)

        r = Rec(home)
        page = home
        r.start()
        r.wait(0.5)

        with r.scene("hero"):
            r.wait(0.8)
            r.cam("figure", 1.7, 1800)
            r.move_to("figure svg", 1200, 0.9, 0.36)
            r.wait(1.6)
            r.move_to("figure svg", 1600, 0.16, 0.76)
            r.wait(1.2)
            r.move_to("figure svg", 1200, 0.5, 0.5)
            r.wait(1.2)
            r.cam_reset(1100)
            r.log("hero done")

        with r.scene("book"):
            r.scroll_to(".console-frame", 1500, 96)
            r.click("#console-tab-book", 500)
            r.cam("#console-panel-book .grid", 1.6, 1300)
            r.wait(3.4)
            r.cam("#console-panel-book .recharts-wrapper", 1.5, 1300, -40)
            r.sweep("#console-panel-book .recharts-wrapper", 0.1, 0.96, 0.45, 3800)
            r.cam_reset(900)
            r.click('#console-panel-book [aria-label="Time range"] button:nth-child(2)', 600)
            r.wait(1.0)
            r.click('#console-panel-book [aria-label="Time range"] button:nth-child(3)', 500)
            r.log("book done")

        with r.scene("market"):
            r.click("#console-tab-market", 600)
            r.wait(1.6)
            r.cam("#console-panel-market > div", 1.45, 1300)
            r.sweep("#console-panel-market svg", 0.05, 0.9, 0.5, 6200)
            r.cam_reset(900)
            r.log("market done")

        with r.scene("spread"):
            r.click("#console-tab-spread", 600)
            r.wait(1.6)
            r.cam("#console-panel-spread > div", 1.5, 1300)
            for fx, fy in [(0.45, 0.22), (0.63, 0.48), (0.8, 0.7), (0.97, 0.16)]:
                r.move_to("#console-panel-spread svg", 700, fx, fy)
                r.wait(0.9)
            r.cam_reset(900)
            r.log("spread done")

        with r.scene("risk"):
            r.click("#console-tab-risk", 600)
            r.wait(1.6)
            r.cam("#console-panel-risk > div > div:first-child", 1.6, 1300)
            r.move_to("#console-panel-risk li:nth-child(5)", 800, 0.45, 0.5)
            r.wait(1.6)
            r.move_to("#console-panel-risk li:nth-child(7)", 800, 0.6, 0.5)
            r.wait(1.0)
            r.cam("#console-panel-risk > div > div:last-child", 1.6, 1300)
            r.wait(1.8)
            r.cam_reset(900)
            r.log("risk done")

        with r.scene("tape"):
            r.scroll_to('[aria-label="Recent trades"]', 1500, 96)
            r.cam(".tape", 1.5, 1300)
            r.move(1500, 540, 600)
            r.wait(4.2)
            r.cam("text=Matched Bitget", 1.7, 1300)
            r.wait(3.6)
            r.cam_reset(900)
            r.log("tape done")

        with r.scene("reasons"):
            r.scroll_to("[aria-label=\"In Qwen's words\"]", 1400, 96)
            r.cam("[aria-label=\"In Qwen's words\"] .spotlight", 1.4, 1300)
            r.wait(5.0)
            r.click('[aria-label="Choose a trade"] button:nth-child(2)', 700)
            r.move(1700, 200, 700)
            r.log("reasons done")

        with r.scene("loop"):
            r.cam_reset(700)
            r.scroll_to('[aria-label="One decision"] ol', 1400, 120)
            r.cam('[aria-label="One decision"] ol', 1.45, 1300)
            r.move(960, 700, 700)
            r.wait(4.0)
            r.cam('[aria-label="One decision"] figure', 1.45, 1300)
            r.wait(3.4)
            r.cam_reset(900)
            r.log("loop done")

        def open_page(path, ready):
            home.goto(SITE + path, wait_until="networkidle", timeout=180_000)
            home.wait_for_selector(ready, timeout=180_000)
            home.evaluate(CURSOR_JS)
            home.evaluate("window.__cur.move(1300, 420, 1)")
            r.slow()
            r.real_wait(2.5)

        open_page("/agent", "#feed li button")
        with r.scene("agent"):
            r.scroll_to("#feed li:nth-child(1)", 1200, 220)
            r.click("#feed li:nth-child(1) button", 700)
            r.wait(1.8)
            r.scroll_in("dialog[open]", 560, 2400)
            r.log("agent done")

        home.keyboard.press("Escape")
        open_page("/performance", '[aria-label="Checked against Bitget"] table')
        with r.scene("performance"):
            r.wait(0.4)
            r.scroll_to('[aria-label="Checked against Bitget"]', 1600, 96)
            r.cam("text=Matched Bitget", 1.5, 1200)
            r.wait(2.2)
            r.cam('[aria-label="Checked against Bitget"] table', 1.4, 1200)
            r.move_to('[aria-label="Checked against Bitget"] table', 700, 0.6, 0.3)
            r.log("performance done")

        r.wait(0.4)
        r.stop()
        browser.close()
        print("frames", len(r.frames), flush=True)


if __name__ == "__main__":
    main()
