#!/usr/bin/env bash
#
# install.sh - one-time setup for the SAR Pi gateway.
#
# What it does:
#   1. creates a Python venv in development/pi/venv/
#   2. pip-installs requirements.txt into it
#   3. on Pi OS, makes sure SPI + lgpio are enabled for the SX1278
#   4. (optional) installs and enables the sar-pi systemd service so
#      main.py comes up on every boot
#
# Re-run safely. venv is reused, requirements are only re-installed if
# requirements.txt is newer.
#
# Usage:
#   bash install.sh                 # setup + leave service stopped
#   bash install.sh --enable        # setup + install + enable systemd
#   bash install.sh --no-systemd    # setup only, never touch systemd
#
set -euo pipefail

cd "$(dirname "$0")"
ROOT="$(pwd)"
USER_NAME="$(id -un)"
GROUP_NAME="$(id -gn)"
ENABLE_SYSTEMD=0
INSTALL_SYSTEMD=1

for arg in "$@"; do
    case "$arg" in
        --enable)        ENABLE_SYSTEMD=1 ;;
        --no-systemd)    INSTALL_SYSTEMD=0 ;;
        -h|--help)
            sed -n '2,18p' "$0"
            exit 0 ;;
        *) echo "unknown option: $arg" >&2; exit 2 ;;
    esac
done

echo ">>> SAR Pi gateway setup"
echo "    repo path : $ROOT"
echo "    user      : $USER_NAME"
echo "    group     : $GROUP_NAME"
echo

# --- 1. venv ----------------------------------------------------------------
if [ ! -d venv ]; then
    echo ">>> creating venv"
    python3 -m venv venv
else
    echo ">>> venv exists, reusing"
fi

# shellcheck disable=SC1091
source venv/bin/activate

echo ">>> pip install -r requirements.txt"
pip install --upgrade pip wheel >/dev/null
pip install -r requirements.txt

# --- 2. OS packages (Pi only) ----------------------------------------------
if grep -q RaspberryPi /proc/cpuinfo 2>/dev/null; then
    echo ">>> Raspberry Pi detected - checking SPI + lgpio"
    if ! dpkg -s python3-lgpio >/dev/null 2>&1; then
        echo "    installing python3-lgpio (needed for SX1278 GPIO on Pi 5)"
        sudo apt-get update -qq
        sudo apt-get install -y -qq python3-lgpio
    fi
    if ! grep -q '^dtparam=spi=on' /boot/firmware/config.txt 2>/dev/null \
       && ! grep -q '^dtparam=spi=on' /boot/config.txt 2>/dev/null; then
        echo
        echo "    SPI is OFF in /boot/firmware/config.txt."
        echo "    Run:  sudo raspi-config    -> Interface Options -> SPI -> Enable"
        echo "    then reboot. (install.sh cannot enable SPI itself.)"
    else
        echo "    SPI is already enabled"
    fi
    # Allow the current user to talk to /dev/spidev* without sudo.
    if ! groups "$USER_NAME" | grep -q spi; then
        echo ">>> adding $USER_NAME to the spi group (logout/login after this)"
        sudo usermod -a -G spi "$USER_NAME"
    fi
fi

# --- 3. systemd unit (optional) --------------------------------------------
if [ "$INSTALL_SYSTEMD" -eq 1 ]; then
    echo ">>> writing sar-pi.service from template (paths auto-resolved)"
    TMP_UNIT="$(mktemp)"
    sed -e "s|^User=.*|User=$USER_NAME|" \
        -e "s|^WorkingDirectory=.*|WorkingDirectory=$ROOT|" \
        -e "s|^ExecStart=.*|ExecStart=$ROOT/venv/bin/python3 $ROOT/main.py|" \
        sar-pi.service > "$TMP_UNIT"
    sudo cp "$TMP_UNIT" /etc/systemd/system/sar-pi.service
    sudo systemctl daemon-reload
    if [ "$ENABLE_SYSTEMD" -eq 1 ]; then
        sudo systemctl enable --now sar-pi
        echo "    service enabled and started.  journalctl -u sar-pi -f"
    else
        echo "    service file installed (not enabled).  sudo systemctl enable --now sar-pi"
    fi
    rm -f "$TMP_UNIT"
fi

echo
echo ">>> done."
echo
echo "Quick check (no hardware required):"
echo "    source venv/bin/activate"
echo "    python3 main.py --fake-radio"
echo "    open http://localhost:8000/  (and http://localhost:8000/portal)"
echo
echo "Real hardware:"
echo "    sudo systemctl enable --now sar-pi      # if you skipped --enable"
echo "    journalctl -u sar-pi -f                # live logs"
echo
echo "Day-to-day updates:"
echo "    bash update.sh                         # git pull + restart service"
