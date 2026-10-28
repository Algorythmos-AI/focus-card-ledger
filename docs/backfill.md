# Rebuilt history (backfilled 28 Oct 2026)

The live ledger starts on 19 Oct 2026, the first published card. To get a longer record, the card was re-picked
for every session from 4 Mar to 16 Oct 2026 (158 sessions, 1,256 setups) and scored with the same scorer as the
live records. Each of these records carries:
- `card_source: "rebuilt"`
- `backfilled: true`
- a `rebuild` note listing the inputs it had.

They never feed the headline numbers in the README.

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

- **With the option-volume input:** all 8 rebuilt cards were identical to the published ones, with the same names, ranks, levels and targets.
- **Without it** (the case for every day before 12 Oct): 29 of the 32 names matched (91%). Every matched name had the same levels and bias, though ranks sometimes moved.
- **Levels for 12 Oct:** levels rebuilt from the daily file differ from the saved file by a few cents. The daily file was pulled during the 9 Oct session, so its last bar is not final. Sessions up to 9 Oct only use bars that were already final.

## Bars, by quality tier

| Tier | Sessions | Bars |
| --- | --- | --- |
| Published | 19–28 Oct | IBKR 2-min (22–28 Oct); Webull 1-min aggregated to 2-min (19–21 Oct) |
| Rebuilt, 2-min | 4 May – 16 Oct | Webull 1-min aggregated to 2-min, aligned to 09:30 ET (`tools/webull_bars.py`) |
| Rebuilt, 60-min | 4 Mar – 1 May | IBKR hourly (options-tab/bars_hourly_Mar-Oct2026_10names.json) |

Webull's OpenAPI keeps minute bars for 180 days, so 4 May is as far back as 2-minute bars go. Sam claimed the
free "Nasdaq Basic – Non Display" OpenAPI quote permission on 28 Oct 2026 to unlock them.

### Do Webull bars score the same as IBKR's?

`tools/source_check.py` (`reports/source_check.json`) re-scored the 40 published setups that have IBKR
2-minute bars, this time on Webull bars:

- **Same result** (trigger, fill, target or stop) on all 40.
- **R matched exactly on 38.** The other two differed by 0.01R and 0.03R.
- **2-minute closes** matched to a median of 0.03 basis points (95th percentile 1.5 bp, over 7,800 bars).

### What coarse bars got wrong

Before the Webull bars, the rebuilt history used 30- and 60-minute IBKR bars. Re-scoring the same rebuilt
setups on 2-minute bars gave:

| Setups first scored on | Setups | Filled (coarse → 2-min) | Stopped (coarse → 2-min) | Average R (coarse → 2-min) |
| --- | --- | --- | --- | --- |
| 30-min bars (14 Jul – 12 Oct) | 511 | 86 → 140 | 15 → 68 | +0.94R → +0.29R |
| 60-min bars (4 May – 13 Jul) | 382 | 60 → 114 | 7 → 57 | +1.04R → +0.29R |

Coarse bars hide the short closes through the stop, so they made the card look about three times better than it
was. **The 60-minute tier that remains (4 Mar – 1 May) is optimistic in the same way.** Read only its bias,
open and trigger facts, which come from the day's open, high, low and close. `reports/tier_check.json` shows the
same effect on the published days.

## What the history says (as of 28 Oct 2026)

These come from the 925 rebuilt setups with 2-minute bars, 4 May – 16 Oct. They are history, not proof: setups on
one day move together, so the real uncertainty is wider than the ranges shown.

- **Small positive edge on the stock, before costs.** Of 925 setups, 51% triggered and 267 filled.
  - Win rate: T1 was hit before the stop 43% of the time (95% range 37–49%), and 51% were stopped.
  - Average R: +0.25 on the card's exits, +0.22 with the 5-minute rule, +0.18 holding for T2. Profit factors were 1.39, 1.47 and 1.21.
  - At 2R targets, a 33% win rate breaks even, so 43% clears it. Option costs and the −25% option stop are not included.
- **T2 is rarely reached:** 5% of fills.
- **The bias is wrong more often than right.** It was right on 40% of name-days (95% range 36–44%). "Hold support" was right 37% of the time, "breakout watch" 44%.
- **The open settles most bias calls.** When the stock opened over the ceiling, breakout bias was right 74% of the time. When it opened under the floor, support bias was right 3%. Both are known at 09:30, before the first allowed entry at 09:35.
- **Card score and rank don't rank setups.** The information coefficient (how well the score orders the outcomes) is +0.05 for score against R and +0.04 for rank. On the live cards it is +0.23, from 21 trades.
- **Distance from the close decides whether a level is reached.** Levels under 0.5 ATR away triggered 57% of the time, 0.5–1 ATR away 26%, and more than 1 ATR away 6%.
- **By name:** NVDA and TSLA did best (+0.89R and +0.66R per fill). PLTR (+0.04R) and GOOGL (+0.18R) did worst.
- **By weekday:** Monday and Wednesday did best (+0.65R and +0.70R). Friday was near zero (+0.08R).

## Option prices before 28 Oct

These can't be recovered:
- **IBKR** drops an expiry from the option chain the day after it expires, so its contract ids can't be looked up later. On 28 Oct 2026 the oldest SPY expiry listed was 20261028.
- **Webull's OpenAPI** has no options data in Australia. Sam's app OPRA subscription doesn't carry over to the API, which still answers "subscribe to US_OPTION".

Option P&L (C) therefore starts on 28 Oct and grows each live day. The after-close job pulls the option bars the
same evening. On 28 Oct they were still there at 21:41 UTC, 1 h 40 m after the close.

## Reproduce

```
python tools/rebuild_cards.py --out /tmp/cards --check
for f in /tmp/cards/2026-*.json; do python -m ledger predict --card $f --backfilled; done
python tools/webull_bars.py --from 2026-05-04 --to 2026-10-21 --out /tmp/wb     # needs WEBULL_APP_KEY/SECRET
python -m ledger bars --name SPY --ibkr <file>     # IBKR hourly for 4 Mar - 1 May; finer complete copies win
python -m ledger score --all && python -m ledger scorecard
python tools/source_check.py --webull /tmp/wb && python tools/tier_check.py --m30 /tmp/m30
```
