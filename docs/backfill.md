# Rebuilt history (backfilled 28 Oct 2026)

The live ledger starts on 19 Oct 2026, the first published card. To get a longer record, the card was re-picked
for every session from 4 Mar to 16 Oct 2026 (158 sessions, 1,256 setups) and scored with the same scorer as
the live records. Each of these records carries `card_source: "rebuilt"`, `backfilled: true` and a `rebuild`
note listing the inputs it had. They never feed the headline numbers in the README.

## How the cards were rebuilt

`tools/rebuild_cards.py` calls the card's own code (`olib.levels_for` and `focus.pick` in the options-levels
skill), so nothing is re-typed:

| Sessions | Levels | Option volume input | Universe |
| --- | --- | --- | --- |
| 12–16 Oct | saved levels files | iv_history (real) | 10 names |
| 4 Mar – 9 Oct | rebuilt from IBKR daily bars, as run.py builds them | missing: 1.0x assumed | 10 names |

There was no pre-market snapshot for any rebuilt day, so every rebuilt setup has confidence `medium` and gap
`unknown`. AVGO and AMD joined the card on 27 Oct, so they are not in the history.

### How close is a rebuilt card to the real one?

`--check` re-picked the 8 sessions that have a published card (19–28 Oct):

- With the option-volume input, all 8 rebuilt cards were identical to the published ones: the same names, ranks, levels and targets.
- Without it, which is the case for every day before 12 Oct, 29 of the 32 names matched (91%). Every matched name had the same levels and bias, but ranks sometimes moved.
- One more check: the 2026-10-12 levels rebuilt from the daily file differ from the saved file by a few cents. The daily file was pulled during the 9 Oct session, so its last bar is not final. Sessions up to 9 Oct only use bars that were already final.

## Bars, by quality tier

IBKR keeps fine bars for a short time only, so the rebuilt days are scored on what was still available:

| Tier | Sessions | Bars |
| --- | --- | --- |
| Published | 19–28 Oct | 2-min (22–28 Oct), 5-min (19–21 Oct) |
| Rebuilt, 5-min | 13–16 Oct | IBKR 5-min |
| Rebuilt, 30-min | 14 Jul – 12 Oct | IBKR 30-min |
| Rebuilt, 60-min | 4 Mar – 13 Jul | IBKR hourly (options-tab/bars_hourly_Mar-Oct2026_10names.json) |

### What coarse bars get wrong

`tools/tier_check.py` scored the 60 published setups three ways: on their fine bars, on 30-minute bars and on
60-minute bars (`reports/tier_check.json`).

| Measure | Fine bars | 30-min | 60-min |
| --- | --- | --- | --- |
| Same result as fine | – | 46 of 60 | 41 of 60 |
| Filled | 20 | 12 | 10 |
| Stopped | 9 | 5 | 2 |
| Average R of the filled setups | +0.47R | +0.33R | +1.15R |

So on 30- and 60-minute bars, about half the retest fills are missed. Stops are missed even more often, because the stop is a close through the level and a long bar hides the short closes inside it. **Treat the stop rate, win rate and average R of the coarse tiers as optimistic.** Some facts don't depend on bar size, because they come from the day's open, high, low and close:

- whether the bias was right;
- where the stock opened;
- whether the level was crossed at all.

The trigger rate is a little low on coarse bars too, because a 30-minute close beyond the level is harder to get than a 2-minute one.

## What the history says (as of 28 Oct 2026)

These come from the 1,256 rebuilt setups. They are history, not proof: the setups on one day move together, so the real uncertainty is wider than the ranges shown.

- **Bias:** the card's bias was right on 40% of the name-days (95% range 37–43%, 616 name-days):
  - "Hold support" was right 37% of the time.
  - "Breakout watch" was right 44% of the time.
  - Live cards so far: 44% (14 of 32).
- **The open settles most bias calls.** When the stock opened over the ceiling, breakout bias was right 74% of the time. When it opened under the floor, support bias was right 4% of the time. That is close to true by definition, but it is known at 09:30, before the first allowed entry at 09:35.
- **Card score does not rank setups yet.** In the history, the information coefficient (how well the score orders the outcomes) is −0.12 for the card score against R, and −0.11 for rank. On the live cards it is +0.32, from 22 trades. More live days will settle which is right.
- **How far the level sits from the close:**
  - Levels under 0.5 ATR from the close triggered 51% of the time.
  - Levels 0.5–1 ATR away triggered 21% of the time.
  - Levels more than 1 ATR away triggered 6% of the time.
- **Results by name:** PLTR and TSLA had the weakest results per setup (+0.56R and +0.81R, coarse bars). AMZN, META and NVDA had the best (+1.3R to +1.4R). All of these are rough numbers.

## Option prices before 28 Oct

These can't be recovered. IBKR drops an expiry from the option chain the day after it expires. Its contract ids can't be looked up after that, so there are no option bars for the 0DTE contracts on rebuilt days. This was checked on 28 Oct 2026: the oldest SPY expiry listed was 20261028. Option P&L (C) therefore starts on 28 Oct and grows with each live day. The after-close job pulls the option bars the same evening, while the contracts can still be found.

## Reproduce

```
python -m ledger.transcript --since <ISO> --out /tmp/m30 --step THIRTY_MINS     # bars from the session transcript
python tools/rebuild_cards.py --out /tmp/cards --check
for f in /tmp/cards/2026-*.json; do python -m ledger predict --card $f --backfilled; done
python -m ledger bars --name SPY --ibkr <file>        # hourly, then 30-min, then 5-min: the finer complete copy wins
python -m ledger score --all && python -m ledger scorecard
python tools/tier_check.py --m30 /tmp/m30
```
