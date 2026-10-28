# Daily runbook (run by the scheduled tasks)

Research only. Never place, preview, modify or stage orders. Use only IBKR market-data tools:
`get_price_history`, `get_option_parameters`, `get_option_data`.

Setup each time: if `/home/user/focus-card-ledger` is missing, clone `Algorythmos-AI/focus-card-ledger` there.
`git pull` first. Symbol -> IBKR contract id: `ledger/contracts.json`. The card for a session is
`/mnt/project-files/options-tab/data/focus/<session>.json` (session = today's New York date).

## Before the open (09:05-09:29 New York)

1. No card file for today, or `premarket.as_of` not today: stop quietly (holiday or card not built).
2. `python -m ledger predict --card <card>` (exit 3 = the card changed after an earlier record: keep the first, report it).
3. `python -m ledger validate`, then commit `predictions/` as "predictions <session>" and push to main before 09:30 ET.
   A push after 09:30 ET breaks the pre-open proof: report it.

## After the close (16:20 New York, while today's 0DTE option bars still exist)

1. No predictions file for today: stop quietly.
2. For each card symbol: `get_price_history(contract_id, security_type="STK", step="TWO_MINS", period="ONE_DAY", outside_rth=false)`.
3. `python -m ledger.transcript --since <time this firing started, UTC> --out /tmp/ibkr`, then for each symbol
   `python -m ledger bars --name <SYMBOL> --ibkr /tmp/ibkr/<contract_id>.json --session <session>`.
4. `python -m ledger score --session <session>`.
5. Options (C), for each outcome with `filled: true`:
   - `get_option_parameters(contract_id)`: take the first expiration on or after the session with the plain trading
     class (not `2XXX`).
   - `get_option_data(expiration_id, min_strike, max_strike)`: strikes from the stock entry outward about 4% in the
     trade direction (calls above, puts below).
   - Walk out from the first out-of-the-money strike: `get_price_history(<numeric id>, security_type="OPT",
     exchange="SMART", step="TWO_MINS", period="ONE_DAY", outside_rth=false)` until the close at the fill bar is
     <= 2.00 (max 6 strikes).
   - Re-run step 3's extractor, then `python -m ledger bars --name <SYM>_<strike><C|P> --ibkr ... --kind OPT --session <session>`
     for each pulled contract, and write `manifests/options/<session>.json`
     (`{"<id>": {"expiry": "YYYYMMDD", "chain": {"<strike>": {"name": "...", "description": "..."}}}}`).
   - `python -m ledger options --session <session> --manifest manifests/options/<session>.json`.
6. `python -m ledger scorecard`; on Fridays also `python -m ledger report --week <ISO week, e.g. 2026-W44>`.
7. `python -m unittest discover tests` and `python -m ledger validate`, then commit everything as
   "outcomes <session>" and push to main.
