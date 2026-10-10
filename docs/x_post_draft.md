> **Historical draft (2026-09-28).** The deadline question it raises has since passed, and the figures are as of that date. Kept for the record.

# X promotional post draft (rewritten Sept 28, against the live handbook and form)

## Read this first: a real conflict between two official sources

Checked directly, live, on Sept 28:

- The **Google Form** (the actual submission mechanism, https://forms.gle/GyWZCMCPocgJdJon6) currently
  states: "The submission deadline is October 8, 23:59 (UTC+8)."
- The **Developer Handbook** (https://bitget-ai.gitbook.io/bitgetai_hackathons2/, "Last updated 10 days
  ago" as of this check) states the submission deadline is **September 27, 2026**, with public voting
  running **September 22-28** (today) and judge review **September 22 - October 7**, winners announced
  **October 8**.

These do not agree, and I cannot resolve it for you - guessing wrong here is worse than anything else in
this document. Two readings:
1. The deadline was extended to Oct 8 and the form was updated to reflect it, but the handbook page
   (static, "last updated 10 days ago") was not.
2. The form's date is stale or wrong, and the real deadline (and today, the last day of voting) already
   passed or is closing today.

**Before doing anything else, check the official Telegram (https://t.me/+o1tYqQ_lXxllYjgy) or
@Bitget_AI's recent posts for an extension announcement.** If you find nothing either way, submitting
today rather than waiting is the safer move - the form is live and accepting responses right now
regardless of which date is correct.

## The exact current requirement (quoted from the live handbook, Chapter III/IV)

> Promotion requirement: Submission must include at least 1 X post link - retweet
> https://x.com/Bitget_AI/status/2100519318824055159?s=20, and introduce the product / Agent / strategy
> you are building. No X post = incomplete submission.
>
> X Promotional Post Link (required): Must include #BitgetHackathon + @Bitget_AI, and be an interactive
> promotional post introducing the product / Agent / strategy you're building, and need quote this
> https://x.com/Bitget_AI/status/2100519318824055159?s=20

Read together, this means: use X's **Quote** action (not a bare Retweet, not a Reply) on
https://x.com/Bitget_AI/status/2100519318824055159, write your own genuine introduction in the quote
text, and include `#BitgetHackathon` and `@Bitget_AI` in that text. The quoted post is attached by X
automatically and does not count against your 280 characters.

This replaces the old draft's guess at an "official post to retweet" (marked TBD at the time) - the
link above is now stated directly in the handbook, not inferred.

## The post (quote-tweet https://x.com/Bitget_AI/status/2100519318824055159, write this as your comment)

Verified with a script, not eyeballed - X counts any link as a flat 23 characters (t.co wrapping); the
quoted post itself does not count.

```
Tokenized US stocks trade 24/7. The real market doesn't.

Gloaming prices Bitget rTokens overnight with Qwen3.8-max, under hard non-LLM risk limits, and trades the gap - every decision explained, every cost counted.

Live: https://gloamingdesk.vercel.app

#BitgetHackathon @Bitget_AI
```

275 of 280 characters. Carries the hook, what it does (Qwen decides, a separate risk layer holds it
back), a live link a reader can open immediately, and both required tags.

## Reply thread (two replies under the main post, more depth for anyone who scrolls)

```
Qwen3.8-max is the real decision-maker: 91%+ of ~9,600 logged decisions came directly from it, each with its own written reason you can read in the live timeline - never a summary written after the fact.

Code: https://github.com/angelraph/gloaming
```

```
We tested our own thesis on real data first: trading a 0.5%+ spread averaged -37.6bp after costs, no edge. Qwen now knows that, and mostly holds. Two other bugs we found live are documented too, not hidden.

https://gloamingdesk.vercel.app/method
```

## Long-form explainer thread (optional, pairs with a demo video)

Post the main post above (quoting the official post) as the intro, then this as a 9-post reply thread
underneath for anyone who wants the full picture. Each post verified under 280 characters.

```
1/9
Tokenized US stocks trade 24/7. The real shares they track only trade on NYSE/Nasdaq about 6.5 hours a day, weekdays.

Outside that window, nothing forces the tokenized price back to the real one. It still trades.

That gap is what Gloaming is built around.
```

```
2/9
Bitget calls these rTokens (AAPL, TSLA, SPY and more). Gloaming's agent runs only while NYSE is closed: it prices each rToken from what its real share last closed at, plus live futures, crypto and FX proxies since that close, and trades the resulting spread.
```

```
3/9
Qwen3.8-max makes the call, not a hardcoded formula: direction, size, stop, and a written reason for every decision. A separate, deterministic, non-LLM layer can reject or resize any of it - position caps, exposure caps, a daily breaker, no leverage.
```

```
4/9
We didn't just assume the thesis works. We backtested the exact live signal on real hourly data first: trading a spread of 0.5%+ against itself averaged -37.6bp after costs, only 44% of trades won. So Qwen is told that, and told its own trading costs, and mostly holds.
```

```
5/9
Two real bugs, found from our own public decision log and fixed in the open, not hidden: an early signal that mostly measured each session's own move (not a gap), and a data-provider gap that briefly anchored a weekend cycle to the wrong day's close.
```

```
6/9
Fees and slippage aren't an afterthought either: every fill is charged a stated 0.10% fee + 0.05% slippage, and every performance number on the Desk is shown net of what was actually charged.
```

```
7/9
Gloaming Desk is the companion piece: same live data, read-only. The book against its risk limits, a page per symbol, a decision inspector showing exactly what Qwen saw and why, a chat grounded only in real numbers, and a stress test against real historical nights.
```

```
8/9
It never places a trade - the human decides. Paper trading only: Bitget's demo environment doesn't list rToken symbols yet, so fills post to a self-maintained ledger marked to real, live rToken prices. Everything except "the exchange accepts the order" is real.
```

```
9/9
Live: https://gloamingdesk.vercel.app
Code: https://github.com/angelraph/gloaming

Built solo for Bitget's AI Base Camp Hackathon S2.

#BitgetHackathon @Bitget_AI
```

## What to attach to the main post

A short screen recording or GIF of the live dashboard (the risk meters, a page per symbol, the decision
inspector open on a real trade, the spread chart) is the clearest proof this is a real, working product.
15-30 seconds scrolling https://gloamingdesk.vercel.app covers it. You don't need the clip ready before
posting the text - you can post now and attach it later, or edit the post to add media.

## Before you submit

1. Resolve the deadline question above first (Telegram or @Bitget_AI) - don't wait if you can't confirm
   in a few minutes; the form is live now either way.
2. Open https://x.com/Bitget_AI/status/2100519318824055159 on X, tap **Quote** (not Retweet, not Reply),
   paste the post text above into your comment, attach the demo clip if you have it, and post.
3. Copy the URL of the post you just made.
4. Paste that URL into the Google Form's **"X Promotional Post Link"** field (and into "Submission
   Material Links" too, since the handbook lists it as a required deliverable there as well) - once per
   track/theme you submit (this project enters two: Agentic Trading and AI Trading Desk). Reuse the same
   X post for both submissions; it introduces the whole project.
5. Do this only once you're ready to submit for real - it becomes part of your official entry.
