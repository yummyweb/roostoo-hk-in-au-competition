"""Explicit, locked config migration for an existing allocation ledger."""
import argparse
from dataclasses import asdict
import fcntl
import hashlib
import json
import math
import os
from pathlib import Path
import time
import uuid

from .api import APIError, Client
from .bot import save_state
from .rules import load_rules
from .strategy import Config


# Config fields added after earlier ledgers were hashed, newest group first.
LEGACY_FIELDS = [{'ema_fresh_bars', 'mr_window', 'mr_entry_z', 'mr_fraction', 'mr_slots', 'mr_hold_bars', 'mr_stop', 'mr_cooldown_bars'},
                 {'breakout_high_bars', 'trail_atr'},
                 {'drawdown_brake', 'brake_window_bars'},
                 {'take_profit_pct', 'take_profit_trail', 'take_profit_fraction'}]


def digest(config, legacy=0):
    values=asdict(config)
    for group in LEGACY_FIELDS[:legacy]:
        for field in group:
            values.pop(field, None)
    return hashlib.sha256(json.dumps(values, sort_keys=True).encode()).hexdigest()


def supported(config):
    config.validate()
    legs = config.rank_model == 'regime_legs'
    if (config.allow_short and not legs) or config.strategy not in ('allocation', 'cross_asset'):
        raise ValueError('Migration supports long-only allocation strategies, and shorts only in the regime-legs mode')
    if config.strategy == 'cross_asset' and config.rank_model not in ('regime_adaptive', 'trend_budget'):
        raise ValueError('Live cross-asset execution requires regime_adaptive or trend_budget')


def append_event(path, event):
    with path.with_suffix('.jsonl').open('a') as journal:
        journal.write(json.dumps(event, allow_nan=False) + '\n')
        journal.flush()
        os.fsync(journal.fileno())


def migrate(path, config, universe, live, client):
    supported(config)
    # Require the existing ledger: this command must never reset an account.
    if not path.is_file():
        raise ValueError(f'Existing ledger required: {path}. Check ROOSTOO_STATE.')
    with path.with_suffix('.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        original = path.read_bytes()
        state = json.loads(original)
        if state['mode'] != ('live' if live else 'paper'):
            raise ValueError('Updater cannot switch paper/live mode; select the existing account ledger')
        if state.get('inflight'):
            raise ValueError('Unresolved submitted order: reconcile it before updating')
        if state['config_hash'] == digest(config):
            print('Config hash unchanged; ledger retained.')
            return

        previous = None
        journal = path.with_suffix('.jsonl')
        with journal.open() as events:
            for line in events:
                try:
                    event = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if event.get('event') not in ('start', 'config_migration') or 'config' not in event:
                    continue
                candidate = Config(**event['config'])
                if any(digest(candidate, n) == state['config_hash'] for n in range(len(LEGACY_FIELDS)+1)):
                    previous = candidate
        if previous is None:
            raise ValueError('Cannot verify previous config from ledger journal; migration blocked')
        supported(previous)
        if previous.initial_cash != config.initial_cash:
            raise ValueError('initial_cash cannot change for an existing account')

        pairs_doc = json.loads(universe.read_text())
        pairs = pairs_doc if isinstance(pairs_doc, list) else pairs_doc['pairs']
        if not pairs:
            raise ValueError('Execution universe is empty')
        client.sync_clock()
        rules = load_rules(client.exchange_info(), pairs)
        if live:
            balance = client.balance()
            wallet = balance.get('SpotWallet', balance.get('Wallet'))
            if not isinstance(wallet, dict):
                raise ValueError('Unknown wallet response schema')
        else:
            wallet = {'USD': {'Free': state.get('cash', previous.initial_cash), 'Lock': 0}}
            wallet.update({pair.split('/')[0]: {'Free': quantity, 'Lock': 0}
                           for pair, quantity in state.get('inventory', {}).items()})
        for asset, balance in wallet.items():
            for field in ('Free', 'Lock'):
                value = float(balance.get(field, 0))
                if not math.isfinite(value) or value < 0:
                    raise ValueError('Invalid wallet balance')
            if asset != 'USD' and float(balance.get('Free', 0)) > 0 and asset + '/USD' not in rules:
                raise ValueError(f'Held asset {asset} is outside the new execution universe')
        if config.rank_model != 'regime_legs' and state.get('shorts'):
            raise ValueError('Paper short positions are open: close them under regime_legs before switching strategy')
        if live:
            if config.rank_model != 'regime_legs' and client.short_positions().get('Positions'):
                raise ValueError('Short positions require reconciliation')
            try:
                pending = client.request('GET', '/v3/pending_count', signed=True)
                if 'TotalPending' not in pending or int(pending['TotalPending']) != 0:
                    raise ValueError('Pending orders or unknown pending-order response; migration blocked')
            except APIError as error:
                if 'no pending order' not in str(error).lower():
                    raise

        backup = path.with_name(path.name + '.before-update.' + uuid.uuid4().hex)
        with backup.open('xb') as output:
            output.write(original)
            output.flush()
            os.fsync(output.fileno())
        # Keep fills, cash, holdings, equity peak, halt and submission throttle.
        # Only unsubmitted decisions are invalidated for the new strategy.
        # Trailing-stop levels belong to the old rule; high-water marks are kept, so they rebuild under the new one.
        # Positions of another strategy are not this one's: its book starts empty and the runner releases what it finds.
        book = state.get('book', {}) if previous.rank_model == config.rank_model == 'regime_legs' else {}
        updated = dict(state, config_hash=digest(config), pending=None, targets={}, stop_levels={}, queue=[], legs_bar=None, book=book,
                       target_day=None, target_regime=None, market_regime=None, regime_age=0)
        append_event(path, {'event': 'config_migration', 'timestamp': int(time.time()*1000),
                            'mode': state['mode'], 'old_config_hash': state['config_hash'],
                            'config_hash': digest(config), 'config': asdict(config),
                            'backup': str(backup), 'discarded_pending': state.get('pending')})
        save_state(path, updated)
        print(f'Config migrated. Trading history and risk state preserved. Backup: {backup}')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', required=True)
    parser.add_argument('--state', required=True)
    parser.add_argument('--universe', required=True)
    args = parser.parse_args()
    migrate(Path(args.state), Config(**json.loads(Path(args.config).read_text())),
            Path(args.universe), os.environ.get('ROOSTOO_LIVE', '0') == '1',
            Client(os.environ.get('ROOSTOO_API_KEY', ''), os.environ.get('ROOSTOO_API_SECRET', '')))


if __name__ == '__main__':
    main()
