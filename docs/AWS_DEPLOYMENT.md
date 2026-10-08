# AWS deployment

`deploy/aws_start.sh` installs the repository on an Amazon Linux EC2 instance, creates
a Python virtual environment, writes a locked systemd unit, and starts the
persistent Roostoo runner. It is repeatable and keeps the state ledger under
`/opt/roostoo/runs/aws/`.

The script defaults to paper mode. The bot reads `ROOSTOO_LIVE` from the
root-owned `/etc/roostoo/roostoo.env` on every start. Changing that value requires
a restart and a ledger belonging to the requested mode: an existing paper
ledger cannot be reused for live execution. The repository contains no credentials;
enter them on the host:

```sh
git clone https://github.com/yummyweb/roostoo-hk-in-au-competition.git /tmp/roostoo
sudo install -d -m 0750 /etc/roostoo
sudo install -m 0600 /tmp/roostoo/deploy/roostoo.env.example /etc/roostoo/roostoo.env
sudoedit /etc/roostoo/roostoo.env
sudo bash /tmp/roostoo/deploy/aws_start.sh
```

The installer uses `dnf`, matching the hackathon Amazon Linux image.

## Hackathon AWS template

The hackathon launch guide requires the AWS account's `ap-southeast-2`
(Sydney) region, the supplied `Hackathon-Starter-Template`, and a single
`t3.medium` instance. Launch only one instance and connect through **EC2 →
Connect → Session Manager**; SSH and EC2 Instance Connect are blocked by the
event account. The template's Amazon Linux image is why this installer prefers
`dnf`.

Open a Session Manager terminal, clone the repository, create the protected
environment file, and run the installer with `sudo`:

```sh
cd ~
git clone https://github.com/yummyweb/roostoo-hk-in-au-competition.git /tmp/roostoo
sudo install -d -m 0750 /etc/roostoo
sudo install -m 0600 /tmp/roostoo/deploy/roostoo.env.example /etc/roostoo/roostoo.env
sudoedit /etc/roostoo/roostoo.env
sudo bash /tmp/roostoo/deploy/aws_start.sh
```

The service runs under systemd, so closing the Session Manager browser tab does
not stop the bot. A `tmux` session is useful for manual diagnostics, but is not
needed to keep this service running. The event guide also limits storage to
30 GB and restricts the account to the provided EC2 deployment; do not add
other AWS services or launch another instance.

Use `ROOSTOO_UNIVERSE_CONFIG=/opt/roostoo/config/universe-crypto.json` for the
65 crypto pairs Roostoo quotes (`universe-50.json` is the earlier 50-pair set).
The default `config/live_candidate.json` runs the team's regime strategy on
5-minute bars: each coin is labelled BULL, BEAR or CHOP every five minutes;
BULL and BEAR coins trade the 80/320-minute EMA trend, entered on a pullback
(long and short), a BEAR coin that drops 2% in one bar is bought for a bounce,
CHOP coins trade 8-hour z-score mean reversion both ways, and every position
is checked each minute against a stop-loss, a momentum rule and a profit lock.
It fills each pair's history from Binance 5-minute closes when it starts, then
builds its bars from Roostoo's own quotes, so verify the pair list and wallet
before any live activation.

Holdings and shorts the strategy did not open itself are closed on the first
cycles after a switch. The breakout preset is `config/breakout_candidate.json`.

## Diagnosing no orders

Read the running process's output first:

```sh
sudo systemctl status roostoo-bot --no-pager
sudo journalctl -u roostoo-bot -n 100 --no-pager
sudo systemctl show roostoo-bot -p ExecStart -p ActiveState -p SubState
```

- `"mode": "paper"` means orders are simulated locally. The file named
  `live_candidate.json` selects the strategy; it does not enable live orders.
