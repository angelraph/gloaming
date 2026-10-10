"""Narration for the Gloaming demo. One entry per scene; make_vo() writes vo/<id>.mp3 and
vo/durations.json so the recorder and the editor can time every scene to its voice."""
import asyncio
import json
import re
import subprocess
from pathlib import Path

import edge_tts
import imageio_ffmpeg

VOICE = "en-US-AndrewMultilingualNeural"
RATE = "-3%"
HERE = Path(__file__).parent
VO = HERE / "vo"

SCENES = [
    ("intro", "Gloaming. Smarter trades. Real opportunities."),
    ("problem",
     "Bitget's rTokens are tokenized U.S. stocks, and they trade around the clock. "
     "The real shares behind them trade for six and a half hours on a weekday. "
     "For the other seventeen and a half hours, and all weekend, nothing pins an rToken to its stock. "
     "That window is the gloaming."),
    ("idea",
     "Gloaming estimates where each rToken should be trading, from its last real close and what index futures, "
     "crypto and the dollar have done since. The difference is the spread. "
     "An AI agent decides what to do about it, a hard risk layer checks every trade, and every number is public."),
    ("hero",
     "This is the live desk. The dial is a twenty four hour New York clock. "
     "The copper arc is the time the real market is shut and the agent is allowed to act. "
     "The hand is now, and the paper book sits in the middle."),
    ("book",
     "Since submission, the desk has a night console: four live views of the same real data. "
     "The book shows paper equity, today's result, and realized profit after costs. "
     "Equity only moves when a trade fills, so it is drawn as steps."),
    ("market",
     "The market view draws Bitget's own hourly candles, the agent's fair value on top, and the closed hours in copper. "
     "The gap between the candles and that line is exactly what the agent trades."),
    ("spread",
     "The spread map shows all nine symbols, hour by hour. Copper means the rToken traded above fair value, blue means below. "
     "The dark columns are New York trading hours, when the agent stands aside."),
    ("risk",
     "And risk: every position, long or short, against its fifteen percent cap, with net and gross exposure beside it. "
     "These limits are enforced in code. No model can talk its way past them."),
    ("tape",
     "The tape scrolls through real fills. Also new since submission, every fill is checked against Bitget's public one minute candles. "
     "Seven hundred and ninety five of seven hundred and ninety seven matched a price Bitget really traded, and the two that missed are listed."),
    ("reasons",
     "This is the agent's own reasoning. Qwen three point eight max explains each trade, weighing the spread against costs and its own book, "
     "and those words are shown unedited."),
    ("loop",
     "Every cycle follows one loop: observe, decide, gate, execute, record. This is the newest real decision, step by step. "
     "Most nights the answer is hold, because the spread is smaller than the cost of trading."),
    ("agent",
     "On the agent page, any decision can be opened to see the market inputs, the book Qwen was shown, its reasoning, and the risk verdict."),
    ("performance",
     "The performance page shows the record exactly as it is, including the loss, split where the signal was rebuilt, "
     "with every fill checked against Bitget."),
    ("outro",
     "Gloaming runs unattended every fifteen minutes, and every decision is committed to a public repository. "
     "Gloaming. It trades the hours the market can't."),
]


def duration(path: Path) -> float:
    out = subprocess.run([imageio_ffmpeg.get_ffmpeg_exe(), "-i", str(path)], capture_output=True, text=True).stderr
    h, m, s = re.search(r"Duration: (\d+):(\d+):([\d.]+)", out).groups()
    return int(h) * 3600 + int(m) * 60 + float(s)


async def make_vo():
    VO.mkdir(exist_ok=True)
    durations = {}
    for sid, text in SCENES:
        path = VO / f"{sid}.mp3"
        for attempt in range(6):
            try:
                await edge_tts.Communicate(text, VOICE, rate=RATE).save(str(path))
                break
            except Exception as exc:  # this machine's network drops requests; retry
                print("retry", sid, exc)
                await asyncio.sleep(2 + attempt)
        durations[sid] = round(duration(path), 3)
        print(sid, durations[sid])
    (VO / "durations.json").write_text(json.dumps(durations, indent=1))
    print("total", round(sum(durations.values()), 1))


if __name__ == "__main__":
    asyncio.run(make_vo())
