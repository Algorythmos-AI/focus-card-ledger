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

The headline tables use only cards that were really published (from 19 Oct). The rebuilt history (4 Mar – 16 Oct) sits in its own tables, split by bar size; how it was rebuilt and how far to trust it is in [docs/backfill.md](docs/backfill.md).

<!-- scorecard:start -->
Last scored session: **2026-10-28** · 8 sessions of published cards · 158 sessions of rebuilt history.

### Published cards

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

### Last 20 published sessions

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

### Rebuilt history, by bar size

Cards re-picked from saved data with the card's own code (`tools/rebuild_cards.py`). Coarse bars miss many retest fills, so read fill and R numbers here as rough; the bias, trigger and day-range facts hold on any bar size. `reports/tier_check.json` measures the gap.

| Measure | Published cards (19 Oct – 28 Oct) | Rebuilt, 5-min bars (13 Oct – 16 Oct) | Rebuilt, 30-min bars (14 Jul – 12 Oct) | Rebuilt, 60-min bars (4 Mar – 13 Jul) |
| --- | --- | --- | --- | --- |
| Setups published | 64 | 32 | 511 | 713 |
| Triggered | 56% (36/64; 95% 44–68%) | 56% (18/32; 95% 39–72%) | 42% (217/511; 95% 38–47%) | 44% (313/713; 95% 40–48%) |
| Filled after the retest | 61% (22/36; 95% 45–75%) | 50% (9/18; 95% 29–71%) | 40% (86/217; 95% 33–46%) | 31% (97/313; 95% 26–36%) |
| Hit T1 before the stop | 55% (12/22; 95% 35–73%) | 44% (4/9; 95% 19–73%) | 57% (49/86; 95% 46–67%) | 65% (63/97; 95% 55–74%) |
| Stopped | 41% (9/22; 95% 23–61%) | 56% (5/9; 95% 27–81%) | 17% (15/86; 95% 11–27%) | 12% (12/97; 95% 7–20%) |
| Reached T2 | 0% (0/22; 95% 0–15%) | 22% (2/9; 95% 6–55%) | 5% (4/86; 95% 2–11%) | 2% (2/97; 95% 1–7%) |
| Average R, card exits | +0.61R | +0.22R | +0.94R | +1.11R |
| Average R, 5-minute rule | +0.38R | +0.22R | – | – |
| Average R, hold for T2 | +1.00R | +0.39R | +0.49R | +0.75R |
| Total R (card / 5-min / T2) | +13.36R / +8.32R / +22.08R | +1.95R / +1.95R / +3.54R | +80.42R / – / +41.86R | +107.25R / – / +72.75R |
| Option P&L, 1 contract (card / 5-min / T2) | -$87 / -$133 / -$164 over 5 trades | – / – / – over 0 trades | – / – / – over 0 trades | – / – / – over 0 trades |
| Average best / worst move | +1.76R / -1.13R | +1.95R / -0.97R | +2.30R / -0.84R | +2.42R / -0.97R |
| Median minutes to T1 | 18 | 2 | – | – |
| Bias read right | 44% (14/32; 95% 28–61%) | 19% (3/16; 95% 7–43%) | 44% (110/250; 95% 38–50%) | 38% (132/349; 95% 33–43%) |

Card score vs R (information coefficient), rebuilt history: -0.122; rank vs R: -0.111.

#### Rebuilt history by bias

| Group | Setups | Bias read right | Triggered | Hit T1 before the stop | Average R, card |
| --- | --- | --- | --- | --- | --- |
| breakout | 522 | 44% (115/261; 95% 38–50%) | 45% (234/522; 95% 41–49%) | 63% (47/75; 95% 51–73%) | +0.93R |
| range | 19 | – | 21% (4/19; 95% 8–43%) | 100% (2/2; 95% 34–100%) | +2.00R |
| support | 715 | 37% (130/354; 95% 32–42%) | 43% (310/715; 95% 40–47%) | 58% (67/115; 95% 49–67%) | +1.01R |

#### Rebuilt history by where the stock opened

| Group | Setups | Bias read right | Triggered | Hit T1 before the stop | Average R, card |
| --- | --- | --- | --- | --- | --- |
| Opened between floor and ceiling | 717 | 37% (130/350; 95% 32–42%) | 38% (274/717; 95% 35–42%) | 56% (66/118; 95% 47–65%) | +0.86R |
| Opened over the ceiling | 310 | 74% (111/151; 95% 66–80%) | 49% (153/310; 95% 44–55%) | 63% (26/41; 95% 48–76%) | +1.01R |
| Opened under the floor | 229 | 4% (4/114; 95% 1–9%) | 53% (121/229; 95% 46–59%) | 73% (24/33; 95% 56–85%) | +1.40R |

#### Rebuilt history by card rank

| Group | Setups | Bias read right | Triggered | Hit T1 before the stop | Average R, card |
| --- | --- | --- | --- | --- | --- |
| 1 | 316 | 38% (60/158; 95% 31–46%) | 43% (137/316; 95% 38–49%) | 48% (20/42; 95% 33–62%) | +0.83R |
| 2 | 316 | 42% (66/156; 95% 35–50%) | 45% (142/316; 95% 40–50%) | 54% (32/59; 95% 42–66%) | +0.81R |
| 3 | 315 | 37% (57/154; 95% 30–45%) | 41% (128/315; 95% 35–46%) | 81% (35/43; 95% 67–90%) | +1.51R |
| 4 | 309 | 42% (62/147; 95% 34–50%) | 46% (141/309; 95% 40–51%) | 60% (29/48; 95% 46–73%) | +0.88R |

#### Rebuilt history by how far the level was from the close

| Group | Setups | Bias read right | Triggered | Hit T1 before the stop | Average R, card |
| --- | --- | --- | --- | --- | --- |
| 0.5-1 ATR | 226 | 38% (82/216; 95% 32–45%) | 21% (47/226; 95% 16–27%) | 68% (13/19; 95% 46–85%) | +1.07R |
| <0.5 ATR | 983 | 40% (242/611; 95% 36–44%) | 51% (498/983; 95% 48–54%) | 59% (102/172; 95% 52–66%) | +0.97R |
| >1 ATR | 47 | 55% (21/38; 95% 40–70%) | 6% (3/47; 95% 2–17%) | 100% (1/1; 95% 21–100%) | +2.00R |

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

## How a setup is scored (scorer 1.1)

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
tools/                          rebuild_cards.py (past cards), tier_check.py (coarse-bar error bar)
docs/backfill.md                how the rebuilt history was made and how far to trust it
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
