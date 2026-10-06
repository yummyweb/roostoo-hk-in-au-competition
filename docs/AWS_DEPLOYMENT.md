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

Use `ROOSTOO_UNIVERSE_CONFIG=/opt/roostoo/config/universe-50.json` for the fixed
50-pair execution universe. The default `config/live_candidate.json` now runs
the long-only diversified trend ensemble: daily targets from 3/7/14/30-day
trend votes, a 20% volatility target, 20% per-asset and 80% total caps, a 1%
drift band, and a gradual 4% drawdown brake. It warms 721 Binance hourly
candles per pair as a proxy and trades current Roostoo quotes, so verify the
pair list and wallet before any live activation.

The ensemble holds cash for every pair with fewer than two positive trend
votes, so it can be fully in cash in a broad decline.

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
- `"mode": "live"` with `"pending": null` can be an intentional wait. Targets
  refresh at 00:00 UTC; between refreshes the runner trades only when a holding
  drifts more than 1% of equity from its target or the brake changes exposure.
  A `"brake"` below 1 in the status line means exposure is being reduced.
- `Cycle blocked:` or a startup traceback identifies an execution/data error.
  Missing credentials, a starting cash mismatch, stale candles/quotes, and
  unresolved orders prevent trading. The live starting wallet must be flat and
  match the configured `initial_cash` (default USD 100,000).
- A non-null `pending` is queued for a later cycle, at least 60 seconds after
  the signal. Check the following cycle for a fill or error.

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
submission, stale quotes, locked balances, unmanaged assets, or an existing
process. A systemd restart does not bypass those checks. Stop the service and
reconcile the exchange manually after a timeout or ambiguous response.
