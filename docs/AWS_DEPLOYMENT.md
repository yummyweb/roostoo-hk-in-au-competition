# AWS deployment

`deploy/aws_start.sh` installs the repository on an Ubuntu EC2 instance, creates
a Python virtual environment, writes a locked systemd unit, and starts the
persistent Roostoo runner. It is repeatable and keeps the state ledger under
`/opt/roostoo/runs/aws/`.

The script defaults to paper mode. The bot reads `ROOSTOO_LIVE` from the
root-owned `/etc/roostoo/roostoo.env` on every start, so changing that value and
restarting the service changes the mode. The repository contains no credentials;
enter them on the host:

```sh
git clone https://github.com/yummyweb/roostoo-hk-in-au-competition.git /tmp/roostoo
sudo install -d -m 0750 /etc/roostoo
sudo install -m 0600 /tmp/roostoo/deploy/roostoo.env.example /etc/roostoo/roostoo.env
sudoedit /etc/roostoo/roostoo.env
sudo bash /tmp/roostoo/deploy/aws_start.sh
```

Use `ROOSTOO_UNIVERSE_CONFIG=/opt/roostoo/config/universe-50.json` for the fixed
50-pair execution universe. The default `config/live_candidate.json` now runs
the causal regime-adaptive long-only mode: a 12-hour momentum input, 2% move
hurdle, 24-hour regime confirmation, top three candidates, and 72-hour
rebalancing. It uses Binance hourly candles as a proxy and current Roostoo
quotes, so verify the pair list and wallet before any live activation.

The regime runner stays in cash during `BEAR` and `CHOP`. Its live classifier
uses the configured 50-pair universe; the separate 222-asset classifier was
research-only discovery data.

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