- `State belongs to a different mode/config` means the selected ledger was
  created in another mode or with another configuration. For strategy updates
  in the same mode, use `sudo bash /opt/roostoo/deploy/aws_update.sh` as described
  in the [README](../README.md#updating-the-running-bot). For a paper/live mode
  switch, follow the transition procedure below.
- The status line shows `"regimes"` (how many coins carry each label),
  `"positions"` (open positions by leg and side), `"invested"` (share of the
  account in positions), `"ready"` (coins with enough history to trade), `"sharpe"` and `"sortino"`
  (from the account's value at the end of each UTC day since the start, today
  as it stands, annualised over 365 days; null until two days exist), `"brake"` (true while the loss brake blocks new
  entries), `"queued"` (orders waiting for their minute), `"done"` (the order
  sent this cycle) and `"why"` (its reason, for example `profit lock` or
  `stop loss`). Entries are decided every five minutes and exits are checked
  every minute; `"done": null` means nothing needed doing that minute.
- `Cycle blocked:` or a startup traceback identifies an execution/data error.
  Missing credentials, a starting cash mismatch, stale quotes and an unresolved
  spot order prevent trading. With the regime strategy, `No candles for this
  hour` means the candle download failed (with bars built from quotes: the
  start-up history from Binance): queued orders still go out and the
  minute exits (stop-loss, profit lock, profit target) still run, but no new
  entry is decided and the hourly exits are not checked until it succeeds (it
  is retried every minute). The live starting wallet must be flat and
  match the configured `initial_cash` (default USD 100,000).
- `"queued"` above zero means orders are waiting: one is sent per cycle, at
  least 60 seconds after the previous order. Check the following cycles for
  `"done"` or an error. The breakout and ensemble presets print `"pending"`
  instead.

Rerunning `aws_start.sh` now restarts the service so updated code, environment,
and unit arguments take effect. Previously, `systemctl enable --now` left an
already running bot on its old settings.

## Switching an existing paper deployment to live

Stop the service and inspect the selected ledger's `mode`, `inflight`, and
`config_hash`. Reconcile the actual account, including holdings and open orders.
If the existing ledger is paper-only and this account has no previous live
session, preserve it and set these values in `/etc/roostoo/roostoo.env`:

```ini
ROOSTOO_LIVE=1
ROOSTOO_STATE=/opt/roostoo/runs/aws/live-state.json
```

Enter the API credentials in the same file and rerun
`sudo bash /opt/roostoo/deploy/aws_start.sh`. `ROOSTOO_STATE` is embedded in the
generated unit, so changing it requires rerunning the installer. Keep the path
under `/opt/roostoo/runs/`, which is writable by the service. Resume the original
ledger for an existing live session; never create a new ledger to bypass an
unresolved order or a drawdown halt. Confirm `"mode": "live"` in the journal.

If an existing state file was created with the previous allocation config, the
config hash intentionally blocks an automatic strategy switch. In paper mode,
archive the old ledger and start a fresh paper session:

```sh
sudo systemctl stop roostoo-bot
sudo cp /opt/roostoo/runs/aws/state.json /opt/roostoo/runs/aws/state.allocation.json
sudo cp /opt/roostoo/runs/aws/state.jsonl /opt/roostoo/runs/aws/state.allocation.jsonl
sudo rm /opt/roostoo/runs/aws/state.json /opt/roostoo/runs/aws/state.jsonl
sudo systemctl start roostoo-bot
```

For a live account, reconcile holdings and open orders first; do not delete a
state file containing an unresolved live position or order.

Before setting `ROOSTOO_LIVE=1`, reconcile the account, run the finite general
account canary, and start with paper mode. Check:

```sh
sudo systemctl status roostoo-bot
sudo journalctl -u roostoo-bot -f
sudo systemctl stop roostoo-bot   # emergency stop; does not cancel exchange orders
```

The runner persists an intent before each POST and blocks on an unresolved
spot submission, stale quotes, locked coin balances, unmanaged assets, or an
existing process. A systemd restart does not bypass those checks. Stop the
service and reconcile the exchange manually after a timeout or ambiguous
response to a spot order. With the regime strategy, locked USD is short
collateral and does not block, a short open or close left without an answer is
settled from `/v6/short_positions` on the next cycle, and a failed read of that
list blocks the cycle instead of being read as "no shorts".
