# Broad-universe audit

The previous broad comparison is useful as a diagnostic, but several details
make it unsuitable as a competition result without correction.

## Findings

1. **The symbol screen removes real crypto assets.**
   `scripts/download_broad_universe.py` excludes every Binance base asset whose
   name ends in `B` (`not baseAsset.endswith('B')`). This is a ticker-shape
   rule, not an instrument-type check. It removes legitimate assets including
   BNB, ARB and SHIB. The broad screen also applies the same kind of inference
   to leveraged suffixes. A stock classification should come from instrument
   metadata.

2. **Stablecoin screening was incomplete.**
   The hard-coded list omitted BFUSD and XUSD, both present in the downloaded
   broad cache. The corrected pool excludes those two by explicit symbol
   allowlist. No substring or suffix matching is used.

3. **The historical universe was selected with current information.**
   The screen ranks currently `TRADING` Binance USDT symbols by the current
   24-hour quote volume. `screen.json` records no timestamp for that ranking;
   `download.json` is written after the downloads. Therefore a replay from
   2025-10-01 uses post-period listing status and volume information. Requiring
   complete coverage then removes newer or failed listings, creating
   survivorship bias. The manifest notes this, but the return comparison still
   needs to be read as a selected-universe study.

4. **The broad and 50-asset returns are on different periods.**
   The broad study has 8,760 hourly timestamps from 2025-10-01 through
   2026-10-01. Its first block begins after a 720-hour warm-up (2025-10-31),
   blocks b1–b4 end on 2026-06-28, and the reported tail is 95 days. The
   50-asset replay starts in May 2025 and its later evaluation begins around
   2026-06-19. A tail return such as +14.24% for broad momentum therefore is
   not a like-for-like comparison with the 50-asset +2.63% result.

5. **Most broad symbols have no Roostoo instrument metadata.**
   Of the 215 bars in `data/binance-broad-1h.csv`, only 55 pair names match the
   cached Roostoo `TradePairs` metadata; 160 are Binance-only from the
   competition adapter's perspective. `scripts/broad_universe_study.py`
   assigns every unknown pair a generic 8-decimal, $1 minimum `PairRule` with
   `CanTrade=True`. This makes the simulation executable, but it does not
   establish that those assets can be traded on Roostoo or that their lot
   sizes, minimums and liquidity resemble the model. It can understate order
   rejection and implementation costs.

6. **The assembled broad manifest has an asset-name error.**
   `scripts/assemble_broad_universe.py` writes manifest entries such as
   `AAVEUSDT/USD`, while the CSV rows and `read_csv` pair names are
   `AAVE/USD`. The error does not change the bars used by the study, but it can
   silently break later metadata joins and makes the recorded universe
   unreliable.

## Corrected discovery pool

`scripts/assemble_regime_pool.py` creates
`data/regime-discovery-1h.csv` from the existing caches without downloading or
modifying either source. It unions the broad and cached full-history files,
prefers `data/binance-all` on duplicate symbols, and requires every asset to
have all 8,760 candles from 2025-10-01 00:00 UTC through 2026-10-01 00:00 UTC.

The result contains **222 assets and 1,944,720 rows**. BNB, ARB and SHIB are
present. The manifest records SHA-256 hashes and exact source paths for every
included and excluded file. Exclusions are:

- 21 symbols whose Roostoo metadata says `AssetType: stock`;
- 2 explicit stable assets, BFUSD and XUSD;
- 1 incomplete requested-window history, ASTER.

Unknown symbols are retained as discovery candidates and marked as missing
Roostoo metadata. They must be intersected with current tradable pairs before
any live or competition deployment. The pool still inherits the original
cache screens' current-listing and current-volume survivorship bias; the
correction removes ticker-name bias and records the limitation instead of
claiming an unbiased historical universe.

The corrected pool has not been used to select a final strategy in this audit.
Its purpose is to provide a reproducible, correctly typed input for the next
regime and low-turnover study.
