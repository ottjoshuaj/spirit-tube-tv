#!/usr/bin/env bash
set -e

INSTALL_DIR="$(cd "$(dirname "$0")" && pwd)"

echo "=== Spirit Tube TV — Installer ==="
echo "Install dir: $INSTALL_DIR"
echo ""

# 1. System packages
echo "[1/5] Installing system packages..."
sudo apt-get update -qq
sudo apt-get install -y \
    rtl-sdr \
    librtlsdr-dev \
    python3-pip \
    python3-pygame \
    python3-numpy \
    python3-dev

# 2. Python packages
echo "[2/5] Installing Python packages..."
pip3 install --break-system-packages pyrtlsdr sounddevice

# 3. Blacklist conflicting kernel module
echo "[3/5] Blacklisting dvb_usb_rtl28xxu kernel module..."
echo 'blacklist dvb_usb_rtl28xxu' | sudo tee /etc/modprobe.d/rtlsdr.conf > /dev/null
sudo update-initramfs -u -k all 2>/dev/null || true

# 4. udev rule — allow non-root access to RTL-SDR USB device
echo "[4/5] Adding udev rule for RTL-SDR..."
sudo tee /etc/udev/rules.d/20-rtlsdr.rules > /dev/null <<'EOF'
SUBSYSTEM=="usb", ATTRS{idVendor}=="0bda", ATTRS{idProduct}=="2838", GROUP="plugdev", MODE="0664"
SUBSYSTEM=="usb", ATTRS{idVendor}=="0bda", ATTRS{idProduct}=="2832", GROUP="plugdev", MODE="0664"
EOF
sudo udevadm control --reload-rules
sudo usermod -aG plugdev "$USER"

# 5. Autostart
echo "[5/5] Installing autostart entry..."
mkdir -p "$HOME/.config/autostart"
sed "s|__INSTALL_DIR__|$INSTALL_DIR|g" \
    "$INSTALL_DIR/autostart/spirit-tube-tv.desktop" \
    > "$HOME/.config/autostart/spirit-tube-tv.desktop"

echo ""
echo "=== Installation complete ==="
echo "IMPORTANT: Reboot your Pi for the module blacklist and udev rules to take effect."
echo "After reboot, Spirit Tube TV will start automatically when you log in."
echo ""
echo "To run manually:  python3 $INSTALL_DIR/main.py"
