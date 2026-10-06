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
from .bot import Runner, save_state
from .rules import load_rules
from .strategy import Config


LEGACY_FIELDS = {'take_profit_pct', 'take_profit_trail', 'take_profit_fraction'}


def digest(config, legacy=False):
    values=asdict(config)
    if legacy:
        for field in LEGACY_FIELDS:
            values.pop(field, None)
    return hashlib.sha256(json.dumps(values, sort_keys=True).encode()).hexdigest()


def supported(config):
    config.validate()
    if config.allow_short or config.strategy not in ('allocation', 'cross_asset'):
        raise ValueError('Migration supports long-only allocation strategies only')
    if config.strategy == 'cross_asset' and config.rank_model != 'regime_adaptive':
        raise ValueError('Live cross-asset execution requires regime_adaptive')


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
                if digest(candidate) == state['config_hash'] or digest(candidate, legacy=True) == state['config_hash']:
                    previous = candidate
        if previous is None:
            raise ValueError('Cannot verify previous config from ledger journal; migration blocked')
        supported(previous)
        if previous.initial_cash != config.initial_cash:
            raise ValueError('initial_cash cannot change for an existing account')

        runner = Runner(previous, path, client, live)
        pairs_doc = json.loads(universe.read_text())
        pairs = pairs_doc if isinstance(pairs_doc, list) else pairs_doc['pairs']
        if not pairs:
            raise ValueError('Execution universe is empty')
        client.sync_clock()
        runner.rules = load_rules(client.exchange_info(), pairs)
        wallet = runner.wallet()
        for asset, balance in wallet.items():
            for field in ('Free', 'Lock'):
                value = float(balance.get(field, 0))
                if not math.isfinite(value) or value < 0:
                    raise ValueError('Invalid wallet balance')
            if asset != 'USD' and float(balance.get('Free', 0)) > 0 and asset + '/USD' not in runner.rules:
                raise ValueError(f'Held asset {asset} is outside the new execution universe')
        if live:
            if client.short_positions().get('Positions'):
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
        updated = dict(state, config_hash=digest(config), pending=None, targets={},
                       target_day=None, target_regime=None, market_regime=None, regime_age=0)
        runner.log({'event': 'config_migration', 'timestamp': int(time.time()*1000),
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
