# X promotional post draft

Requirements confirmed from the handbook: must include `#BitgetHackathon` and
`@Bitget_AI`, must genuinely introduce the project (a bare retweet is invalid),
and must retweet Bitget's official hackathon post - **that official post link
is still marked TBD in the handbook as of this draft**. Check the hackathon
Telegram (https://t.me/+o1tYqQ_lXxllYjgy) or the activity hub closer to
submission for the actual link to retweet; I can't fill that in for you since
it doesn't exist publicly yet.

## The post (one single post, hook + what it does + proof + tags, all in one)

Character count verified with a script rather than eyeballed. X counts any
link as a fixed 23 characters no matter how long the real URL is (its t.co
link-wrapping rule), so the real character budget here is 258 out of 280,
22 to spare:

```
Tokenized US stocks trade 24/7. The real market doesn't.

Gloaming prices rTokens overnight from live futures, crypto and FX signals with Qwen3.8-max, under hard risk controls, then trades that gap.

Live: https://gloamingdesk.vercel.app

#BitgetHackathon @Bitget_AI
```

This replaces the old two-post version (a text-only post plus a separate
reply carrying the link). One post now carries everything: the hook, what
Gloaming actually does, the tech (Qwen3.8-max, real risk controls), a live
link a reader can click immediately, and the required hashtag/tag. Nobody
has to open a reply to find the proof it's real.

## Optional follow-up reply (only if you want a second post with more depth)

```
Qwen3.8-max is the real decision-maker here, not a chatbot bolted on after
the fact - 95 of the last 107 logged decisions came directly from it, each
with its own written reasoning you can read in the live timeline.

Code: https://github.com/angelraph/gloaming
```

## Long-form explainer thread (for pairing with the demo video)

Use the short post above (the one that ships with the video) as the intro
post, then post this as a 10-post reply thread underneath it for anyone who
wants the full explanation. Each post below is individually verified under
280 characters as X counts them (any link counts as a flat 23 characters).

```
1/10
Tokenized US stocks trade 24/7. The real shares they track only trade on NYSE/Nasdaq about 6.5 hours a day, weekdays only.

Outside that window, nothing forces the tokenized price back to the real price. It still trades though.

That gap is what Gloaming is built around.
```

```
2/10
Bitget calls these tokenized shares rTokens (AAPL, TSLA, SPY and more, 1:1 backed via Reality Protocol). They trade nights, weekends, holidays. NYSE does not.

Every closed hour, an rToken can quietly drift from what the real stock is worth, unwatched.
```

```
3/10
Gloaming Agent runs only during those closed hours. It builds a synthetic fair value per rToken from signals that stay live overnight: an index-futures proxy, BTC/ETH crypto sentiment, and FX risk sentiment.

Then it compares that to the rToken's real onchain price.
```

```
4/10
The reasoning is done by Qwen3.8-max, not a hardcoded formula. It reads the live spread and proxy data, decides direction, size, stop-loss, and writes its own rationale for every single decision. Logged, readable, never hidden.
```

```
5/10
Qwen is never the last word. A separate, deterministic, non-LLM module can reject or resize any decision it makes: position caps, circuit breakers, volatility-scaled sizing, no leverage, ever.

Every logged decision records exactly which path actually produced it.
```

```
6/10
Honest technical note: Bitget's demo trading doesn't support rToken symbols yet, confirmed live. Fills post to a self-maintained paper ledger marked to real live rToken prices.

Only "the exchange accepts the order" is simulated. Everything else is real.
```

```
7/10
Gloaming Desk is the companion piece: a read-only dashboard over that same live data. A fair-value-vs-actual chart, a full overnight timeline, a chat panel grounded only in real data, never invented numbers.

It never places a trade. The human makes the final call.
```

```
8/10
It also has a decision stress test: replay a real historical overnight move against the current book and see the hypothetical outcome before anything happens for real.
```

```
9/10
Backtest on 84 real days across a 9-symbol rToken universe: Sharpe 2.09, Sortino 2.29, max drawdown -3.51%, win rate 57%. The live paper log is younger and still growing, disclosed exactly that way, nothing dressed up.
```

```
10/10
Live: https://gloamingdesk.vercel.app
Code: https://github.com/angelraph/gloaming

Built solo for Bitget's AI and Crypto Hackathon, Genesis Season 2.

#BitgetHackathon @Bitget_AI
```

## What to attach to the main post

A short screen recording or GIF of the live dashboard (the fair-value chart,
the overnight timeline with real Qwen rationale text, and the chat panel
answering a real question) does the most work here - it's the "interactive"
element and the clearest way to show this is a real, working product rather
than a screenshot of a mockup. A 15-30 second clip scrolling through
https://gloamingdesk.vercel.app covers it. Attach it directly to the post
above; you do not need to wait for it to exist before posting the text if
you'd rather post now and come back to attach the clip later.

## Before you post

1. Post the text above as your own genuine introduction, not just a retweet
   with no text - the handbook explicitly flags bare retweets as invalid
2. Attach the demo clip (or post now, edit/attach later)
3. Separately, find and retweet the actual official Bitget hackathon post
   (link still TBD in the handbook - check Telegram/activity hub). This is
   a second, separate action from step 1, not something the text post above
   replaces.
