#!/usr/bin/env python3
"""Assemble a corrected, provenance-preserving Binance research pool.

The two cache directories were produced by different discovery jobs.  This
script unions their per-symbol histories, prefers the longer ``binance-all``
file when both caches contain a symbol, and keeps only candles covering the
requested common one-year window.  It deliberately does not infer an asset's
type from its ticker spelling (for example, a trailing ``B``); stock symbols
are excluded only when the supplied Roostoo metadata labels them as stock.
"""
import argparse
import csv
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from roostoo.data import Bar, validate_bars, write_csv


HOUR = 3_600_000
DEFAULT_START = "2025-10-01"
DEFAULT_END = "2026-10-01"
# Explicit quote-like assets which are not useful for a long-only crypto
# discovery pool.  This is an allowlisted set; no suffix or substring rule is
# applied.  BFUSD/XUSD are included because they are explicit Binance USD
# stable assets present in the cached files.
EXPLICIT_STABLES = {
    "USDT", "USDC", "FDUSD", "TUSD", "USDP", "DAI", "BUSD", "USD1",
    "EUR", "TRY", "BRL", "BFUSD", "XUSD",
}


def epoch(day):
    return int(datetime.fromisoformat(day).replace(tzinfo=timezone.utc).timestamp() * 1000)


def digest(path):
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def load_window(path, start, end):
    """Return bars for exactly [start, end), or None when coverage is partial."""
    expected = list(range(start, end, HOUR))
    rows = []
    with path.open(newline="") as f:
        for row in csv.DictReader(f):
            ts = int(row["timestamp"])
            if start <= ts < end:
                rows.append(Bar(ts, row["pair"], *(float(row[k]) for k in ("open", "high", "low", "close")),
                                float(row.get("volume") or 0)))
    rows.sort(key=lambda b: b.timestamp)
    if len(rows) != len(expected) or [b.timestamp for b in rows] != expected:
        return None
    return rows


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--broad", default="data/binance-broad-all")
    p.add_argument("--cached", default="data/binance-all")
    p.add_argument("--roostoo", default="data/binance-all/roostoo-exchange.json")
    p.add_argument("--start", default=DEFAULT_START)
    p.add_argument("--end", default=DEFAULT_END)
    p.add_argument("--output", default="data/regime-discovery-1h.csv")
    a = p.parse_args()
    start, end = epoch(a.start), epoch(a.end)
    if end <= start or (end - start) % HOUR:
        raise SystemExit("start/end must define complete hourly candles")

    # Prefer the cached full-history directory when a symbol is present in
    # both.  The broad cache remains a deterministic fallback.
    paths = {}
    source_dirs = [("binance-all", Path(a.cached)), ("binance-broad-all", Path(a.broad))]
    for source_name, directory in source_dirs:
        for path in sorted(directory.glob("*USDT.csv")):
            symbol = path.name[:-4]  # strip .csv
            pair = symbol[:-4] + "/USD" if symbol.endswith("USDT") else None
            if pair and pair not in paths:
                paths[pair] = (source_name, path)

    roostoo = json.loads(Path(a.roostoo).read_text()).get("TradePairs", {})
    included, excluded, series, records = [], [], {}, []
    for pair in sorted(paths):
        source_name, path = paths[pair]
        base = pair[:-4]
        record = {
            "pair": pair, "base_asset": base, "source_cache": source_name,
            "source_file": str(path), "source_sha256": digest(path),
            "roostoo_metadata": bool(pair in roostoo),
            "roostoo_asset_type": roostoo.get(pair, {}).get("AssetType"),
            "roostoo_can_trade": roostoo.get(pair, {}).get("CanTrade"),
        }
        reason = None
        if base in EXPLICIT_STABLES:
            reason = "explicit_stable_asset"
        elif roostoo.get(pair, {}).get("AssetType") == "stock":
            reason = "roostoo_metadata_asset_type_stock"
        if reason:
            record["reason"] = reason
            excluded.append(record)
            continue
        rows = load_window(path, start, end)
        if rows is None:
            record["reason"] = "incomplete_requested_window"
            excluded.append(record)
            continue
        # Validate each selected source before combining it.  This catches a
        # malformed cache while preserving the originals for inspection.
        validate_bars(rows)
        series[pair] = rows
        record["rows_in_window"] = len(rows)
        included.append(pair)
        records.append(record)

    if len(series) < 2:
        raise SystemExit("fewer than two complete assets remain")
    joined = [bar for pair in sorted(series) for bar in series[pair]]
    joined.sort(key=lambda b: (b.timestamp, b.pair))
    interval = validate_bars(joined)
    manifest = {
        "source": "Binance public spot OHLCV caches; USDT mapped to USD",
        "synthetic": False,
        "selection": "Union of existing binance-all and binance-broad-all per-symbol caches; binance-all preferred on duplicate symbols; exact one-year hourly coverage required.",
        "requested_start": a.start, "requested_end_exclusive": a.end,
        "common_start_ms": start, "common_end_exclusive_ms": end,
        "common_candles_per_asset": (end - start) // HOUR,
        "asset_count": len(series), "universe": sorted(included),
        "source_files": records,
        "excluded_files": excluded,
        "excluded_counts": {
            "explicit_stable_asset": sum(x.get("reason") == "explicit_stable_asset" for x in excluded),
            "roostoo_metadata_asset_type_stock": sum(x.get("reason") == "roostoo_metadata_asset_type_stock" for x in excluded),
            "incomplete_requested_window": sum(x.get("reason") == "incomplete_requested_window" for x in excluded),
        },
        "roostoo_metadata_file": str(Path(a.roostoo)),
        "stable_asset_allowlist": sorted(EXPLICIT_STABLES),
        "type_filter": "Only Roostoo TradePairs.AssetType == stock is excluded; symbols ending in B or other ticker spelling are retained.",
        "quote_mapping": "Binance USDT mapped to USD; historical Roostoo spreads/depth unavailable",
        "bias_notes": [
            "The cache contents were selected by earlier current-volume/listing screens; this union is not survivorship-free.",
            "Symbols missing from Roostoo metadata are retained as discovery candidates but are not automatically tradable.",
            "Current Roostoo metadata is a type/tradability reference, not historical listing state.",
            "No pre-listing candles or synthetic fills are inserted; the common window removes partial histories.",
        ],
        "assembled_at": datetime.now(timezone.utc).isoformat(),
    }
    write_csv(a.output, joined, manifest)
    print(json.dumps({"output": a.output, "assets": len(series), "rows": len(joined),
                      "excluded": len(excluded), "start": start, "end_exclusive": end}, indent=2))


if __name__ == "__main__":
    main()
