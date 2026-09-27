# Deploying to the Pi

This folder is what runs on the Raspberry Pi gateway. It is **the
canonical, single copy** of the Pi codebase - `phase 9/pi/` mirrors
this, but is not edited here. Update this folder; `phase 9/pi/` is
periodically re-synced from it.

## One-time setup on a fresh Pi

```bash
cd development/pi
bash install.sh --enable
```

That:

1. creates `venv/` and pip-installs `requirements.txt`
2. enables SPI if you're on a Pi that needs it
3. installs the systemd unit with `User=` and paths auto-filled from
   the current shell (no editing the `.service` file by hand)
4. enables + starts the service, so `main.py` comes up on every boot

After it finishes:

```bash
journalctl -u sar-pi -f            # live logs
```

… and open `http://<pi-ip>:8000/` for the dashboard.

## Day-to-day updates

When new code lands on `main`, on the Pi:

```bash
cd development/pi
bash update.sh
```

This pulls the latest, re-installs requirements if `requirements.txt`
changed, and `systemctl restart sar-pi` so the dashboard reflects the
new code within a few seconds.

## Just try it without hardware

```bash
cd development/pi
python3 main.py --fake-radio
```

Opens the dashboard at `http://localhost:8000/` and replays synthetic
mesh packets so you can see the UI work without an SX1278 wired up.
Hit Ctrl-C to stop.

## Files added this round

| File | Purpose |
|---|---|
| `install.sh` | one-shot setup; idempotent; auto-fills the systemd unit |
| `update.sh` | git pull + restart; the day-to-day deploy workflow |
| `DEPLOY.md` | this file |
| `sar-pi.service` | now a template with `<TEMPLATE>` markers and explicit install/update notes |

## Troubleshooting

**`Could not claim GPIO25` on restart** — the previous `main.py` was
killed mid-syscall and didn't release the GPIO. Fix: `sudo systemctl
restart sar-pi` (the radio's `close()` runs on the next clean exit),
or `sudo fuser -k /dev/spidev0.0` if SPI is also stuck.

**Service installed but not running** — `journalctl -u sar-pi -n 50`
usually shows the SPI permission or missing-venv problem right away.

**Dashboard loads but no mesh data** — check the SX1278 wiring against
the pin table at the top of `sx1278.py`. Re-run `bash install.sh`
after any change; it does not damage existing state.

**Updates aren't landing** — `bash update.sh --check` shows what would
change. If `git pull --ff-only` fails, you probably have local edits
in `development/pi/` (e.g. a tweaked `config.py`); commit or stash
them before pulling.
