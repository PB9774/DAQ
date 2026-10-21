#!/bin/bash
# Accelerons Electric BMS — RPi4 installer · v20
#
# This is the ONLY place PyQt5/numpy/pyqtgraph get installed. main.py no
# longer auto-installs packages at runtime — having two install paths
# (apt here + pip at runtime) risked ending up with two different PyQt5
# builds fighting each other. If you ever see an import error, re-run
# this script rather than letting the app "fix itself".
set -e
DIR="$(cd "$(dirname "$0")"; pwd)"
echo "============================================"
echo "  Accelerons Electric BMS — Installer (v20)"
echo "============================================"
echo

echo "[1/5] System packages..."
sudo apt-get update -qq
sudo apt-get install -y python3-pyqt5 python3-numpy python3-pip fonts-inter 2>/dev/null \
  || sudo apt-get install -y python3-pyqt5 python3-numpy python3-pip

echo "[2/5] Python packages (pyqtgraph only — everything else comes from apt above)..."
pip3 install pyqtgraph --break-system-packages --quiet 2>/dev/null || pip3 install pyqtgraph --quiet

echo "[3/5] Backlight udev rule (no sudo at runtime)..."
RULE='SUBSYSTEM=="backlight",KERNEL=="rpi_backlight",GROUP="video",MODE="0664"'
echo "$RULE" | sudo tee /etc/udev/rules.d/99-backlight.rules > /dev/null
sudo udevadm control --reload-rules 2>/dev/null || true
sudo usermod -aG video "$USER" 2>/dev/null || true
echo "   Log out and back in for group to take effect."

echo "[4/5] Permissions..."
chmod +x "$DIR/main.py"

echo "[5/5] Auto-restart on crash (systemd service)..."
read -p "   Install accelerons-bms.service so the dashboard auto-restarts if it crashes? [y/N] " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
  SERVICE_FILE="/etc/systemd/system/accelerons-bms.service"
  sudo tee "$SERVICE_FILE" > /dev/null <<EOF
[Unit]
Description=Accelerons Electric BMS Dashboard
After=graphical.target

[Service]
Type=simple
User=$USER
Environment=DISPLAY=:0
WorkingDirectory=$DIR
ExecStart=/usr/bin/python3 $DIR/main.py
Restart=on-failure
RestartSec=3

[Install]
WantedBy=graphical.target
EOF
  sudo systemctl daemon-reload
  sudo systemctl enable accelerons-bms.service
  echo "   Installed and enabled. It will start on next boot."
  echo "   Manual control: sudo systemctl [start|stop|status] accelerons-bms"
  echo "   NOTE: while this service is active, don't also run 'python3 main.py'"
  echo "   by hand for dev/testing — you'll get two instances competing for"
  echo "   the display. Run 'sudo systemctl stop accelerons-bms' first."
else
  echo "   Skipped. You can install it later by re-running this script."
fi

echo ""
echo "Done!"
echo "  Run manually: python3 $DIR/main.py"
echo "  Fullscreen:   Set FULLSCREEN=True in main.py"
echo "  Brightness:   Settings -> Display slider"
echo "  Restart app:  Settings -> System -> Restart App Now (manual)"
echo "                systemd (if installed above) handles crash auto-restart"
echo "  Telemetry:    Logs page -> Start Streaming, then: nc <rpi-ip> 9000"
