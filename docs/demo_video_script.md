# Gloaming demo video, step by step

A walkthrough you can literally read out loud while you click. Practice it
twice before you hit record, it gets natural fast. Total run time if you
follow it at a normal pace: roughly 90 seconds to 2 minutes. That covers
both submissions in one video, since they read the same live site.

## Before you press record

1. Open a fresh browser tab (private/incognito is cleanest, no bookmarks
   bar, no other tabs visible) and go to https://gloamingdesk.vercel.app
2. Let it fully load once, then refresh it so it's showing the freshest
   numbers right before you record.
3. Close anything else on your screen: email, chat apps, notifications.
   Turn on Do Not Disturb.
4. Have your screen recorder ready (Windows: Xbox Game Bar, Win+G, or any
   screen recorder you already use). Record at 1080p if you can.
5. Read through the whole script below once, out loud, before recording.
   You don't need to memorize it word for word, just know where each part
   goes so it flows.

## The walkthrough

### 1. Open on the top of the page (about 8 seconds)

**Do this:** Just let the page sit there, don't scroll yet. Point your
mouse near the title if you want, but no clicking needed here.

**Say this:**
"This is Gloaming. Bitget's rTokens trade twenty four seven, but the real
stocks they track only trade when NYSE is open. This dashboard watches
that gap."

### 2. The status badge and the four numbers (about 12 seconds)

**Do this:** Move your mouse up to the top right corner where it says
"Agent active" or "Agent idle" next to the NYSE status. Then move down to
the four number tiles (Equity, Cash, Today's P&L, Total Fills) and just
hover over them one at a time, left to right.

**Say this:**
"Up here it tells you in real time whether the Agent is currently active,
that only happens while NYSE is closed. These numbers below are the real
paper trading account, real equity, real cash, real P&L, and the real
number of fills it's made so far. Nothing here is a mockup, this is
whatever the account actually looks like right now."

### 3. The fair value spread chart (about 12 seconds)

**Do this:** Scroll down slowly until the bar chart titled "Fair-value
spread by symbol" is centered on screen. Let it sit there a second so
viewers can actually see the bars.

**Say this:**
"This chart shows, for each stock's rToken right now, how far its price
has drifted from what the Agent thinks it should be worth based on
overnight signals, futures, crypto, and FX. Bars above zero mean the
token looks too expensive. Bars below zero mean it looks cheap."

### 4. The overnight timeline, the most important part (about 25 seconds)

**Do this:** Keep scrolling until you reach "Overnight timeline" on the
left side. Click into that scrollable box and scroll down two or three
entries so a full one is visible, ideally one where the source tag says
qwen3.8-max. Let the camera sit on one full entry, including its written
rationale text, long enough to actually read it.

**Say this:**
"This is every decision the Agent has made, logged one by one. Each entry
shows the symbol, whether it bought or sold, and the actual reasoning
text written by Qwen3.8-max, not a canned message, this is what the
model itself wrote when it made this call. You can see it's cautious,
it explicitly sizes down when it's not fully sure the move isn't just
random noise. And notice this tag right here, it tells you exactly which
system made each decision, Qwen or the backup rule, so nothing is hidden."

### 5. The chat panel (about 20 seconds)

**Do this:** Scroll right or down to the "Ask the desk" panel. Click into
the text box and type a real question, something like: "What happened
overnight?" or "Why did AAPL trade rich overnight?" Press enter or click
send, then wait for the real answer to appear on screen and let the
camera hold on it while it's visible.

**Say this while typing:**
"You can also just ask it directly."

**Say this once the answer appears:**
"That answer isn't generated freely, it's grounded only in the real data
you just saw in the timeline. It can't invent numbers, and it never
places a trade, it only explains."

### 6. The stress test panel (about 12 seconds)

**Do this:** Scroll further down to the decision stress test section.
Point at it, maybe click through one scenario if there's a dropdown or
button to select one.

**Say this:**
"This last panel replays a real historical overnight move against the
current book, so you can see what would have happened without anything
actually changing for real. It's a what if, not a trade."

### 7. Close it out (about 10 seconds)

**Do this:** Scroll back up to the top of the page so the title is
visible again for the last shot.

**Say this:**
"Everything you just saw, the code, the risk controls, the full decision
log, all of it is public on GitHub. This has been running unattended,
live, every fifteen minutes, for days. Thanks for watching."

## After recording

1. Watch it back once before uploading, check the audio is clear and the
   text on screen is readable, not too small.
2. Upload it wherever the submission form asks (YouTube unlisted works
   fine if there's no direct upload option).
3. Paste that link into the "Demo video" line in both
   `docs/submission_agentic_trading.md` and
   `docs/submission_ai_trading_desk.md`, then copy each section from those
   files into the actual Google Form.

That's the whole video. One take covers both tracks since they're reading
the same real, live system.
