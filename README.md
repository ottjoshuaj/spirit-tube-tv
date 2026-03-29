# Spirit Tube TV

An RTL-SDR spirit box for Raspberry Pi 5. Scans FM radio, AM radio, and old
analog VHF/UHF TV channels while displaying live signal visualizations and
playing demodulated audio. Designed for the official 7" Pi touchscreen.

## Hardware

| Item | Notes |
|------|-------|
| Raspberry Pi 5 | 4 GB RAM or more recommended |
| Raspberry Pi OS 64-bit | Bookworm or later |
| RTL-SDR V3 dongle | R820T2 + RTL2832U chipset |
| Official 7" Pi Touchscreen | 800×480, DSI connector |
| Bluetooth or USB speaker | Paired/connected before launch |

## Install

```bash
git clone https://github.com/YOUR_USERNAME/spirit-tube-tv.git
cd spirit-tube-tv
./install.sh
sudo reboot
```

After reboot the app starts automatically when you log in to the Pi OS desktop.

## Manual Launch

```bash
python3 main.py
```

Press **Esc** to exit.

## Usage

1. Tap **FM**, **AM**, or **TV** on the band select screen.
2. Use the transport buttons to scan:
   - **|◀** / **▶|** — jump one channel back / forward
   - **◀◀** / **▶▶** — auto-scan backward / forward (1.5 s per channel)
   - **⏸ / ▶** — pause or resume auto-scan
3. Tap **←** (top-left) to stop and return to band select.

## Troubleshooting

**RTL-SDR not detected** *(run these checks after rebooting)*
```bash
lsusb | grep Realtek   # should show Bus ... ID 0bda:2838
rtl_test              # should show device found
```
If not found, check that the blacklist file exists:
```bash
cat /etc/modprobe.d/rtlsdr.conf
# should contain: blacklist dvb_usb_rtl28xxu
```
Then reboot.

**No audio**
- Ensure your BT speaker is paired and set as the default ALSA output before launching.
- Check with: `aplay -l`

**App doesn't autostart**
Verify the desktop entry was installed:
```bash
cat ~/.config/autostart/spirit-tube-tv.desktop
```
Re-run `./install.sh` if the file is missing.
