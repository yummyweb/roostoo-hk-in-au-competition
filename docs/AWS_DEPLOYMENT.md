# AWS deployment

`deploy/aws_start.sh` installs the repository on an Ubuntu EC2 instance, creates
a Python virtual environment, writes a locked systemd unit, and starts the
persistent Roostoo runner. It is repeatable and keeps the state ledger under
`/opt/roostoo/runs/aws/`.

The script defaults to paper mode. It only passes `--live` when the root-owned
`/etc/roostoo/roostoo.env` contains `ROOSTOO_LIVE=1`. The repository contains no
credentials; enter them on the host:

```sh
git clone https://github.com/yummyweb/roostoo-hk-in-au-competition.git /tmp/roostoo
sudo install -d -m 0750 /etc/roostoo
sudo install -m 0600 /tmp/roostoo/deploy/roostoo.env.example /etc/roostoo/roostoo.env
sudoedit /etc/roostoo/roostoo.env
sudo bash /tmp/roostoo/deploy/aws_start.sh
```

Use `ROOSTOO_UNIVERSE_CONFIG=/opt/roostoo/config/universe-50.json` for the fixed
50-pair allocation universe. The default `config/live_candidate.json` uses the
same slow, strength-gated allocation family selected for research. The runner currently supports the deterministic
long-only allocation engine; the research-only regime-adaptive ranking study is
not silently presented as the live implementation. It uses Binance hourly
candles as a proxy and current Roostoo quotes, so verify the pair list and wallet
before any live activation.

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
