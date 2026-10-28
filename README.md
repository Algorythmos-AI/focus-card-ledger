# Focus card ledger

What the Top 4 Focus Card on lab.algorythmos.com/options predicted, and what the market actually did.

Every trading day:

1. **Before the open**, each card setup (4 names × call and put) is written to `predictions/` and committed. That commit is the proof the card was not changed after the fact. Predictions are never edited.
2. **After the close**, the setups are scored against IBKR 2-minute regular-hours bars. Results go to `outcomes/`, and the bars go to `bars/` with their hash.
3. **Option check (C).** For every filled setup, the option the card's size rule would pick is priced on its own 2-minute bars and written to `options/`. That option is the nearest out-of-the-money strike at $2.00 or less.
4. **Rebuild.** `scorecard.json`, `data/setups.csv`, the daily pages in `reports/daily/` and the table below are rebuilt from those files. A weekly report goes to `reports/weekly/`.

Research only. Nothing here places or suggests orders.

## Scorecard

R is measured on the stock, from entry to stop, before option costs. Each rate shows its 95% range. Sessions before 29 Oct 2026 were backfilled after the fact (`backfilled: true`), so they are not proof of a pre-open record. 19-21 Oct use 5-minute bars because IBKR no longer had 2-minute bars for them.

<!-- scorecard:start -->
Last scored session: **2026-10-28** · 8 sessions in the ledger.

### All setups

| Measure | Result |
| --- | --- |
| Setups published | 64 |
| Triggered | 56% (36/64; 95% 44–68%) |
| Filled after the retest | 61% (22/36; 95% 45–75%) |
| Hit T1 before the stop | 55% (12/22; 95% 35–73%) |
| Stopped | 41% (9/22; 95% 23–61%) |
| Reached T2 | 0% (0/22; 95% 0–15%) |
| Average R, card exits | +0.61R |
| Average R, 5-minute rule | +0.38R |
| Average R, hold for T2 | +1.00R |
| Total R (card / 5-min / T2) | +13.36R / +8.32R / +22.08R |
| Option P&L, 1 contract (card / 5-min / T2) | -$87 / -$133 / -$164 over 5 trades |
| Average best / worst move | +1.76R / -1.13R |
| Median minutes to T1 | 18 |
| Bias read right | 44% (14/32; 95% 28–61%) |

### Last 20 sessions

| Measure | Result |
| --- | --- |
| Setups published | 64 |
| Triggered | 56% (36/64; 95% 44–68%) |
| Filled after the retest | 61% (22/36; 95% 45–75%) |
| Hit T1 before the stop | 55% (12/22; 95% 35–73%) |
| Stopped | 41% (9/22; 95% 23–61%) |
| Reached T2 | 0% (0/22; 95% 0–15%) |
| Average R, card exits | +0.61R |
| Average R, 5-minute rule | +0.38R |
| Average R, hold for T2 | +1.00R |
| Total R (card / 5-min / T2) | +13.36R / +8.32R / +22.08R |
| Option P&L, 1 contract (card / 5-min / T2) | -$87 / -$133 / -$164 over 5 trades |
| Average best / worst move | +1.76R / -1.13R |
| Median minutes to T1 | 18 |
| Bias read right | 44% (14/32; 95% 28–61%) |

### 2026-10-28

| Setup | Level → entry / stop / T1 / T2 | Result | R card | R 5-min | Option $ |
| --- | --- | --- | --- | --- | --- |
| AVGO call (#1, support) | 345.67 → 345.79 / 344.49 / 348.39 / 354.48 | target1 | +2.00R | +2.00R | -$45 |
| AVGO put (#1, support) | 341.1 → 340.98 / 342.28 / 338.38 / 323.25 | no trigger | – | – | – |
| AMD call (#2, support) | 563.92 → 564.22 / 560.95 / 570.76 / 581.03 | target1 | +2.00R | -0.31R | -$37 |
| AMD put (#2, support) | 556.79 → 556.49 / 559.76 / 549.95 / 538.5 | no trigger | – | – | – |
| NVDA call (#3, breakout) | 219.19 → 219.25 / 218.57 / 220.61 / 224.44 | stopped | -1.10R | -0.47R | -$26 |
| NVDA put (#3, breakout) | 215.53 → 215.47 / 216.15 / 214.11 / 210.18 | session close | +0.16R | +0.16R | -$14 |
| SPY call (#4, breakout) | 770.41 → 770.48 / 769.68 / 772.08 / 774.44 | target1 | +2.00R | -0.08R | +$35 |
| SPY put (#4, breakout) | 767.53 → 767.46 / 768.26 / 765.86 / 761.63 | no trigger | – | – | – |

<!-- scorecard:end -->

## How a setup is scored (scorer 1.0)

- **Trigger:** a 2-minute close beyond the card's level.
- **Fill:** a later bar touches the entry and closes back on the trade side of the level. This is the card's "then a dip holds it" or "then a bounce fails under it". It must happen outside the no-entry windows, stored in New York time so clock changes don't move them: 09:30-09:35 and 11:30-13:00 ET. That is before 00:35 and 02:30-04:00 Sydney while both cities are on daylight time. A close through the stop before any valid retest kills the setup.
- **Stop:** a 2-minute close through the stop. **Targets:** the bar's high or low reaches them.
- **Same-bar conflict:** if one bar both reaches T1 and closes through the stop, it is flagged and scored as a stop.
- **Exit rules, all three scored:**
    - `card`: T1, the stop, or the session close.
    - `five_min`: the card rules, but out at about 5 minutes if the trade isn't in profit.
    - `hold_t2`: T2, the stop, or the session close.
- **Option P&L (C):**
    - **Entry:** the option's 2-minute close at the stock fill bar.
    - **Exit:** the earlier of the −25% option stop and the stock exit.
    - **Basis:** IBKR last-trade bars, with no spread, slippage or fees.
- **Bias:** "hold support" is right if the day's low stayed above the floor. "Breakout watch" is right if the session closed above the ceiling.
- **Confidence (v1):** set before the open from pre-market. A setup is **high** when the pre-market already leans its way, **low** when the pre-market gaps against it, and **medium** otherwise.

## Layout

```
predictions/YYYY/DATE.jsonl     before the open, append-only
outcomes/YYYY/DATE.jsonl        after the close, linked by id + prediction sha256
options/YYYY/DATE.jsonl         option result per filled setup
bars/YYYY/DATE/SYMBOL.json      the bars each outcome was scored on
scorecard.json, data/setups.csv derived; rebuilt by `python -m ledger scorecard`
reports/daily, reports/weekly   readable pages
schema/                         required fields per record type
```

## Commands

```
python -m ledger predict --card options-tab/data/focus/2026-10-29.json
python -m ledger bars --name SPY --ibkr spy_2min.json
python -m ledger score --session 2026-10-29
python -m ledger options --session 2026-10-29 --manifest options_manifest.json
python -m ledger scorecard
python -m ledger report --week 2026-W44
python -m ledger validate origin/main
python -m unittest discover tests
```
