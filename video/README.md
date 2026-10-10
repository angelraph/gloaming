# Gloaming demo film

A narrated 3:38 walkthrough (1920x1080, 30 fps, H.264 video and AAC audio) of the live Desk, made for the judges of the Bitget AI Base Camp Hackathon S2. It covers the problem (rTokens trade around the clock, the real shares do not), the idea (price each rToken from its last real close, act only on a spread that can pay for itself), and then the live product: the night console, every fill checked against Bitget, Qwen's own reasoning, the one-decision loop, the agent page and the performance record, loss included.

The film is built by a small pipeline of scripts in this folder. Rendered media (`out/`, `clips/`, `rec/`, `vo/`) is not committed; the sources are.

## What is real

- **Footage.** Every shot of the product is the live production Desk at https://gloamingdesk.vercel.app, recorded on 2026-10-09 with Playwright (Chromium) at 1920x1080, with the page zoomed to 1.6 so numbers stay legible. Each page is fully loaded, data included, before its scene is recorded. The Desk is read-only and nothing in the film places a trade: every action is a hover, a scroll or a click that opens something that was already there (a decision inspector, a tab).
- **Numbers.** Every figure on screen is read by the Desk from the repository's own files at the time of recording. The two checks quoted in the narration (795 of 797 fills matched a price Bitget really traded, two misses listed) come from [`gloaming_agent/fill_verification.json`](../gloaming_agent/fill_verification.json), written by [`gloaming_agent/verify_fills.py`](../gloaming_agent/verify_fills.py).
- **Voice.** A synthetic voice (Microsoft Edge text to speech, `en-US-AndrewMultilingualNeural`, rate -3%). The full script is in [`narration.py`](narration.py).
- **Music.** An ambient bed synthesized from scratch in [`music.py`](music.py): no samples, no licences, ducked under the voice.
- **Motion graphics.** The intro, problem, idea, chapter cards and outro are drawn in [`mg.html`](mg.html) (HTML canvas) and rendered frame by frame, deterministically, by [`render_mg.py`](render_mg.py). They are illustrations and are not presented as live data.

## How the footage was captured

The recording machine is slow, so the page is recorded in slow motion and played back faster rather than captured at a low frame rate.

1. [`slowmo.js`](slowmo.js) slows the page's clock to one third (`performance.now` and `requestAnimationFrame`), so animations and scrolls run at a third of their real speed while Chrome's screencast captures frames.
2. [`cursor.js`](cursor.js) draws a pointer and moves it between targets, so the viewer can see what is being pointed at. Clicks are real events in the page.
3. [`record_site.py`](record_site.py) drives the scenes and records Chrome's screencast with each frame's real timestamp. Each scene lasts as long as its voice clip plus a short pad, using `vo/durations.json`.
4. [`assemble.py`](assemble.py) cuts the recording into scenes, compresses time back to normal speed at 30 fps, interleaves the motion-graphics clips, lays each voice clip at its scene and mixes it over the music bed with ducking and loudness normalisation (-16 LUFS).

## Run order

Requirements: Python 3.13 with `playwright` (run `playwright install chromium`), `edge-tts`, `imageio-ffmpeg` and `numpy`.

```bash
cd video
python narration.py     # writes vo/<scene>.mp3 and vo/durations.json
python render_mg.py     # writes clips/*.mp4 for the motion-graphics scenes
python record_site.py   # records the live Desk into rec/
python assemble.py      # writes out/gloaming_demo.mp4
```

`record_site.py` records whatever the live Desk shows on the day you run it, so the numbers in a new take will differ from the narration; edit the scene text in `narration.py` to match before re-recording.

## Scenes

| # | Scene | Source | What it shows |
|---|---|---|---|
| 1 | intro | motion graphics | The Gloaming mark and tagline |
| 2 | problem | motion graphics | rTokens trade 24/7, the real shares about 6.5 hours a weekday |
| 3 | idea | motion graphics | Fair value from the last close and live proxies, the spread, the agent and the risk layer |
| 4 | hero | live Desk | The Dusk Dial: a 24-hour New York clock and the paper book |
| 5 | book | live Desk | Night console: paper equity, today, realized P&L net of costs |
| 6 | market | live Desk | Bitget hourly candles against the agent's fair value, closed hours shaded |
| 7 | spread | live Desk | The nine-symbol, hour-by-hour spread map |
| 8 | risk | live Desk | Every position against its cap, with net and gross exposure |
| 9 | tape | live Desk | The fill tape and the check against Bitget's candles |
| 10 | reasons | live Desk | Qwen's reasoning, shown unedited |
| 11 | loop | live Desk | One decision, step by step: observe, decide, gate, execute, record |
| 12 | agent | live Desk | The decision inspector |
| 13 | performance | live Desk | The record as it is, split by signal era, checked against Bitget |
| 14 | outro | motion graphics | The lockup and the line |
