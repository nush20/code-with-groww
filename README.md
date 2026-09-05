## Why MarketMemo?

Most watchlists optimize for showing more information: prices, percentage changes,
news, alerts, charts, and indicators.

MarketMemo asks a different question:

> **What happened while I was away that I can no longer understand from the current price?**

Consider:

₹100 → ₹102 → ₹106 → ₹110 → ₹105 → ₹101

A user who checks only the endpoints sees a **+1% move**.

But during that period, the stock:
- moved 10% from the user's checkpoint,
- crossed a price level they cared about,
- and gave back most of the move before they returned.

That information has disappeared from the current snapshot.

MarketMemo calls this a **Hidden Journey**.

Instead of treating a watchlist as a collection of current prices, MarketMemo treats
it as a timeline.

## The Product

### 1. Watchlist — Where is it now?

A persistent personal watchlist for NSE equities with:

- latest available price and daily change
- high, low, and previous close
- market-data freshness
- personal price and percentage watch levels

### 2. Market Recap — What happened today?

Market Recap reconstructs the latest trading session across the user's watchlist.

Instead of showing only closing returns, it surfaces:

- the day's price journey
- largest meaningful movements
- reversals and recoveries
- watchlist-wide activity
- relevant company developments published that day

Company developments are shown as context, **not as claimed causes of price movement**.

### 3. Catch-Up — What happened while I was away?

Catch-Up starts from the last checkpoint the user explicitly acknowledged.

It looks for information that may have disappeared from the current snapshot:

**Hidden Journey**  
A meaningful move occurred but substantially reversed before the user returned.

**Personal Watch Level**  
A level the user cared about was crossed, even if the price later moved back.

**Unusual Movement**  
The excursion was unusually large relative to the stock's own historical movement.

Opening or refreshing MarketMemo never moves the checkpoint. Only **Mark caught up**
does.

### 4. Stock Detail — Show me the evidence

For 1D, 1W, 2W, and 1M periods, Stock Detail exposes the underlying journey:

- historical chart
- deterministic summary
- period high and low
- return and reversal/recovery
- important moments
- personal watch-level controls

  ## The Product

### 1. Watchlist — Where is it now?

A persistent personal watchlist for NSE equities with:

- latest available price and daily change
- high, low, and previous close
- market-data freshness
- personal price and percentage watch levels

### 2. Market Recap — What happened today?

Market Recap reconstructs the latest trading session across the user's watchlist.

Instead of showing only closing returns, it surfaces:

- the day's price journey
- largest meaningful movements
- reversals and recoveries
- watchlist-wide activity
- relevant company developments published that day

Company developments are shown as context, **not as claimed causes of price movement**.

### 3. Catch-Up — What happened while I was away?

Catch-Up starts from the last checkpoint the user explicitly acknowledged.

It looks for information that may have disappeared from the current snapshot:

**Hidden Journey**  
A meaningful move occurred but substantially reversed before the user returned.

**Personal Watch Level**  
A level the user cared about was crossed, even if the price later moved back.

**Unusual Movement**  
The excursion was unusually large relative to the stock's own historical movement.

Opening or refreshing MarketMemo never moves the checkpoint. Only **Mark caught up**
does.

### 4. Stock Detail — Show me the evidence

For 1D, 1W, 2W, and 1M periods, Stock Detail exposes the underlying journey:

- historical chart
- deterministic summary
- period high and low
- return and reversal/recovery
- important moments
- personal watch-level controls

## Deterministic by Design

MarketMemo does **not** ask an LLM to decide what happened in the market.

The core pipeline is:

Upstox market data
→ normalized candles
→ deterministic calculations
→ meaningful-change detectors
→ structured verified facts
→ user-facing explanation

Gemini is optional and sits only at the final wording layer.

It cannot:
- calculate returns or reversals
- decide whether an event is meaningful
- infer why a stock moved
- predict prices
- recommend trades

If Gemini is unavailable or produces unsupported output, MarketMemo falls back to
deterministic templates.

**AI explains verified facts; it does not create them.**

## Key Engineering Decisions

### Baselines move only when the user says so
Page refreshes and logins never silently reset Catch-Up state. The user explicitly
controls the checkpoint with **Mark caught up**.

### Market state is shared; meaning is personalized
Price history for RELIANCE is the same regardless of who watches it.

Market observations can therefore be fetched and cached at the instrument level,
while only genuinely personal state is stored per user:

- watchlist membership
- watch levels
- Catch-Up checkpoint

This avoids recomputing identical market state for every user.

### Fail partially, not completely
A failed quote, news request, or optional summary should not make the entire watchlist
unusable.

### Stale data stays visibly stale
MarketMemo keeps provider timestamps and distinguishes market observation time from
the time the application received the response.

### Context is not causality
A company development occurring during a price movement can be useful context.
MarketMemo does not claim it caused the movement unless that relationship is explicitly
established by a trusted source.

## Reproducible Historical Replay

Live markets are not guaranteed to produce an interesting event during a demo.

MarketMemo therefore includes an isolated historical replay built from snapshotted
real Upstox inputs.

The replay stores **inputs, not conclusions**:

- historical OHLC candles
- historical volatility data
- available company-development metadata
- replayed checkpoint/watch-level state

Those inputs pass through the **same production analysis pipeline** as live Catch-Up.

No excursion percentage, reversal percentage, unusualness score, or detector result
is hard-coded.

The replay never modifies the user's real watchlist, watch levels, or Catch-Up
checkpoint.

**HISTORICAL REPLAY · REAL MARKET DATA**
